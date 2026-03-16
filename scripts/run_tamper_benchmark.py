"""Run tamper simulation benchmark and verification."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List


def _setup_import_path(project_root: Path) -> None:
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run tamper attack benchmark for verify workflow",
    )
    parser.add_argument(
        "--chain-file",
        type=Path,
        default=Path("data/artifacts/task1_temporal_defense_chain.json"),
        help="Clean chain artifact file",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("data/raw/robo-care"),
        help="Dataset root for verification recomputation",
    )
    parser.add_argument(
        "--timestamp-file",
        type=Path,
        default=Path("data/raw/robo-care/Timestamps/OT10/10-1-10_timestamps.json"),
        help="Timestamp json file",
    )
    parser.add_argument(
        "--annotation-file",
        type=Path,
        default=Path("data/raw/robo-care/Action Labeling/OT10/10-1-10_2_rgb_ch.csv"),
        help="Annotation csv file",
    )
    parser.add_argument(
        "--target-step-index",
        type=int,
        default=50,
        help="Target step index used for single-point tampering",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/experiments/tamper_benchmark"),
        help="Benchmark output directory",
    )
    parser.add_argument(
        "--rgb-only",
        action="store_true",
        help="Run only dataset RGB tamper attacks",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    args = parse_args()
    project_root = Path(__file__).resolve().parent.parent
    _setup_import_path(project_root)

    from sm3_chain_guard.simulation.tamper_simulator import TamperSimulator
    from sm3_chain_guard.verification.verifier import Task1ChainVerifier

    output_dir = (project_root / args.output_dir).resolve()
    tampered_dir = output_dir / "tampered_chains"
    reports_dir = output_dir / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    tampered_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    simulator = TamperSimulator()
    verifier = Task1ChainVerifier()

    attack_rows: List[Dict[str, object]] = []
    if not args.rgb_only:
        for attack_type in simulator.available_attacks():
            logging.info("Running attack: %s", attack_type)
            tampered_chain_file = tampered_dir / f"{attack_type}.json"
            meta = simulator.simulate(
                chain_file=(project_root / args.chain_file).resolve(),
                attack_type=attack_type,
                output_file=tampered_chain_file,
                target_step_index=args.target_step_index,
            )

            report = verifier.verify(
                chain_file=tampered_chain_file,
                dataset_root=(project_root / args.dataset_root).resolve(),
                timestamp_file=(project_root / args.timestamp_file).resolve(),
                annotation_file=(project_root / args.annotation_file).resolve(),
            )
            report_file = reports_dir / f"{attack_type}_report.json"
            verifier.save_report(report=report, output_file=report_file)

            detected = report.summary.failed_records > 0
            attack_rows.append(
                {
                    "attack_type": attack_type,
                    "attack_scope": "chain_artifact",
                    "target_step_index": meta.get("target_step_index"),
                    "detected": int(detected),
                    "failed_records": report.summary.failed_records,
                    "first_failed_step_index": report.summary.first_failed_step_index
                    if report.summary.first_failed_step_index is not None
                    else -1,
                    "report_file": str(report_file),
                    "tampered_chain_file": str(tampered_chain_file),
                }
            )

    rgb_backup_dir = output_dir / "rgb_backups"
    for attack_type in simulator.available_rgb_attacks():
        logging.info("Running RGB attack: %s", attack_type)
        meta = simulator.simulate_rgb_tamper(
            chain_file=(project_root / args.chain_file).resolve(),
            dataset_root=(project_root / args.dataset_root).resolve(),
            attack_type=attack_type,
            backup_dir=rgb_backup_dir,
            target_step_index=args.target_step_index,
        )
        try:
            report = verifier.verify(
                chain_file=(project_root / args.chain_file).resolve(),
                dataset_root=(project_root / args.dataset_root).resolve(),
                timestamp_file=(project_root / args.timestamp_file).resolve(),
                annotation_file=(project_root / args.annotation_file).resolve(),
            )
        finally:
            simulator.restore_rgb_tamper(meta)

        report_file = reports_dir / f"{attack_type}_report.json"
        verifier.save_report(report=report, output_file=report_file)

        detected = report.summary.failed_records > 0
        attack_rows.append(
            {
                "attack_type": attack_type,
                "attack_scope": "rgb_dataset",
                "target_step_index": meta.get("target_step_index"),
                "detected": int(detected),
                "failed_records": report.summary.failed_records,
                "first_failed_step_index": report.summary.first_failed_step_index
                if report.summary.first_failed_step_index is not None
                else -1,
                "report_file": str(report_file),
                "tampered_chain_file": "",
            }
        )

    summary_json = output_dir / "benchmark_summary.json"
    summary_csv = output_dir / "benchmark_summary.csv"

    summary_json.write_text(
        json.dumps(
            {
                "total_attacks": len(attack_rows),
                "detected_attacks": sum(int(row["detected"]) for row in attack_rows),
                "rows": attack_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    with summary_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "attack_type",
                "attack_scope",
                "target_step_index",
                "detected",
                "failed_records",
                "first_failed_step_index",
                "report_file",
                "tampered_chain_file",
            ],
        )
        writer.writeheader()
        writer.writerows(attack_rows)

    logging.info("Benchmark summary JSON: %s", summary_json)
    logging.info("Benchmark summary CSV: %s", summary_csv)


if __name__ == "__main__":
    main()
