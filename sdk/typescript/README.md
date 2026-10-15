# TypeScript coordinator client

Source SDK using native `fetch`, `AbortController` and streaming reads; no package dependencies. Import `CoordinatorClient` from `./client.ts` in Node 24 (native TypeScript stripping), or compile with your application's TypeScript toolchain for another runtime. No separately published package is claimed.

```typescript
import { CoordinatorClient } from './client.ts';
const client = new CoordinatorClient('http://127.0.0.1:8080', participant, token);
const taskId = await client.createTask('x+1', {x: '2'});
const lease = await client.lease(60);
```

Methods: `createTask`, `status`, `lease`, `heartbeat`, `submit`, `cancel`. Server capabilities and issued tokens are prerequisites; obtain credentials through deployment secret configuration. Submissions contain existing result IDs, never executable code. Two worker identities are required for server consensus.

Only explicit HTTPS or loopback HTTP origins are accepted, using the runtime's default TLS verification. Redirects fail. The constructor's last arguments configure the total abort timeout in milliseconds (default 5000, maximum 60000) and response byte bound (default 65536, maximum 1048576). Requests are limited to 64 KiB. Responses use bounded streaming, fatal UTF-8 decoding, JSON parsing and strict route-specific fields. JavaScript's JSON parser uses standard last-key semantics for duplicate JSON keys. Errors omit tokens and response bodies. No automatic retries, remote hosting or credential provisioning is included.

Interop tests run the actual `.ts` source when native TypeScript support exists. Older runtimes such as Node 20 explicitly skip that runtime check; Python interoperability remains required.
