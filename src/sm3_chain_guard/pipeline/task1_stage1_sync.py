"""Stage-1 pipeline: synchronization and standardization."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import List, Literal

from sm3_chain_guard.data.task1_loader import Task1DataLoader
from sm3_chain_guard.models.frame_models import (
    StandardizedFrame,
    StandardizedFrameArtifact,
    StandardizedFrameSerializable,
)
from sm3_chain_guard.sync.aligner import Task1NearestNeighborAligner

LOGGER = logging.getLogger(__name__)

ImageStreamMode = Literal["raw_file_bytes", "decoded_rgb_bytes"]


class Task1Stage1SyncPipeline:
    """Build standardized multimodal frame objects for Task1."""

    def __init__(
        self,
        dataset_root: Path,
        timestamp_file: Path,
        annotation_file: Path,
        reference_camera: str = "Cam1",
        tolerance_sec: float = 0.050,
        image_stream_mode: ImageStreamMode = "raw_file_bytes",
    ) -> None:
        self.dataset_root = dataset_root
        self.timestamp_file = timestamp_file
        self.annotation_file = annotation_file
        self.reference_camera = reference_camera
        self.tolerance_sec = tolerance_sec
        self.image_stream_mode = image_stream_mode

        self.loader = Task1DataLoader()
        self.aligner = Task1NearestNeighborAligner(
            reference_camera=reference_camera,
            tolerance_sec=tolerance_sec,
        )

    def build_frames(
        self,
        max_steps: int | None = None,
        sample_stride: int = 1,
    ) -> List[StandardizedFrame]:
        """Run phase-1 synchronization pipeline and return in-memory frames."""
        camera_timestamps = self.loader.load_camera_timestamps(self.timestamp_file)
        annotations = self.loader.load_annotation_segments(self.annotation_file)

        aligned_steps = self.aligner.align(
            camera_timestamps=camera_timestamps,
            annotation_segments=annotations,
            max_steps=max_steps,
            sample_stride=sample_stride,
        )
        LOGGER.info("Aligned steps: %s", len(aligned_steps))

        frames: List[StandardizedFrame] = []
        for step in aligned_steps:
            camera_to_image_path = {}
            camera_to_image_stream = {}
            valid = True

            for camera_id, frame_index in step.camera_to_frame_index.items():
                image_path = self.loader.build_image_path(
                    dataset_root=self.dataset_root,
                    camera_id=camera_id,
                    frame_index=frame_index,
                )
                if not image_path.exists():
                    LOGGER.warning("Skip step due to missing image: %s", image_path)
                    valid = False
                    break

                camera_to_image_path[camera_id] = str(image_path)
                camera_to_image_stream[camera_id] = self.loader.load_image_stream(
                    image_path=image_path,
                    mode=self.image_stream_mode,
                )

            if not valid:
                continue

            frames.append(
                StandardizedFrame(
                    step_index=step.step_index,
                    reference_camera=step.reference_camera,
                    reference_timestamp=step.reference_timestamp,
                    camera_to_frame_index=step.camera_to_frame_index,
                    camera_to_time_delta_sec=step.camera_to_time_delta_sec,
                    annotation_text=step.annotation_text,
                    camera_to_image_path=camera_to_image_path,
                    camera_to_image_stream=camera_to_image_stream,
                    image_stream_mode=self.image_stream_mode,
                )
            )
        return frames

    def to_artifact(self, frames: List[StandardizedFrame]) -> StandardizedFrameArtifact:
        """Convert in-memory frames to serializable artifact model."""
        serializable_frames: List[StandardizedFrameSerializable] = []
        for frame in frames:
            serializable_frames.append(
                StandardizedFrameSerializable(
                    step_index=frame.step_index,
                    reference_camera=frame.reference_camera,
                    reference_timestamp=frame.reference_timestamp.to_normalized_string(),
                    camera_to_frame_index=frame.camera_to_frame_index,
                    camera_to_time_delta_sec=frame.camera_to_time_delta_sec,
                    annotation_text=frame.annotation_text,
                    camera_to_image_path=frame.camera_to_image_path,
                    camera_to_image_stream_base64={
                        camera_id: base64.b64encode(image_bytes).decode("ascii")
                        for camera_id, image_bytes in frame.camera_to_image_stream.items()
                    },
                    image_stream_mode=frame.image_stream_mode,
                )
            )

        return StandardizedFrameArtifact(
            dataset_root=str(self.dataset_root),
            timestamp_file=str(self.timestamp_file),
            annotation_file=str(self.annotation_file),
            reference_camera=self.reference_camera,
            tolerance_sec=self.tolerance_sec,
            image_stream_mode=self.image_stream_mode,
            total_frames=len(serializable_frames),
            frames=serializable_frames,
        )

    @staticmethod
    def save_artifact(artifact: StandardizedFrameArtifact, output_file: Path) -> None:
        """Persist artifact to JSON."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            artifact.model_dump_json(indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def save_jsonl_metadata_only(frames: List[StandardizedFrame], output_file: Path) -> None:
        """
        Save lightweight JSONL with metadata only (no image streams).

        中文说明：
        当全量 base64 图像流文件过大时，可先输出该轻量文件用于检查对齐质量。
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as fp:
            for frame in frames:
                line = {
                    "step_index": frame.step_index,
                    "reference_camera": frame.reference_camera,
                    "reference_timestamp": frame.reference_timestamp.to_normalized_string(),
                    "camera_to_frame_index": frame.camera_to_frame_index,
                    "camera_to_time_delta_sec": frame.camera_to_time_delta_sec,
                    "annotation_text": frame.annotation_text,
                    "camera_to_image_path": frame.camera_to_image_path,
                    "image_stream_mode": frame.image_stream_mode,
                }
                fp.write(json.dumps(line, ensure_ascii=False) + "\n")
