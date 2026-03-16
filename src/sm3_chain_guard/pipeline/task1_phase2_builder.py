"""Phase-2 builder for Robo-Care Task1."""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from sm3_chain_guard.hashing.aggregator import MultiModalAggregator
from sm3_chain_guard.hashing.sm3_engine import SM3Engine
from sm3_chain_guard.hashing.temporal_chain import TemporalChainLinker
from sm3_chain_guard.hashing.unimodal_hasher import ImageHashMode, UniModalHasher
from sm3_chain_guard.models.chain_models import (
    AlignedFrameData,
    ChainRecord,
    HashChainArtifact,
    TimePoint,
    UniModalHashes,
)
from sm3_chain_guard.utils.time_utils import nearest_index

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnnotationSegment:
    """Annotation interval in relative seconds."""

    begin_sec: float
    end_sec: float
    text: str


class Task1Phase2Builder:
    """Build phase-2 temporal hash chain from Robo-Care Task1 data."""

    def __init__(
        self,
        dataset_root: Path,
        timestamp_file: Path,
        annotation_file: Path,
        image_hash_mode: ImageHashMode = "raw_bytes",
        tolerance_sec: float = 0.050,
        ref_camera: str = "Cam1",
    ) -> None:
        self.dataset_root = dataset_root
        self.timestamp_file = timestamp_file
        self.annotation_file = annotation_file
        self.image_hash_mode = image_hash_mode
        self.tolerance_sec = tolerance_sec
        self.ref_camera = ref_camera

        sm3_engine = SM3Engine()
        self.unimodal_hasher = UniModalHasher(sm3_engine=sm3_engine)
        self.aggregator = MultiModalAggregator(sm3_engine=sm3_engine)
        self.temporal_linker = TemporalChainLinker(sm3_engine=sm3_engine)

    def build(self, max_steps: int | None = None, sample_stride: int = 1) -> HashChainArtifact:
        """Build complete phase-2 chain records."""
        camera_timestamps = self._load_camera_timestamps(self.timestamp_file)
        segments = self._load_annotations(self.annotation_file)

        aligned = self._align_frames(
            camera_timestamps=camera_timestamps,
            annotation_segments=segments,
            max_steps=max_steps,
            sample_stride=sample_stride,
        )
        LOGGER.info("Aligned frame count: %s", len(aligned))

        records: List[ChainRecord] = []
        previous_hash = self.temporal_linker.genesis_hash

        for frame in aligned:
            image_hash = self.unimodal_hasher.hash_image_multiview(
                camera_to_image_path=frame.camera_to_image_path,
                mode=self.image_hash_mode,
            )
            timestamp_hash = self.unimodal_hasher.hash_timestamp(frame.reference_timestamp)
            annotation_hash = self.unimodal_hasher.hash_annotation(frame.annotation_text)

            aggregate_hash = self.aggregator.aggregate(
                image_hash=image_hash,
                timestamp_hash=timestamp_hash,
                annotation_hash=annotation_hash,
            )
            final_hash = self.temporal_linker.link(
                aggregate_hash=aggregate_hash,
                previous_hash=previous_hash,
            )

            record = ChainRecord(
                step_index=frame.step_index,
                reference_timestamp=frame.reference_timestamp.to_normalized_string(),
                camera_to_frame_index=frame.camera_to_frame_index,
                camera_to_image_path={
                    key: str(value) for key, value in frame.camera_to_image_path.items()
                },
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
            records.append(record)
            previous_hash = final_hash

        return HashChainArtifact(
            dataset_root=str(self.dataset_root),
            timestamp_file=str(self.timestamp_file),
            annotation_file=str(self.annotation_file),
            image_hash_mode=self.image_hash_mode,
            total_records=len(records),
            records=records,
        )

    def save_artifact(self, artifact: HashChainArtifact, output_file: Path) -> None:
        """Write artifact json."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            artifact.model_dump_json(indent=2),
            encoding="utf-8",
        )
        LOGGER.info("Artifact written: %s", output_file)

    def _load_camera_timestamps(
        self,
        timestamp_file: Path,
    ) -> Dict[str, List[Tuple[int, TimePoint, float]]]:
        """Load and normalize timestamp json."""
        raw = json.loads(timestamp_file.read_text(encoding="utf-8"))

        data: Dict[str, List[Tuple[int, TimePoint, float]]] = {}
        for key, items in raw.items():
            if not key.startswith("rgb_cam"):
                continue

            camera_id = f"Cam{key.replace('rgb_cam', '')}"
            entries: List[Tuple[int, TimePoint, float]] = []
            for item in items:
                frame_idx = int(item["frame"])
                time_raw = item["time"]
                timepoint = TimePoint(
                    secs=int(time_raw["secs"]),
                    nsecs=int(time_raw["nsecs"]),
                )
                entries.append((frame_idx, timepoint, timepoint.to_float_seconds()))

            entries.sort(key=lambda x: x[2])
            data[camera_id] = entries

        if self.ref_camera not in data:
            raise ValueError(f"Reference camera not found in timestamps: {self.ref_camera}")
        return data

    def _load_annotations(self, annotation_file: Path) -> List[AnnotationSegment]:
        """Load annotation csv and build interval list."""
        segments: List[AnnotationSegment] = []
        with annotation_file.open("r", encoding="utf-8-sig", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                begin_sec = float(row["Begin Time - ss.msec"])
                end_sec = float(row["End Time - ss.msec"])

                task = (row.get("Task") or "").strip()
                subtask = (row.get("Subtask") or "").strip()
                component = (row.get("subtask_Component") or "").strip()
                text = "|".join(
                    [
                        f"task={task}" if task else "",
                        f"subtask={subtask}" if subtask else "",
                        f"component={component}" if component else "",
                    ]
                ).strip("|")
                text = text if text else "UNKNOWN"

                segments.append(
                    AnnotationSegment(
                        begin_sec=begin_sec,
                        end_sec=end_sec,
                        text=text,
                    )
                )
        return segments

    def _align_frames(
        self,
        camera_timestamps: Dict[str, List[Tuple[int, TimePoint, float]]],
        annotation_segments: List[AnnotationSegment],
        max_steps: int | None,
        sample_stride: int,
    ) -> List[AlignedFrameData]:
        """
        Align multiview frames by nearest-neighbor timestamp.

        中文说明：
        - 以参考相机时间轴作为主轴。
        - 其它相机在各自时间轴中寻找最近邻时间戳。
        - 当时间差超过容忍阈值时，丢弃该时间步，避免伪对齐。
        """
        ref_entries = camera_timestamps[self.ref_camera]
        ref_start = ref_entries[0][2]

        other_cameras = sorted([name for name in camera_timestamps if name != self.ref_camera])
        camera_only_times = {
            name: [item[2] for item in camera_timestamps[name]] for name in other_cameras
        }

        aligned: List[AlignedFrameData] = []
        for idx, (ref_frame, ref_time, ref_sec) in enumerate(ref_entries):
            if idx % sample_stride != 0:
                continue
            if max_steps is not None and len(aligned) >= max_steps:
                break

            camera_to_frame_index: Dict[str, int] = {self.ref_camera: ref_frame}
            is_valid = True

            for camera_id in other_cameras:
                nearest = nearest_index(
                    sorted_values=camera_only_times[camera_id],
                    target=ref_sec,
                )
                matched_frame, _matched_time, matched_sec = camera_timestamps[camera_id][nearest]

                if abs(matched_sec - ref_sec) > self.tolerance_sec:
                    is_valid = False
                    break

                camera_to_frame_index[camera_id] = matched_frame

            if not is_valid:
                continue

            annotation_text = self._match_annotation(
                relative_sec=(ref_sec - ref_start),
                segments=annotation_segments,
            )

            camera_to_image_path: Dict[str, Path] = {}
            for camera_id, frame_index in camera_to_frame_index.items():
                image_path = self._build_image_path(camera_id, frame_index)
                if not image_path.exists():
                    LOGGER.warning("Image not found, skip step: %s", image_path)
                    is_valid = False
                    break
                camera_to_image_path[camera_id] = image_path

            if not is_valid:
                continue

            aligned.append(
                AlignedFrameData(
                    step_index=len(aligned),
                    reference_timestamp=ref_time,
                    camera_to_frame_index=camera_to_frame_index,
                    camera_to_image_path=camera_to_image_path,
                    annotation_text=annotation_text,
                )
            )
        return aligned

    @staticmethod
    def _match_annotation(relative_sec: float, segments: List[AnnotationSegment]) -> str:
        """Find annotation by relative time."""
        for seg in segments:
            if seg.begin_sec <= relative_sec < seg.end_sec:
                return seg.text
        return "UNKNOWN"

    def _build_image_path(self, camera_id: str, frame_index: int) -> Path:
        """Build image path from camera id and frame index."""
        return (
            self.dataset_root
            / "RGB"
            / "OT10"
            / "Task1"
            / camera_id
            / "RGB"
            / f"{frame_index:05d}_anonymized.jpg"
        )
