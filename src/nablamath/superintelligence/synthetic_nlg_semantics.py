"""Closed semantic profiles for narration: methods, risks and scoped evidence.

Profiles guide a plan; they do not assert that an invariant was checked. The
confirmation is generated separately from the actual certificate and receipt.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticProfile:
    goal: str
    strategy: str
    caution: str


PROFILES = {
    'solve_linear': SemanticProfile(
        'resolver o sistema linear',
        'vou preservar a ordem das incógnitas durante a eliminação racional',
        'a existência de um vetor solução não certifica, por si só, sua unicidade'),
    'matrix_properties': SemanticProfile(
        'extrair os invariantes matriciais',
        'determinante, posto e menores devem ser distinguidos',
        'determinante positivo isolado não basta para concluir positividade definida'),
    'matrix_inverse': SemanticProfile(
        'encontrar a inversa da matriz',
        'a verificação apropriada é conferir os produtos nos dois sentidos',
        'uma matriz singular não admite inversa bilateral'),
    'differentiate': SemanticProfile(
        'derivar a expressão composta',
        'vou respeitar produto, cadeia e restrições declaradas',
        'cancelamentos algébricos não autorizam ampliar o domínio'),
    'rational_compare': SemanticProfile(
        'comparar as funções racionais',
        'vou separar igualdade no domínio comum da equivalência de domínios',
        'a identidade de numeradores reduzidos não apaga pontos originalmente excluídos'),
    'nt_pell': SemanticProfile(
        'resolver a equação diofantina',
        'os convergentes da fração contínua produzem candidatos inteiros',
        'a substituição certifica a identidade, não a minimalidade do candidato'),
    'modules.presentation': SemanticProfile(
        'decompor o módulo apresentado',
        'a forma de Smith separa parte livre e fatores invariantes de torção',
        'a ordem do grupo não determina seus fatores invariantes'),
    'homological.complex': SemanticProfile(
        'calcular a homologia do complexo',
        'primeiro importam as formas dos bordos e a condição d²=0',
        'núcleo e imagem precisam ser comparados no mesmo grau'),
    'homological.homotopy': SemanticProfile(
        'verificar a homotopia de cadeias',
        'vou conferir a identidade f−g=dh+hd em cada grau',
        'as dimensões dos mapas que elevam o grau fazem parte da verificação'),
    'representations.decompose': SemanticProfile(
        'decompor a representação pelos caracteres',
        'o produto interno dos caracteres fornece as multiplicidades',
        'a família irreducível precisa ser validada e sua completude é uma afirmação separada'),
    'representations.intertwiners': SemanticProfile(
        'determinar os intertwiners',
        'as equações TA_g=B_gT formam um único sistema homogêneo',
        'trocar a ordem dos fatores altera o sistema e seu espaço de soluções'),
    'lie.structure': SemanticProfile(
        'investigar a estrutura da álgebra de Lie',
        'vou distinguir Jacobi, centro, álgebra derivada e forma de Killing',
        'uma álgebra perfeita pode ter radical não nulo e não ser semissimples'),
    'lie.pbw': SemanticProfile(
        'reordenar a palavra na base PBW',
        'cada permuta de geradores deve incluir o termo de comutador correspondente',
        'o produto no envolvente universal não é comutativo'),
    'lie.decomposition': SemanticProfile(
        'separar radical e quociente semissimples',
        'as séries de ideais e a degenerescência de Killing devem ser interpretadas juntas',
        'degenerescência da forma não significa que a álgebra inteira seja solúvel'),
    'schemes.eliminate': SemanticProfile(
        'eliminar os parâmetros do ideal',
        'uma ordem lexicográfica apropriada separa variáveis eliminadas e remanescentes',
        'o ideal de eliminação descreve um fecho algébrico, não toda informação da imagem construtível'),
    'schemes.affine': SemanticProfile(
        'estudar o esquema afim',
        'a base de Gröbner controla o ideal e sua dimensão',
        'o conjunto de zeros sozinho não determina a estrutura não reduzida'),
    'schemes.saturate': SemanticProfile(
        'saturar o ideal pelo denominador',
        'a variável auxiliar implementa a localização no aberto principal',
        'remover uma componente não equivale a autorizar divisão em todos os pontos'),
    'topology.integral_homology': SemanticProfile(
        'determinar a homologia integral',
        'os bordos orientados e a forma de Smith preservam a informação de torção',
        'o posto racional não detecta somandos cíclicos finitos'),
    'topology.integral_cohomology': SemanticProfile(
        'determinar a cohomologia integral',
        'o teorema dos coeficientes universais relaciona graus adjacentes',
        'a torção pode aparecer em grau diferente do observado na homologia'),
    'geometry.pullback': SemanticProfile(
        'transportar a métrica para a nova carta',
        'vou usar JᵀgJ com as coordenadas na ordem declarada',
        'a carta só pode ser usada onde o jacobiano tem posto apropriado'),
    'geometry.covariant': SemanticProfile(
        'calcular a derivada covariante',
        'o termo de conexão complementa as derivadas das componentes vetoriais',
        'derivadas parciais de componentes não são, em geral, uma derivada tensorial'),
    'forms.derivative': SemanticProfile(
        'aplicar a derivada exterior',
        'os índices devem ser reordenados com o sinal da permutação',
        'a antissimetria não permite substituir produtos exteriores por produtos escalares'),
    'forms.pullback': SemanticProfile(
        'transportar a forma diferencial',
        'a substituição dos coeficientes acompanha os menores orientados do jacobiano',
        'substituir apenas as coordenadas e omitir os diferenciais daria uma forma incorreta'),
    'forms.integrate': SemanticProfile(
        'integrar a forma orientada',
        'a integração iterada usa os intervalos e a orientação fornecidos',
        'inverter orientação muda o sinal da integral'),
    'stochastic.ito': SemanticProfile(
        'aplicar Itô multivariado',
        'vou conservar todos os termos da covariação BBᵀ na contração com a Hessiana',
        'Brownianos independentes não tornam a covariação do estado automaticamente diagonal'),
    'autograd.jet': SemanticProfile(
        'obter o jet multivariado',
        'cada multiíndice identifica uma derivada e sua ordem total',
        'derivadas avaliadas em um ponto não certificam uma identidade global'),
    'variations.density': SemanticProfile(
        'derivar as equações dos campos',
        'as derivadas totais dos momentos geram as equações e os fluxos de fronteira',
        'a condição de Legendre não estabelece sozinha um mínimo global'),
    'complex.meromorphic': SemanticProfile(
        'obter a expansão local no polo',
        'a parte principal deve ser separada do coeficiente de ordem menos um',
        'uma expansão local não classifica automaticamente singularidades em todo o plano'),
    'functional_analysis': SemanticProfile(
        'construir a projeção ortogonal ponderada',
        'o sistema de Gram impõe ortogonalidade do resíduo às direções da base',
        'a métrica ponderada não pode ser substituída silenciosamente pela euclidiana'),
    'distributions.derivative': SemanticProfile(
        'diferenciar a distribuição singular',
        'a ordem de cada derivada de Dirac aumenta segundo a ordem solicitada',
        'a distribuição é avaliada por dualidade, não como função pontual'),
    'distributions.pairing': SemanticProfile(
        'avaliar a distribuição no germe de teste',
        'cada derivada de Dirac contribui com o sinal (−1)^k e o jet no suporte',
        'o sinal da dualidade não pode ser removido quando a ordem é ímpar'),
    'distributions.fourier': SemanticProfile(
        'transformar a distribuição',
        'a convenção declarada liga a derivada à multiplicação por iω',
        'a normalização e o sinal da exponencial precisam acompanhar a fórmula'),
    'markov_hitting': SemanticProfile(
        'calcular a absorção e seus momentos',
        'os sistemas de primeiro passo devem distinguir os eventos de atingir cada alvo',
        'esperança condicional finita não implica esperança incondicional finita'),
    'markov_rewards': SemanticProfile(
        'resolver a equação descontada de Bellman',
        'vou manter a convenção por linhas de P no produto Pv',
        'a normalização de P e o desconto fazem parte das hipóteses'),
    'graph_max_flow': SemanticProfile(
        'certificar o fluxo máximo',
        'a igualdade fluxo–corte fornece o vínculo entre a construção e a cota superior',
        'um fluxo viável isolado não demonstra otimalidade'),
    'optimization.certificate': SemanticProfile(
        'verificar o certificado primal-dual',
        'viabilidade e lacuna nula devem ser conferidas nas convenções declaradas',
        'objetivos numericamente próximos não substituem igualdade racional exata'),
    'analysis_pade': SemanticProfile(
        'construir a aproximação racional de Padé',
        'o produto da série de Taylor pelo denominador deve casar os coeficientes prescritos',
        'casamento formal de Taylor não é uma cota uniforme de aproximação'),
    'integral_equations': SemanticProfile(
        'resolver a equação integral de posto finito',
        'os momentos do núcleo reduzem o problema a um sistema racional',
        'um resíduo discreto em poucos pontos não certifica a equação integral completa'),
}


def profile_for(request):
    key = request['arguments'].get('action') if request['operation'] == 'advanced_math' else request['operation']
    return PROFILES.get(key)


PATH_WORDS = {
    'result':'resultado', 'particular':'solução particular', 'inverse':'inversa',
    'determinant':'determinante', 'dimension':'dimensão', 'rank':'posto',
    'numerator':'numerador', 'denominator':'denominador', 'value':'valor',
    'normal_left':'forma normal à esquerda', 'normal_right':'forma normal à direita',
    'probability':'probabilidade', 'probabilities':'probabilidades', 'states':'estados',
    'coefficients':'coeficientes', 'duality_gap':'lacuna de dualidade',
    'betti_numbers':'números de Betti', 'torsion':'torção', 'free_rank':'posto livre',
    'multiplicities':'multiplicidades', 'killing_form':'forma de Killing',
    'domain_equivalence_established':'equivalência de domínio estabelecida',
    'equal_on_common_domain':'igualdade no domínio comum',
    'characteristic_polynomial':'polinômio característico',
    'shape':'dimensão', 'status':'situação', 'nullspace':'núcleo',
    'particular':'solução particular', 'pivots':'pivôs',
    'obligations':'condições', 'expression':'expressão',
}


def describe_path(path):
    if not path:
        return 'estrutura do resultado'
    if len(path) == 3 and path[0] in {'inverse', 'matrix'} and all(type(part) is int for part in path[1:]):
        name = PATH_WORDS.get(path[0], path[0])
        return f"entrada ({path[1] + 1}, {path[2] + 1}) da {name}"
    return ' → '.join(f'componente {part + 1}' if type(part) is int
                      else PATH_WORDS.get(part, str(part).replace('_', ' ')) for part in path)


def explain_difference(difference, render_value):
    where = describe_path(difference['path'])
    return (f"em {where}, eu propus {render_value(difference['observed'])}, "
            f"mas o cálculo registrado dá {render_value(difference['expected'])}")
