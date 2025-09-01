"""Utilities for parsing Wikipedia wikitext into structured components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import wikitextparser as wtp


@dataclass
class ParsedArticle:
    """Container for parsed article components."""

    sections: Dict[str, str]
    images: List[str]
    infobox: Dict[str, str]
    references: List[str]


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
    images: List[str] = []
    for link in parsed.wikilinks:
        title = link.title.strip()
        if title.lower().startswith(("file:", "image:")) and title not in images:
            images.append(title)

    # Extract the first infobox template, keeping simple key/value pairs
    infobox: Dict[str, str] = {}
    for template in parsed.templates:
        name = template.name.lower().strip()
        if name.startswith("infobox"):
            for arg in template.arguments:
                key = arg.name.strip()
                value = arg.value.strip()
                infobox[key] = value
            break

    # Map section titles to their raw contents
    sections: Dict[str, str] = {}
    for section in parsed.sections:
        title = section.title or "lead"
        content = section.contents.strip()
        if content:
            sections[title.strip()] = content

    # Collect raw reference tags
    references: List[str] = []
    for tag in parsed.get_tags("ref"):
        content = tag.contents.strip()
        if content:
            references.append(content)

    return ParsedArticle(
        sections=sections, images=images, infobox=infobox, references=references
    )
