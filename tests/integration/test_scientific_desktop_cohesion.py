"""Real HTTP integration of the desktop's shared scientific calculation engine.

This suite deliberately tests the existing session token, Origin and Host
barriers. Scientific receipts are not forced into the legacy expression DB.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest import TestCase
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from nablamath.desktop.app import make_server


class ScientificDesktopCohesionTests(TestCase):
    def test_catalog_receipts_and_security_match_public_calculator(self):
        with TemporaryDirectory() as directory:
            server, research = make_server(Path(directory))
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/", timeout=5) as response:
                    page = response.read().decode("utf-8")
                self.assertIn('id="scientific-operation"', page)
                self.assertIn('id="scientific-calculate"', page)
                self.assertIn('id="scientific-save"', page)
                token = page.split("const auth='", 1)[1].split("'", 1)[0]

                def request(path, arguments=None, *, auth=token, origin=base):
                    data = (json.dumps(arguments).encode("utf-8")
                            if arguments is not None else None)
                    headers = {"X-Nabla-Token": auth, "Content-Type": "application/json"}
                    if origin is not None:
                        headers["Origin"] = origin
                    with urlopen(Request(base + path, data=data, headers=headers),
                                 timeout=5) as response:
                        return json.load(response)

                catalog = request("/api/catalog")
                names = {row["name"] for row in catalog["operations"]}
                self.assertGreaterEqual(len(names), 69)
                for operation in ("evaluate", "nt_primality", "ff_extension",
                                  "analysis_integral", "graph_max_flow",
                                  "prob_stationary"):
                    self.assertIn(operation, names)

                cases = (
                    ("nt_primality", {"n": 97}, "prime", True),
                    ("nt_factorization", {"n": 12}, "totient", 4),
                    ("analysis_integral", {"coefficients": [0, 0, 1],
                                           "lower": 0, "upper": 1}, "integral", "1/3"),
                    ("graph_max_flow", {"vertices": ["s", "t"],
                                        "edges": [["s", "t", "3/2"]],
                                        "source": "s", "sink": "t"}, "value", "3/2"),
                )
                for operation, arguments, key, expected in cases:
                    with self.subTest(operation=operation):
                        result = request("/api/calculate", {
                            "operation": operation, "arguments": arguments
                        })
                        self.assertEqual(result["result"][key], expected)
                        self.assertEqual(result["request"]["operation"], operation)
                        self.assertFalse(result["formal_proof"])
                        self.assertTrue(result["content_id"])
                self.assertEqual(research.count(), 0)
                stored = request("/api/save-calculation", {
                    "operation": "analysis_integral",
                    "arguments": {"coefficients": [0, 0, 1], "lower": 0, "upper": 1}
                })
                from nablamath.calc.notebook import Notebook
                notebook_path = Path(stored["path"])
                self.assertTrue(notebook_path.is_file())
                self.assertTrue(stored["replayed"])
                self.assertFalse(stored["already_present"])
                self.assertEqual(Notebook.load(notebook_path).replay(), 1)
                duplicate = request("/api/save-calculation", {
                    "operation": "analysis_integral",
                    "arguments": {"coefficients": [0, 0, 1], "lower": 0, "upper": 1}
                })
                self.assertTrue(duplicate["already_present"])
                self.assertEqual(duplicate["path"], stored["path"])
                self.assertEqual(research.count(), 0)
                # A rota / permite ambos os nomes loopback; a origem POST
                # precisa corresponder exatamente ao Host escolhido.
                localhost = f"http://localhost:{server.server_port}"
                local_headers = {"X-Nabla-Token": token, "Origin": localhost,
                                 "Content-Type": "application/json"}
                request_body = json.dumps({
                    "operation": "nt_primality", "arguments": {"n": 97}
                }).encode("utf-8")
                with urlopen(Request(localhost + "/api/calculate",
                                     data=request_body, headers=local_headers),
                             timeout=5) as response:
                    self.assertTrue(json.load(response)["result"]["prime"])

                with self.assertRaises(HTTPError) as failure:
                    request("/api/catalog", auth="invalid")
                self.assertEqual(failure.exception.code, 403)

                with self.assertRaises(HTTPError) as failure:
                    request("/api/calculate",
                            {"operation": "nt_primality", "arguments": {"n": 97}},
                            origin="http://not-allowed.test")
                self.assertEqual(failure.exception.code, 403)

                for invalid in (
                    {"operation": "nt_primality"},
                    {"operation": "nt_primality", "arguments": []},
                    {"operation": "nt_primality", "arguments": {"n": 97, "unused": 1}},
                    {"operation": "__import__", "arguments": {}},
                ):
                    with self.subTest(invalid=invalid), self.assertRaises(HTTPError) as failure:
                        request("/api/calculate", invalid)
                    self.assertEqual(failure.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)


if __name__ == "__main__":
    import unittest
    unittest.main()
