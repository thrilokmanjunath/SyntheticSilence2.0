"""Figure 1: pipeline overview, drawn with matplotlib so it prints in grayscale."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402


def pipeline_figure(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(3.45, 3.05), dpi=300)
    ax.set_xlim(0, 3.45)
    ax.set_ylim(0, 3.05)
    ax.axis("off")
    font = {"family": "serif", "size": 6.4, "color": "black"}

    def box(x, y, w, h, text, dashed=False):
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.04", linewidth=0.8,
            edgecolor="black", facecolor="white", linestyle=(0, (3, 2)) if dashed else "-"))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", **font, linespacing=1.15)

    def arrow(x0, y0, x1, y1):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=6,
                                     linewidth=0.8, color="black", shrinkA=0, shrinkB=0))

    w, h, x = 1.62, 0.36, 0.08
    ys = [2.62, 2.12, 1.62, 1.12, 0.62, 0.12]
    labels = [
        "Selected passage",
        "Extract claims\n(language model)",
        "Retrieve sources\n(Wikipedia, OpenAlex)",
        "Rank by cosine similarity\n(keep top 6)",
        "Per-source stance + quote\n(language model)",
        "Verdict rules\n(deterministic)",
    ]
    for y, text in zip(ys, labels):
        box(x, y, w, h, text)
    for upper, lower in zip(ys[:-1], ys[1:]):
        arrow(x + w / 2, upper, x + w / 2, lower + h)

    # Experimental branch, computed alongside and not used by the verdict.
    bx, bw = 2.0, 1.38
    box(bx, 1.02, bw, 0.56, "Density (kNN,\nMahalanobis) and\nentropy: gap score", dashed=True)
    arrow(x + w, ys[3] + h / 2, bx, 1.30)
    ax.text(bx + bw / 2, 0.93, "experimental,\nnot in verdict", ha="center", va="top", **{**font, "size": 5.6})

    # Output.
    box(bx, ys[5] - 0.07, bw, 0.5, "Streamed result\nper claim: verdict,\nquote and sources")
    arrow(x + w, ys[5] + h / 2, bx, ys[5] + h / 2)

    fig.savefig(path, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
