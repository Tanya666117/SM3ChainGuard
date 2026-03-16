"""Tamper simulation utilities for chain attack benchmarking."""

from __future__ import annotations

import copy
import random
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np

from sm3_chain_guard.data.task1_loader import Task1DataLoader
from sm3_chain_guard.models.chain_models import HashChainArtifact


def _flip_hex_char(hex_text: str) -> str:
    """Flip one random hex character to a different value."""
    if not hex_text:
        return hex_text
    idx = random.randint(0, len(hex_text) - 1)
    current = hex_text[idx].lower()
    candidates = [c for c in "0123456789abcdef" if c != current]
    replacement = random.choice(candidates)
    return hex_text[:idx] + replacement + hex_text[idx + 1 :]


class TamperSimulator:
    """Apply configurable tamper attacks to chain artifacts."""

    def __init__(self, seed: int = 20260316) -> None:
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

    @staticmethod
    def available_attacks() -> List[str]:
        """Return supported attack types."""
        return [
            "image_hash_bitflip",
            "timestamp_hash_bitflip",
            "annotation_hash_bitflip",
            "aggregate_hash_bitflip",
            "final_hash_bitflip",
            "previous_hash_bitflip",
            "annotation_text_edit",
            "reference_timestamp_edit",
            "camera_frame_index_edit",
            "swap_adjacent_records",
            "delete_one_record",
            "duplicate_one_record",
        ]

    @staticmethod
    def available_rgb_attacks() -> List[str]:
        """Return supported dataset-side RGB tamper attack types."""
        return [
            "rgb_block_occlusion",
            "rgb_gaussian_noise",
            "rgb_jpeg_reencode_low_quality",
        ]

    def simulate(
        self,
        chain_file: Path,
        attack_type: str,
        output_file: Path,
        target_step_index: int = 10,
    ) -> Dict[str, Any]:
        """
        Simulate one attack and write tampered chain artifact.

        中文说明：
        - 该模拟器针对已生成的时序哈希链凭证进行篡改注入，
          用于验证 verify 流程的定位与检出能力。
        """
        if attack_type not in self.available_attacks():
            raise ValueError(f"Unsupported attack type: {attack_type}")

        artifact = HashChainArtifact.model_validate_json(
            chain_file.read_text(encoding="utf-8")
        )
        if not artifact.records:
            raise ValueError("Chain artifact has no records.")

        records = copy.deepcopy(artifact.records)
        idx = max(0, min(target_step_index, len(records) - 1))
        meta: Dict[str, Any] = {
            "attack_type": attack_type,
            "target_step_index": idx,
            "original_total_records": len(records),
        }

        if attack_type == "image_hash_bitflip":
            records[idx].unimodal_hashes.image_hash = _flip_hex_char(
                records[idx].unimodal_hashes.image_hash
            )
        elif attack_type == "timestamp_hash_bitflip":
            records[idx].unimodal_hashes.timestamp_hash = _flip_hex_char(
                records[idx].unimodal_hashes.timestamp_hash
            )
        elif attack_type == "annotation_hash_bitflip":
            records[idx].unimodal_hashes.annotation_hash = _flip_hex_char(
                records[idx].unimodal_hashes.annotation_hash
            )
        elif attack_type == "aggregate_hash_bitflip":
            records[idx].aggregate_hash = _flip_hex_char(records[idx].aggregate_hash)
        elif attack_type == "final_hash_bitflip":
            records[idx].final_hash = _flip_hex_char(records[idx].final_hash)
        elif attack_type == "previous_hash_bitflip":
            records[idx].previous_hash = _flip_hex_char(records[idx].previous_hash)
        elif attack_type == "annotation_text_edit":
            records[idx].annotation_text = f"{records[idx].annotation_text}|tampered=true"
        elif attack_type == "reference_timestamp_edit":
            records[idx].reference_timestamp = "0.000000000"
        elif attack_type == "camera_frame_index_edit":
            camera_keys = sorted(records[idx].camera_to_frame_index.keys())
            if not camera_keys:
                raise ValueError("No camera frame index found.")
            camera_id = camera_keys[0]
            records[idx].camera_to_frame_index[camera_id] += 1
            meta["edited_camera"] = camera_id
        elif attack_type == "swap_adjacent_records":
            if idx >= len(records) - 1:
                idx = len(records) - 2
                meta["target_step_index"] = idx
            records[idx], records[idx + 1] = records[idx + 1], records[idx]
            meta["swapped_with"] = idx + 1
        elif attack_type == "delete_one_record":
            removed = records.pop(idx)
            meta["removed_step_index"] = removed.step_index
        elif attack_type == "duplicate_one_record":
            duplicate = copy.deepcopy(records[idx])
            records.insert(min(idx + 1, len(records)), duplicate)
            meta["duplicated_step_index"] = duplicate.step_index

        artifact.records = records
        artifact.total_records = len(records)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")

        meta["tampered_total_records"] = len(records)
        meta["output_file"] = str(output_file)
        return meta

    def simulate_rgb_tamper(
        self,
        chain_file: Path,
        dataset_root: Path,
        attack_type: str,
        backup_dir: Path,
        target_step_index: int = 10,
        target_camera: str | None = None,
    ) -> Dict[str, Any]:
        """
        Apply in-place RGB tamper to one dataset image and keep backup for restoration.

        Notes:
        - This modifies one JPG in dataset_root in place.
        - Caller MUST invoke restore_rgb_tamper with returned metadata.
        """
        if attack_type not in self.available_rgb_attacks():
            raise ValueError(f"Unsupported RGB attack type: {attack_type}")

        artifact = HashChainArtifact.model_validate_json(
            chain_file.read_text(encoding="utf-8")
        )
        if not artifact.records:
            raise ValueError("Chain artifact has no records.")

        idx = max(0, min(target_step_index, len(artifact.records) - 1))
        record = artifact.records[idx]
        camera_keys = sorted(record.camera_to_frame_index.keys())
        if not camera_keys:
            raise ValueError("No camera index available in target record.")
        camera_id = target_camera or camera_keys[0]
        if camera_id not in record.camera_to_frame_index:
            raise ValueError(f"Camera {camera_id} is not present in target record.")

        frame_index = int(record.camera_to_frame_index[camera_id])
        image_path = Task1DataLoader.build_image_path(
            dataset_root=dataset_root,
            camera_id=camera_id,
            frame_index=frame_index,
        )
        if not image_path.exists():
            raise FileNotFoundError(f"Target image file not found: {image_path}")

        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = (
            backup_dir
            / f"{attack_type}_step{record.step_index}_{camera_id}_{frame_index:05d}.jpg.bak"
        )
        backup_file.write_bytes(image_path.read_bytes())

        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to decode image for RGB tamper: {image_path}")
        tampered = image.copy()

        if attack_type == "rgb_block_occlusion":
            h, w = tampered.shape[:2]
            side = max(8, min(h, w) // 6)
            x0 = max(0, (w - side) // 2)
            y0 = max(0, (h - side) // 2)
            tampered[y0 : y0 + side, x0 : x0 + side] = 0
        elif attack_type == "rgb_gaussian_noise":
            noise = np.random.normal(loc=0.0, scale=18.0, size=tampered.shape).astype(
                np.float32
            )
            noisy = tampered.astype(np.float32) + noise
            tampered = np.clip(noisy, 0, 255).astype(np.uint8)
        elif attack_type == "rgb_jpeg_reencode_low_quality":
            pass

        if attack_type == "rgb_jpeg_reencode_low_quality":
            ok = cv2.imwrite(str(image_path), tampered, [int(cv2.IMWRITE_JPEG_QUALITY), 35])
        else:
            ok = cv2.imwrite(str(image_path), tampered)
        if not ok:
            raise ValueError(f"Failed to write tampered image: {image_path}")

        return {
            "attack_type": attack_type,
            "attack_scope": "rgb_dataset",
            "target_step_index": int(record.step_index),
            "target_camera": camera_id,
            "target_frame_index": frame_index,
            "target_image_path": str(image_path),
            "backup_file": str(backup_file),
        }

    @staticmethod
    def restore_rgb_tamper(meta: Dict[str, Any]) -> None:
        """Restore original image bytes from backup metadata."""
        image_path = Path(str(meta["target_image_path"]))
        backup_file = Path(str(meta["backup_file"]))
        if backup_file.exists():
            image_path.write_bytes(backup_file.read_bytes())
            backup_file.unlink(missing_ok=True)
