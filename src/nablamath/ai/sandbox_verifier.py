"""Algorithmic judge for structured rational claims, not an OS code sandbox."""
from ..formal.statement import FormalStatement
from dataclasses import dataclass
from enum import Enum
import json
import math
import multiprocessing
import time

from ..core.semantic_ir import canonical_json
from .verifier_process import verify_worker
from ..calc.receipt import receipt


class VerificationStatus(str,Enum):
    PROVEN = 'PROVEN'
    COUNTEREXAMPLE_FOUND = 'COUNTEREXAMPLE_FOUND'
    TIMEOUT_REJECTED = 'TIMEOUT_REJECTED'
    UNSUPPORTED = 'UNSUPPORTED'
    UNAVAILABLE = 'UNAVAILABLE'
    REJECTED = 'REJECTED'


@dataclass(frozen=True)
class VerificationResult:
    status: VerificationStatus
    details: dict
    elapsed_seconds: float

    @property
    def counterexample(self):
        return self.details.get('witness') if self.status == VerificationStatus.COUNTEREXAMPLE_FOUND else None

    def to_data(self):
        return {'status':self.status.value,'verification':self.details,
                'elapsed_seconds':self.elapsed_seconds,'formal_proof':False}


class AIVerifier:
    """At most five seconds for translation and solving in a killable process.

    PROVEN describes an SMT result in the declared fragment. It never upgrades
    a conjecture to a Lean certificate or a claim about arbitrary mathematics.
    Unsupported syntax, unavailable solvers and inconsistent assumptions have
    distinct refusal states and cannot be mislabelled as timeout or proof.
    """
    def __init__(self, *, timeout_seconds=5, logic='QF_NRA'):
        if type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 5:
            raise ValueError('The hard wall-clock budget must be in (0,5] seconds')
        if logic not in {'QF_LRA','QF_NRA'}:
            raise ValueError('Unsupported SMT logic')
        self.timeout_seconds,self.logic = timeout_seconds,logic

    def verify(self, conjecture):
        started = time.monotonic()
        if isinstance(conjecture,FormalStatement):
            conjecture = conjecture.to_data()
        try:
            # Reject oversized objects before serialization or process creation.
            # This also prevents arbitrary objects from running conversion hooks.
            stack = [(conjecture,0)]
            count = 0
            while stack:
                value,depth = stack.pop(); count += 1
                if depth > 32 or count > 4096:
                    raise ValueError('Conjecture structure exceeds its input budget')
                if type(value) is str:
                    if len(value) > 65536:
                        raise ValueError('Conjecture exceeds 64 KiB')
                elif type(value) in (int,bool) or value is None:
                    if type(value) is int and value.bit_length() > 4096:
                        raise ValueError('Conjecture integer exceeds its input budget')
                elif type(value) is float and math.isfinite(value):
                    pass
                elif type(value) is list and len(value) <= 4096:
                    stack.extend((item,depth+1) for item in value)
                elif type(value) is dict and len(value) <= 4096 and all(type(k) is str and len(k) <= 4096 for k in value):
                    stack.extend((item,depth+1) for item in value.values())
                else:
                    raise ValueError('Conjecture must contain bounded JSON data')
            raw = canonical_json(conjecture)
        except (TypeError,ValueError,RecursionError) as error:
            return VerificationResult(VerificationStatus.REJECTED,{'status':'error','reason':str(error)},time.monotonic()-started)
        if len(raw.encode()) > 65536:
            return VerificationResult(VerificationStatus.REJECTED,{'status':'error','reason':'Conjecture exceeds 64 KiB'},time.monotonic()-started)
        context = multiprocessing.get_context('spawn')
        reader,writer = context.Pipe(duplex=False)
        process = context.Process(target=verify_worker,args=(writer,json.loads(raw),max(1,int(self.timeout_seconds*1000)),self.logic))
        details = None
        try:
            process.start(); writer.close()
            # Reserve time to terminate and reap a solver that exhausts its budget.
            reserve = min(.1,self.timeout_seconds/4)
            remaining = max(0,self.timeout_seconds-reserve-(time.monotonic()-started))
            if reader.poll(remaining):
                try:
                    details = json.loads(reader.recv_bytes(1048576))
                except (EOFError,OSError,ValueError):
                    details = {'status':'error','reason':'SMT worker exited or exceeded its response budget'}
            if details is None or time.monotonic()-started > self.timeout_seconds:
                details = {'status':'timeout','reason':'Hard wall-clock limit exceeded; worker terminated'}
        except (OSError,RuntimeError) as error:
            details = {'status':'error','reason':'SMT process could not execute: '+str(error)[:1000]}
        finally:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=.05)
                if process.is_alive():
                    process.kill(); process.join(timeout=.05)
            reader.close(); writer.close()
        state = details.get('status')
        status = (VerificationStatus.PROVEN if state == 'unsat' else
                  VerificationStatus.COUNTEREXAMPLE_FOUND if state == 'counterexample' and details.get('exact_replay') else
                  VerificationStatus.TIMEOUT_REJECTED if state == 'timeout' or (state == 'unknown' and 'timeout' in details.get('reason','').lower()) else
                  VerificationStatus.UNSUPPORTED if state == 'unsupported' else
                  VerificationStatus.UNAVAILABLE if state == 'unavailable' else VerificationStatus.REJECTED)
        return VerificationResult(status,details,time.monotonic()-started)


def verify_claim(statement, *, timeout_ms=5000):
    if isinstance(statement,dict):
        statement = FormalStatement.from_data(statement)
    if not isinstance(statement,FormalStatement):
        raise TypeError('A structured FormalStatement is required; free text is not a theorem')
    if type(timeout_ms) is not int or not 1 <= timeout_ms <= 5000:
        raise ValueError('SMT calls have a hard maximum of 5000 ms')
    result = AIVerifier(timeout_seconds=timeout_ms/1000,logic='QF_LRA').verify(statement).details
    status = result['status']
    verdict = ('supported_in_fragment' if status == 'unsat' else
               'refuted' if status == 'counterexample' and result.get('exact_replay') else 'unverified')
    return receipt('ai.verify_claim',statement.to_data(),{'verdict':verdict,'verification':result},
                   backend='z3',metadata={'timeout_ms':timeout_ms,'trust':'SMT result, not a Lean kernel proof'})


class SandboxVerifier:
    def verify(self, statement, **options):
        return verify_claim(statement,**options)

    def require_supported(self, statement, **options):
        record = self.verify(statement,**options)
        if record['result']['verdict'] != 'supported_in_fragment':
            raise ValueError('Mathematical claim rejected: '+record['result']['verdict'])
        return record
