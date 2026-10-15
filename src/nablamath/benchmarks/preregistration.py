"""Immutable, predeclared paired exact-task studies with an append-only ledger.

A registration fixes models, task cohort, metric and stopping rule before results
are submitted. Caller labels are not authenticated people, timestamps are not an
external notary, and this module does not provide a secret holdout or train code.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from pathlib import Path
import sqlite3

from ..core.semantic_contracts import (canonical_payload, load_json, require_digest,
                                       require_fields, require_text)
from ..core.semantic_ir import fingerprint, rational
from ..evaluation.frozen import FrozenEvaluation


@dataclass(frozen=True)
class RegisteredComparison:
    manifest_json: str

    def __post_init__(self):
        data = load_json(self.manifest_json)
        require_fields(data, {'schema_version', 'protocol_id', 'models', 'primary_metric',
                             'minimum_delta', 'alpha', 'owner', 'stopping_rule', 'reference_model'})
        if type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise ValueError('Unsupported comparison version')
        require_digest(data['protocol_id'])
        require_text(data['owner'], 'owner', limit=256)
        if data['primary_metric'] != 'paired_exact_accuracy':
            raise ValueError('Only predeclared exact accuracy is supported')
        if data['stopping_rule'] != 'score each declared model exactly once; preserve all outcomes':
            raise ValueError('Optional stopping is not supported')
        models = data['models']
        if not isinstance(models, dict) or not 2 <= len(models) <= 8:
            raise ValueError('Two to eight committed models required')
        require_text(data['reference_model'], 'reference model', limit=128)
        if data['reference_model'] not in models:
            raise ValueError('Explicit reference model must be registered')
        for name, digest in models.items():
            require_text(name, 'model name', limit=128)
            require_digest(digest)
        for name, low, high in [('minimum_delta', 0, 1), ('alpha', 0, 1)]:
            if not isinstance(data[name], str):
                raise ValueError('Thresholds must use exact rational strings')
            value = rational(data[name])
            if not low <= value <= high or name == 'alpha' and value in (0, 1):
                raise ValueError('Invalid predeclared threshold')
        object.__setattr__(self, 'manifest_json', canonical_payload(data))

    @classmethod
    def register(cls, protocol, *, models, owner, reference_model, minimum_delta='0', alpha='1/20'):
        if not isinstance(protocol, FrozenEvaluation):
            raise ValueError('FrozenEvaluation required before registration')
        return cls(canonical_payload({'schema_version': 1, 'protocol_id': protocol.protocol_id,
            'models': models, 'reference_model': reference_model, 'primary_metric': 'paired_exact_accuracy',
            'minimum_delta': minimum_delta, 'alpha': alpha, 'owner': owner,
            'stopping_rule': 'score each declared model exactly once; preserve all outcomes'}))

    def to_data(self):
        return load_json(self.manifest_json)

    @property
    def study_id(self):
        return fingerprint(self.to_data())

    def score(self, protocol, submissions):
        data = self.to_data()
        if not isinstance(protocol, FrozenEvaluation) or protocol.protocol_id != data['protocol_id']:
            raise ValueError('Frozen protocol differs from registered cohort')
        if not isinstance(submissions, dict) or set(submissions) != set(data['models']):
            raise ValueError('Every predeclared model must be evaluated, without extras')
        reports = {name: protocol.evaluate(submissions[name]) for name in sorted(submissions)}
        baseline_name = data['reference_model']
        baseline_scores = {r['task_id']: r['candidate'] for r in reports[baseline_name]['scores']}
        comparisons = {}
        for name, report in reports.items():
            scores = {r['task_id']: r['candidate'] for r in report['scores']}
            if set(scores) != set(baseline_scores):
                raise ValueError('Paired cohorts differ')
            wins = sum(scores[key] and not baseline_scores[key] for key in scores)
            losses = sum(baseline_scores[key] and not scores[key] for key in scores)
            n = wins + losses
            # Exact one-sided sign test on discordant pairs. Inference assumes
            # independent/exchangeable pairs; this condition is NOT established.
            probability = (Fraction(sum(comb(n, k) for k in range(wins, n+1)), 2**n)
                           if n else Fraction(1))
            delta = Fraction(wins-losses, len(scores))
            comparisons[name] = {'wins': wins, 'losses': losses,
                'ties': len(scores)-n, 'delta': str(delta),
                'one_sided_sign_p': str(probability),
                'descriptive_threshold_met': delta > rational(data['minimum_delta'])
                    and probability <= rational(data['alpha']),
                'inferential_assumptions_validated': False,
                'multiple_comparison_correction_applied': False}
        result = {'schema_version': 1, 'study_id': self.study_id,
            'protocol_id': protocol.protocol_id, 'models': data['models'],
            'reference_model': baseline_name, 'evaluations': reports,
            'comparisons': comparisons, 'scientific_gain_established': False,
            'model_execution_verified': False,
            'scope': 'fixed descriptive paired study; identities, exchangeability and holdout secrecy unverified'}
        return {**result, 'result_id': fingerprint(result)}

    def replay(self, report, protocol, submissions):
        try:
            return canonical_payload(report) == canonical_payload(self.score(protocol, submissions))
        except (ValueError, KeyError, TypeError, ArithmeticError):
            return False


class StudyLedger:
    """Transactional registration-before-results, one result per registered study.

    Ledger administrators can modify the file; this is local append-only API
    behavior and detects hash corruption, not a tamper-proof public timestamp.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS studies (id TEXT PRIMARY KEY, manifest TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS outcomes (study_id TEXT PRIMARY KEY, result TEXT NOT NULL, '
                       'FOREIGN KEY(study_id) REFERENCES studies(id))')

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute('PRAGMA foreign_keys=ON')
            with db:
                yield db
        finally:
            db.close()

    def register(self, study):
        if not isinstance(study, RegisteredComparison):
            raise ValueError('Typed study required')
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT manifest FROM studies WHERE id=?', (study.study_id,)).fetchone()
            if row is not None:
                if row[0] != study.manifest_json:
                    raise ValueError('Stored study commitment corrupted')
                return False
            if db.execute('SELECT count(*) FROM studies').fetchone()[0] >= 10000:
                raise ValueError('Study capacity exhausted')
            db.execute('INSERT INTO studies VALUES (?,?)', (study.study_id, study.manifest_json))
            return True

    def record(self, study, protocol, submissions):
        # Obtain and validate detached canonical data before committing a result.
        if not isinstance(study, RegisteredComparison):
            raise ValueError('Typed study required')
        snapshot = load_json(canonical_payload(submissions))
        report = study.score(protocol, snapshot)
        encoded = canonical_payload({'report': report, 'submissions': snapshot})
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            stored = db.execute('SELECT manifest FROM studies WHERE id=?', (study.study_id,)).fetchone()
            if stored is None or stored[0] != study.manifest_json:
                raise ValueError('Register this exact study before recording outcomes')
            try:
                db.execute('INSERT INTO outcomes VALUES (?,?)', (study.study_id, encoded))
            except sqlite3.IntegrityError as exc:
                raise ValueError('Study already has an outcome; failed studies are not overwritten') from exc
        return report

    def replay(self, study, protocol):
        if not isinstance(study, RegisteredComparison):
            return False
        try:
            with self._connection() as db:
                row = db.execute('SELECT substr(s.manifest,1,1000001),substr(o.result,1,1000001) FROM studies s JOIN outcomes o ON s.id=o.study_id '
                                 'WHERE s.id=?', (study.study_id,)).fetchone()
            if row is None or row[0] != study.manifest_json or len(row[1]) > 1_000_000:
                return False
            data = load_json(row[1])
            require_fields(data, {'report', 'submissions'})
            return study.replay(data['report'], protocol, data['submissions'])
        except (ValueError, TypeError, KeyError, sqlite3.Error):
            return False
