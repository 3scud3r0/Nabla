from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from nablamath.forge.reverse_builder import generate_task
from nablamath.datasets.schema import make_record, ScientificRecord
from nablamath.datasets.curation import curate
from nablamath.datasets.serializer import dumps, loads
from nablamath.datasets.quality_gate import quality_gate
from nablamath.datasets.split_policy import audit
from nablamath.export.bundle import export_bundle, verify_bundle
from nablamath.export.huggingface import prepare_hub


def record(family='linear_system', seed=71):
    generated = generate_task(family, seed, 2)
    return make_record(generated.task, generated.witness, license_id='CC0-1.0',
                       provenance='test generator seed '+str(seed), scope='bounded exact tasks',
                       limitations='synthetic; no demonstrated learning gain', attempts=({},))


class DatasetTests(unittest.TestCase):
    def test_strict_roundtrip_and_reexecution(self):
        r = record()
        self.assertEqual(loads(dumps([r]))[0], r)
        row = r.to_data()
        row['trace']['candidate']['solution'][0] = '999'
        with self.assertRaises(ValueError):
            ScientificRecord.from_data(row)
        for key in ('license_id', 'provenance', 'scope', 'limitations'):
            row = r.to_data(); row[key] = ''
            with self.subTest(key=key), self.assertRaises(ValueError):
                ScientificRecord.from_data(row)
        self.assertFalse(r.to_data()['attempts'][0]['verification']['valid'])

    def test_curate_dedup_rejections_and_family_holdout(self):
        candidates = [record(family, seed) for family in ('linear_system', 'factored_polynomial',
                      'polynomial_integral', 'convex_quadratic') for seed in (2, 9)]
        curated, report = curate([*candidates, candidates[0], {'invalid': True}])
        self.assertTrue(report['accepted'])
        self.assertEqual(len(report['rejected']), 2)
        self.assertEqual(len(curated), 8)
        self.assertTrue(audit(curated)['clean'])
        leaked = [curated[0].with_split('train'), curated[0].with_split('test')]
        self.assertFalse(audit(leaked)['clean'])
        self.assertFalse(quality_gate(leaked)['accepted'])

    def test_bundle_replays_partitions_and_card(self):
        records, _ = curate([record('linear_system'), record('factored_polynomial')])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'dataset'
            export_bundle(records, root)
            self.assertTrue(verify_bundle(root))
            self.assertFalse(prepare_hub(root)['publication_performed'])
            card = json.loads((root/'card.json').read_text())
            self.assertEqual(card['training_gain'], 'not_established')
            (root/'train.jsonl').write_text('forged')
            manifest = json.loads((root/'manifest.json').read_text())
            manifest['files']['train.jsonl'] = hashlib.sha256(b'forged').hexdigest()
            (root/'manifest.json').write_text(json.dumps(manifest))
            self.assertFalse(verify_bundle(root))

    def test_parquet_lossless_and_metadata_crosscheck(self):
        try:
            import pyarrow
        except ImportError:
            self.skipTest('Arrow opcional')
        from nablamath.export.parquet import write_parquet, read_parquet
        records, _ = curate([record(), record('factored_polynomial')])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_parquet(records, root/'records.parquet')
            self.assertEqual(records, read_parquet(root/'records.parquet'))
            export_bundle(records, root/'bundle', parquet=True)
            self.assertTrue(verify_bundle(root/'bundle'))

    def test_artifact_traversal_hash_and_defects(self):
        r = record()
        row = r.to_data()
        row['artifacts'] = [{'path': '../bad', 'sha256': '0'*64, 'modality': 'text', 'task_id': r.task.content_id}]
        with self.assertRaises(ValueError):
            ScientificRecord.from_data(row)
        row = r.to_data(); row['defects'] = ['known invalid labels']
        self.assertFalse(quality_gate([ScientificRecord.from_data(row)], require_partitions=False)['accepted'])

    def test_aligned_artifact_is_recomputed_even_if_hash_is_updated(self):
        from nablamath.datasets.multimodal import build_sample
        r = record()
        diagram = next(m['content'] for m in build_sample(r).to_data()['modalities'] if m['kind']=='diagram')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'diagram.svg').write_text(diagram)
            row = r.to_data()
            row['artifacts'] = [{'path':'diagram.svg','sha256':hashlib.sha256(diagram.encode()).hexdigest(),
                                 'modality':'diagram','task_id':r.task.content_id}]
            linked = ScientificRecord.from_data(row).with_split('train')
            self.assertTrue(quality_gate([linked],asset_root=root)['accepted'])
            export_bundle([linked],root/'bundle',asset_root=root)
            self.assertTrue(verify_bundle(root/'bundle'))
            (root/'diagram.svg').write_text('unrelated')
            row['artifacts'][0]['sha256'] = hashlib.sha256(b'unrelated').hexdigest()
            self.assertFalse(quality_gate([ScientificRecord.from_data(row)],asset_root=root,require_partitions=False)['accepted'])

    def test_hub_upload_is_an_explicit_separate_operation(self):
        from unittest.mock import Mock, patch
        import sys, types
        from nablamath.export.huggingface import upload_bundle
        records, _ = curate([record()])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'bundle'
            export_bundle(records,root)
            api = Mock()
            with patch.dict(sys.modules, {'huggingface_hub':types.SimpleNamespace(HfApi=Mock(return_value=api))}):
                upload_bundle(root,'owner/test',private=True)
            api.create_repo.assert_called_once_with(repo_id='owner/test',repo_type='dataset',private=True,exist_ok=True)
            self.assertEqual(api.upload_folder.call_count,1)
            self.assertEqual(api.upload_file.call_args.kwargs['path_in_repo'],'README.md')
