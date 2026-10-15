from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from nablamath.pipeline.cache import LocalCache


def test_concurrent_conflicting_results_never_overwrite_winner(tmp_path):
    cache = LocalCache(tmp_path)
    barrier = Barrier(12)

    def put(index):
        barrier.wait(timeout=10)
        try:
            return (index, cache.put("v1", {"x": 1}, [], {"result": index}))
        except ValueError:
            return (index, None)

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(put, range(12)))
    winners = [(index, key) for index, key in results if key is not None]
    assert len(winners) == 1
    index, key = winners[0]
    assert cache.get(key) == {"result": index}
    assert cache.put("v1", {"x": 1}, [], {"result": index}) == key
    assert list(cache.index.iterdir()) == [cache.index / key]


def test_invalid_keys_and_corrupt_blobs_are_rejected(tmp_path):
    cache = LocalCache(tmp_path)
    assert cache.get("0" * 64) is None
    for key in ["../outside", "", "G" * 64, None]:
        with pytest.raises(ValueError):
            cache.get(key)
    key = cache.put("v1", {}, [], {"answer": 42})
    digest = (cache.index / key).read_text()
    (cache.blobs.root / digest[:2] / digest).write_bytes(b"forged")
    with pytest.raises(ValueError, match="corrompido"):
        cache.get(key)
