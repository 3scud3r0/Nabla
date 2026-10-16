// Derive bounded status from the reviewed matrix; no telemetry or external calls.
export function deriveEvidenceStatus(matrix) {
  if (matrix?.schema_version !== 1 || !Array.isArray(matrix.requirements) || matrix.requirements.length !== 213) {
    throw new Error('Expected the canonical 213-requirement matrix');
  }
  const counts = {planned: 0, partial: 0, validated: 0};
  const ids = new Set();
  for (const row of matrix.requirements) {
    if (!row || typeof row.status !== 'string' || !Number.isInteger(row.id) || row.id < 1 || row.id > 213 || ids.has(row.id) || !Object.hasOwn(counts, row.status)) {
      throw new Error('Invalid requirement identity or status');
    }
    ids.add(row.id);
    counts[row.status]++;
  }
  return {total: ids.size, ...counts, source: 'docs/acceptance/evidence_matrix.json',
    roadmap_source: matrix.source, roadmap_source_sha256: matrix.source_sha256,
    interpretation: 'Partial implementation is not full scientific validation.'};
}

export function renderEvidenceStatus(node, matrix) {
  const state = deriveEvidenceStatus(matrix);
  node.textContent = `${state.validated}/${state.total} integralmente validados; ${state.partial} parciais; ${state.planned} planejados.`;
  node.setAttribute('role', 'status');
  node.setAttribute('aria-live', 'polite');
  return state;
}
