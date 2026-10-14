"""Flag stale/refuted dependencies without rewriting historic scientific claims."""

def dependency_impact(graph,changed_revision):
    changed=graph.ledger.get(changed_revision)
    affected=graph.affected_by(changed_revision)
    alerts=[]
    for identifier in affected:
        revision=graph.ledger.get(identifier)
        reasons=[]
        for dependency in graph.dependencies[identifier]:
            original=graph.ledger.get(dependency);latest=graph.ledger.latest(original.claim)
            if latest.status in {'refuted','withdrawn'}:
                reasons.append({'dependency':dependency,'latest_revision':latest.revision_id,'reason':'dependency_'+latest.status})
            elif latest.revision_id!=dependency:
                reasons.append({'dependency':dependency,'latest_revision':latest.revision_id,'reason':'newer_dependency_version'})
        alerts.append({'revision_id':identifier,'claim':revision.claim,'status_unchanged':revision.status,
                       'requires_review':bool(reasons) or changed.status in {'refuted','withdrawn'},'reasons':reasons})
    return {'changed_revision':changed_revision,'affected':list(affected),'alerts':alerts,
            'automatic_claim_rewrite_performed':False}
