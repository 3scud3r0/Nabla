# Nabla Frontier Foundry v3 — compositional inverse synthesis

## What this delivers

A reproducible mathematical **research prototype**, not a copy of OpenAI's undisclosed training pipeline. Ten base construction grammars, ten substantive task combinations per family, and 100 different solution schemas / operator compositions. SymPy algebraically or combinatorially checks planted answers using alternative algorithms. SHA-256 content IDs come from the official Nabla receipt contract by default. The portable fallback **must** be explicit and is labeled throughout.

| Family | Inverse construction | Independent checker |
| --- | --- | --- |
| Polynomial ideals | Triangular ideal then polynomial unimodular mixing | Buchberger and two-way ideal reductions over finite fields |
| Exact potential | Construct potential, reveal compatible gradient | Reconstruct using radial path integration; zero curl |
| Lie representations | Construct sl2 and conjugate by integer shears | All commutators and quadratic Casimir by exact matrix multiplication |
| Stochastic dynamics | Start from gamma-type invariant density | Zero probability flux, normalization, generator moment identity |
| Geometry | Conformally rescale oblique flat metric | Christoffel, Ricci and scalar curvature contraction |
| Finite fields | Define irreducible extension and affine element | Minimal polynomial vs multiplication-matrix trace/norm |
| Graph networks | Generate connected weighted circuit | Matrix-tree cofactor vs independent weighted tree enumeration; Thomson energy |
| Error correcting codes | Construct code and plant one error | Complete small-codeword enumeration and unique syndrome decoding |
| Lyapunov | Plant stable similarity-conjugate dynamics | Exact Lyapunov residual, Sylvester minors, eigenvalue stability |
| Generating functions | Plant directed walk matrix | Resolvent rational expression vs powers of adjacency |

## Install and run

From the Nabla project root:

```bash
python -m pip install -e '.[test,research]'
python -m unittest discover -s tests -p 'test_frontier_foundry.py' -v
python tools/frontier_foundry.py --count 100 --output .nabla/frontier-v3/dataset_frontier_foundry_100.txt
python tools/frontier_foundry.py --verify --output .nabla/frontier-v3/dataset_frontier_foundry_100.txt
```

Offline reference mode if `nablamath` is not importable:

```bash
python tools/frontier_foundry.py --portable --count 100 --output ./dataset_frontier_foundry_100.txt
python tools/frontier_foundry.py --portable --verify --output ./dataset_frontier_foundry_100.txt
```

Each run creates five files: human-readable `*.txt`; machine-readable `*.jsonl`; answer-free, **family-disjoint** evaluation prompts `*.eval_prompts.jsonl`; an evaluation answer key `*.eval_answer_key.jsonl`; `*.txt.manifest.json`. The public full TXT also contains all reference answers; do not treat it as a secret benchmark. There are 80 train records in 8 families and 20 evaluation records in two families never included in train. This is a family-disjoint split, not a guarantee of absence from any external model's pretraining.

## Exact model response scoring / learning from mistakes

Provide JSONL responses with `{"problem_id":"FOUNDRY-0001","answer":{...}}`. Exactly named schema keys are necessary, while finite rational strings are accepted up to equivalence: `2/4` equals `1/2`. This code **does not execute model-supplied Python** or call SymPy on arbitrary model responses. Returns exact pass/fail per sample, accuracy per family and a failure-rate-prioritized curriculum proposal. It does **not** train a model, run an LLM benchmark, or automatically expand new mathematical theories.

```bash
python tools/frontier_foundry.py --score model_predictions.jsonl --output dataset_frontier_foundry_100.txt
```

The grader is strict about expected schema, so mathematically valid free-form proofs need separate proof assistants or parsers before they can receive credit. Full answer JSON must match; this is a strict-verification first version, not a free-form proof grader.

## Guarantees and limitations

- **Exact for supported contracts**: rational arithmetic, finite field calculations, symbolic identities and bounded combinatorial enumerations. All examples are constructed synthetically, not scraped from contest websites or books.
- **Not machine-checkable universal proofs**: `INDEPENDENT_EXACT_CHECKS_NOT_FORMAL_PROOF` is intentional. No Lean 4 proofs are generated; the Nabla `AIVerifier`/Z3 and Lean bridges are possible future independent backends but are not falsely invoked here. Finite samples and symbolic CAS are not a guarantee of truth about unconstrained physics.
- **Not authenticated authorship**: receipts and SHA-256 detect accidental tampering and support replay, not publication identity; signing needs a trusted key and explicit signing flow.
- **Not objectively frontier-hard**: 100 different combinations of subproblems within 10 substantive mathematical domains; solving difficulty is a **structural proxy** until assessed with independent solvers or language models using the provided scoring API. No evidence this matches internal o1/o3 training sets or their difficulty distribution.
- **No private chain of thought**: `derivation` is an authored, checkable public explanation, not a recording of how any AI model reasoned.
- **Robustness**: bounded count (100), exact replay, comparison of every generated deliverable byte by byte, refuse duplicate model answers, disjoint family split, test all 100 wrong-answer mutations.

## Path to deeper difficulty

Current PR establishes a *verifiable foundation*. Next research milestones (not falsely described as completed) include mechanized Lean proofs, user-provided model eval calibration, structural grammar evolution guided by observed errors, cross-CAS certification, security-hardened execution sandboxes, and comparisons with held-out human expert evaluations. Scaling count does not imply scaling difficulty.