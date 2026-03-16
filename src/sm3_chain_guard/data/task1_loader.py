"""Task1 raw data loaders for Robo-Care."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

import cv2

from sm3_chain_guard.models.frame_models import AnnotationSegment, SyncTimePoint


class Task1DataLoader:
    """Load timestamps, annotations and image streams from Task1."""

    def load_camera_timestamps(
        self,
        timestamp_file: Path,
    ) -> Dict[str, List[Tuple[int, SyncTimePoint, float]]]:
        """Load timestamp json into per-camera sorted timeline."""
        raw = json.loads(timestamp_file.read_text(encoding="utf-8"))
        result: Dict[str, List[Tuple[int, SyncTimePoint, float]]] = {}

        for key, items in raw.items():
            if not key.startswith("rgb_cam"):
                continue

            camera_id = f"Cam{key.replace('rgb_cam', '')}"
            timeline: List[Tuple[int, SyncTimePoint, float]] = []
            for item in items:
                frame_index = int(item["frame"])
                timepoint = SyncTimePoint(
                    secs=int(item["time"]["secs"]),
                    nsecs=int(item["time"]["nsecs"]),
                )
                timeline.append((frame_index, timepoint, timepoint.to_float_seconds()))

            timeline.sort(key=lambda x: x[2])
            result[camera_id] = timeline

        return result

    def load_annotation_segments(self, annotation_file: Path) -> List[AnnotationSegment]:
        """Load action labeling csv into annotation intervals."""
        encodings = ["utf-8-sig", "utf-16", "gb18030"]
        last_error: Exception | None = None

        for encoding in encodings:
            try:
                segments: List[AnnotationSegment] = []
                with annotation_file.open("r", encoding=encoding, newline="") as fp:
                    reader = csv.DictReader(fp)
                    for row in reader:
                        begin_sec = float(row["Begin Time - ss.msec"])
                        end_sec = float(row["End Time - ss.msec"])

                        task = (row.get("Task") or "").strip()
                        subtask = (row.get("Subtask") or "").strip()
                        component = (row.get("subtask_Component") or "").strip()

                        annotation_text = "|".join(
                            [
                                f"task={task}" if task else "",
                                f"subtask={subtask}" if subtask else "",
                                f"component={component}" if component else "",
                            ]
                        ).strip("|")
                        annotation_text = annotation_text if annotation_text else "UNKNOWN"

                        segments.append(
                            AnnotationSegment(
                                begin_sec=begin_sec,
                                end_sec=end_sec,
                                annotation_text=annotation_text,
                            )
                        )
                return segments
            except (UnicodeDecodeError, KeyError, ValueError) as exc:
                last_error = exc
                continue

        raise ValueError(
            f"Failed to parse annotation file with supported encodings: {annotation_file}"
        ) from last_error

    @staticmethod
    def build_image_path(dataset_root: Path, camera_id: str, frame_index: int) -> Path:
        """Build Task1 image path from camera id and frame index."""
        return (
            dataset_root
            / "RGB"
            / "OT10"
            / "Task1"
            / camera_id
            / "RGB"
            / f"{frame_index:05d}_anonymized.jpg"
        )

    @staticmethod
    def load_image_stream(
        image_path: Path,
        mode: str = "raw_file_bytes",
    ) -> bytes:
        """
        Convert image to binary stream for multimodal frame object.

        中文说明：
        - raw_file_bytes: 直接读取图像文件原始字节流，速度快、可追溯到文件级篡改。
        - decoded_rgb_bytes: 先解码再转 RGB bytes，可降低编码器差异影响。
        """
        if mode == "raw_file_bytes":
            return image_path.read_bytes()

        if mode == "decoded_rgb_bytes":
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"Failed to decode image: {image_path}")
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return rgb.tobytes()

        raise ValueError(f"Unsupported image stream mode: {mode}")
