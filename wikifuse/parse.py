"""Utilities for parsing Wikipedia wikitext into structured components."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import wikitextparser as wtp


@dataclass
class ParsedPassage:
    """Source text bounded by paragraph breaks or inline citations."""

    text: str
    references: list[str]


@dataclass
class ParsedArticle:
    """Container for parsed article components."""

    sections: dict[str, str]
    images: list[str]
    infobox: dict[str, str]
    references: list[str]
    passages: dict[str, list[ParsedPassage]] = field(default_factory=dict)


def _parse_passages(
    content: str, named: dict[tuple[str, str], str]
) -> list[ParsedPassage]:
    parsed = wtp.parse(content)
    ref_spans = [tag.span for tag in parsed.get_tags("ref")]
    for template in reversed(list(parsed.templates)):
        if not any(start <= template.span[0] < end for start, end in ref_spans):
            template.string = ""
    for tag in reversed(list(parsed.get_tags("references"))):
        tag.string = ""
    content = parsed.string
    passages: list[ParsedPassage] = []
    cursor = 0
    for tag in parsed.get_tags("ref"):
        start, end = tag.span
        before = content[cursor:start]
        if before.strip():
            for paragraph in re.split(r"\n\s*\n", before):
                if paragraph.strip():
                    passages.append(ParsedPassage(paragraph.strip(), []))
        if not passages or re.search(r"\n\s*\n\s*$", before):
            raise ValueError("Reference has no preceding passage in its paragraph")
        ref = tag.contents.strip()
        if not ref:
            key = (tag.attrs.get("group", ""), tag.attrs.get("name", ""))
            if key not in named:
                raise ValueError(f"Undefined named reference: {key!r}")
            ref = named[key]
        if passages and ref not in passages[-1].references:
            passages[-1].references.append(ref)
        cursor = end
        while passages and cursor < len(content) and content[cursor] in ".,;:!?":
            passages[-1].text += content[cursor]
            cursor += 1
    for paragraph in re.split(r"\n\s*\n", content[cursor:]):
        if paragraph.strip():
            passages.append(ParsedPassage(paragraph.strip(), []))
    return passages


def parse_wikitext(wikitext: str) -> ParsedArticle:
    """Parse raw wikitext into sections, images, infobox, and references.

    This parser uses ``wikitextparser`` for a light‑weight extraction that is
    sufficient for merging content across languages.  It does not aim to fully
    replicate MediaWiki parsing but instead exposes the pieces of an article
    that the merge pipeline cares about.
    """

    parsed = wtp.parse(wikitext)

    # Extract images from ``[[File:..]]`` or ``[[Image:..]]`` links and ensure
    # uniqueness. ``wikitextparser`` exposes these as regular wikilinks, so we
    # filter by the link title prefix.
    images: list[str] = []
    for link in parsed.wikilinks:
        title = link.title.strip()
        if title.lower().startswith(("file:", "image:")) and title not in images:
            images.append(title)

    # Extract the first infobox template, keeping simple key/value pairs
    infobox: dict[str, str] = {}
    for template in parsed.templates:
        name = template.name.lower().strip()
        if name.startswith("infobox"):
            for arg in template.arguments:
                key = arg.name.strip()
                value = arg.value.strip()
                infobox[key] = value
            break

    named: dict[tuple[str, str], str] = {}
    reference_lists = parsed.get_tags("references")
    references: list[str] = []
    for tag in parsed.get_tags("ref"):
        content = tag.contents.strip()
        if content:
            if content not in references:
                references.append(content)
            if "name" in tag.attrs:
                inherited_group = next(
                    (
                        block.attrs.get("group", "")
                        for block in reference_lists
                        if block.span[0] <= tag.span[0] < block.span[1]
                    ),
                    "",
                )
                key = (tag.attrs.get("group", inherited_group), tag.attrs["name"])
                if key in named and named[key] != content:
                    raise ValueError(f"Conflicting named reference: {key!r}")
                named[key] = content

    sections: dict[str, str] = {}
    passages: dict[str, list[ParsedPassage]] = {}
    for section in parsed.get_sections(include_subsections=False):
        title = (section.title or "lead").strip()
        content = section.contents.strip()
        if content:
            sections[title] = "\n\n".join(filter(None, [sections.get(title), content]))
            passages.setdefault(title, []).extend(_parse_passages(content, named))

    return ParsedArticle(
        sections=sections,
        images=images,
        infobox=infobox,
        references=references,
        passages=passages,
    )
