"""Generate IEEE-ready figures from benchmark summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate figures for IEEE paper",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=Path("data/experiments/tamper_benchmark/benchmark_summary.json"),
        help="Benchmark summary JSON file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/figures"),
        help="Output directory for figures",
    )
    return parser.parse_args()


def _save_attack_detection_figure(rows: list[dict], output_dir: Path) -> None:
    attack_names = [row["attack_type"] for row in rows]
    detected = [int(row["detected"]) for row in rows]

    plt.figure(figsize=(12, 5))
    colors = ["#2E86AB" if val == 1 else "#D64550" for val in detected]
    plt.bar(range(len(attack_names)), detected, color=colors)
    plt.xticks(range(len(attack_names)), attack_names, rotation=35, ha="right")
    plt.yticks([0, 1], ["Missed", "Detected"])
    plt.ylim(-0.1, 1.2)
    plt.title("Tamper Attack Detection Result")
    plt.tight_layout()
    plt.savefig(output_dir / "fig_attack_detection.png", dpi=300)
    plt.close()


def _save_first_failure_figure(rows: list[dict], output_dir: Path) -> None:
    attack_names = [row["attack_type"] for row in rows]
    first_failed = [int(row["first_failed_step_index"]) for row in rows]

    plt.figure(figsize=(12, 5))
    plt.bar(range(len(attack_names)), first_failed, color="#4E79A7")
    plt.xticks(range(len(attack_names)), attack_names, rotation=35, ha="right")
    plt.ylabel("First Failed Step Index")
    plt.title("Earliest Detection Position by Attack Type")
    plt.tight_layout()
    plt.savefig(output_dir / "fig_first_failed_step.png", dpi=300)
    plt.close()


def _save_cascade_ratio_figure(rows: list[dict], output_dir: Path) -> None:
    attack_names = [row["attack_type"] for row in rows]
    failed_records = [int(row["failed_records"]) for row in rows]
    max_records = max(max(failed_records), 1)
    cascade_ratio = [val / max_records for val in failed_records]

    plt.figure(figsize=(12, 5))
    plt.bar(range(len(attack_names)), cascade_ratio, color="#59A14F")
    plt.xticks(range(len(attack_names)), attack_names, rotation=35, ha="right")
    plt.ylabel("Normalized Cascade Impact")
    plt.title("Relative Cascading Inconsistency Impact")
    plt.tight_layout()
    plt.savefig(output_dir / "fig_cascade_impact.png", dpi=300)
    plt.close()


def _save_architecture_figure(output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis("off")

    blocks = [
        (0.05, 0.35, 0.22, 0.3, "Stage-1\nSynchronization"),
        (0.32, 0.35, 0.22, 0.3, "Stage-2\nSM3 Hash Chain"),
        (0.59, 0.35, 0.22, 0.3, "Stage-3\nVerify & Locate"),
    ]
    for x, y, w, h, text in blocks:
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02",
            linewidth=1.5,
            edgecolor="#1f1f1f",
            facecolor="#E8F1FA",
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=11)

    ax.annotate("", xy=(0.32, 0.5), xytext=(0.27, 0.5), arrowprops={"arrowstyle": "->"})
    ax.annotate("", xy=(0.59, 0.5), xytext=(0.54, 0.5), arrowprops={"arrowstyle": "->"})
    ax.text(0.84, 0.5, "Report", va="center", fontsize=10)
    ax.annotate("", xy=(0.84, 0.5), xytext=(0.81, 0.5), arrowprops={"arrowstyle": "->"})

    plt.title("SM3ChainGuard End-to-End Workflow")
    plt.tight_layout()
    plt.savefig(output_dir / "fig_system_architecture.png", dpi=300)
    plt.close()


def main() -> None:
    args = parse_args()
    summary_path = args.summary_json
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = summary["rows"]

    _save_attack_detection_figure(rows=rows, output_dir=output_dir)
    _save_first_failure_figure(rows=rows, output_dir=output_dir)
    _save_cascade_ratio_figure(rows=rows, output_dir=output_dir)
    _save_architecture_figure(output_dir=output_dir)


if __name__ == "__main__":
    main()
