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

GRAMMAR_VERSION = 'grounded-nlg-v3'


@dataclass(frozen=True)
class Production:
    weight: int
    text: str


GRAMMAR = {
    'plan': ((3, '<opening> {action}. {strategy}.'),),
    'opening': ((2, 'Vou'), (2, 'Quero'), (1, 'A ideia é'), (1, 'Nesta etapa, quero')),
    'attempt': ((2, 'Meu primeiro palpite é {candidate}. Vou conferir se ele satisfaz a relação original.'),
                (1, 'Estou considerando {candidate}; antes de seguir, quero testar esse valor na conta.'),
                (1, 'Por enquanto, fico com {candidate}. Agora vou verificar se fecha com os dados.'),
                (1, 'Uma possibilidade é {candidate}. Vou comparar esse palpite com a equação do problema.')),
    'check': ((2, 'Vou comparar esse palpite com o cálculo registrado e conferir os campos alterados.'),
              (1, 'Antes de aceitar esse valor, vou verificar como ele se compara ao resultado calculado.'),
              (2, 'Agora confiro o palpite com a operação e o resultado registrados.')),
    'diagnose': ((2, 'Opa, {diagnosis}.'),
                 (1, 'Já achei: {diagnosis}.'),
                 (1, 'O que não bate: {diagnosis}.')),
    'correct': ((2, 'Vou corrigir isso: {correction}.'),
                (1, 'Com a correção, {correction}.'),
                (1, 'O ajuste fica assim: {correction}.'),),
    'execute': ((2, 'Fazendo a conta com os dados declarados, obtenho {result}.'),
                (1, 'Seguindo as convenções do problema, chego a {result}.'),
                (1, 'Ao executar essa operação, encontro {result}.'),),
    'confirm': ((2, 'A checagem confirma o alcance desta etapa: {evidence}.'),
                (1, 'Com essa conferência, registro a conclusão: {evidence}.'),
                (1, 'Essa verificação sustenta o resultado neste passo: {evidence}.'),),
}


def _narrative_result(value, render_value):
    """Summarize common structured calculator results without dumping their payloads."""
    if isinstance(value, dict) and 'action' in value and 'result' in value:
        value = value['result']
    if isinstance(value, dict):
        if 'inverse' in value:
            return 'a inversa é ' + render_value(value['inverse'])
        if {'particular', 'rank', 'status'} <= set(value):
            size = len(value['particular']) if isinstance(value['particular'], list) else 0
            return (f"uma solução {value['status']} de posto {value['rank']} "
                    f"com vetor particular de {size} componentes")
        if {'determinant', 'rank'} <= set(value):
            return f"determinante {render_value(value['determinant'])} e posto {render_value(value['rank'])}"
        if {'identity', 'x', 'y'} <= set(value):
            return (f"{value['identity']}, com x = {render_value(value['x'])} "
                    f"e y = {render_value(value['y'])}")
    return render_value(value)


def _narrative_answer(value, render_value):
    if isinstance(value, list):
        return '; '.join(_narrative_answer(item, render_value) for item in value)
    if isinstance(value, dict):
        if {'identity', 'x', 'y'} <= set(value):
            return (f"x = {render_value(value['x'])}, y = {render_value(value['y'])}; "
                    f"a identidade {value['identity']} confere")
        if 'inverse' in value:
            return 'inversa: ' + render_value(value['inverse'])
    return _narrative_result(value, render_value)


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
        from .synthetic_cot_unroller import _natural_value, _natural_request
        from .synthetic_nlg_semantics import profile_for, describe_path, explain_difference
        events = []
        for step in record['steps']:
            dependencies = step.get('depends_on', [])
            if len(dependencies) != len(set(dependencies)) or any(type(i) is not int or not 1 <= i < step['index'] for i in dependencies):
                raise ValueError('Dependência narrativa inválida ou futura')
            error = step.get('error')
            if error:
                _validate_error_evidence(step)
            result = _narrative_result(step['receipt']['result'], _natural_value)
            certificate = step.get('certificate')
            evidence = 'a comparação coincide com o resultado calculado nesta etapa'
            if certificate:
                if certificate.get('independent_of_producing_solver'):
                    claims = certificate.get('claims', [])
                    claim_text = _natural_value(claims[0]) if isinstance(claims, list) and len(claims) == 1 else _natural_value(claims)
                    evidence = 'uma verificação adicional confirmou ' + claim_text.rstrip('. ')
                elif certificate.get('kind') == 'exact_residual':
                    evidence = 'ao substituir na equação, o resíduo exato foi ' + str(certificate['value'])
                elif certificate.get('kind') == 'deliberate_false_identity':
                    evidence = 'a comparação racional rejeitou a igualdade proposta'
                else:
                    evidence += '; certificado delimitado: ' + _natural_value(certificate)
            differences = error['detection']['differences'] if error else []
            candidate = '; '.join(
                describe_path(d['path']) + ': ' + _natural_value(d['observed'])
                for d in differences)
            corrections = []
            for difference in differences:
                where = describe_path(difference['path'])
                if where.startswith('entrada '):
                    corrections.append(f'a {where} fica em {_natural_value(difference["expected"])}')
                elif where.startswith('componente '):
                    corrections.append(f'a {where} fica em {_natural_value(difference["expected"])}')
                elif where == 'posto':
                    corrections.append(f'o posto passa a ser {_natural_value(difference["expected"])}')
                elif where == 'determinante':
                    corrections.append(f'o determinante passa a ser {_natural_value(difference["expected"])}')
                else:
                    corrections.append(f'o valor de {where} passa a ser {_natural_value(difference["expected"])}')
            correction = '; '.join(corrections)
            # Diagnose only the observed mismatch; the mutation label remains metadata.
            diagnosis = '; '.join(explain_difference(d, _natural_value) for d in differences) if error else ''
            profile = profile_for(step['receipt']['request'])
            strategy = profile.strategy if profile else 'vou seguir a operação e os parâmetros declarados'
            strategy = strategy[:1].upper() + strategy[1:]
            slots = {'action': profile.goal if profile else _natural_request(step['receipt']['request']).replace('**', '^'),
                     'result': result, 'candidate': candidate or 'uma estrutura diferente do resultado calculado',
                     'correction': correction or result,
                     'strategy':strategy,
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
                 'O texto a seguir é uma simulação narrativa em primeira pessoa, montada a partir de cálculos e verificações registrados. Não é um relato de pensamento espontâneo nem de raciocínio interno de uma rede neural.']
        if record.get('challenge_profile'):
            lines.append('Carga matemática: ' + record['challenge_profile']['burden'])
        grouped = {}
        for event in self.events(record):
            grouped.setdefault(event['step'], []).append(event)
        for step in record['steps']:
            lines += ['', f"{step['description']}"]
            lines += [event['text'] for event in grouped[step['index']]]
            from .synthetic_nlg_semantics import profile_for
            profile = profile_for(step['receipt']['request'])
            if profile:
                lines.append('Só preciso tomar cuidado com um ponto: ' + profile.caution + '.')
        lines += ['', 'Resposta final: ' + _narrative_answer(record['answer'], _natural_value),
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
