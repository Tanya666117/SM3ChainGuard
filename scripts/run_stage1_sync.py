"""Run phase-1 synchronization and standardization for Robo-Care Task1."""

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
        description="Stage-1 synchronization for Robo-Care Task1",
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
        help="Reference camera id (e.g., Cam1)",
    )
    parser.add_argument(
        "--tolerance-sec",
        type=float,
        default=0.05,
        help="Nearest-neighbor max tolerance in seconds",
    )
    parser.add_argument(
        "--image-stream-mode",
        type=str,
        choices=["raw_file_bytes", "decoded_rgb_bytes"],
        default="raw_file_bytes",
        help="Image to binary stream mode",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=300,
        help="Max synchronized steps to generate",
    )
    parser.add_argument(
        "--sample-stride",
        type=int,
        default=1,
        help="Use every Nth reference frame",
    )
    parser.add_argument(
        "--full-artifact-output",
        type=Path,
        default=Path("data/interim/task1_standardized_frames_b64.json"),
        help="Output JSON with base64 image streams",
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=Path("data/interim/task1_standardized_frames_metadata.jsonl"),
        help="Output lightweight JSONL metadata",
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

    from sm3_chain_guard.pipeline.task1_stage1_sync import Task1Stage1SyncPipeline

    pipeline = Task1Stage1SyncPipeline(
        dataset_root=(project_root / args.dataset_root).resolve(),
        timestamp_file=(project_root / args.timestamp_file).resolve(),
        annotation_file=(project_root / args.annotation_file).resolve(),
        reference_camera=args.reference_camera,
        tolerance_sec=args.tolerance_sec,
        image_stream_mode=args.image_stream_mode,
    )
    frames = pipeline.build_frames(
        max_steps=args.max_steps,
        sample_stride=args.sample_stride,
    )
    logging.info("Standardized frames built: %s", len(frames))

    artifact = pipeline.to_artifact(frames)
    pipeline.save_artifact(artifact, output_file=(project_root / args.full_artifact_output))
    pipeline.save_jsonl_metadata_only(
        frames=frames,
        output_file=(project_root / args.metadata_output),
    )
    logging.info("Stage-1 outputs are generated successfully.")


if __name__ == "__main__":
    main()
