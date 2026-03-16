"""Stage-2 pipeline: three-layer temporal SM3 hash chain."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Dict

from sm3_chain_guard.hashing.aggregator import MultiModalAggregator
from sm3_chain_guard.hashing.sm3_engine import SM3Engine
from sm3_chain_guard.hashing.temporal_chain import TemporalChainLinker
from sm3_chain_guard.hashing.unimodal_hasher import UniModalHasher
from sm3_chain_guard.models.chain_models import ChainRecord, HashChainArtifact, UniModalHashes
from sm3_chain_guard.models.frame_models import StandardizedFrameArtifact

LOGGER = logging.getLogger(__name__)


class Task1Stage2ChainPipeline:
    """Build phase-2 hash chain from stage-1 standardized frame artifact."""

    def __init__(self, genesis_hash: str | None = None) -> None:
        sm3_engine = SM3Engine()
        self.unimodal_hasher = UniModalHasher(sm3_engine=sm3_engine)
        self.aggregator = MultiModalAggregator(sm3_engine=sm3_engine)
        self.temporal_linker = TemporalChainLinker(sm3_engine=sm3_engine, genesis_hash=genesis_hash)

    def build_chain(
        self,
        stage1_artifact_file: Path,
        sample_stride: int = 1,
    ) -> HashChainArtifact:
        """Build complete three-layer chain records from standardized frames."""
        stage1_artifact = StandardizedFrameArtifact.model_validate_json(
            stage1_artifact_file.read_text(encoding="utf-8")
        )
        LOGGER.info("Loaded stage-1 frames: %s", stage1_artifact.total_frames)

        records = []
        previous_hash = self.temporal_linker.genesis_hash

        for frame in stage1_artifact.frames:
            camera_to_stream = self._decode_streams(frame.camera_to_image_stream_base64)

            # 第一层：单模态 SM3
            image_hash = self.unimodal_hasher.hash_image_multiview_streams(camera_to_stream)
            timestamp_hash = self.unimodal_hasher.hash_timestamp_text(frame.reference_timestamp)
            annotation_hash = self.unimodal_hasher.hash_annotation(frame.annotation_text)

            # 第二层：多模态聚合 SM3
            aggregate_hash = self.aggregator.aggregate(
                image_hash=image_hash,
                timestamp_hash=timestamp_hash,
                annotation_hash=annotation_hash,
            )

            # 第三层：时序链式 SM3
            final_hash = self.temporal_linker.link(
                aggregate_hash=aggregate_hash,
                previous_hash=previous_hash,
            )

            records.append(
                ChainRecord(
                    step_index=frame.step_index,
                    reference_timestamp=frame.reference_timestamp,
                    camera_to_frame_index=frame.camera_to_frame_index,
                    camera_to_image_path=frame.camera_to_image_path,
                    annotation_text=frame.annotation_text,
                    unimodal_hashes=UniModalHashes(
                        image_hash=image_hash,
                        timestamp_hash=timestamp_hash,
                        annotation_hash=annotation_hash,
                    ),
                    aggregate_hash=aggregate_hash,
                    previous_hash=previous_hash,
                    final_hash=final_hash,
                )
            )
            previous_hash = final_hash

        artifact = HashChainArtifact(
            dataset_root=stage1_artifact.dataset_root,
            timestamp_file=stage1_artifact.timestamp_file,
            annotation_file=stage1_artifact.annotation_file,
            image_hash_mode=stage1_artifact.image_stream_mode,
            reference_camera=stage1_artifact.reference_camera,
            tolerance_sec=stage1_artifact.tolerance_sec,
            sample_stride=sample_stride,
            total_records=len(records),
            records=records,
        )
        LOGGER.info("Stage-2 chain records generated: %s", artifact.total_records)
        return artifact

    @staticmethod
    def save_artifact(artifact: HashChainArtifact, output_file: Path) -> None:
        """Persist temporal chain artifact."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
        LOGGER.info("Stage-2 chain artifact saved: %s", output_file)

    @staticmethod
    def _decode_streams(camera_to_image_stream_base64: Dict[str, str]) -> Dict[str, bytes]:
        """Decode base64 image streams for hashing."""
        return {
            camera_id: base64.b64decode(payload.encode("ascii"))
            for camera_id, payload in camera_to_image_stream_base64.items()
        }
