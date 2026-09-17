import math

import pytest

from scholar_harness.papers.embeddings import HashingEmbeddingProvider


def test_hashing_embeddings_are_deterministic_and_normalized() -> None:
    provider = HashingEmbeddingProvider(dimensions=64)

    first, second, empty = provider.embed(["Agent memory", "Agent memory", ""])

    assert first == second
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)
    assert empty == [0.0] * 64
    assert provider.provider_id == "hashing-v1:64"


def test_hashing_embeddings_reject_tiny_dimensions() -> None:
    with pytest.raises(ValueError, match="at least 8"):
        HashingEmbeddingProvider(dimensions=4)
