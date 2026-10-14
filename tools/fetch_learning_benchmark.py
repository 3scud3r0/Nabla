"""Fetch the public MIT GSM8K snapshot over verified HTTPS, pinning its Git commit."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

COMMIT='3101c7d5072418e28b9008a6636bde82a006892c'
ROOT_URL=f'https://raw.githubusercontent.com/openai/grade-school-math/{COMMIT}/'
FILES={'LICENSE':'LICENSE','train.jsonl':'grade_school_math/data/train.jsonl','test.jsonl':'grade_school_math/data/test.jsonl'}


def fetch(destination):
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.gsm8k-',dir=destination.parent))
    try:
        for name,path in FILES.items():
            subprocess.run(['curl','--fail','--location','--proto','=https','--tlsv1.2','--max-time','90',
                            ROOT_URL+path,'--output',str(stage/name)],check=True)
        if not (stage/'LICENSE').read_text(encoding='utf-8').startswith('MIT License'):
            raise ValueError('Unexpected benchmark license; inspect source')
        manifest={'dataset':'GSM8K','repository':'https://github.com/openai/grade-school-math','commit':COMMIT,
                  'license_id':'MIT','sources':{name:ROOT_URL+path for name,path in FILES.items()},
                  'files':{name:hashlib.sha256((stage/name).read_bytes()).hexdigest() for name in FILES}}
        (stage/'source-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8')
        stage.rename(destination)
        return manifest
    finally:
        if stage.exists():shutil.rmtree(stage)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    print(json.dumps(fetch(parser.parse_args().destination),sort_keys=True))
