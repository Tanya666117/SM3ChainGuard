"""Core data models for phase-2 hash chain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class TimePoint:
    """ROS style timestamp with second and nanosecond precision."""

    secs: int
    nsecs: int

    def to_float_seconds(self) -> float:
        """Convert to float seconds for nearest-neighbor matching."""
        return self.secs + (self.nsecs / 1_000_000_000.0)

    def to_normalized_string(self) -> str:
        """Return canonical string to ensure stable hash input."""
        return f"{self.secs}.{self.nsecs:09d}"


@dataclass(frozen=True)
class AlignedFrameData:
    """One synchronized multimodal frame at time step t."""

    step_index: int
    reference_timestamp: TimePoint
    camera_to_frame_index: Dict[str, int]
    camera_to_image_path: Dict[str, Path]
    annotation_text: str


class UniModalHashes(BaseModel):
    """Three unimodal hashes generated at one time step."""

    image_hash: str = Field(..., min_length=64, max_length=64)
    timestamp_hash: str = Field(..., min_length=64, max_length=64)
    annotation_hash: str = Field(..., min_length=64, max_length=64)


class ChainRecord(BaseModel):
    """Full record for one hash chain step."""

    step_index: int
    reference_timestamp: str
    camera_to_frame_index: Dict[str, int]
    camera_to_image_path: Dict[str, str]
    annotation_text: str
    unimodal_hashes: UniModalHashes
    aggregate_hash: str = Field(..., min_length=64, max_length=64)
    previous_hash: str = Field(..., min_length=64, max_length=64)
    final_hash: str = Field(..., min_length=64, max_length=64)


class HashChainArtifact(BaseModel):
    """Persisted phase-2 hash chain credential file."""

    dataset_root: str
    timestamp_file: str
    annotation_file: str
    hash_algorithm: str = "SM3"
    image_hash_mode: str
    reference_camera: str | None = None
    tolerance_sec: float | None = None
    sample_stride: int | None = None
    genesis_hash: str = "0" * 64
    created_at_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_records: int
    records: List[ChainRecord]
