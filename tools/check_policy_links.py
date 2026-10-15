"""Validate local document references; link health does not approve policy content."""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
POLICIES = (
    "docs/governance/independent_review_policy.md", "docs/governance/scientific_claims_policy.md",
    "docs/strategy/scientific_risk_register.md", "docs/strategy/annual_reassessment.md",
    "docs/future/F13_OPEN_RESEARCH.md", "docs/future/2035_2045_2056_criteria.md",
    "benchmarks/private/README.md", "benchmarks/contamination/README.md",
    "benchmarks/protocols/README.md", "benchmarks/external/README.md",
)


def check_links(paths, *, root=ROOT):
    root = Path(root).resolve()
    checked = 0
    for path in paths:
        path = Path(path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Policy file must exist within repository")
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            raise ValueError("Empty policy document")
        for reference in re.findall(r"\[[^\]]+\]\(([^)]+)\)", raw):
            target = urlsplit(reference.strip("<>"))
            if target.scheme or target.netloc or not target.path:
                continue
            resolved = (path.parent / unquote(target.path)).resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                raise ValueError(f"Broken or escaping policy reference: {path.name}: {reference}")
            checked += 1
    return checked


if __name__ == "__main__":
    print(f"Validated {check_links([ROOT / path for path in POLICIES])} local policy links; no policy approval implied")
