#!/usr/bin/env python3
"""Minimal example demonstrating the high level merge pipeline."""

from onepage.merge import merge_article
from onepage.render import WikitextRenderer


def main():
    qid = "Q1058"  # Narendra Modi
    languages = ["en", "hi"]

    # This call requires network access to the Wikimedia APIs.
    ir = merge_article(qid, languages)

    renderer = WikitextRenderer("en")
    wikitext = renderer.render(ir)
    print(wikitext[:500])


if __name__ == "__main__":
    main()
