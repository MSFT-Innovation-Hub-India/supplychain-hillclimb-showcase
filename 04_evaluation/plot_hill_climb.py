from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def plot(report_path: Path, output_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    points = report.get("hill_climb", {}).get("points", [])
    if not points:
        raise ValueError("report does not contain hill_climb points; rerun evaluate.py")
    if any(point.get("p50_latency_seconds") is None for point in points):
        raise ValueError("latency telemetry is incomplete; rerun all arms with the instrumented evaluator")
    if any(point.get("estimated_usd_per_scenario") is None for point in points):
        raise ValueError("cost estimates are missing; rerun evaluate.py with --pricing for every arm")

    latencies = [point["p50_latency_seconds"] for point in points]
    qualities = [point["quality_score"] for point in points]
    costs = [point["estimated_usd_per_scenario"] for point in points]
    maximum_cost = max(costs) or 1.0
    sizes = [180 + 920 * cost / maximum_cost for cost in costs]
    colors = ["#8bd000", "#00b7c3", "#ffb900", "#d83b01", "#8764b8"]
    label_offsets = [(14, 42), (14, -48)]

    plt.style.use("dark_background")
    figure, axis = plt.subplots(figsize=(12, 7), constrained_layout=True)
    figure.patch.set_facecolor("#090909")
    axis.set_facecolor("#151515")
    axis.grid(color="#555555", alpha=0.35, linewidth=0.8)

    for index, point in enumerate(points):
        color = colors[index % len(colors)]
        axis.scatter(
            point["p50_latency_seconds"],
            point["quality_score"],
            s=sizes[index],
            color=color,
            edgecolor="white",
            linewidth=1.2,
            alpha=0.9,
            zorder=3,
        )
        axis.annotate(
            f"{point['label']}\n"
            f"quality {point['quality_score']:.3f}\n"
            f"${point['estimated_usd_per_scenario']:.4f}/scenario",
            (point["p50_latency_seconds"], point["quality_score"]),
            xytext=label_offsets[index] if index < len(label_offsets) else (12, 12),
            textcoords="offset points",
            fontsize=10,
            weight="bold",
            arrowprops={"arrowstyle": "-", "color": "#aaaaaa", "lw": 0.8},
        )
        if index:
            previous = points[index - 1]
            axis.annotate(
                "",
                xy=(point["p50_latency_seconds"], point["quality_score"]),
                xytext=(previous["p50_latency_seconds"], previous["quality_score"]),
                arrowprops={"arrowstyle": "->", "color": "#dddddd", "lw": 1.5},
                zorder=2,
            )

    axis.set_title("Supply-Chain Model Hill Climb", fontsize=24, weight="bold", loc="left", pad=18)
    axis.set_xlabel("P50 end-to-end latency (seconds, lower is better)", fontsize=12)
    axis.set_ylabel("Deterministic business quality (higher is better)", fontsize=12)
    axis.set_ylim(0, min(1.0, max(qualities) + 0.12))
    axis.text(
        0.01,
        0.01,
        "Bubble area represents estimated inference cost per scenario. Arrows follow --arm order.",
        transform=axis.transAxes,
        color="#cccccc",
        fontsize=10,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, facecolor=figure.get_facecolor())
    plt.close(figure)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    destination = args.output or args.report.with_name(f"{args.report.stem}-hill-climb.png")
    plot(args.report, destination)
    print(destination)