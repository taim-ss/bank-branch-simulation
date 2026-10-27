"""Check the bank-branch results against queueing theory and draw the figures.

Usage:  python scripts/analyze_runs.py [--figures]

Reads data/bank-runs.csv (24 AnyLogic runs: 12 configurations x two buffer settings,
fixed seed 1) and compares each measured utilisation with the offered-load prediction
rho = arrival rate x routing share x mean service time / servers.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "bank-runs.csv"
FIGURES = ROOT / "docs" / "figures"

# Means of the triangular service-time distributions, in minutes.
MEAN_SERVICE = {"atm": (0.8 + 1.5 + 3.5) / 3, "teller": (2.5 + 6 + 11) / 3, "business": (6 + 12 + 22) / 3}
CHOSEN = ["T1a-3", "T2-3", "T3-2", "T4-1", "T5-2"]
TARGET_MIN = {"T1a": 20000, "T2": 20000, "T3": 20000, "T4": 20000, "T5": 7000}
# A run counts as a steady-state measurement if it ran at least this long.
MIN_STEADY_MIN = 5000


def fluctuating_rate() -> float:
    """Renewal rate 1/E[1/lambda] for triangular(2.5, 5.5, 12.5)."""
    low, mode, high = 2.5, 5.5, 12.5
    mean_interval = (
        2 * ((mode - low) - low * math.log(mode / low)) / ((high - low) * (mode - low))
        + 2 * (high * math.log(high / mode) - (high - mode)) / ((high - low) * (high - mode))
    )
    return 1 / mean_interval


def load_runs(path: Path = RUNS) -> pd.DataFrame:
    runs = pd.read_csv(path)
    parts = runs["run_id"].str.extract(r"R\d+_(?P<task>T\d[a-z]?)_?(?P<variant>\d?)_(?P<buffers>spec|big)")
    runs["config"] = parts["task"] + "-" + parts["variant"].where(parts["variant"] != "", "")
    runs["config"] = runs["config"].str.replace(r"^(T1a)-(\d)$", r"\1-\2", regex=True)
    runs["buffers"] = parts["buffers"]
    runs["chosen"] = runs["config"].isin(CHOSEN)
    runs["target_min"] = runs["config"].str.extract(r"^(T1a|T\d)")[0].map(TARGET_MIN)
    runs["completed"] = runs["stop_min"] >= runs["target_min"] - 1e-6
    return runs


def effective_rate(runs: pd.DataFrame) -> pd.Series:
    """Arrival rate used for the prediction.

    Tasks 1-4 use the stated rate. In Task 5 the interarrival time is exponential(triangular(...)),
    so use the independently calculated renewal rate 1/E[1/lambda].
    """
    return runs["arrival_rate"].where(~runs["fluctuating"], fluctuating_rate())


def with_predictions(runs: pd.DataFrame) -> pd.DataFrame:
    out = runs.copy()
    rate = effective_rate(out)
    teller_share = out["p_teller"] + out["p_rework"] * out["p_atm"]
    out["pred_atm"] = rate * out["p_atm"] * MEAN_SERVICE["atm"] / out["n_atm"]
    out["pred_teller"] = rate * teller_share * MEAN_SERVICE["teller"] / out["n_teller"]
    out["pred_business"] = rate * out["p_business"] * MEAN_SERVICE["business"] / out["n_business"]
    return out


def deviations(runs: pd.DataFrame) -> pd.DataFrame:
    """Per run: largest |measured - predicted| over branches that are in use and stable."""
    out = with_predictions(runs)
    used = {"atm": out["p_atm"] > 0, "teller": out["p_teller"] > 0, "business": out["p_business"] > 0}
    stable = pd.Series(True, index=out.index)
    gaps = pd.DataFrame(index=out.index)
    for branch, in_use in used.items():
        predicted, measured = out[f"pred_{branch}"], out[f"util_{branch}"]
        stable &= ~(in_use & (predicted >= 1))
        gaps[branch] = ((measured - predicted).abs()).where(in_use)
    out["max_gap"] = gaps.max(axis=1)
    out["stable_prediction"] = stable
    out["steady"] = stable & (out["stop_min"] >= MIN_STEADY_MIN)
    return out


def draw_figures(runs: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES.mkdir(parents=True, exist_ok=True)
    data = deviations(runs)

    # 1. Predicted versus measured utilisation.
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    for branch in ("atm", "teller", "business"):
        sub = data[data[f"p_{branch}"] > 0]
        good = sub[sub["steady"]]
        bad = sub[~sub["steady"]]
        ax.scatter(good[f"pred_{branch}"], good[f"util_{branch}"], c="#2b6aa3", s=34, zorder=3)
        ax.scatter(bad[f"pred_{branch}"], bad[f"util_{branch}"], c="#b2312c", marker="^", s=34, zorder=3)
    ax.plot([0, 1.05], [0, 1.05], c="#667", lw=1)
    ax.fill_between([0, 1.05], [-0.03, 1.02], [0.03, 1.08], color="#999", alpha=0.15)
    ax.axvline(1.0, c="#b2312c", ls="--", lw=1)
    ax.set_xlim(0, 1.3)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Predicted utilisation  rho = rate x share x E[S] / servers")
    ax.set_ylabel("Measured utilisation (time average)")
    ax.set_title("Measured vs predicted utilisation, all branches of 24 runs")
    ax.scatter([], [], c="#2b6aa3", label="stable branch, run of 5,000+ min")
    ax.scatter([], [], c="#b2312c", marker="^", label="overloaded branch or early stop")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "utilisation-validation.png", dpi=160)
    plt.close(fig)

    # 2. Share of the target run time each configuration survived with the specified buffers.
    spec = data[data["buffers"] == "spec"].copy()
    spec["share"] = (spec["stop_min"] / spec["target_min"]).clip(upper=1) * 100
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    colours = ["#2b8a3e" if c else "#9aa0a6" for c in spec["chosen"]]
    labels = [f"{c}  ({a}/{t}/{b})" for c, a, t, b in zip(spec["config"], spec["n_atm"], spec["n_teller"], spec["n_business"])]
    ax.barh(labels[::-1], spec["share"][::-1], color=colours[::-1])
    ax.set_xlabel("Share of the target run time completed (%), buffers as specified")
    ax.set_title("Which configurations survive the specified buffers?\n(green = configuration chosen for the task)")
    for y, value in enumerate(spec["share"][::-1]):
        ax.text(min(value + 1, 92), y, f"{value:.0f}%", va="center", fontsize=8)
    ax.set_xlim(0, 105)
    fig.tight_layout()
    fig.savefig(FIGURES / "survival-by-configuration.png", dpi=160)
    plt.close(fig)

    # 3. Customer experience of the chosen configurations (buffers raised, steady state).
    chosen = data[(data["buffers"] == "big") & data["chosen"]]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    names = [f"{c}\n{a} ATM / {t} teller /\n{b} business" for c, a, t, b in zip(chosen["config"], chosen["n_atm"], chosen["n_teller"], chosen["n_business"])]
    ax.bar(names, chosen["in_system_mean"], color="#2b6aa3")
    for x, value in enumerate(chosen["in_system_mean"]):
        ax.text(x, value + 0.1, f"{value:.2f}", ha="center", fontsize=9)
    ax.set_ylabel("Mean time in the bank (minutes)")
    ax.set_title("Chosen configuration per task: customer time in the bank")
    ax.set_ylim(0, max(chosen["in_system_mean"]) * 1.2)
    fig.tight_layout()
    fig.savefig(FIGURES / "chosen-configurations.png", dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figures", action="store_true", help="regenerate docs/figures")
    args = parser.parse_args()

    data = deviations(load_runs())
    steady = data[data["steady"]]
    chosen = data[data["chosen"] & data["steady"]]
    print(f"steady-state runs with a stable prediction: {len(steady)} of {len(data)}")
    print(f"  largest utilisation gap, all steady runs:    {100 * steady['max_gap'].max():.1f} percentage points")
    print(f"  largest utilisation gap, chosen configs:     {100 * chosen['max_gap'].max():.1f} percentage points")
    early = data[~data["steady"] & data["stable_prediction"]]
    for _, row in early.iterrows():
        print(f"  stopped early {row['run_id']}: {row['stop_min']:.1f} min, gap {100 * row['max_gap']:.1f} pp")
    if args.figures:
        draw_figures(load_runs())
        print(f"figures written to {FIGURES}")


if __name__ == "__main__":
    main()
