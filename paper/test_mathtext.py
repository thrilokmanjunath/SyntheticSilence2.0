import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mathtext import parse, plain  # noqa: E402


def styles(latex):
    return [(t, sorted(s)) for t, s in parse(latex)]


def test_greek_operators_and_spacing():
    out = plain(r"\kappa_i \ge 0.5")
    assert out.startswith("κ") and "≥" in out and out.endswith("0.5")
    assert plain(r"\emptyset") == "∅"


def test_fraction_and_sqrt_are_parenthesised_only_when_needed():
    assert plain(r"\frac{1}{k}") == "1/k"
    assert plain(r"\frac{a+b}{n}") == "(a+b)/n"
    assert plain(r"\sqrt{x+1}") == "√(x+1)"


def test_subscripts_and_superscripts_carry_style():
    segs = styles(r"x_{ij}^2")
    assert ("ij", ["i", "sub"]) in segs
    assert ("2", ["sup"]) in segs


def test_sum_with_limits():
    segs = parse(r"\sum_{j=1}^{k}")
    assert segs[0][0] == "∑"
    assert "".join(t for t, s in segs if "sub" in s) == "j=1"
    assert "".join(t for t, s in segs if "sup" in s) == "k"


def test_text_and_operatorname_are_upright_and_unescaped():
    assert styles(r"\text{no\_sources}") == [("no_sources", [])]
    assert plain(r"\operatorname{tr}(S)") == "tr(S)"


def test_hat_adds_combining_accent_and_bold_vectors():
    assert plain(r"\hat{p}") == "p̂"
    assert ("u", ["b", "i"]) in styles(r"\mathbf{u}") or ("u", ["b"]) in styles(r"\mathbf{u}")


def test_unknown_command_is_visible_not_dropped():
    assert "\\mystery" in plain(r"a \mystery b")


def test_inline_dollar_signs_are_ignored():
    assert plain("$x$") == "x"


def test_all_equations_in_the_paper_convert_without_leftover_commands():
    import content as C

    for _, _, blocks in C.SECTIONS:
        for block in blocks:
            if block[0] == "eq":
                out = plain(block[1].replace("\\qquad", " "))
                assert "\\" not in out, f"unconverted command in: {block[1][:60]} -> {out[:80]}"
