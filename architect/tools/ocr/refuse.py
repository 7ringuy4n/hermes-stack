"""Tell a real OCR result apart from a chat reply that never saw the image.

Kept dependency-free so it can be unit tested without the service stack.
"""
from __future__ import annotations

import re

REFUSE_RE = re.compile(
    r"can't|cannot|unable to|don't support|do not support|not (?:able|supported)|"
    r"no vision|image not|refuse|i'm just a language|text-only|"
    r"model_not_found|was retired|request too large|oneOf at|"
    # A text-only model behind the router answers 200 OK with a chat reply asking
    # for the picture. That is not extracted text, so it must not win over tesseract.
    r"don't see (?:an |any |the )?(?:image|file|picture|attachment)|"
    r"do not see (?:an |any |the )?(?:image|file|picture|attachment)|"
    r"no image (?:was )?(?:attached|provided|included)|"
    r"haven't (?:provided|attached|uploaded|shared)|"
    r"please (?:upload|share|provide|attach|paste)|"
    r"once you (?:share|upload|provide|attach)",
    re.I,
)

RETRY_STATUS = {400, 404, 410, 413, 415, 422, 429, 500, 502, 503}

_SMART_QUOTES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"'})


def llm_refused(status: int, body: str, text: str) -> bool:
    """True when the upstream failed or answered without reading the image."""
    if status in RETRY_STATUS:
        return True
    blob = f"{body}\n{text}".translate(_SMART_QUOTES)
    return bool(REFUSE_RE.search(blob))
