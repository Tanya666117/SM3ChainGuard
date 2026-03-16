"""Run phase-3 verification for temporal defense chain."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _setup_import_path(project_root: Path) -> None:
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify stage-2 temporal defense chain against source dataset",
    )
    parser.add_argument(
        "--chain-file",
        type=Path,
        default=Path("data/artifacts/task1_temporal_defense_chain.json"),
        help="Chain artifact generated in stage-2",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("data/raw/robo-care"),
        help="Robo-Care root path",
    )
    parser.add_argument(
        "--timestamp-file",
        type=Path,
        default=Path("data/raw/robo-care/Timestamps/OT10/10-1-10_timestamps.json"),
        help="Timestamp json file path",
    )
    parser.add_argument(
        "--annotation-file",
        type=Path,
        default=Path("data/raw/robo-care/Action Labeling/OT10/10-1-10_2_rgb_ch.csv"),
        help="Annotation csv file path",
    )
    parser.add_argument(
        "--reference-camera",
        type=str,
        default="Cam1",
        help="Fallback reference camera when chain metadata is missing",
    )
    parser.add_argument(
        "--tolerance-sec",
        type=float,
        default=0.05,
        help="Fallback timestamp tolerance when chain metadata is missing",
    )
    parser.add_argument(
        "--sample-stride",
        type=int,
        default=1,
        help="Fallback sample stride when chain metadata is missing",
    )
    parser.add_argument(
        "--image-stream-mode",
        type=str,
        default="raw_file_bytes",
        choices=["raw_file_bytes", "decoded_rgb_bytes"],
        help="Fallback image stream mode when chain metadata is missing",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=Path("data/artifacts/task1_verification_report.json"),
        help="Verification report output path",
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

    from sm3_chain_guard.verification.verifier import Task1ChainVerifier

    verifier = Task1ChainVerifier()
    report = verifier.verify(
        chain_file=(project_root / args.chain_file).resolve(),
        dataset_root=(project_root / args.dataset_root).resolve(),
        timestamp_file=(project_root / args.timestamp_file).resolve(),
        annotation_file=(project_root / args.annotation_file).resolve(),
        reference_camera=args.reference_camera,
        tolerance_sec=args.tolerance_sec,
        sample_stride=args.sample_stride,
        image_stream_mode=args.image_stream_mode,
    )
    verifier.save_report(report=report, output_file=(project_root / args.output_report))

    logging.info("Verification summary: %s", report.summary.model_dump())
    if report.summary.failed_records > 0:
        logging.warning("Tampering or mismatch detected.")
    else:
        logging.info("No mismatches detected. Chain verification passed.")


if __name__ == "__main__":
    main()
