"""Seeded weighted grammar and evidence-grounded narrative state machine.

This is an authored explanation of a computation, not recovered neural CoT.
Randomness changes wording only. Claims and transitions come from receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random
import re
from string import Formatter

GRAMMAR_VERSION = 'grounded-nlg-v1'


@dataclass(frozen=True)
class Production:
    weight: int
    text: str


GRAMMAR = {
    'plan': ((3, '<opening> {action}. {strategy}. <discipline>'),),
    'opening': ((2, 'Vamos começar por'), (2, 'A estratégia desta etapa é'),
                (1, 'O próximo objetivo é'), (1, 'Para avançar, precisamos de')),
    'discipline': ((2, 'Vou preservar as hipóteses de domínio durante o cálculo.'),
                   (1, 'Os dados desta etapa fixam o alcance da conclusão.')),
    'attempt': ((2, 'Introduzimos uma tentativa deliberadamente alterada: {candidate}.'),
                (1, 'Vamos explorar o efeito de uma falha controlada: {candidate}.'),
                (1, 'O candidato rotulado como incorreto contém esta alteração: {candidate}.'),
                (1, 'Antes de aceitar o cálculo, vamos testar o candidato sintético: {candidate}.')),
    'check': ((2, 'Antes de prosseguir, verifico a consistência com a requisição original: {check}.'),
              (1, 'A aceitação depende da checagem, que consiste em {check}.'),
              (2, 'Agora submeto a tentativa à checagem registrada: {check}.')),
    'diagnose': ((2, 'A divergência ficou localizada: {diagnosis}.'),
                 (1, 'A comparação fornece um diagnóstico concreto: {diagnosis}.'),
                 (1, 'O teste rejeitou a tentativa. O ponto concreto é este: {diagnosis}.')),
    'correct': ((2, 'Refazendo essa escolha, conservamos {result}.'),
                (1, 'Descarto a alteração rejeitada. O resultado que permanece é {result}.'),
                (1, 'A correção é substituir o candidato pelo resultado reexecutado: {result}.')),
    'execute': ((2, 'Com os dados declarados, o cálculo resulta em {result}.'),
                (1, 'Mantendo as convenções do problema, chegamos a {result}.'),
                (1, 'Efetuando a operação indicada, obtemos {result}.')),
    'confirm': ((2, 'A conclusão desta etapa está limitada à evidência disponível: {evidence}.'),
                (1, 'O recibo sustenta a seguinte conclusão delimitada: {evidence}.'),
                (1, 'Podemos registrar o resultado com este alcance: {evidence}.')),
}


class WeightedGrammar:
    """Small weighted CFG with closed slots, bounded expansion and provenance."""
    def __init__(self, rules=None):
        self.rules = {name: tuple(Production(*p) for p in productions)
                      for name, productions in (GRAMMAR if rules is None else rules).items()}
        for name, productions in self.rules.items():
            if not productions or any(type(p.weight) is not int or p.weight <= 0 for p in productions):
                raise ValueError('Produções devem ter pesos inteiros positivos: ' + name)
            for p in productions:
                if any(symbol not in self.rules for symbol in re.findall(r'<([a-z_]+)>', p.text)):
                    raise ValueError('Não terminal desconhecido')

    def expand(self, symbol, slots, rng):
        used = []
        def visit(name, depth):
            if depth > 12 or len(used) >= 64:
                raise ValueError('Orçamento da gramática excedido')
            productions = self.rules[name]
            ticket = rng.randrange(sum(p.weight for p in productions))
            for index, production in enumerate(productions):
                ticket -= production.weight
                if ticket < 0:
                    break
            used.append(f'{name}:{index}')
            text = re.sub(r'<([a-z_]+)>', lambda match: visit(match[1], depth+1), production.text)
            fields = [field for _, field, _, _ in Formatter().parse(text) if field is not None]
            if any(field not in slots or not field.isidentifier() for field in fields):
                raise ValueError('Slot sem evidência ou acesso de atributo proibido')
            # Insert data only after grammar expansion; braces in math are data.
            return text
        template = visit(symbol, 0)
        return template.format_map(slots), used


_TRANSITIONS = {
    None: {'plan'}, 'plan': {'attempt', 'execute'}, 'attempt': {'check'},
    'check': {'diagnose'}, 'diagnose': {'correct'}, 'correct': {'confirm'},
    'execute': {'confirm'}, 'confirm': set(),
}


class ProceduralNarrator:
    """A deterministic finite-state narrator whose slots contain observed facts."""
    def __init__(self, wording_seed=0):
        if type(wording_seed) is not int or not 0 <= wording_seed < 2**63:
            raise ValueError('wording_seed deve ser inteiro não negativo de 63 bits')
        self.seed = wording_seed
        self.grammar = WeightedGrammar()

    def events(self, record):
        # Lazy import prevents the formatter/narrator import cycle.
        from .synthetic_cot_unroller import _natural_value, _natural_request, _mutation_prose
        from .synthetic_nlg_semantics import profile_for, describe_path, explain_difference
        events = []
        for step in record['steps']:
            dependencies = step.get('depends_on', [])
            if len(dependencies) != len(set(dependencies)) or any(type(i) is not int or not 1 <= i < step['index'] for i in dependencies):
                raise ValueError('Dependência narrativa inválida ou futura')
            error = step.get('error')
            if error:
                _validate_error_evidence(step)
            result = _natural_value(step['receipt']['result'])
            certificate = step.get('certificate')
            evidence = 'concordância com a reexecução do mesmo motor; não é prova independente'
            if certificate:
                if certificate.get('independent_of_producing_solver'):
                    evidence = 'verificação de referência adicional: ' + _natural_value(certificate.get('claims', []))
                elif certificate.get('kind') == 'exact_residual':
                    evidence = 'substituição com resíduo exato ' + str(certificate['value'])
                elif certificate.get('kind') == 'deliberate_false_identity':
                    evidence = (_mutation_prose(certificate.get('mutation', '')) +
                                ' testada como identidade falsa por comparação racional')
                else:
                    evidence += '; certificado delimitado: ' + _natural_value(certificate)
            differences = error['detection']['differences'] if error else []
            candidate = '; '.join(
                describe_path(d['path']) + ', valor proposto ' + _natural_value(d['observed'])
                for d in differences)
            # A numeric mutation is never relabelled as a dimensional or physical error.
            diagnosis = (_mutation_prose(error['mutation']['kind']) + '; ' +
                         '; '.join(explain_difference(d, _natural_value) for d in differences)) if error else ''
            profile = profile_for(step['receipt']['request'])
            strategy = ('Estratégia: ' + profile.strategy) if profile else 'A operação e seus parâmetros definem o método desta etapa'
            check = 'comparar o resultado com a reexecução do catálogo'
            if error and error['detection'].get('reference_check', {}).get('status') == 'rejects_candidate':
                check += '; a referência racional adicional também rejeitou o candidato nas afirmações que ela cobre'
            slots = {'action': profile.goal if profile else _natural_request(step['receipt']['request']).replace('**', '^'),
                     'result': result, 'candidate': candidate or 'estrutura divergente do recibo',
                     'check': check, 'strategy':strategy,
                     'diagnosis': diagnosis, 'evidence': evidence}
            states = ('plan', 'attempt', 'check', 'diagnose', 'correct', 'confirm') if error else ('plan', 'execute', 'confirm')
            previous = None
            for state in states:
                if state not in _TRANSITIONS[previous]:
                    raise ValueError('Transição narrativa inválida')
                seed = hashlib.sha256(f'{GRAMMAR_VERSION}|{self.seed}|{record["id"]}|{step["index"]}|{state}'.encode()).digest()
                text, productions = self.grammar.expand(state, slots, random.Random(int.from_bytes(seed, 'big')))
                events.append({'step':step['index'], 'state':state, 'text':text,
                               'receipt_id':step['receipt']['content_id'], 'productions':productions,
                               'depends_on':dependencies})
                previous = state
        return events

    def render(self, record):
        from .synthetic_cot_unroller import _natural_value, _natural_prompt
        # Generic recipes previously embedded raw request JSON in their prompt.
        prompt = _natural_prompt(record)
        lines = [prompt, '', 'Método: ' + record['method'],
                 'Narração procedural sintética, produzida por gramática; não representa pensamento interno de uma rede neural.']
        if record.get('challenge_profile'):
            lines.append('Carga matemática: ' + record['challenge_profile']['burden'])
        grouped = {}
        for event in self.events(record):
            grouped.setdefault(event['step'], []).append(event)
        for step in record['steps']:
            lines += ['', f"Etapa {step['index']} — {step['description']}"]
            arguments = step['receipt']['request']['arguments']
            lines.append('Dados: ' + _natural_value(arguments))
            labels = {'plan':'Plano', 'attempt':'Tentativa sintética', 'check':'Checagem',
                      'diagnose':'Diagnóstico do verificador', 'correct':'Correção',
                      'execute':'Cálculo', 'confirm':'Confirmação'}
            lines += [labels[event['state']] + ': ' + event['text'] for event in grouped[step['index']]]
            from .synthetic_nlg_semantics import profile_for
            profile = profile_for(step['receipt']['request'])
            if profile:
                lines.append('Cuidado de interpretação: ' + profile.caution + '.')
            lines.append('Recibo: ' + step['receipt']['content_id'])
        lines += ['', 'Resposta final: ' + _natural_value(record['answer']),
                  'Dificuldade: perfil avançado autorado, não calibrado por comparação externa. '
                  'Validade e utilidade de treino não se inferem do comprimento ou da fluência.']
        return '\n'.join(lines)


def _validate_error_evidence(step):
    """Reject narrative contradictions instead of beautifying forged metadata."""
    from .synthetic_cot_unroller import _leaves
    error = step['error']
    detection = error['detection']
    if detection['accepted'] or not error.get('synthetic'):
        raise ValueError('Uma correção exige candidato sintético rejeitado')
    expected = dict(_leaves(step['receipt']['result']))
    observed = dict(_leaves(error['candidate']))
    differences = {path:(expected.get(path),observed.get(path))
                   for path in set(expected)|set(observed)
                   if path not in expected or path not in observed or expected[path] != observed[path]}
    entries = detection['differences']
    reported = {tuple(d['path']):(d['expected'],d['observed']) for d in entries}
    if not differences or len(reported) != len(entries) or reported != differences:
        raise ValueError('Diagnóstico sem correspondência com o candidato e o recibo')
