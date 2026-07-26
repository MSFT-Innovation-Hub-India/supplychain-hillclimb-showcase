"""Plot the measured quality, cost, and latency model-package hill climb."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


ORDER = ("teacher_default", "sft", "teacher_medium", "rft_medium")
DISPLAY = {
    "teacher_default": ("GPT-5.2", "Teacher · no reasoning"),
    "sft": ("GPT-4.1-mini", "SFT · distilled teacher knowledge"),
    "teacher_medium": ("GPT-5.2", "Teacher · medium reasoning"),
    "rft_medium": ("o4-mini", "RFT · medium reasoning"),
}
WEIGHTS = {"quality": 0.70, "cost": 0.15, "latency": 0.15}
GREEN = "#86d000"
RED = "#ff5a52"
AMBER = "#f5b700"
WHITE = "#f7f7f7"
MUTED = "#b8b8b8"
PANEL = "#1b1b1b"
GRID = "#555555"


def normalize(values: list[float], *, lower_is_better: bool = False) -> list[float]:
    minimum, maximum = min(values), max(values)
    if maximum == minimum:
        return [1.0] * len(values)
    normalized = [(value - minimum) / (maximum - minimum) for value in values]
    return [1.0 - value for value in normalized] if lower_is_better else normalized


def load_stages(report_path: Path) -> list[dict]:
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    by_label = {point["label"]: point for point in report["hill_climb"]["points"]}
    stages = [dict(by_label[label]) for label in ORDER]

    quality = normalize([stage["quality_score"] for stage in stages])
    cost = normalize([stage["estimated_usd_per_scenario"] for stage in stages], lower_is_better=True)
    latency = normalize([stage["p50_latency_seconds"] for stage in stages], lower_is_better=True)
    for index, stage in enumerate(stages):
        stage["success_index"] = 100 * (
            WEIGHTS["quality"] * quality[index]
            + WEIGHTS["cost"] * cost[index]
            + WEIGHTS["latency"] * latency[index]
        )
    return stages


def trend(current: float, previous: float, *, lower_is_better: bool = False) -> tuple[str, str]:
    improvement = current < previous if lower_is_better else current > previous
    if abs(current - previous) < 1e-12:
        return "=", MUTED
    return ("↑" if current > previous else "↓"), GREEN if improvement else RED


def plot(report_path: Path, output_path: Path) -> None:
    stages = load_stages(report_path)
    scores = [stage["success_index"] for stage in stages]
    x_values = list(range(len(stages)))

    plt.style.use("dark_background")
    figure = plt.figure(figsize=(16, 9), facecolor="#050505")
    axis = figure.add_axes((0.055, 0.20, 0.90, 0.62), facecolor="#0d0d0d")

    boundaries = [-0.5, 0.5, 1.5, 2.5, 3.5]
    axis.stairs(scores, boundaries, color=GREEN, linewidth=2.8, fill=True, alpha=0.18)
    axis.stairs(scores, boundaries, color=GREEN, linewidth=2.8)

    for index, score in enumerate(scores):
        marker_color = GREEN if index == len(scores) - 1 else (RED if index == 1 else AMBER)
        axis.scatter(index, score, s=260, color=marker_color, edgecolor=WHITE, linewidth=2, zorder=5)
        axis.text(index, score + 4.0, f"{score:.0f}", ha="center", va="bottom", color=WHITE,
                  fontsize=16, fontweight="bold")

    axis.set_xlim(-0.5, 3.5)
    axis.set_ylim(0, 105)
    axis.set_ylabel("Composite success index", color=WHITE, fontsize=15, fontweight="bold")
    axis.set_yticks((0, 20, 40, 60, 80, 100))
    axis.set_yticklabels(("0", "20", "40", "60", "80", "100"), color=MUTED, fontsize=11)
    axis.set_xticks([])
    axis.grid(axis="y", color=GRID, alpha=0.35, linewidth=0.8)
    for spine in axis.spines.values():
        spine.set_color("#aaaaaa")

    figure.text(0.055, 0.925, "Supply-chain model hill climb", color=WHITE, fontsize=31, fontweight="bold")
    figure.text(0.055, 0.875, "Quality first, then optimize cost and latency without giving it back",
                color=WHITE, fontsize=18)
    figure.text(0.955, 0.885, "70% quality  ·  15% cost  ·  15% latency",
                color=MUTED, fontsize=11, ha="right")

    metrics_y = 0.09
    box_width = 0.225
    box_left = 0.055
    for index, stage in enumerate(stages):
        left = box_left + index * box_width
        selected = index == len(stages) - 1
        figure.patches.append(Rectangle(
            (left, 0.015), box_width, 0.16, transform=figure.transFigure,
            facecolor="#222222" if selected else PANEL,
            edgecolor=GREEN if selected else "#777777", linewidth=2 if selected else 1,
        ))
        model, method = DISPLAY[stage["label"]]
        figure.text(left + 0.012, 0.145, model, color=GREEN if selected else WHITE,
                    fontsize=14, fontweight="bold")
        figure.text(left + 0.012, 0.119, method, color=MUTED, fontsize=10)

        metrics = (
            ("Quality", stage["quality_score"], False, ".3f"),
            ("P50 latency", stage["p50_latency_seconds"], True, ".2f"),
            ("Token cost", stage["estimated_usd_per_scenario"], True, ".4f"),
        )
        for row, (name, value, lower_is_better, value_format) in enumerate(metrics):
            y = metrics_y - row * 0.027
            if index == 0:
                symbol, color = "●", MUTED
            else:
                previous = stages[index - 1]
                previous_key = {
                    "Quality": "quality_score",
                    "P50 latency": "p50_latency_seconds",
                    "Token cost": "estimated_usd_per_scenario",
                }[name]
                symbol, color = trend(value, previous[previous_key], lower_is_better=lower_is_better)
            unit = "s" if name == "P50 latency" else ("$" if name == "Token cost" else "")
            rendered = f"{value:{value_format}}"
            rendered = f"${rendered}" if unit == "$" else f"{rendered}{unit}"
            figure.text(left + 0.012, y, f"{symbol} {name}", color=color, fontsize=9, fontweight="bold")
            figure.text(left + box_width - 0.012, y, rendered, color=WHITE, fontsize=9, ha="right")

    figure.text(0.055, 0.845,
                "Green = improved vs previous stage   Red = worsened vs previous stage   Gray = baseline",
                color=MUTED, fontsize=10)
    figure.text(0.955, 0.005,
                "Index uses min-max normalization across the four measured packages; lower cost and latency are better.",
                color="#8f8f8f", fontsize=8, ha="right")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, facecolor=figure.get_facecolor())
    plt.close(figure)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plot(args.report, args.output)
    print(args.output)
