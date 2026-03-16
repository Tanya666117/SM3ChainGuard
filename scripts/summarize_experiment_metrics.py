"""Summarize verification benchmark metrics for paper-ready reporting.

This script aggregates:
1) One clean-chain verification report (negative sample),
2) Multiple tamper attack reports (positive samples),
and exports model-performance metrics to JSON/CSV/Markdown.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize SM3ChainGuard benchmark performance metrics",
    )
    parser.add_argument(
        "--clean-report",
        type=Path,
        default=Path("data/artifacts/task1_verification_report.json"),
        help="Verification report generated from clean chain (negative sample)",
    )
    parser.add_argument(
        "--tamper-reports-dir",
        type=Path,
        default=Path("data/experiments/tamper_benchmark/reports"),
        help="Directory containing attack verification reports (*_report.json)",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("data/experiments/tamper_benchmark/performance_metrics.json"),
        help="Output JSON path for aggregated metrics",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data/experiments/tamper_benchmark/per_attack_metrics.csv"),
        help="Output CSV path for per-attack metrics",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("data/experiments/tamper_benchmark/performance_metrics.md"),
        help="Output Markdown summary path",
    )
    parser.add_argument(
        "--target-step-index",
        type=int,
        default=None,
        help="Optional expected tamper step index for localization-error statistics",
    )
    parser.add_argument(
        "--stage1-artifact",
        type=Path,
        default=Path("data/interim/task1_standardized_frames_b64.json"),
        help="Stage-1 artifact used for storage-overhead estimation",
    )
    parser.add_argument(
        "--chain-artifact",
        type=Path,
        default=Path("data/artifacts/task1_temporal_defense_chain.json"),
        help="Stage-2 chain artifact used for storage-overhead estimation",
    )
    return parser.parse_args()


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _attack_type_from_report_name(report_path: Path) -> str:
    suffix = "_report"
    stem = report_path.stem
    if stem.endswith(suffix):
        return stem[: -len(suffix)]
    return stem


def _format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _attack_family(attack_type: str) -> str:
    if attack_type.startswith("rgb_"):
        return "rgb_content_tamper"
    if "bitflip" in attack_type:
        return "hash_bitflip"
    if attack_type in {
        "annotation_text_edit",
        "reference_timestamp_edit",
        "camera_frame_index_edit",
    }:
        return "semantic_edit"
    if attack_type in {"swap_adjacent_records", "delete_one_record", "duplicate_one_record"}:
        return "structural_edit"
    return "other"


def _compute_four_dimension_results(
    *,
    per_attack_rows: List[Dict[str, Any]],
    sample_level_metrics: Dict[str, float],
    localization_stats: Dict[str, Any],
    stage1_artifact: Path,
    chain_artifact: Path,
    clean_total_records: int,
) -> Dict[str, Any]:
    family_total: Counter[str] = Counter()
    family_detected: Counter[str] = Counter()
    weak_total = 0
    weak_detected = 0
    weak_attack_set = {
        "image_hash_bitflip",
        "timestamp_hash_bitflip",
        "annotation_hash_bitflip",
        "aggregate_hash_bitflip",
        "final_hash_bitflip",
        "previous_hash_bitflip",
        "annotation_text_edit",
        "reference_timestamp_edit",
        "camera_frame_index_edit",
        "rgb_block_occlusion",
        "rgb_gaussian_noise",
        "rgb_jpeg_reencode_low_quality",
    }

    for row in per_attack_rows:
        attack_type = str(row["attack_type"])
        detected = int(row["detected"])
        family = _attack_family(attack_type)
        family_total[family] += 1
        family_detected[family] += detected
        if attack_type in weak_attack_set:
            weak_total += 1
            weak_detected += detected

    family_detection_rate = {
        family: round(_safe_div(family_detected[family], total), 6)
        for family, total in sorted(family_total.items())
    }

    stage1_size_bytes = stage1_artifact.stat().st_size if stage1_artifact.exists() else None
    chain_size_bytes = chain_artifact.stat().st_size if chain_artifact.exists() else None
    storage_overhead_ratio = None
    per_record_chain_bytes = None
    if (
        stage1_size_bytes is not None
        and chain_size_bytes is not None
        and stage1_size_bytes > 0
    ):
        storage_overhead_ratio = round(_safe_div(chain_size_bytes, stage1_size_bytes), 6)
    if chain_size_bytes is not None and clean_total_records > 0:
        per_record_chain_bytes = round(_safe_div(chain_size_bytes, clean_total_records), 4)

    return {
        "detection": {
            "attack_detection_rate": sample_level_metrics["attack_detection_rate"],
            "precision": sample_level_metrics["precision"],
            "recall": sample_level_metrics["recall"],
            "f1_score": sample_level_metrics["f1_score"],
            "specificity": sample_level_metrics["specificity"],
            "balanced_accuracy": sample_level_metrics["balanced_accuracy"],
            "clean_false_positive_rate": sample_level_metrics[
                "clean_false_positive_rate"
            ],
        },
        "localization": {
            "mean_first_failed_step_index": localization_stats[
                "mean_first_failed_step_index"
            ],
            "median_first_failed_step_index": localization_stats[
                "median_first_failed_step_index"
            ],
            "mean_detection_delay_vs_target": localization_stats[
                "mean_detection_delay_vs_target"
            ],
            "mean_abs_localization_error": localization_stats[
                "mean_abs_localization_error"
            ],
        },
        "robustness": {
            "detection_rate_by_attack_family": family_detection_rate,
            "weak_tampering_sensitivity": round(_safe_div(weak_detected, weak_total), 6),
            "weak_tampering_total_attacks": weak_total,
            "weak_tampering_detected_attacks": weak_detected,
        },
        "cost": {
            "stage1_artifact_size_bytes": stage1_size_bytes,
            "chain_artifact_size_bytes": chain_size_bytes,
            "storage_overhead_ratio_chain_over_stage1": storage_overhead_ratio,
            "avg_chain_bytes_per_record": per_record_chain_bytes,
        },
    }


def _write_per_attack_csv(rows: List[Dict[str, Any]], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "attack_type",
        "detected",
        "total_records",
        "passed_records",
        "failed_records",
        "failed_ratio",
        "first_failed_step_index",
        "detection_delay_vs_target",
        "abs_localization_error",
    ]
    with output_file.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(
    output_file: Path,
    key_metrics: Dict[str, Any],
    frame_key_metrics: Dict[str, Any],
    per_attack_rows: List[Dict[str, Any]],
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# SM3ChainGuard Performance Metrics")
    lines.append("")
    lines.append("## Core Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(
        f"| Attack Detection Rate | {key_metrics['attack_detection_rate_pct']} |"
    )
    lines.append(f"| Accuracy | {key_metrics['accuracy_pct']} |")
    lines.append(f"| Precision | {key_metrics['precision_pct']} |")
    lines.append(f"| Recall | {key_metrics['recall_pct']} |")
    lines.append(f"| F1 Score | {key_metrics['f1_score_pct']} |")
    lines.append(f"| Specificity | {key_metrics['specificity_pct']} |")
    lines.append(
        f"| Balanced Accuracy | {key_metrics['balanced_accuracy_pct']} |"
    )
    lines.append(
        f"| Clean False Positive Rate | {key_metrics['clean_false_positive_rate_pct']} |"
    )
    lines.append("")
    lines.append("## Frame-Level Contextual Metrics")
    lines.append("")
    lines.append(
        "These frame-level metrics treat frames from tamper reports as positive-context "
        "samples, and frames from clean report as negative-context samples."
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(
        f"| Contextual Detection Rate | {frame_key_metrics['contextual_detection_rate_pct']} |"
    )
    lines.append(f"| Accuracy | {frame_key_metrics['accuracy_pct']} |")
    lines.append(f"| Precision | {frame_key_metrics['precision_pct']} |")
    lines.append(f"| Recall | {frame_key_metrics['recall_pct']} |")
    lines.append(f"| F1 Score | {frame_key_metrics['f1_score_pct']} |")
    lines.append(f"| Specificity | {frame_key_metrics['specificity_pct']} |")
    lines.append(
        f"| Balanced Accuracy | {frame_key_metrics['balanced_accuracy_pct']} |"
    )
    lines.append("")
    lines.append("## Per-Attack Detection")
    lines.append("")
    lines.append(
        "| Attack | Detected | Failed Records | Failed Ratio | First Failed Step |"
    )
    lines.append("|---|:---:|---:|---:|---:|")
    for row in per_attack_rows:
        detected_text = "Yes" if int(row["detected"]) == 1 else "No"
        first_failed = row["first_failed_step_index"]
        first_failed_text = "-" if first_failed is None else str(first_failed)
        lines.append(
            f"| {row['attack_type']} | {detected_text} | {row['failed_records']} | "
            f"{row['failed_ratio']:.6f} | {first_failed_text} |"
        )
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()

    clean_report = _load_json(args.clean_report)
    clean_summary = clean_report["summary"]
    clean_total = int(clean_summary["total_records"])
    clean_failed = int(clean_summary["failed_records"])
    clean_detected = int(clean_failed > 0)

    tamper_report_files = sorted(args.tamper_reports_dir.glob("*_report.json"))
    if not tamper_report_files:
        raise FileNotFoundError(
            f"No attack reports found in directory: {args.tamper_reports_dir}"
        )

    per_attack_rows: List[Dict[str, Any]] = []
    failed_ratio_values: List[float] = []
    detected_first_failed_steps: List[int] = []
    delay_values: List[int] = []
    abs_error_values: List[int] = []
    mismatch_counter: Counter[str] = Counter()
    total_failed_frames_across_attacks = 0

    for report_file in tamper_report_files:
        report = _load_json(report_file)
        summary = report["summary"]
        attack_type = _attack_type_from_report_name(report_file)

        total_records = int(summary["total_records"])
        passed_records = int(summary["passed_records"])
        failed_records = int(summary["failed_records"])
        detected = int(failed_records > 0)
        failed_ratio = _safe_div(failed_records, total_records)
        first_failed = summary["first_failed_step_index"]

        detection_delay = None
        abs_error = None
        if args.target_step_index is not None and first_failed is not None:
            detection_delay = int(first_failed) - int(args.target_step_index)
            abs_error = abs(detection_delay)
            delay_values.append(detection_delay)
            abs_error_values.append(abs_error)

        if first_failed is not None:
            detected_first_failed_steps.append(int(first_failed))
        failed_ratio_values.append(failed_ratio)
        total_failed_frames_across_attacks += failed_records

        for frame in report.get("frame_results", []):
            if bool(frame.get("passed", True)):
                continue
            for mismatch in frame.get("mismatched_modalities", []):
                mismatch_counter[str(mismatch)] += 1

        per_attack_rows.append(
            {
                "attack_type": attack_type,
                "detected": detected,
                "total_records": total_records,
                "passed_records": passed_records,
                "failed_records": failed_records,
                "failed_ratio": round(failed_ratio, 6),
                "first_failed_step_index": first_failed,
                "detection_delay_vs_target": detection_delay,
                "abs_localization_error": abs_error,
            }
        )

    total_attacks = len(per_attack_rows)
    detected_attacks = sum(int(row["detected"]) for row in per_attack_rows)
    missed_attacks = total_attacks - detected_attacks

    # Sample-level binary classification:
    # - Clean report is one negative sample.
    # - Each tamper report is one positive sample.
    tp = detected_attacks
    fn = missed_attacks
    fp = clean_detected
    tn = 1 - fp

    accuracy = _safe_div(tp + tn, total_attacks + 1)
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1_score = _safe_div(2 * precision * recall, precision + recall)
    specificity = _safe_div(tn, tn + fp)
    balanced_accuracy = (recall + specificity) / 2.0
    clean_false_positive_rate = _safe_div(clean_failed, clean_total)
    attack_detection_rate = _safe_div(detected_attacks, total_attacks)

    # Frame-level contextual classification:
    # - All clean-report frames are negative-context samples.
    # - All tamper-report frames are positive-context samples.
    # - Prediction uses verifier result: failed->positive, passed->negative.
    tamper_total_frames = sum(int(row["total_records"]) for row in per_attack_rows)
    tamper_failed_frames = sum(int(row["failed_records"]) for row in per_attack_rows)

    frame_tp = tamper_failed_frames
    frame_fn = tamper_total_frames - tamper_failed_frames
    frame_fp = clean_failed
    frame_tn = clean_total - clean_failed

    frame_accuracy = _safe_div(
        frame_tp + frame_tn,
        frame_tp + frame_tn + frame_fp + frame_fn,
    )
    frame_precision = _safe_div(frame_tp, frame_tp + frame_fp)
    frame_recall = _safe_div(frame_tp, frame_tp + frame_fn)
    frame_f1_score = _safe_div(
        2 * frame_precision * frame_recall,
        frame_precision + frame_recall,
    )
    frame_specificity = _safe_div(frame_tn, frame_tn + frame_fp)
    frame_balanced_accuracy = (frame_recall + frame_specificity) / 2.0
    contextual_detection_rate = _safe_div(tamper_failed_frames, tamper_total_frames)

    mismatch_frequency = {}
    if total_failed_frames_across_attacks > 0:
        for key, count in sorted(mismatch_counter.items()):
            mismatch_frequency[key] = {
                "count": count,
                "ratio_over_all_failed_frames": round(
                    _safe_div(count, total_failed_frames_across_attacks),
                    6,
                ),
            }

    localization_stats = {
        "target_step_index": args.target_step_index,
        "mean_first_failed_step_index": (
            round(statistics.mean(detected_first_failed_steps), 4)
            if detected_first_failed_steps
            else None
        ),
        "median_first_failed_step_index": (
            float(statistics.median(detected_first_failed_steps))
            if detected_first_failed_steps
            else None
        ),
        "mean_detection_delay_vs_target": (
            round(statistics.mean(delay_values), 4) if delay_values else None
        ),
        "mean_abs_localization_error": (
            round(statistics.mean(abs_error_values), 4) if abs_error_values else None
        ),
    }

    sample_level_metrics = {
        "attack_detection_rate": round(attack_detection_rate, 6),
        "accuracy": round(accuracy, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1_score": round(f1_score, 6),
        "specificity": round(specificity, 6),
        "balanced_accuracy": round(balanced_accuracy, 6),
        "clean_false_positive_rate": round(clean_false_positive_rate, 6),
    }

    four_dimension_results = _compute_four_dimension_results(
        per_attack_rows=per_attack_rows,
        sample_level_metrics=sample_level_metrics,
        localization_stats=localization_stats,
        stage1_artifact=args.stage1_artifact,
        chain_artifact=args.chain_artifact,
        clean_total_records=clean_total,
    )

    aggregated = {
        "inputs": {
            "clean_report": str(args.clean_report),
            "tamper_reports_dir": str(args.tamper_reports_dir),
            "num_tamper_reports": total_attacks,
        },
        "core_metrics": {
            "attack_detection_rate": sample_level_metrics["attack_detection_rate"],
            "accuracy": sample_level_metrics["accuracy"],
            "precision": sample_level_metrics["precision"],
            "recall": sample_level_metrics["recall"],
            "f1_score": sample_level_metrics["f1_score"],
            "specificity": sample_level_metrics["specificity"],
            "balanced_accuracy": sample_level_metrics["balanced_accuracy"],
            "clean_false_positive_rate": sample_level_metrics[
                "clean_false_positive_rate"
            ],
            "confusion_matrix_sample_level": {
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
            },
            "frame_level_contextual": {
                "contextual_detection_rate": round(contextual_detection_rate, 6),
                "accuracy": round(frame_accuracy, 6),
                "precision": round(frame_precision, 6),
                "recall": round(frame_recall, 6),
                "f1_score": round(frame_f1_score, 6),
                "specificity": round(frame_specificity, 6),
                "balanced_accuracy": round(frame_balanced_accuracy, 6),
                "confusion_matrix": {
                    "tp": frame_tp,
                    "fp": frame_fp,
                    "tn": frame_tn,
                    "fn": frame_fn,
                },
            },
        },
        "tamper_frame_effect_stats": {
            "mean_failed_ratio_per_attack": round(
                statistics.mean(failed_ratio_values),
                6,
            ),
            "median_failed_ratio_per_attack": round(
                float(statistics.median(failed_ratio_values)),
                6,
            ),
            "max_failed_ratio_per_attack": round(max(failed_ratio_values), 6),
            "min_failed_ratio_per_attack": round(min(failed_ratio_values), 6),
        },
        "localization_stats": localization_stats,
        "four_dimension_results": four_dimension_results,
        "mismatch_frequency": mismatch_frequency,
        "per_attack_rows": per_attack_rows,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(aggregated, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_per_attack_csv(per_attack_rows, args.output_csv)

    key_metrics_for_md = {
        "attack_detection_rate_pct": _format_pct(attack_detection_rate),
        "accuracy_pct": _format_pct(accuracy),
        "precision_pct": _format_pct(precision),
        "recall_pct": _format_pct(recall),
        "f1_score_pct": _format_pct(f1_score),
        "specificity_pct": _format_pct(specificity),
        "balanced_accuracy_pct": _format_pct(balanced_accuracy),
        "clean_false_positive_rate_pct": _format_pct(clean_false_positive_rate),
    }
    frame_key_metrics_for_md = {
        "contextual_detection_rate_pct": _format_pct(contextual_detection_rate),
        "accuracy_pct": _format_pct(frame_accuracy),
        "precision_pct": _format_pct(frame_precision),
        "recall_pct": _format_pct(frame_recall),
        "f1_score_pct": _format_pct(frame_f1_score),
        "specificity_pct": _format_pct(frame_specificity),
        "balanced_accuracy_pct": _format_pct(frame_balanced_accuracy),
    }
    _write_markdown(
        args.output_md,
        key_metrics_for_md,
        frame_key_metrics_for_md,
        per_attack_rows,
    )

    print("Metrics JSON:", args.output_json)
    print("Per-attack CSV:", args.output_csv)
    print("Markdown summary:", args.output_md)
    print("Attack Detection Rate:", _format_pct(attack_detection_rate))
    print("Accuracy:", _format_pct(accuracy))
    print("Precision:", _format_pct(precision))
    print("Recall:", _format_pct(recall))
    print("F1 Score:", _format_pct(f1_score))
    print("Frame Contextual Accuracy:", _format_pct(frame_accuracy))
    print("Frame Contextual F1:", _format_pct(frame_f1_score))


if __name__ == "__main__":
    main()
