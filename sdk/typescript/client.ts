/** Bounded JSON coordinator client. Native fetch; no credential logging or redirects. */
export class CoordinatorError extends Error {}
const digest = (x: unknown): string => {
  if (typeof x !== 'string' || !/^[0-9a-f]{64}$/.test(x)) throw new Error('Invalid digest');
  return x;
};
const fields = (x: any, names: string[]) => {
  if (!x || typeof x !== 'object' || Array.isArray(x) || Object.keys(x).sort().join(',') !== names.sort().join(','))
    throw new CoordinatorError('Invalid response fields');
};
const expiration = (x: unknown) => {
  if (typeof x !== 'number' || !Number.isFinite(x) || x <= 0) throw new CoordinatorError('Invalid expiration');
};
const secondsValid = (x: number) => {
  if (!Number.isInteger(x) || x < 1 || x > 3600) throw new Error('Invalid lease duration');
};
export class CoordinatorClient {
  private endpoint: string;
  private participant: string;
  private token: string;
  private timeoutMs: number;
  private maxResponseBytes: number;
  constructor(endpoint: string, participant: string, token: string, timeoutMs = 5000, maxResponseBytes = 65536) {
    const u = new URL(endpoint);
    const local = u.hostname === 'localhost' || u.hostname === '[::1]' || /^127(?:\.\d{1,3}){3}$/.test(u.hostname);
    if (!['http:', 'https:'].includes(u.protocol) || (u.protocol === 'http:' && !local) ||
        u.username || u.password || u.pathname !== '/' || u.search || u.hash)
      throw new Error('Explicit HTTPS or loopback HTTP origin required');
    if ([participant, token].some((x, i) => typeof x !== 'string' || !x || x.length > [128, 4096][i] || /[^\x20-\x7e]/.test(x)))
      throw new Error('Invalid credentials');
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 60000 ||
        !Number.isInteger(maxResponseBytes) || maxResponseBytes < 1 || maxResponseBytes > 1048576)
      throw new Error('Invalid transport bounds');
    this.endpoint = u.origin; this.participant = participant; this.token = token;
    this.timeoutMs = timeoutMs; this.maxResponseBytes = maxResponseBytes;
  }
  private async request(method: string, path: string, payload?: any): Promise<any> {
    const body = payload === undefined ? undefined : JSON.stringify(payload);
    if (body && new TextEncoder().encode(body).length > 65536) throw new Error('Request too large');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(this.endpoint + path, {method, body, redirect: 'error', signal: controller.signal,
        headers: {'Authorization': 'Bearer ' + this.token, 'X-Nabla-Participant': this.participant,
          'Content-Type': 'application/json', 'Accept': 'application/json'}});
      if (response.status !== 200 || response.headers.get('content-type')?.split(';')[0].trim() !== 'application/json') {
        await response.body?.cancel(); throw new CoordinatorError('Unexpected HTTP status or content type');
      }
      if (!response.body) throw new CoordinatorError('Missing response body');
      const reader = response.body.getReader(); const chunks: Uint8Array[] = []; let size = 0;
      try {
        while (true) {
          const {done, value} = await reader.read(); if (done) break;
          size += value.length;
          if (size > this.maxResponseBytes) {await reader.cancel(); throw new CoordinatorError('Response exceeds bound');}
          chunks.push(value);
        }
      } finally {reader.releaseLock();}
      const bytes = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) {bytes.set(chunk, offset); offset += chunk.length;}
      return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes));
    } catch {throw new CoordinatorError('Coordinator transport or response failure');}
    finally {clearTimeout(timer);}
  }
  async createTask(expression: string, values: Record<string, string | number>): Promise<string> {
    if (typeof expression !== 'string' || !expression || !values || typeof values !== 'object' || Array.isArray(values))
      throw new Error('Expression and bindings required');
    const r = await this.request('POST', '/tasks', {expression, values}); fields(r, ['task_id']);
    try {return digest(r.task_id);} catch {throw new CoordinatorError('Invalid task ID');}
  }
  async status(taskId: string): Promise<string> {
    const r = await this.request('GET', '/tasks/' + digest(taskId)); fields(r, ['task_id', 'status']);
    if (r.task_id !== taskId || !['pending', 'verified', 'cancelled'].includes(r.status)) throw new CoordinatorError('Invalid task status');
    return r.status;
  }
  async lease(seconds = 60): Promise<any> {
    secondsValid(seconds); const r = await this.request('POST', '/leases', {seconds}); fields(r, ['lease']);
    const l = r.lease; if (l === null) return null;
    fields(l, ['task_id', 'expression', 'values', 'lease_expires_unix']); expiration(l.lease_expires_unix);
    try {digest(l.task_id);} catch {throw new CoordinatorError('Invalid lease task ID');}
    if (typeof l.expression !== 'string' || !l.expression || l.expression.length > 65536 || !l.values ||
        typeof l.values !== 'object' || Array.isArray(l.values) || Object.keys(l.values).length > 128 ||
        Object.entries(l.values).some(([k,v]) => !k || k.length > 128 || typeof v !== 'string' ||
          !/^-?\d+(?:\/\d+)?$/.test(v) || (v.includes('/') && /^0+$/.test(v.split('/')[1]))))
      throw new CoordinatorError('Invalid lease data');
    return l;
  }
  async heartbeat(taskId: string, seconds = 60): Promise<number> {
    secondsValid(seconds); const r = await this.request('POST', '/tasks/' + digest(taskId) + '/heartbeat', {seconds});
    fields(r, ['lease_expires_unix']); expiration(r.lease_expires_unix); return r.lease_expires_unix;
  }
  async submit(taskId: string, resultId: string): Promise<string> {
    return this.action(taskId, 'submit', {result_id: digest(resultId)}, ['awaiting_second_worker', 'verified']);
  }
  async cancel(taskId: string): Promise<string> {return this.action(taskId, 'cancel', {}, ['cancelled']);}
  private async action(taskId: string, action: string, payload: any, statuses: string[]): Promise<string> {
    const r = await this.request('POST', '/tasks/' + digest(taskId) + '/' + action, payload); fields(r, ['status']);
    if (!statuses.includes(r.status)) throw new CoordinatorError('Invalid action status'); return r.status;
  }
}
