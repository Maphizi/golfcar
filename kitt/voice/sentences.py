"""Zerlegt einen Token-Strom in Sätze, sobald sie vollständig sind (für satzweise Sprachausgabe)."""
from __future__ import annotations

import re

_END = re.compile(r"([.!?…]+[\"'»)]?)(\s|$)")
_ABBR = ("z.b.", "d.h.", "u.a.", "bzw.", "ca.", "dr.", "nr.", "evtl.", "usw.")


class SentenceSplitter:
    def __init__(self, min_chars: int = 12):
        self.buf = ""
        self.min_chars = min_chars

    def feed(self, token: str) -> list[str]:
        self.buf += token
        out = []
        while True:
            m = _END.search(self.buf)
            if not m:
                break
            cand = self.buf[:m.end(1)]
            low = cand.lower().rstrip()
            if any(low.endswith(a) for a in _ABBR) or len(cand.strip()) < self.min_chars:
                # Abkürzung oder zu kurz: weiter sammeln (nur, wenn noch Text folgen kann)
                nxt = _END.search(self.buf, m.end())
                if not nxt:
                    break
                cand = self.buf[:nxt.end(1)]
                m = nxt
            out.append(cand.strip())
            self.buf = self.buf[m.end():]
        return [s for s in out if s]

    def flush(self) -> list[str]:
        rest = self.buf.strip()
        self.buf = ""
        return [rest] if rest else []
