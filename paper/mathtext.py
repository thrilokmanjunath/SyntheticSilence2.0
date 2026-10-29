"""
Minimal LaTeX-math to styled text, for the Word output.

Supports exactly the constructs the paper uses (fractions, roots, sums, sub/superscripts, hats,
Greek, a few operators). Anything unknown is passed through as plain text so a missing symbol is
visible in the output rather than silently dropped.

A segment is (text, style) with style a frozenset drawn from {"i", "b", "sub", "sup"}.
"""
from __future__ import annotations

from typing import List, Tuple

Segment = Tuple[str, frozenset]

SYMBOLS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "theta": "θ", "lambda": "λ",
    "delta": "δ", "varepsilon": "ε", "epsilon": "ε", "kappa": "κ",
    "mu": "μ", "rho": "ρ", "sigma": "σ", "tau": "τ", "Sigma": "Σ", "Delta": "Δ",
    "Phi": "Φ", "phi": "φ", "Gamma": "Γ", "Omega": "Ω", "omega": "ω",
    "neg": "¬", "Vert": "‖", "vert": "|", "propto": "∝", "infty": "∞", "subseteq": "⊆",
    "blacksquare": "∎",
    "sum": "∑", "cdot": "·", "ge": "≥", "geq": "≥", "le": "≤", "leq": "≤",
    "ne": "≠", "neq": "≠", "in": "∈", "lor": "∨", "land": "∧", "emptyset": "∅",
    "to": "→", "pm": "±", "approx": "≈", "dots": "…", "ldots": "…", "exists": "∃",
    "mid": "|", "lceil": "⌈", "rceil": "⌉", "lVert": "‖", "rVert": "‖", "times": "×",
}
SPACES = {",": " ", ";": " ", "!": "", "quad": " ", "qquad": "  ", " ": " "}
DROP = {"left", "right", "bigl", "bigr", "Bigl", "Bigr", "big", "displaystyle"}
FUNCS = {"max", "min", "log", "exp", "cos", "ln", "sin"}
STYLE_CMDS = {"mathbf": "b", "boldsymbol": "b", "mathcal": "i", "mathbb": "b"}
RAW_CMDS = {"mathrm", "text", "operatorname"}


class _Parser:
    def __init__(self, s: str):
        self.s = s
        self.i = 0

    def eof(self) -> bool:
        return self.i >= len(self.s)

    def peek(self) -> str:
        return self.s[self.i] if not self.eof() else ""

    def group_raw(self) -> str:
        """Reads {...} (or one char) verbatim, without interpreting it."""
        self.skip_space()
        if self.peek() == "{":
            depth, start = 0, self.i + 1
            while not self.eof():
                c = self.s[self.i]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        raw = self.s[start:self.i]
                        self.i += 1
                        return raw
                self.i += 1
            return self.s[start:]
        ch = self.peek()
        self.i += 1
        return ch

    def skip_space(self) -> None:
        while not self.eof() and self.s[self.i] == " ":
            self.i += 1

    def atom(self) -> List[Segment]:
        """One braced group, one command, or one character, as segments."""
        self.skip_space()
        if self.peek() == "{":
            return parse(self.group_raw())
        return self.token()

    def token(self) -> List[Segment]:
        c = self.peek()
        if c == "\\":
            return self.command()
        self.i += 1
        if c.isalpha():
            return [(c, frozenset({"i"}))]
        return [(c, frozenset())]

    def command(self) -> List[Segment]:
        self.i += 1  # backslash
        if self.eof():
            return []
        if not self.s[self.i].isalpha():
            ch = self.s[self.i]
            self.i += 1
            if ch in SPACES:
                return [(SPACES[ch], frozenset())] if SPACES[ch] else []
            if ch == "\\":
                return [("\n", frozenset())]
            return [(ch, frozenset())]  # \{ \} \_ \% ...
        start = self.i
        while not self.eof() and self.s[self.i].isalpha():
            self.i += 1
        name = self.s[start:self.i]

        if name in DROP:
            return []
        if name in SPACES:
            return [(SPACES[name], frozenset())]
        if name in SYMBOLS:
            return [(SYMBOLS[name], frozenset())]
        if name in FUNCS:
            return [(name, frozenset())]
        if name in STYLE_CMDS:
            flag = STYLE_CMDS[name]
            return [(t, st | {flag}) for t, st in self.atom()]
        if name in RAW_CMDS:
            return [(self.group_raw().replace("\\_", "_"), frozenset())]
        if name in ("frac", "dfrac"):
            num, den = self.atom(), self.atom()
            return _paren(num) + [("/", frozenset())] + _paren(den)
        if name == "sqrt":
            return [("√", frozenset())] + _paren(self.atom())
        if name == "hat":
            inner = self.atom()
            return [(t + ("̂" if k == len(inner) - 1 else ""), st) for k, (t, st) in enumerate(inner)]
        if name == "top":
            return [("T", frozenset({"sup"}))]
        if name == "bar":
            inner = self.atom()
            return [(t + ("̄" if k == len(inner) - 1 else ""), st) for k, (t, st) in enumerate(inner)]
        return [("\\" + name, frozenset())]


def _paren(segs: List[Segment]) -> List[Segment]:
    text = "".join(t for t, _ in segs)
    if len(text) <= 1 or text.replace(".", "").isdigit():
        return segs
    return [("(", frozenset())] + segs + [(")", frozenset())]


def parse(latex: str) -> List[Segment]:
    p = _Parser(latex)
    out: List[Segment] = []
    while not p.eof():
        c = p.peek()
        if c in "_^":
            p.i += 1
            flag = "sub" if c == "_" else "sup"
            out.extend((t, st | {flag}) for t, st in p.atom())
        elif c == "{":
            out.extend(parse(p.group_raw()))
        elif c == "$":
            p.i += 1
        else:
            out.extend(p.token())
    return _merge(out)


def _merge(segs: List[Segment]) -> List[Segment]:
    merged: List[Segment] = []
    for text, style in segs:
        if merged and merged[-1][1] == style:
            merged[-1] = (merged[-1][0] + text, style)
        else:
            merged.append((text, style))
    return merged


def plain(latex: str) -> str:
    return "".join(t for t, _ in parse(latex))
