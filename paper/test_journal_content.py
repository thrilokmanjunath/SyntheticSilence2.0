"""Static checks on the journal draft: no unconverted math, every citation and cross-reference resolves."""
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "journal"))

import content_journal as J  # noqa: E402
import mathtext  # noqa: E402
from refs_journal import CITES, REFERENCES  # noqa: E402


def texts():
    """Every running-text string in the draft."""
    out = [J.TITLE, J.ABSTRACT, J.ACKNOWLEDGMENTS]
    sections = ([b for _, blocks in J.SECTIONS for b in blocks]
                + [b for _, blocks in J.LIMITATIONS for b in blocks]
                + [b for _, blocks in J.APPENDICES for b in blocks])
    for b in sections:
        kind = b[0]
        if kind in ("p", "remark", "sub"):
            out.append(b[1])
        elif kind == "list":
            out.extend(b[1])
        elif kind == "thm":
            out.extend([b[2], b[3]])
        elif kind == "proof":
            out.extend(b[1])
        elif kind == "fig":
            out.append(b[2])
        elif kind in ("table", "matrix"):
            out.append(b[1])
            if b[-1]:
                out.append(b[-1])
    return out


def test_every_inline_math_fragment_converts_completely():
    bad = []
    for t in texts():
        for frag in re.findall(r"\$([^$]*)\$", t):
            out = mathtext.plain(frag)
            if "\\" in out:          # an unknown command is passed through visibly
                bad.append((frag[:50], out[:50]))
    assert not bad, bad[:5]


def test_every_equation_converts_completely():
    for _, blocks in J.SECTIONS:
        for b in blocks:
            if b[0] == "eq":
                assert "\\" not in mathtext.plain(b[1].replace("\\qquad", " ")), b[1][:60]


def test_every_citation_key_exists_and_every_reference_is_cited():
    cited = set()
    for t in texts():
        for m in re.finditer(r"\[@([^\]]+)\]", t):
            for part in m.group(1).split(";"):
                key = part.strip().lstrip("@").split(":")[0]
                cited.add(key)
    assert cited <= set(CITES) and cited <= set(REFERENCES), cited - set(CITES)
    assert set(CITES) == set(REFERENCES)
    assert cited == set(CITES), f"never cited: {set(CITES) - cited}"


def test_numbered_references_in_text_exist():
    counts = {"Figure": 0, "Table": 0, "thm": 0}
    for _, blocks in J.SECTIONS:
        for b in blocks:
            if b[0] == "fig":
                counts["Figure"] += 1
            elif b[0] in ("table", "matrix"):
                counts["Table"] += 1
            elif b[0] == "thm":
                counts["thm"] += 1
    body = " ".join(texts())
    for n in map(int, re.findall(r"Figure (\d+)", body)):
        assert 1 <= n <= counts["Figure"], f"Figure {n}"
    for n in map(int, re.findall(r"(?:Theorem|Proposition) (\d+)", body)):
        assert 1 <= n <= counts["thm"], f"Theorem/Proposition {n}"
    for n in map(int, re.findall(r"Table (\d+)", body)):
        assert 1 <= n <= counts["Table"], f"Table {n}"


def test_section_references_exist():
    n_sections = len(J.SECTIONS)
    subs = {i: sum(1 for b in blocks if b[0] == "sub") for i, (_, blocks) in enumerate(J.SECTIONS, start=1)}
    body = " ".join(texts())
    for m in re.finditer(r"Sections? (\d+)(?:\.(\d+))?", body):
        sec, sub = int(m.group(1)), m.group(2)
        assert 1 <= sec <= n_sections, m.group(0)
        if sub:
            assert 1 <= int(sub) <= subs[sec], m.group(0)


def test_matrices_are_rectangular_and_labelled_consistently():
    for _, blocks in J.SECTIONS + J.APPENDICES:
        for b in blocks:
            if b[0] == "matrix":
                _, _, rows, cols, values, _ = b
                assert len(values) == len(rows)
                assert all(len(r) == len(cols) for r in values)
