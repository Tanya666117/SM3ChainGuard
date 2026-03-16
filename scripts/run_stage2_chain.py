"""Run stage-2 three-layer temporal SM3 chain building."""

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
        description="Stage-2 temporal SM3 chain builder for Robo-Care Task1",
    )
    parser.add_argument(
        "--stage1-artifact",
        type=Path,
        default=Path("data/interim/task1_standardized_frames_b64.json"),
        help="Input stage-1 standardized artifact file",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("data/artifacts/task1_temporal_defense_chain.json"),
        help="Output temporal defense chain file",
    )
    parser.add_argument(
        "--genesis-hash",
        type=str,
        default=None,
        help="Optional custom genesis hash (64 hex chars)",
    )
    parser.add_argument(
        "--sample-stride",
        type=int,
        default=1,
        help="Sampling stride metadata for chain provenance",
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

    from sm3_chain_guard.pipeline.task1_stage2_chain import Task1Stage2ChainPipeline

    stage2 = Task1Stage2ChainPipeline(genesis_hash=args.genesis_hash)
    artifact = stage2.build_chain(
        stage1_artifact_file=(project_root / args.stage1_artifact),
        sample_stride=args.sample_stride,
    )
    stage2.save_artifact(artifact=artifact, output_file=(project_root / args.output_file))

    if artifact.records:
        logging.info("Last chain hash (tip): %s", artifact.records[-1].final_hash)
    logging.info("Stage-2 temporal defense chain build completed.")


if __name__ == "__main__":
    main()
