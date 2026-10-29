"""Figures for the journal draft. Grayscale-safe; every figure is drawn from data.py or from the formulas."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import data  # noqa: E402

plt.rcParams.update({
    "font.family": "serif", "font.size": 7.5, "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
})
DPI = 300
NAMES = list(data.CONFUSION)
SHORT = {"Pooled, OpenAlex": "Pooled\nOpenAlex", "Pooled, Wikipedia": "Pooled\nWikipedia", "Stance, Wikipedia": "Stance\nWikipedia"}


def confusion_heatmaps(path: Path) -> None:
    """Row-normalised confusion matrices (share of each gold class), counts printed in cells."""
    # Column-width figure: the two Wikipedia variants, which are the comparison the paper turns on.
    # The OpenAlex baseline matrix is given in full in its own table.
    shown = ["Pooled, Wikipedia", "Stance, Wikipedia"]
    fig, axes = plt.subplots(1, 2, figsize=(3.3, 1.75), dpi=DPI, sharey=True)
    for ax, name in zip(axes, shown):
        m = np.array(data.CONFUSION[name])
        r = np.array(data.row_normalised(data.CONFUSION[name]))
        im = ax.imshow(r, cmap="Greys", vmin=0, vmax=1, aspect="auto")
        for i in range(3):
            for j in range(4):
                ax.text(j, i, f"{m[i, j]}", ha="center", va="center",
                        color="white" if r[i, j] > 0.55 else "black", fontsize=6.5)
        ax.set_xticks(range(4), ["S", "R", "N", "M"])
        ax.set_yticks(range(3), ["SUPPORTS", "REFUTES", "NEI"])
        ax.set_xlabel("predicted", fontsize=7)
        ax.set_title(name, fontsize=7)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(length=0)
    axes[0].set_ylabel("gold")
    cbar = fig.colorbar(im, ax=axes, fraction=0.04, pad=0.02)
    cbar.set_label("share of gold class", fontsize=6.5)
    cbar.ax.tick_params(labelsize=6)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def accuracy_intervals(path: Path) -> None:
    """Overall and decisive accuracy with 95% Wilson intervals, same 100 claims in every variant."""
    fig, ax = plt.subplots(figsize=(3.35, 2.25), dpi=DPI)
    width = 0.36
    x = np.arange(len(NAMES))
    for k, (key, ckey, label, hatch) in enumerate([
        ("accuracy", "accuracy_ci", "Accuracy (n = 100)", ""),
        ("decisive_accuracy", "decisive_ci", "Decisive accuracy (n = 69)", "////"),
    ]):
        vals = [data.metrics(data.CONFUSION[n])[key] for n in NAMES]
        cis = [data.metrics(data.CONFUSION[n])[ckey] for n in NAMES]
        err = np.array([[v - c[0], c[1] - v] for v, c in zip(vals, cis)]).T
        pos = x + (k - 0.5) * width
        ax.bar(pos, vals, width, yerr=err, capsize=2, color="white" if hatch else "0.55",
               edgecolor="black", hatch=hatch, linewidth=0.6, label=label, error_kw={"linewidth": 0.7})
        for p, v in zip(pos, vals):
            ax.text(p, v + 0.02, f"{v * 100:.1f}", ha="center", va="bottom", fontsize=6)
    ax.set_xticks(x, [SHORT[n] for n in NAMES])
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("proportion correct")
    ax.axhline(1 / 3, color="black", linewidth=0.5, linestyle=":")
    ax.text(2.55, 1 / 3 + 0.01, "chance (3 classes)", ha="right", fontsize=6)
    ax.legend(frameon=False, fontsize=6.5, loc="upper left")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def entropy_curves(path: Path) -> None:
    """U(tau) for similarity sets of different spread, with the Proposition 2 lower bound."""
    fig, ax = plt.subplots(figsize=(3.35, 2.3), dpi=DPI)
    taus = np.linspace(0.02, 0.6, 300)
    rng = np.random.default_rng(12)
    n = 10
    for style, spread in (("-", 0.05), ("--", 0.15), ("-.", 0.40)):
        s = np.linspace(0.30, 0.30 + spread, n)
        u = []
        for t in taus:
            z = s / t
            p = np.exp(z - z.max())
            p /= p.sum()
            u.append(-(p * np.log(p)).sum() / math.log(n))
        ax.plot(taus, u, "k", linestyle=style, linewidth=1.0, label=f"spread = {spread:.2f}")
        bound = np.maximum(0, 1 - spread / (taus * math.log(n)))
        ax.plot(taus, bound, color="0.55", linestyle=style, linewidth=0.7)
    ax.axvline(0.1, color="black", linewidth=0.5, linestyle=":")
    ax.text(0.105, 0.04, r"$\tau = 0.1$", fontsize=6.5)
    ax.set_xlabel(r"temperature $\tau$")
    ax.set_ylabel(r"normalised entropy $U$")
    ax.set_ylim(0, 1.02)
    ax.legend(frameon=False, fontsize=6.5, loc="lower right", title="black: U, gray: bound", title_fontsize=6)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def verdict_regions(path: Path) -> None:
    """Which verdict follows from (number of counted supports, strongest counted support), no refutations."""
    fig, ax = plt.subplots(figsize=(3.35, 2.1), dpi=DPI)
    counts = np.arange(0, 5)
    confs = np.array([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    grid = np.zeros((len(confs), len(counts)))
    for i, c in enumerate(confs):
        for j, n in enumerate(counts):
            qualifies = n >= 2 or (n == 1 and c >= 0.8)
            grid[i, j] = 1 if qualifies else 0
    ax.imshow(grid, origin="lower", cmap="Greys", vmin=0, vmax=1.6, aspect="auto")
    for i in range(len(confs)):
        for j in range(len(counts)):
            if counts[j] == 0:
                label = "insufficient"
            else:
                label = "supported" if grid[i, j] else "insufficient\n(leans true)"
            ax.text(j, i, label, ha="center", va="center", fontsize=5.4,
                    color="white" if grid[i, j] else "black")
    ax.set_xticks(range(len(counts)), [str(n) for n in counts])
    ax.set_yticks(range(len(confs)), [f"{c:.1f}" for c in confs])
    ax.set_xlabel(r"counted supporting sources $|\mathcal{P}|$")
    ax.set_ylabel(r"strongest counted $\kappa$")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def build_all(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    confusion_heatmaps(out / "confusion.png")
    accuracy_intervals(out / "accuracy.png")
    entropy_curves(out / "entropy.png")
    verdict_regions(out / "regions.png")


if __name__ == "__main__":
    build_all(Path(sys.argv[1]))
    print("figures written")
