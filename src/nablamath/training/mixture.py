"""Deterministic no-replacement mixtures, exact weights and explicit source audit."""
import random

from ..core.semantic_ir import rational, fingerprint
from ..core.semantic_contracts import canonical_payload
from ..datasets.corpus_registry import CorpusManifest


def plan_mixture(corpora, weights, *, count, seed, split="train"):
    if (not isinstance(corpora, (list, tuple)) or not 1 <= len(corpora) <= 128
            or not isinstance(weights, dict) or type(count) is not int or not 1 <= count <= 10000
            or type(seed) is not int or not 0 <= seed < 2**63 or split not in ("train", "validation", "test")):
        raise ValueError("Bounded corpora, exact weights, count and seed required")
    sources, seen = {}, set()
    for corpus in corpora:
        if not isinstance(corpus, CorpusManifest) or corpus.content_id in sources:
            raise ValueError("Unique corpus manifests required")
        data = corpus.to_data()
        if data["split"] != split or seen.intersection(data["records"]):
            raise ValueError("Split mismatch or cross-source record duplication")
        seen.update(data["records"])
        sources[corpus.content_id] = data
    if set(weights) != set(sources):
        raise ValueError("Weights must cover exactly the declared sources")
    weights = {key: rational(value) for key, value in weights.items()}
    if any(value <= 0 for value in weights.values()):
        raise ValueError("Positive exact weights required")
    total = sum(weights.values())
    ideal = {key: count * value / total for key, value in weights.items()}
    quotas = {key: int(value) for key, value in ideal.items()}
    ordered = sorted(ideal, key=lambda key: (-(ideal[key]-quotas[key]), key))
    for key in ordered[:count-sum(quotas.values())]:
        quotas[key] += 1
    if any(quotas[key] > len(sources[key]["records"]) for key in sources):
        raise ValueError("Requested source quota exceeds capacity; no silent reweighting")
    selections = []
    for key in sorted(sources):
        rng = random.Random(int(fingerprint({"seed": seed, "source": key})[:16], 16))
        records = sorted(rng.sample(sources[key]["records"], quotas[key]))
        selections.extend({"record_id": record, "source_id": key} for record in records)
    report = {"schema_version": 1, "split": split, "seed": seed, "count": count,
              "allocations": [{"source_id": key, "weight": str(weights[key]), "count": quotas[key],
                               "license_id": sources[key]["license_id"]} for key in sorted(sources)],
              "selections": selections,
              "scope": "declared record digests only; semantic leakage and license compatibility require review"}
    result = {**report, "mixture_id": fingerprint(report)}
    canonical_payload(result)
    return result


def verify_mixture(report, corpora, weights, *, count, seed, split="train"):
    try:
        return canonical_payload(report) == canonical_payload(plan_mixture(corpora, weights, count=count, seed=seed, split=split))
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False
