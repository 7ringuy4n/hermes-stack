# -*- coding: utf-8 -*-
"""Strip host/account material from lab report text."""
from __future__ import annotations

import re

_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_SUDO = re.compile(r"\[sudo\] password for \S+:\s*", re.I)
_OWN = re.compile(r'"ownId"\s*:\s*"[^"]*"')
_USER_LINE = re.compile(r"HERMES_DASHBOARD_USER=\S+")
_PASS_LINE = re.compile(r"HERMES_DASHBOARD_PASSWORD=\S+")


def sanitize(text: str) -> str:
    text = _SUDO.sub("", text)
    text = _OWN.sub('"ownId":"[redacted]"', text)
    text = _USER_LINE.sub("HERMES_DASHBOARD_USER=[redacted]", text)
    text = _PASS_LINE.sub("HERMES_DASHBOARD_PASSWORD=[set]", text)
    text = _IP.sub("[redacted-addr]", text)
    return text
