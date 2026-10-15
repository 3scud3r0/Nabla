"""Measure finite calibration profiles and preserve unresolved readiness gates."""
import argparse
from pathlib import Path

from nablamath.benchmarks.readiness import calibrate
from nablamath.core.semantic_contracts import canonical_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--laboratory-directory', type=Path, required=True)
    parser.add_argument('--cases', type=int, default=10000)
    parser.add_argument('--integration-cases', type=int, default=512)
    parser.add_argument('--seed', type=int, default=951017)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.output.exists():
        parser.error('Destination exists; previous evidence will not be overwritten')
    result = calibrate(matrix_path=root/'docs/acceptance/evidence_matrix.json',
                       laboratory_directory=args.laboratory_directory, cases=args.cases,
                       integration_cases=args.integration_cases, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(canonical_payload(result)+'\n')
    print(canonical_payload({'finite_checks_passed': result['finite_checks_passed'],
                             'fully_calibrated_and_ready': result['fully_calibrated_and_ready'],
                             'roadmap_counts': result['roadmap']['counts']}))
    # Success means finite checks executed successfully, not that readiness is certified.
    return 0 if result['finite_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
