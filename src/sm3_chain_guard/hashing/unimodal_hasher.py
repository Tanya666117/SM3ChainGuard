"""Unimodal hash generators for image/timestamp/annotation."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Literal

import cv2

from sm3_chain_guard.models.chain_models import TimePoint

from .sm3_engine import SM3Engine

ImageHashMode = Literal["raw_bytes", "decoded_rgb"]


class UniModalHasher:
    """Generate three unimodal hashes with fixed canonical order."""

    def __init__(self, sm3_engine: SM3Engine) -> None:
        self._sm3 = sm3_engine

    def hash_image_multiview(
        self,
        camera_to_image_path: Dict[str, Path],
        mode: ImageHashMode = "raw_bytes",
    ) -> str:
        """
        Hash multiview images into one image hash.

        中文说明：
        - 按固定相机顺序（字典序）处理，保证跨机器、跨运行结果一致。
        - 每个相机片段都加入 camera_id 和长度前缀，避免拼接歧义攻击。
        - raw_bytes 模式直接对 JPG 文件原始字节参与哈希，速度快且实现直接。
        - decoded_rgb 模式先解码成 RGB 再 tobytes，可减少“同像素不同编码”影响。
        """
        payload = bytearray()

        for camera_id in sorted(camera_to_image_path.keys()):
            image_path = camera_to_image_path[camera_id]
            image_bytes = self._load_image_bytes(image_path=image_path, mode=mode)

            camera_id_bytes = camera_id.encode("utf-8")
            payload.extend(len(camera_id_bytes).to_bytes(2, byteorder="big"))
            payload.extend(camera_id_bytes)
            payload.extend(len(image_bytes).to_bytes(8, byteorder="big"))
            payload.extend(image_bytes)

        return self._sm3.hash_bytes(bytes(payload))

    def hash_image_multiview_streams(self, camera_to_image_stream: Dict[str, bytes]) -> str:
        """
        Hash multiview image binary streams directly.

        中文说明：
        - 该方法用于消费阶段一标准化输出（每个相机已转为二进制流）。
        - 同样采用固定相机顺序 + 长度前缀，保持可重现和抗拼接歧义。
        """
        payload = bytearray()
        for camera_id in sorted(camera_to_image_stream.keys()):
            image_bytes = camera_to_image_stream[camera_id]
            camera_id_bytes = camera_id.encode("utf-8")
            payload.extend(len(camera_id_bytes).to_bytes(2, byteorder="big"))
            payload.extend(camera_id_bytes)
            payload.extend(len(image_bytes).to_bytes(8, byteorder="big"))
            payload.extend(image_bytes)
        return self._sm3.hash_bytes(bytes(payload))

    def hash_timestamp(self, timestamp: TimePoint) -> str:
        """Hash normalized timestamp string."""
        return self._sm3.hash_text(timestamp.to_normalized_string())

    def hash_annotation(self, annotation_text: str) -> str:
        """Hash cleaned annotation text."""
        normalized = annotation_text.strip()
        return self._sm3.hash_text(normalized)

    def hash_timestamp_text(self, normalized_timestamp: str) -> str:
        """Hash already-normalized timestamp string."""
        return self._sm3.hash_text(normalized_timestamp.strip())

    @staticmethod
    def _load_image_bytes(image_path: Path, mode: ImageHashMode) -> bytes:
        if mode == "raw_bytes":
            return image_path.read_bytes()

        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to decode image: {image_path}")

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return rgb.tobytes()
