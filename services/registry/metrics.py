"""Aggregate local service counters with small-cohort suppression.

Suppression reduces direct disclosure; it is not differential privacy or a proof
of anonymity. Restrict access to repeated queries and use an external privacy
review before publishing metrics about people or organizations.
"""


def registry_metrics(database, *, now_unix, minimum_cohort=5):
    if type(minimum_cohort) is not int or not 2 <= minimum_cohort <= 10000:
        raise ValueError('Minimum cohort must be between 2 and 10000')
    with database.transaction() as connection:
        database.check_clock(connection, now_unix)
        rows = connection.execute('SELECT peer_id FROM peers WHERE expires>?', (now_unix,)).fetchall()
        active = sum(database.active_peer(connection, row['peer_id'], now_unix=now_unix) for row in rows)
        audit_count = connection.execute('SELECT count(*) FROM audit').fetchone()[0]
        replay_count = connection.execute('SELECT count(*) FROM replays WHERE expires>?', (now_unix,)).fetchone()[0]
    return {'schema_version': 1, 'active_peers': active if active >= minimum_cohort else None,
            'active_peers_suppressed': active < minimum_cohort,
            'audit_capacity_remaining': database.max_audit - audit_count,
            'replay_capacity_remaining': database.max_replays - replay_count,
            'privacy': 'aggregate-only, small-cohort suppression; no anonymity guarantee'}
