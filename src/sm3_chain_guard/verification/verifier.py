"""Phase-3 verifier for temporal tamper-evident chain."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from sm3_chain_guard.hashing.aggregator import MultiModalAggregator
from sm3_chain_guard.hashing.sm3_engine import SM3Engine
from sm3_chain_guard.hashing.temporal_chain import TemporalChainLinker
from sm3_chain_guard.hashing.unimodal_hasher import UniModalHasher
from sm3_chain_guard.models.chain_models import HashChainArtifact
from sm3_chain_guard.models.verification_models import (
    FrameVerificationResult,
    VerificationReport,
    VerificationSummary,
)
from sm3_chain_guard.pipeline.task1_stage1_sync import Task1Stage1SyncPipeline

LOGGER = logging.getLogger(__name__)


class Task1ChainVerifier:
    """Verify phase-2 chain artifact against original dataset."""

    def __init__(self) -> None:
        sm3_engine = SM3Engine()
        self.unimodal_hasher = UniModalHasher(sm3_engine=sm3_engine)
        self.aggregator = MultiModalAggregator(sm3_engine=sm3_engine)
        self.temporal_linker = TemporalChainLinker(sm3_engine=sm3_engine)

    def verify(
        self,
        chain_file: Path,
        dataset_root: Path,
        timestamp_file: Path,
        annotation_file: Path,
        reference_camera: str = "Cam1",
        tolerance_sec: float = 0.050,
        sample_stride: int = 1,
        image_stream_mode: str = "raw_file_bytes",
    ) -> VerificationReport:
        """
        Verify chain by full recomputation.

        中文说明：
        1) 先按阶段一逻辑重建标准化多模态帧；
        2) 再按阶段二三层哈希流程逐帧重算；
        3) 与凭证链逐字段比对，定位时间帧与具体模态差异。
        """
        chain_artifact = HashChainArtifact.model_validate_json(
            chain_file.read_text(encoding="utf-8")
        )
        LOGGER.info("Loaded chain records: %s", chain_artifact.total_records)

        effective_ref_camera = chain_artifact.reference_camera or reference_camera
        effective_tolerance = (
            chain_artifact.tolerance_sec
            if chain_artifact.tolerance_sec is not None
            else tolerance_sec
        )
        effective_stride = chain_artifact.sample_stride or sample_stride
        effective_stream_mode = chain_artifact.image_hash_mode or image_stream_mode

        stage1 = Task1Stage1SyncPipeline(
            dataset_root=dataset_root,
            timestamp_file=timestamp_file,
            annotation_file=annotation_file,
            reference_camera=effective_ref_camera,
            tolerance_sec=effective_tolerance,
            image_stream_mode=effective_stream_mode,
        )
        frames = stage1.build_frames(
            max_steps=chain_artifact.total_records,
            sample_stride=effective_stride,
        )
        LOGGER.info("Rebuilt standardized frames: %s", len(frames))

        frame_results = self._compare_frames_and_chain(
            frames=frames,
            chain_artifact=chain_artifact,
        )

        failed_indices = [item.step_index for item in frame_results if not item.passed]
        summary = VerificationSummary(
            total_records=len(frame_results),
            passed_records=len(frame_results) - len(failed_indices),
            failed_records=len(failed_indices),
            first_failed_step_index=(failed_indices[0] if failed_indices else None),
            tampered_step_indices=failed_indices,
        )

        return VerificationReport(
            chain_file=str(chain_file),
            dataset_root=str(dataset_root),
            timestamp_file=str(timestamp_file),
            annotation_file=str(annotation_file),
            reference_camera=effective_ref_camera,
            tolerance_sec=effective_tolerance,
            image_stream_mode=effective_stream_mode,
            summary=summary,
            frame_results=frame_results,
        )

    def save_report(self, report: VerificationReport, output_file: Path) -> None:
        """Persist verification report as JSON."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        LOGGER.info("Verification report saved: %s", output_file)

    def _compare_frames_and_chain(
        self,
        frames,
        chain_artifact: HashChainArtifact,
    ) -> List[FrameVerificationResult]:
        """Compare recomputed values and return per-frame mismatch details."""
        results: List[FrameVerificationResult] = []
        record_count = min(len(frames), len(chain_artifact.records))

        if len(frames) != len(chain_artifact.records):
            LOGGER.warning(
                "Frame/record length mismatch: rebuilt=%s, chain=%s",
                len(frames),
                len(chain_artifact.records),
            )

        previous_hash = chain_artifact.genesis_hash
        for idx in range(record_count):
            frame = frames[idx]
            record = chain_artifact.records[idx]
            mismatches: List[str] = []

            # 单模态重算
            image_hash = self.unimodal_hasher.hash_image_multiview_streams(
                frame.camera_to_image_stream
            )
            timestamp_hash = self.unimodal_hasher.hash_timestamp_text(
                frame.reference_timestamp.to_normalized_string()
            )
            annotation_hash = self.unimodal_hasher.hash_annotation(frame.annotation_text)

            if image_hash != record.unimodal_hashes.image_hash:
                mismatches.append("image")
            if timestamp_hash != record.unimodal_hashes.timestamp_hash:
                mismatches.append("timestamp")
            if annotation_hash != record.unimodal_hashes.annotation_hash:
                mismatches.append("annotation")

            # 聚合层重算
            aggregate_hash = self.aggregator.aggregate(
                image_hash=image_hash,
                timestamp_hash=timestamp_hash,
                annotation_hash=annotation_hash,
            )
            if aggregate_hash != record.aggregate_hash:
                mismatches.append("aggregate")

            # 链式层重算
            expected_final_hash = self.temporal_linker.link(
                aggregate_hash=aggregate_hash,
                previous_hash=previous_hash,
            )
            if previous_hash != record.previous_hash:
                mismatches.append("previous_link")
            if expected_final_hash != record.final_hash:
                mismatches.append("temporal_chain")

            # 元数据一致性校验（辅助定位）
            if frame.camera_to_frame_index != record.camera_to_frame_index:
                mismatches.append("frame_index_map")
            if frame.annotation_text != record.annotation_text:
                if "annotation" not in mismatches:
                    mismatches.append("annotation")
            if (
                frame.reference_timestamp.to_normalized_string()
                != record.reference_timestamp
            ):
                if "timestamp" not in mismatches:
                    mismatches.append("timestamp")

            results.append(
                FrameVerificationResult(
                    step_index=record.step_index,
                    passed=(len(mismatches) == 0),
                    mismatched_modalities=sorted(set(mismatches)),
                    expected_final_hash=record.final_hash,
                    actual_final_hash=expected_final_hash,
                )
            )
            previous_hash = expected_final_hash

        # 如果数量不一致，补充不可比对记录
        if len(chain_artifact.records) > record_count:
            for idx in range(record_count, len(chain_artifact.records)):
                record = chain_artifact.records[idx]
                results.append(
                    FrameVerificationResult(
                        step_index=record.step_index,
                        passed=False,
                        mismatched_modalities=["missing_recomputed_frame"],
                        expected_final_hash=record.final_hash,
                        actual_final_hash="",
                    )
                )
        elif len(frames) > record_count:
            for idx in range(record_count, len(frames)):
                results.append(
                    FrameVerificationResult(
                        step_index=frames[idx].step_index,
                        passed=False,
                        mismatched_modalities=["extra_recomputed_frame"],
                        expected_final_hash="",
                        actual_final_hash="",
                    )
                )

        return results


def summarize_report(report_file: Path) -> str:
    """Return compact human-readable summary from saved report."""
    report = json.loads(report_file.read_text(encoding="utf-8"))
    summary = report["summary"]
    return (
        f"total={summary['total_records']}, "
        f"passed={summary['passed_records']}, "
        f"failed={summary['failed_records']}, "
        f"first_failed={summary['first_failed_step_index']}"
    )
