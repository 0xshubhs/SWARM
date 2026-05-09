"""Anchor event log parsing. Mirrors events.rs from the program.

We use anchorpy's Coder when an IDL is available; otherwise we fall back to
substring detection over `Program log: ...` lines for the hackathon path.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Anchor logs events as `Program log: <event-name>` followed by a base64
# discriminator. For the hackathon indexer we just look for the event name.
EVENT_NAMES = (
    "MemoryListed",
    "MemoryPurchased",
    "SandboxAccessGranted",
    "DecisionAnchored",
    "ListingDelisted",
    "ListingPriceUpdated",
)

_LOG_RE = re.compile(r"Program log:\s*(\w+)")


@dataclass(slots=True)
class RawEvent:
    name: str
    raw: str


def detect_events(logs: list[str]) -> list[RawEvent]:
    out: list[RawEvent] = []
    for line in logs:
        m = _LOG_RE.search(line)
        if not m:
            continue
        name = m.group(1)
        if name in EVENT_NAMES:
            out.append(RawEvent(name=name, raw=line))
    return out
