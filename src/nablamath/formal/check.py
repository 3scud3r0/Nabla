"""Isolated Lean execution with timeouts and diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import subprocess
import re
import tempfile
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..research import ResearchResult
from ..symbolic.patterns import RewriteRule
from .translate import lean_source, rule_lean_source

@dataclass(frozen=True)
class FormalCheck:
    verified: bool
    detail: str
    content_id: str

def _verify_source(source_text: str, content_id: str, project: Path, timeout_s: int, success_detail: str) -> FormalCheck:
    project=project.resolve()
    if not (project/"lakefile.toml").is_file(): raise ValueError("Projeto Lean não encontrado")
    if type(timeout_s) is not int or not 1<=timeout_s<=900: raise ValueError("timeout fora do intervalo")
    from .lean_checker import find_lake, offline_mathlib_runtime, run_lean_process, ALLOWED_AXIOMS
    lake=find_lake(project)
    if lake is None: return FormalCheck(False,"lake não encontrado",content_id)
    try:
        compiler,environment,expected=offline_mathlib_runtime(project,lake)
    except ValueError as error:
        return FormalCheck(False,str(error),content_id)
    if any(token in source_text for token in ('sorry', 'admit', 'axiom ')):
        return FormalCheck(False,"Fonte com admissao ou axioma rejeitada",content_id)
    with tempfile.TemporaryDirectory(prefix="nablamath-lean-") as directory:
        source=Path(directory)/"Check.lean"; source.write_text(source_text,encoding="utf-8")
        try:
            version=run_lean_process([str(compiler),'--version'],cwd=project,env=environment,timeout=min(timeout_s,20))
            if version.returncode or not re.search(r'Lean \(version '+re.escape(expected)+r'(?:,|\))',version.stdout):
                return FormalCheck(False,"Compiler version does not match project pin",content_id)
            process=run_lean_process([str(compiler),str(source)],cwd=project,env=environment,timeout=timeout_s)
        except FileNotFoundError:
            return FormalCheck(False,"lake não encontrado",content_id)
        except subprocess.TimeoutExpired:
            return FormalCheck(False,"timeout",content_id)
    if "sorry" in process.stdout+process.stderr: return FormalCheck(False,"Admissao Lean rejeitada",content_id)
    if process.returncode: return FormalCheck(False,(process.stderr or process.stdout)[-2000:],content_id)
    output=process.stdout+'\n'+process.stderr
    matches=re.findall(r"depends on axioms:\s*\[([^\]]*)\]",output)
    axioms={name.strip() for group in matches for name in group.split(',') if name.strip()}
    if (axioms-ALLOWED_AXIOMS or (not matches and 'does not depend on any axioms' not in output)):
        return FormalCheck(False,"Auditoria de axiomas ausente ou rejeitada",content_id)
    return FormalCheck(True,success_detail,content_id)

def verify_with_lean(result: "ResearchResult", project: Path, timeout_s: int=120) -> FormalCheck:
    return _verify_source(lean_source(result),result.content_id,project,timeout_s,"Lean verificou a instância racional")

def verify_rule_with_lean(rule: RewriteRule, project: Path, timeout_s: int=120) -> FormalCheck:
    return _verify_source(rule_lean_source(rule),rule.rule_hash,project,timeout_s,"Lean verificou a regra universal")

__all__=["FormalCheck","verify_with_lean","verify_rule_with_lean"]
