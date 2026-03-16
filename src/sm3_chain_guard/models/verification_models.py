"""Data models for phase-3 tamper verification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field


class FrameVerificationResult(BaseModel):
    """Verification outcome for one frame."""

    step_index: int
    passed: bool
    mismatched_modalities: List[str]
    expected_final_hash: str
    actual_final_hash: str


class VerificationSummary(BaseModel):
    """Compact summary for verification report."""

    total_records: int
    passed_records: int
    failed_records: int
    first_failed_step_index: int | None
    tampered_step_indices: List[int]


class VerificationReport(BaseModel):
    """Full verification report artifact."""

    chain_file: str
    dataset_root: str
    timestamp_file: str
    annotation_file: str
    reference_camera: str
    tolerance_sec: float
    image_stream_mode: str
    created_at_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    summary: VerificationSummary
    frame_results: List[FrameVerificationResult]
