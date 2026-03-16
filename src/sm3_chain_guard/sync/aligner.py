"""High-precision timestamp synchronization for Task1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from sm3_chain_guard.models.frame_models import AnnotationSegment, SyncTimePoint
from sm3_chain_guard.utils.time_utils import nearest_index


@dataclass(frozen=True)
class AlignedStep:
    """Aligned step result before image stream packing."""

    step_index: int
    reference_camera: str
    reference_timestamp: SyncTimePoint
    camera_to_frame_index: Dict[str, int]
    camera_to_time_delta_sec: Dict[str, float]
    annotation_text: str


class Task1NearestNeighborAligner:
    """Nearest-neighbor timestamp aligner with tolerance filtering."""

    def __init__(self, reference_camera: str = "Cam1", tolerance_sec: float = 0.050) -> None:
        self.reference_camera = reference_camera
        self.tolerance_sec = tolerance_sec

    def align(
        self,
        camera_timestamps: Dict[str, List[Tuple[int, SyncTimePoint, float]]],
        annotation_segments: List[AnnotationSegment],
        max_steps: int | None = None,
        sample_stride: int = 1,
    ) -> List[AlignedStep]:
        """
        Align all cameras to reference timeline.

        中文说明：
        - 以 reference_camera 的时间轴作为主轴。
        - 每个时间点在其它相机中做最近邻搜索。
        - 超过 tolerance_sec 的匹配视为无效并丢弃，保证对齐精度。
        """
        if self.reference_camera not in camera_timestamps:
            raise ValueError(f"Reference camera not found: {self.reference_camera}")
        if sample_stride < 1:
            raise ValueError("sample_stride must be >= 1.")

        ref_timeline = camera_timestamps[self.reference_camera]
        if not ref_timeline:
            return []

        ref_start_sec = ref_timeline[0][2]
        other_cameras = sorted([key for key in camera_timestamps if key != self.reference_camera])
        other_times = {key: [item[2] for item in camera_timestamps[key]] for key in other_cameras}

        aligned_steps: List[AlignedStep] = []
        for idx, (ref_frame_index, ref_time, ref_sec) in enumerate(ref_timeline):
            if idx % sample_stride != 0:
                continue
            if max_steps is not None and len(aligned_steps) >= max_steps:
                break

            camera_to_frame_index: Dict[str, int] = {self.reference_camera: ref_frame_index}
            camera_to_delta: Dict[str, float] = {self.reference_camera: 0.0}
            valid = True

            for camera_id in other_cameras:
                matched_idx = nearest_index(other_times[camera_id], ref_sec)
                matched_frame, _matched_time, matched_sec = camera_timestamps[camera_id][matched_idx]
                delta_sec = matched_sec - ref_sec

                if abs(delta_sec) > self.tolerance_sec:
                    valid = False
                    break

                camera_to_frame_index[camera_id] = matched_frame
                camera_to_delta[camera_id] = delta_sec

            if not valid:
                continue

            annotation_text = self._match_annotation(ref_sec - ref_start_sec, annotation_segments)
            aligned_steps.append(
                AlignedStep(
                    step_index=len(aligned_steps),
                    reference_camera=self.reference_camera,
                    reference_timestamp=ref_time,
                    camera_to_frame_index=camera_to_frame_index,
                    camera_to_time_delta_sec=camera_to_delta,
                    annotation_text=annotation_text,
                )
            )

        return aligned_steps

    @staticmethod
    def _match_annotation(
        relative_sec: float,
        annotation_segments: List[AnnotationSegment],
    ) -> str:
        """Bind reference time to current annotation interval."""
        for seg in annotation_segments:
            if seg.begin_sec <= relative_sec < seg.end_sec:
                return seg.annotation_text
        return "UNKNOWN"
