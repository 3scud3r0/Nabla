"""Regenerate bounded action inventory; execution evidence lives in the V1 report."""
import hashlib
import json
from pathlib import Path
from nablamath.ops.advanced_math import ACTIONS

ROOT=Path(__file__).resolve().parents[1]


def build():
    actions=[]
    for name,entry in ACTIONS.items():
        module,function=entry['path'].split(':')
        encoded=json.dumps(entry['schema'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        actions.append({'action':name,'module':module,'function':function,
            'source':'src/nablamath/'+module.replace('.','/')+'.py',
            'parameter_schema_sha256':hashlib.sha256(encoded).hexdigest(),
            'validation_status':'see_version_1_validation_not_individual_certification'})
    manifest={'schema_version':1,
              'scope':'Authored bounded computational implementations; no universal mathematical completeness claim',
              'test_execution':'see_version_1_validation',
              'validation_report':'docs/releases/V1_VALIDATION.md',
              'scientific_acceptance_established':False,'catalog_entry':'advanced_math','actions':actions}
    (ROOT/'src/nablamath/mathematical_expansion.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return {'advanced_actions':len(actions)}


if __name__=='__main__':
    print(json.dumps(build()))
