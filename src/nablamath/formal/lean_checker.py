"""Compile generated Lean and reject admissions, unmatched translations and nonstandard axioms."""
from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import signal
import subprocess
import tempfile

from ..core.semantic_ir import fingerprint
from .lean_bridge import translate_statement
from .translation_review import review_translation

ALLOWED_AXIOMS={'propext','Classical.choice','Quot.sound'}


def run_lean_process(command,*,cwd,env,timeout):
    """An isolated process group ensures a timeout also stops Lean spawned by Lake."""
    with subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          text=True,start_new_session=os.name!='nt') as process:
        try:
            stdout,stderr=process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name!='nt':
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            else:process.kill()
            process.communicate()
            raise
        return subprocess.CompletedProcess(command,process.returncode,stdout,stderr)


def find_lake(project):
    executable=shutil.which('lake')
    if executable:
        return Path(executable)
    project=Path(project).resolve()
    pin=(project/'lean-toolchain').read_text(encoding='utf-8').strip() if (project/'lean-toolchain').is_file() else ''
    match=re.fullmatch(r'leanprover/lean4:v([0-9]+\.[0-9]+\.[0-9]+)',pin)
    if match:
        candidate=project.parent.parent/'.tools'/'lean'/f'lean-{match[1]}-linux'/'bin'/'lake'
        if candidate.is_file():
            return candidate
    return None


@dataclass(frozen=True)
class LeanCheck:
    status: str
    statement_id: str
    source_hash: str
    tool_version: str | None
    axioms: tuple[str,...]
    diagnostics: str
    review: dict
    returncode: int | None=None
    strategy: str="auto"

    @property
    def verified(self):
        return self.status=='proved'

    def to_data(self):
        from dataclasses import asdict
        payload={**asdict(self),'backend':'lean4','formal_proof':self.verified}
        return {**payload,'receipt_id':fingerprint(payload)}


def check_lean(translation,project=Path('lean'),timeout=120):
    if type(timeout) is not int or not 1<=timeout<=300:
        raise ValueError('Timeout Lean deve estar entre 1 e 300 segundos')
    review=review_translation(translation)
    def result(status,detail,version=None,axioms=(),code=None):
        return LeanCheck(status,translation.statement.content_id,translation.source_hash,version,tuple(axioms),detail,review.to_data(),code,translation.strategy)
    if not review.accepted:
        return result('translation_rejected','; '.join(review.errors))
    project=Path(project).resolve()
    if not (project/'lean-toolchain').is_file() or not ((project/'lakefile.toml').is_file() or (project/'lakefile.lean').is_file()):
        return result('unavailable','Lean project missing')
    lake=find_lake(project)
    if lake is None:
        return result('unavailable','lake not installed')
    pin=(project/'lean-toolchain').read_text(encoding='utf-8').strip()
    expected=re.fullmatch(r'leanprover/lean4:v([0-9]+\.[0-9]+\.[0-9]+)',pin)
    if expected is None:
        return result('unavailable','Unsupported Lean toolchain pin')
    modules=('Ring','FieldSimp','Linarith','NormNum')
    base=project/'.lake/packages/mathlib/.lake/build/lib/lean/Mathlib/Tactic'
    missing=[name for name in modules if not (base/(name+'.olean')).is_file()]
    if missing:
        return result('unavailable','Mathlib prerequisites not built: '+', '.join(missing)+
                      '; run scripts/setup_formal.sh before evaluating proofs')
    environment=dict(os.environ)
    environment.pop('LEAN_PATH',None)
    environment.pop('LEAN_SRC_PATH',None)
    environment['PATH']=str(lake.parent)+os.pathsep+environment.get('PATH','')
    try:
        version=run_lean_process([str(lake),'env','lean','--version'],cwd=project,env=environment,
                                 timeout=min(timeout,20))
        if version.returncode:
            return result('unavailable',(version.stdout+version.stderr)[-4000:])
        if not re.search(r'Lean \(version '+re.escape(expected[1])+r'(?:,|\))',version.stdout):
            return result('unavailable','Compiler version does not match project pin',version.stdout.strip())
        with tempfile.TemporaryDirectory(prefix='nabla-prove-') as directory:
            source=Path(directory)/'Check.lean'
            source.write_text(translation.source,encoding='utf-8')
            completed=run_lean_process([str(lake),'env','lean',str(source)],cwd=project,env=environment,timeout=timeout)
    except FileNotFoundError:
        return result('unavailable','Lean runtime missing')
    except subprocess.TimeoutExpired:
        return result('timeout','Lean timeout')
    output=completed.stdout+'\n'+completed.stderr
    matches=re.findall(r"'nabla_generated' depends on axioms:\s*\[([^\]]*)\]",output)
    no_axioms="'nabla_generated' does not depend on any axioms" in output
    axioms=tuple(sorted({name.strip() for group in matches for name in group.split(',') if name.strip()}))
    if completed.returncode:
        return result('failed',output[-6000:],version.stdout.strip(),axioms,completed.returncode)
    if 'sorry' in output or set(axioms)-ALLOWED_AXIOMS or (not matches and not no_axioms):
        return result('rejected_axioms',output[-6000:],version.stdout.strip(),axioms,completed.returncode)
    return result('proved',output[-6000:],version.stdout.strip(),axioms,completed.returncode)


def prove_statement(statement,project=Path('lean'),strategy='auto',timeout=120):
    return check_lean(translate_statement(statement,strategy),project,timeout)
