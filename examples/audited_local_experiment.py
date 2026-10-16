"""Reproducible exact-instance workflow; no network, learned claim or theorem."""
from pathlib import Path
import argparse
from nablamath.desktop.workflows import ExperimentWorkflow


def run(directory):
    workflow = ExperimentWorkflow(Path(directory))
    receipt = workflow.execute('x*x+1', {'x':'2'}, consent=True, reviewer='example-local-operator')
    if not workflow.replay(receipt):
        raise RuntimeError('Example evidence replay failed')
    return receipt


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    print(run(args.directory)['workflow_id'])
