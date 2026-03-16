"""Data models for phase-1 synchronization and standardization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class SyncTimePoint:
    """High-precision timestamp point."""

    secs: int
    nsecs: int

    def to_float_seconds(self) -> float:
        """Convert to float seconds."""
        return self.secs + (self.nsecs / 1_000_000_000.0)

    def to_normalized_string(self) -> str:
        """Canonical representation for deterministic pipelines."""
        return f"{self.secs}.{self.nsecs:09d}"


@dataclass(frozen=True)
class AnnotationSegment:
    """Task annotation interval in relative seconds."""

    begin_sec: float
    end_sec: float
    annotation_text: str


@dataclass(frozen=True)
class StandardizedFrame:
    """In-memory synchronized multimodal frame object."""

    step_index: int
    reference_camera: str
    reference_timestamp: SyncTimePoint
    camera_to_frame_index: Dict[str, int]
    camera_to_time_delta_sec: Dict[str, float]
    annotation_text: str
    camera_to_image_path: Dict[str, str]
    camera_to_image_stream: Dict[str, bytes]
    image_stream_mode: Literal["raw_file_bytes", "decoded_rgb_bytes"]


class StandardizedFrameSerializable(BaseModel):
    """JSON serializable frame representation."""

    step_index: int
    reference_camera: str
    reference_timestamp: str
    camera_to_frame_index: Dict[str, int]
    camera_to_time_delta_sec: Dict[str, float]
    annotation_text: str
    camera_to_image_path: Dict[str, str]
    camera_to_image_stream_base64: Dict[str, str]
    image_stream_mode: Literal["raw_file_bytes", "decoded_rgb_bytes"]


class StandardizedFrameArtifact(BaseModel):
    """Persisted output of phase-1 synchronization."""

    dataset_root: str
    timestamp_file: str
    annotation_file: str
    reference_camera: str
    tolerance_sec: float
    image_stream_mode: Literal["raw_file_bytes", "decoded_rgb_bytes"]
    created_at_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_frames: int
    frames: List[StandardizedFrameSerializable]
