import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from nablamath.cli import main
from nablamath.documents.document_model import Document, Section
from nablamath.documents.publication import verify_publication
from nablamath.export.bundle import verify_bundle
from nablamath.agents import Proposal as LegacyProposal, execute_proposal
from nablamath.agents.proposals import Proposal, Action
from nablamath.forge.reverse_builder import generate_task
from nablamath.core.semantic_ir import canonical_json


class WorkflowTests(unittest.TestCase):
    def call(self, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(args)

    def test_studio_and_dataset_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            document = Document('CLI report',(Section('Scope','Bounded synthetic test'),))
            (root/'document.json').write_text(json.dumps(document.to_data()))
            self.assertEqual(self.call(['studio',str(root/'document.json'),str(root/'article')]),0)
            self.assertTrue(verify_publication(root/'article'))
            self.assertEqual(self.call(['dataset-build',str(root/'dataset'),'--count','16','--license','CC0-1.0','--provenance','test']),0)
            self.assertTrue(verify_bundle(root/'dataset'))
            self.assertEqual(self.call(['dataset-check',str(root/'dataset')]),0)
            self.assertEqual(self.call(['evaluate-dataset',str(root/'dataset'),str(root/'learning.json'),'--benchmark','fixture']),0)
            report = json.loads((root/'learning.json').read_text())
            self.assertGreater(report['evaluation']['total'],0)
            self.assertIn('ablations',report)

    def test_world_and_agent_cli_and_legacy_api(self):
        self.assertEqual(execute_proposal(LegacyProposal('x+x',{'x':2},'compatibility')).value,4)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.call(['world-heat',str(root/'heat.json')]),0)
            self.assertEqual(self.call(['world-heat',str(root/'unstable.json'),'--cells','100','--steps','2']),1)
            self.assertFalse((root/'unstable.json').exists())
            task = generate_task('linear_system',42,2).task
            proposal = Proposal('Solve', (Action('solve1','solve',canonical_json({'task':task.to_data()})),),'Bounded')
            (root/'plan.json').write_text(json.dumps(proposal.to_data()))
            self.assertEqual(self.call(['agent',str(root/'plan.json'),str(root/'agent.json'),'--allow','solve']),0)
            self.assertTrue(json.loads((root/'agent.json').read_text())['completed'])
            (root/'bad.json').write_text('{}')
            self.assertEqual(self.call(['studio',str(root/'bad.json'),str(root/'bad-article')]),1)
