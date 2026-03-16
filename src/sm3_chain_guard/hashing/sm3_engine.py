"""SM3 hash engine wrapper."""

from __future__ import annotations

from gmssl import func, sm3


class SM3Engine:
    """Provide stable SM3 hashing for bytes and text."""

    def hash_bytes(self, payload: bytes) -> str:
        """Compute SM3 hash hex string for bytes."""
        return sm3.sm3_hash(func.bytes_to_list(payload))

    def hash_text(self, text: str, encoding: str = "utf-8") -> str:
        """Compute SM3 hash hex string for text."""
        return self.hash_bytes(text.encode(encoding))
