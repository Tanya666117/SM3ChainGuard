"""Multimodal aggregate hash builder."""

from __future__ import annotations

from .sm3_engine import SM3Engine


class MultiModalAggregator:
    """Aggregate unimodal hashes in a fixed order."""

    def __init__(self, sm3_engine: SM3Engine) -> None:
        self._sm3 = sm3_engine

    def aggregate(
        self,
        image_hash: str,
        timestamp_hash: str,
        annotation_hash: str,
    ) -> str:
        """
        Build H_agg,t = SM3(image_hash || timestamp_hash || annotation_hash).

        中文说明：
        固定顺序是核心约束；任何顺序变化都会导致聚合哈希不同，
        从而破坏链一致性。
        """
        payload = "|".join([image_hash, timestamp_hash, annotation_hash])
        return self._sm3.hash_text(payload)
