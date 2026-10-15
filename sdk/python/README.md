# Python coordinator client

Load `client.py` directly or add this directory to your import path. No dependencies beyond Python 3.10+. This source SDK is not separately published.

```python
from client import CoordinatorClient
client = CoordinatorClient('http://127.0.0.1:8080', participant, token)
task_id = client.create_task('x+1', {'x': '2'})
assert client.status(task_id) == 'pending'
lease = client.lease(60)
```

The server must explicitly grant capabilities to the participant. Supply tokens through your deployment's secret mechanism. Methods: `create_task`, `status`, `lease`, `heartbeat`, `submit`, `cancel`. Submission takes the existing result content ID, not executable code. Two distinct workers are needed for server consensus.

Only explicit HTTPS origins or loopback HTTP origins are accepted. Standard TLS certificate verification remains enabled; redirects are rejected. Requests are limited to 64 KiB; responses default to 64 KiB with bounded reads, strict JSON and route-specific validation. Configure `timeout` (seconds, up to 60) and `max_response_bytes` (up to 1 MiB). The socket timeout applies to individual blocking operations; it is not a total request deadline. Network failures raise `CoordinatorError` without embedding tokens or response bodies. This client does not provide remote deployment, identity provisioning, automatic retries or scientific validation beyond the server contract.
