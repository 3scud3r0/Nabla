/** Parse bounded receipt metadata. Display is distinct from verification or replay. */
export function parseReceipt(raw: Uint8Array, expectedId?: string): Record<string, unknown> {
    if (raw.byteLength > 1024 * 1024) throw new Error('Receipt exceeds 1 MiB preview budget');
    const value: unknown = JSON.parse(Buffer.from(raw).toString('utf8'));
    if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error('Invalid receipt');
    const data = value as Record<string, unknown>;
    if (data.schema_version !== 1 || typeof data.content_id !== 'string' || !/^[0-9a-f]{64}$/.test(data.content_id)) {
        throw new Error('Invalid receipt identity');
    }
    if (expectedId && data.content_id !== expectedId) throw new Error('Receipt ID differs from selected hash');
    if (!('result' in data) || !(('request' in data) || data.kind === 'execution_observation')) throw new Error('Unsupported receipt');
    return data;
}
