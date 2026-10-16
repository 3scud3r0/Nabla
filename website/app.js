async function loadSnapshot() {
  const label = document.getElementById('snapshot-date');
  try {
    const response = await fetch('data/status.json', {cache: 'no-store'});
    if (!response.ok) throw new Error('snapshot indisponível');
    const snapshot = await response.json();
    for (const [id, value] of Object.entries({
      'metric-records': snapshot.public_curated_records,
      'metric-participants': snapshot.verified_public_participants,
      'metric-phases': snapshot.completed_phases
    })) {
      if (!Number.isSafeInteger(value) || value < 0) throw new Error('métrica inválida');
      document.getElementById(id).textContent = String(value);
    }
    label.textContent = 'Snapshot: ' + snapshot.as_of + ' · métricas publicadas, sem telemetria em tempo real.';
  } catch (_error) {
    label.textContent = 'Snapshot indisponível; consulte o repositório para confirmar o estado.';
  }
}

function setupLocalContribution() {
  const start = document.getElementById('start-compute');
  const stop = document.getElementById('stop-compute');
  const download = document.getElementById('download-compute');
  const amount = document.getElementById('compute-count');
  const status = document.getElementById('compute-status');
  const progress = document.getElementById('compute-progress');
  let worker = null;
  let rows = [];
  let requested = 0;

  function setRunning(running) {
    start.disabled = running;
    amount.disabled = running;
    stop.disabled = !running;
  }

  start.addEventListener('click', () => {
    const count = Number(amount.value);
    if (!Number.isInteger(count) || count < 1 || count > 5000) {
      status.textContent = 'Informe um número inteiro entre 1 e 5.000.';
      return;
    }
    if (!window.Worker || !window.crypto?.subtle) {
      status.textContent = 'Este navegador não oferece Web Workers e SHA-256. Use uma versão atual do navegador.';
      return;
    }
    rows = [];
    requested = count;
    progress.max = count;
    progress.value = 0;
    download.disabled = true;
    worker = new Worker('worker.js');
    worker.onmessage = ({data}) => {
      if (data.type === 'batch') {
        rows.push(...data.records);
        progress.value = data.completed;
        status.textContent = `Verificados localmente: ${data.completed.toLocaleString()} de ${requested.toLocaleString()} casos · ${rows.length.toLocaleString()} registros. Não enviados à rede.`;
      } else if (data.type === 'done' || data.type === 'stopped') {
        progress.value = data.completed;
        worker.terminate();
        worker = null;
        setRunning(false);
        download.disabled = rows.length === 0;
        status.textContent = `${data.type === 'done' ? 'Concluído' : 'Interrompido'}: ${data.completed.toLocaleString()} casos, ${rows.length.toLocaleString()} registros JSONL no navegador. Nenhum dado foi enviado.`;
      } else if (data.type === 'error') {
        worker.terminate();
        worker = null;
        setRunning(false);
        status.textContent = `Falha no worker: ${data.message}`;
      }
    };
    worker.onerror = () => {
      worker?.terminate();
      worker = null;
      setRunning(false);
      status.textContent = 'O worker falhou. Nenhum resultado foi enviado à rede.';
    };
    setRunning(true);
    status.textContent = 'Iniciando cálculo local…';
    worker.postMessage({type: 'start', count});
  });

  stop.addEventListener('click', () => {
    if (worker) worker.postMessage({type: 'stop'});
    stop.disabled = true;
    status.textContent = 'Parando após o lote atual…';
  });

  download.addEventListener('click', () => {
    if (!rows.length) return;
    const body = rows.map(row => JSON.stringify(row)).join('\n') + '\n';
    const blob = new Blob([body], {type: 'application/x-ndjson'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `nablamath-browser-demo-${new Date().toISOString().slice(0, 10)}.jsonl`;
    link.click();
    URL.revokeObjectURL(url);
  });
}

loadSnapshot();
setupLocalContribution();

// Evidence-derived project status is independent of the local demonstration.
import {renderEvidenceStatus} from './src/evidence.js';
const evidenceNode = document.getElementById('evidence-status');
if (evidenceNode) {
  fetch('data/evidence_matrix.json', {credentials:'omit', cache:'no-store'})
    .then(response => { if (!response.ok) throw new Error('Evidence unavailable'); return response.json(); })
    .then(matrix => renderEvidenceStatus(evidenceNode, matrix))
    .catch(() => { evidenceNode.textContent = 'Matriz de evidências indisponível; nenhum status de conclusão inferido.'; });
}
