"""Replay verified checkpoints against explicit, ordered project milestones."""
from itertools import islice
from ...agents.planner import verify_run
from ...core.semantic_ir import fingerprint


def evaluate_project(proposal, reports, *, milestones, approval_heads=()):
    """Evaluate append-only progress, never infer success from elapsed time.

    Milestones identify action receipts. Approval heads are provenance supplied by
    the caller, not independent evidence of an authenticated human intervention.
    """
    reports = list(islice(reports, 1001))
    milestones = tuple(islice(milestones, len(proposal.actions)+1))
    ids = [a.action_id for a in proposal.actions]
    if (not reports or len(reports) > 1000 or not milestones
            or len(milestones) > len(proposal.actions)
            or len(set(milestones)) != len(milestones)
            or any(m not in ids for m in milestones)):
        raise ValueError('Bounded reports and unique known milestones required')
    previous = []
    progress = []
    for report in reports:
        if report.get('proposal_id') != proposal.content_id or not verify_run(report):
            raise ValueError('Unverifiable project checkpoint')
        receipts = report['receipts']
        if len(receipts) < len(previous) or receipts[:len(previous)] != previous:
            raise ValueError('Project history fork or rollback')
        completed = {r['action_id'] for r in receipts if r['status'] == 'completed'}
        progress.append(dict(head=report['final_receipt'], completed_milestones=[m for m in milestones if m in completed]))
        previous = receipts
    heads = tuple(islice(approval_heads, 1001))
    if len(heads) > 1000 or any(not isinstance(head, str) or len(head) != 64 or any(c not in '0123456789abcdef' for c in head) for head in heads):
        raise ValueError('Invalid intervention reference')
    body = dict(proposal_id=proposal.content_id, checkpoints=progress, milestones=list(milestones),
                achieved=progress[-1]['completed_milestones'], all_achieved=len(progress[-1]['completed_milestones']) == len(milestones),
                intervention_references=list(heads),
                limitations='Replayed trusted scientific tools; no claim of autonomous long-term research or authenticated intervention')
    return dict(body, evaluation_id=fingerprint(body))
