"""One reproducible receipt campaign; report costs without promising a speedup."""
import argparse
import json
from pathlib import Path
import platform
import statistics
import time

from nablamath.calc import CalculationSession


def campaign(count, background):
    delivered = 0
    def sink(record):
        nonlocal delivered
        delivered += 1
    session = CalculationSession(background_receipts=background,
                                 max_pending=min(65536,count), receipt_sink=sink)
    elapsed = []
    started = time.perf_counter()
    for i in range(count):
        before = time.perf_counter()
        result = session.execute('binomial',n=100,k=i%50)
        if background:
            result.result
        elapsed.append(time.perf_counter()-before)
    foreground = time.perf_counter()-started
    session.close()
    total = time.perf_counter()-started
    if delivered != count or session._pending:
        raise AssertionError('Accepted receipts were lost or retained after closing')
    ordered = sorted(elapsed)
    return {'calls':count,'receipts_delivered':delivered,'foreground_seconds':foreground,
            'total_including_flush_seconds':total,
            'call_median_seconds':statistics.median(elapsed),
            'call_p95_seconds':ordered[min(count-1,int(count*.95))]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--calls',type=int,default=4000)
    args = parser.parse_args()
    if not 100 <= args.calls <= 65536:
        parser.error('Use 100–65536 calls')
    report = {'python':platform.python_version(),'platform':platform.platform(),
              'protocol':'One campaign, sync then background; same binomial inputs and counting sink; no sample selection.',
              'synchronous':campaign(args.calls,False),'background':campaign(args.calls,True),
              'limits':'Includes Python/GIL, input snapshots and sinks. No claim of general speedup, GPU throughput or load capacity.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(report,indent=2))
