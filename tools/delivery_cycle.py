"""Run/replay the finite local delivery profile; never certify full roadmap closure."""
import argparse
import json
from pathlib import Path

from nablamath.pipeline.delivery_cycle import run_delivery_cycle,verify_delivery_cycle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--seed',type=int,default=981023)
    parser.add_argument('--check',metavar='PINNED_RUN_SHA256')
    args=parser.parse_args()
    if args.check is not None:
        valid=verify_delivery_cycle(args.destination,expected_run_id=args.check)
        print(json.dumps({'valid':valid,'scope':'local semantic replay, not authenticated publication'}))
        return 0 if valid else 1
    print(json.dumps(run_delivery_cycle(args.destination,seed=args.seed),sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
