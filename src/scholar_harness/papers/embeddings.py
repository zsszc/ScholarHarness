from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

_WORD_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


class EmbeddingProvider(Protocol):
    """Replaceable boundary for local or hosted embedding implementations."""

    @property
    def provider_id(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashingEmbeddingProvider:
    """Small deterministic offline baseline based on signed feature hashing."""

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions < 8:
            raise ValueError("Embedding dimensions must be at least 8")
        self._dimensions = dimensions

    @property
    def provider_id(self) -> str:
        return f"hashing-v1:{self.dimensions}"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        words = [match.group(0).lower() for match in _WORD_PATTERN.finditer(text)]
        features: list[tuple[str, float]] = [(f"w:{word}", 1.0) for word in words]
        for word in words:
            padded = f"^{word}$"
            for width in (3, 4, 5):
                features.extend(
                    (f"c{width}:{padded[index:index + width]}", 0.25)
                    for index in range(max(0, len(padded) - width + 1))
                )

        for feature, weight in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "little")
            index = value % self.dimensions
            sign = 1.0 if value & (1 << 63) else -1.0
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector
