"""Notebook replay and CLI catalog consistency for experimental exact operations."""
import json
import unittest
from nablamath.calc import CalculationSession, Notebook


class AdvancedNotebookIntegrationTests(unittest.TestCase):
    def test_multidomain_notebook_replays_all_operations(self):
        notebook = Notebook("Multi-domain exact mathematics")
        session = CalculationSession()
        cases = (
            ("nt_primality", {"n": 65537}),
            ("ff_extension", {"prime": 2, "modulus": [1,1,1], "element": [0,1]}),
            ("analysis_integral", {"coefficients": [0,0,1], "lower": 0, "upper": 1}),
            ("graph_max_flow", {"vertices": ["s", "t"],
                                "edges": [["s", "t", "3/2"]],
                                "source": "s", "sink": "t"}),
            ("prob_binomial", {"trials": 3, "success_probability": "1/2"}),
        )
        for operation, kwargs in cases:
            notebook.append(session.execute(operation, **kwargs))
        self.assertEqual(notebook.replay(), len(cases))
        self.assertEqual(len(notebook.to_data()["cells"]),len(cases))

    def test_receipts_deterministic_for_same_request(self):
        session = CalculationSession()
        left = session.execute("graph_assignment", costs=[[3,1],[2,4]])
        right = session.execute("graph_assignment", costs=[[3,1],[2,4]])
        self.assertEqual(left.to_data(), right.to_data())
        self.assertEqual(left.to_data()["result"]["minimum_cost"],"3")

    def test_compatibility_public_contract_matches_runtime(self):
        from nablamath.calc.catalog import catalog
        from pathlib import Path
        contract = json.loads((Path(__file__).resolve().parents[2]/
                                "src/nablamath/public_api.json").read_text())
        self.assertEqual(contract["catalog"], catalog())


if __name__ == "__main__":
    unittest.main()
