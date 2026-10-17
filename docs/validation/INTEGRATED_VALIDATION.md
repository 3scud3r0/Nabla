# Integrated validation and assurance boundaries

The integrated gate runs existing source, API, roadmap, release-inventory,
integration and security checks in a single bounded campaign. A nonzero exit,
missing or invalid JUnit XML, **zero collected tests**, any skipped test, a
crash, timeout, or oversized log fails the campaign. All mandatory checks run
even if an earlier one fails, so the complete failure report remains available.

Run from a checkout with the declared test extras installed:

```bash
python tools/integrated_validation.py --profile ci --output .nabla/integrated-validation
python tools/integrated_validation.py --verify .nabla/integrated-validation
```

Use `--profile comprehensive` for an additional complete `pytest tests`
campaign; this is deliberately separate from the bounded required PR gate.
Each run needs a **new output directory**. JSON reports contain the exact HEAD
commit, commands, exit codes, test counts, wall times, and SHA-256 evidence
hashes for stdout, stderr, and JUnit XML. The verifier detects missing or
modified logs, unsafe evidence paths, and an incomplete or failed check list.

**Assurance limits:** these locally hashed artifacts are tamper-*evident*, not
cryptographically signed or independently authenticated. A person able to
rewrite the entire report and its hashes can forge its contents; use protected
CI statuses and trusted workflow permissions for provenance. Passing this gate
does not certify all 213 scientific requirements, Lean/Mathlib, GPU, external
reproducibility, independent review, or stable publisher acceptance. No local
check is authorized to promote `stable_release_accepted` to true. Configure
the `mandatory-evidence` job in branch protection before making it a required
merge prerequisite; this workflow cannot set branch protection itself.
