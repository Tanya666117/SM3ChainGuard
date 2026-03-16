"""Temporal hash chain linker."""

from __future__ import annotations

from .sm3_engine import SM3Engine


class TemporalChainLinker:
    """Generate final temporal hash with previous-step dependency."""

    def __init__(self, sm3_engine: SM3Engine, genesis_hash: str | None = None) -> None:
        self._sm3 = sm3_engine
        self.genesis_hash = genesis_hash if genesis_hash is not None else ("0" * 64)

    def link(self, aggregate_hash: str, previous_hash: str) -> str:
        """
        Compute H_t = SM3(H_agg,t || H_{t-1}).

        中文说明：
        通过引入前一帧哈希作为输入，任意时间点数据变更都会
        级联影响后续所有 H_t，实现强篡改可检测性。
        """
        return self._sm3.hash_text(f"{aggregate_hash}|{previous_hash}")
