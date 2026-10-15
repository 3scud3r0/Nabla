"""Painel de pesquisa local: cálculo racional, loop limitado, exportação e publicação opt-in."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from pathlib import Path
import secrets
import sqlite3
from contextlib import closing
import threading
import webbrowser

from nablamath.curation import curate
from nablamath.research import calculate
from nablamath.orbits import earth_circular_orbit
from nablamath.physics.fluids import PipeFlow
from nablamath.report import write_report
from nablamath.storage import export_verified, import_snapshot, save_result


class LocalResearch:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = self.data_dir / "results.sqlite3"
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self.last_error: str | None = None
        self.attempted = 0

    def count(self) -> int:
        if not self.db.is_file():
            return 0
        with closing(sqlite3.connect(self.db)) as connection, connection:
            return connection.execute("SELECT count(*) FROM results").fetchone()[0]

    def recent(self, limit: int = 12) -> list[dict]:
        if not self.db.is_file():
            return []
        with closing(sqlite3.connect(self.db)) as connection, connection:
            rows = connection.execute("SELECT payload FROM results ORDER BY created_at DESC, content_id DESC LIMIT ?",
                                      (min(max(limit, 1), 100),)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def status(self) -> dict:
        with self._lock:
            return {"records": self.count(), "running": bool(self.worker and self.worker.is_alive()),
                    "attempted_this_session": self.attempted, "last_error": self.last_error,
                    "data_dir": str(self.data_dir), "scope": "Instâncias racionais; sem prova formal ou descoberta científica"}

    def run(self, expression: str, values: dict) -> dict:
        if not isinstance(expression, str) or not isinstance(values, dict) or len(expression) > 256:
            raise ValueError("Expressão inválida ou maior que 256 caracteres")
        result = calculate(expression, values)
        inserted = save_result(self.db, result)
        return {"inserted": inserted, "result": result.to_data()}

    def report(self, expression: str, values: dict) -> dict:
        result = calculate(expression, values)
        save_result(self.db, result)
        path, _ = write_report(result, self.data_dir / (result.content_id + ".tex"))
        return {"path": str(path), "content_id": result.content_id}

    def experiment(self, payload: dict) -> dict:
        from .workflows import ExperimentWorkflow
        return ExperimentWorkflow(self.data_dir / 'experiments').execute(
            payload['expression'], payload['values'], consent=payload.get('consent'),
            reviewer=payload.get('reviewer', ''))

    def orbit(self, altitude_m: float) -> dict:
        return earth_circular_orbit(altitude_m).summary()

    def fluid(self, radius_m: float, length_m: float, pressure_pa: float) -> dict:
        result = PipeFlow(radius_m, length_m, pressure_pa, 1.0, 1000.0).solve()
        return result.__dict__

    def start(self, *, max_examples: int, interval_seconds: float) -> dict:
        if isinstance(max_examples, bool) or not isinstance(max_examples, int) or not 1 <= max_examples <= 1000:
            raise ValueError("Use de 1 a 1000 exemplos por sessão")
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, (int, float)) or not .1 <= interval_seconds <= 60:
            raise ValueError("Intervalo deve estar entre 0,1 e 60 segundos")
        with self._lock:
            if self.worker and self.worker.is_alive():
                raise ValueError("O loop já está em execução")
            self.stop_event.clear()
            self.last_error = None
            self.attempted = 0
            self.worker = threading.Thread(target=self._loop, args=(max_examples, interval_seconds), daemon=True)
            self.worker.start()
        return {"running": True, "max_examples": max_examples}

    def _loop(self, maximum: int, interval: float) -> None:
        # Um conjunto pequeno e explícito: o volume não representa diversidade científica.
        templates = ("x+x", "(x+x)/x", "x*(x+1)", "(x*2)+x")
        try:
            for i in range(maximum):
                if self.stop_event.is_set():
                    break
                expression = templates[i % len(templates)]
                self.run(expression, {"x": str(1 + i // len(templates))})
                with self._lock:
                    self.attempted += 1
                if self.stop_event.wait(interval):
                    break
        except (ValueError, OSError, sqlite3.Error) as exc:
            with self._lock:
                self.last_error = str(exc)

    def stop(self) -> dict:
        self.stop_event.set()
        return {"stopping": True}

    def export(self) -> dict:
        destination = self.data_dir / "verified.jsonl"
        count, digest = export_verified(self.db, destination)
        return {"records": count, "sha256": digest, "path": str(destination)}

    def import_local(self) -> dict:
        source = self.data_dir / "incoming.jsonl"
        inserted, duplicate = import_snapshot(self.db, source)
        return {"inserted": inserted, "duplicate": duplicate}

    def curate_local(self, license_id: str, provenance: str) -> dict:
        return curate(self.db, self.data_dir / "curated.jsonl", license_id=license_id, provenance=provenance)

    def upload(self, payload: dict) -> dict:
        """Publica apenas após declaração expressa de titularidade e destino pelo usuário."""
        if payload.get("consent") is not True or payload.get("redistributable") is not True:
            raise ValueError("Confirme direitos de redistribuição e intenção de publicar")
        token = payload.get("token", "")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Token de escrita no Hugging Face é obrigatório")
        for field in ("repo_id", "reviewer", "license_id", "provenance"):
            if not isinstance(payload.get(field), str) or not payload[field].strip() or len(payload[field]) > 256:
                raise ValueError(f"Campo obrigatório: {field}")
        from nablamath.publisher.huggingface import publish
        from huggingface_hub import HfApi
        snapshot = self.data_dir / "curated.jsonl"
        manifest = self.curate_local(payload["license_id"], payload["provenance"])
        approval = self.data_dir / "curated.jsonl.approval.json"
        approval.write_text(json.dumps({"approved_for_publication": True,
            "snapshot_sha256": manifest["sha256"], "dataset_repo": payload["repo_id"],
            "reviewer": payload["reviewer"], "license_id": payload["license_id"],
            "redistributable": True, "attribution": payload.get("attribution", "")}), encoding="utf-8")
        # Token não é gravado no banco ou no arquivo de aprovação.
        return publish(snapshot, approval=approval, client=HfApi(token=token),
                       repo_id=payload["repo_id"], dry_run=False)


def make_server(data_dir: Path, port: int = 0) -> tuple[ThreadingHTTPServer, LocalResearch]:
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("Porta inválida")
    research = LocalResearch(data_dir)
    token = secrets.token_urlsafe(32)
    html = files("nablamath.desktop").joinpath("index.html").read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Evitar URL de sessão e dados de entrada em logs locais.
            pass

        def _headers(self, status: int, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'none'; base-uri 'none'")
            self.end_headers()

        def _send(self, status: int, content: dict) -> None:
            raw = json.dumps(content, ensure_ascii=False, default=str).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(raw))
            self.wfile.write(raw)

        def _authorized(self) -> bool:
            return (self.headers.get("X-Nabla-Token") == token and
                    self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"))

        def do_GET(self):
            if self.path == "/" and self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"):
                raw = html.replace("__NABLA_TOKEN__", token).encode("utf-8")
                self._headers(200, "text/html; charset=utf-8", len(raw))
                self.wfile.write(raw)
            elif not self._authorized():
                self._send(403, {"error": "Acesso local inválido"})
            elif self.path == "/api/status":
                self._send(200, research.status())
            elif self.path == "/api/recent":
                self._send(200, {"records": research.recent()})
            else:
                self._send(404, {"error": "Rota inexistente"})

        def do_POST(self):
            origin = self.headers.get("Origin")
            if (not self._authorized() or origin != f"http://127.0.0.1:{self.server.server_port}"):
                return self._send(403, {"error": "Origem ou sessão inválida"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16_384:
                    raise ValueError("Requisição deve ter no máximo 16 KiB")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("Objeto JSON esperado")
                routes = {"/api/experiment": lambda: research.experiment(payload),
                          "/api/run": lambda: research.run(payload["expression"], payload["values"]),
                          "/api/start": lambda: research.start(max_examples=payload["max_examples"], interval_seconds=payload["interval_seconds"]),
                          "/api/stop": research.stop, "/api/export": research.export,
                          "/api/import": research.import_local,
                          "/api/curate": lambda: research.curate_local(payload["license_id"], payload["provenance"]),
                          "/api/upload": lambda: research.upload(payload),
                          "/api/report": lambda: research.report(payload["expression"], payload["values"]),
                          "/api/orbit": lambda: research.orbit(payload["altitude_m"]),
                          "/api/fluid": lambda: research.fluid(payload["radius_m"], payload["length_m"], payload["pressure_pa"])}
                if self.path not in routes:
                    return self._send(404, {"error": "Rota inexistente"})
                self._send(200, routes[self.path]())
            except (KeyError, TypeError, ValueError, OSError, sqlite3.Error, ImportError) as exc:
                self._send(400, {"error": str(exc)})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler), research


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Painel local NablaMath")
    parser.add_argument("--data-dir", type=Path, default=Path.home() / "NablaMath")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    server, _ = make_server(args.data_dir, args.port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"NablaMath local: {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
