"""Run the integrated laboratory: python examples/scientific_phases_5_8.py OUTPUT."""
from pathlib import Path
import argparse
from nablamath.scientific_workflows import run_laboratory

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--parquet', action='store_true')
    args = parser.parse_args()
    print(run_laboratory(args.destination, parquet=args.parquet))
