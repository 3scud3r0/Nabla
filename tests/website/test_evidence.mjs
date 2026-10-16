import assert from 'node:assert/strict';
import test from 'node:test';
import {deriveEvidenceStatus, renderEvidenceStatus} from '../../website/src/evidence.js';
function matrix() {
  return {schema_version: 1, source_sha256: 'a'.repeat(64), requirements:
    Array.from({length: 213}, (_, index) => ({id: index + 1, status: 'partial'}))};
}
test('evidence counters preserve partial versus validated', () => {
  const source = matrix(); source.requirements[0].status = 'planned';
  const result = deriveEvidenceStatus(source);
  assert.equal(result.roadmap_source_sha256, 'a'.repeat(64));
  assert.equal(result.partial, 212); assert.equal(result.planned, 1); assert.equal(result.validated, 0);
});
test('prototype keys and coerced statuses cannot become valid states', () => {
  for (const status of ['__proto__', 'constructor', 'toString', ['partial'], null]) {
    const source = matrix(); source.requirements[0].status = status;
    assert.throws(() => deriveEvidenceStatus(source));
  }
});
test('identities and full cardinality are required', () => {
  const source = matrix(); source.requirements[1].id = 1;
  assert.throws(() => deriveEvidenceStatus(source));
  source.requirements.pop(); assert.throws(() => deriveEvidenceStatus(source));
});
test('rendering uses text with accessible live status', () => {
  const node = {attributes: {}, setAttribute(name, value) {this.attributes[name] = value;}};
  renderEvidenceStatus(node, matrix());
  assert.match(node.textContent, /0\/213 integralmente validados; 213 parciais/);
  assert.equal(node.attributes['role'], 'status'); assert.equal(node.attributes['aria-live'], 'polite');
});
