"""Named advanced actions: one audited catalog entry, closed per-action inputs.

All imports are lazy. The registry is an allowlist, never a request import path.
Function APIs remain independently usable; this dispatcher supplies receipts and
the MCP/CLI/notebook contract for the new mathematical implementations.
"""
from importlib import import_module
from copy import deepcopy


def arr(item,maximum=4096,minimum=0):
    return {'type':'array','items':deepcopy(item),'maxItems':maximum,'minItems':minimum}


def obj(fields,required=None):
    return {'type':'object','properties':deepcopy(fields),'required':list(fields if required is None else required),'additionalProperties':False}


def mapping(item):return {'type':'object','maxProperties':256,'additionalProperties':deepcopy(item)}


N={'type':'number'};I={'type':'integer'};B={'type':'boolean'}
T={'type':'string','maxLength':8192};Q={'anyOf':[I,{'type':'string','maxLength':1235,'pattern':r'^[+-]?\d+(?:/\d+|\.\d+)?$'}]}
V=arr(Q);NV=arr(N);M=arr(V,256);NM=arr(NV,256);S=arr(T,32)
EX={'anyOf':[N,T]};EV=arr(EX);EM=arr(EV,32);TENSOR=arr(M,32)
FACETS=arr(arr(I,8,1),128,1);FORM=mapping(EX)
PROPOSITION={'$ref':'#/$defs/proposition'};PROOF={'$ref':'#/$defs/proof'};TERM={'$ref':'#/$defs/term'}
MODEL={'$ref':'#/$defs/model_formula'};ALGTERM={'$ref':'#/$defs/algebra_term'}
RESTRICTIONS=arr(obj({'from':T,'to':T,'matrix':M}),256)
BOUNDARY=obj({'kind':{'enum':['dirichlet','neumann','robin']},'value':N,'alpha':N},['kind','value'])
JUMP=arr(obj({'source':T,'terminal':B,'direction':N},['source']),16)
ACTIONS={}


def _add(name,path,fields,required=None):
    ACTIONS[name]={'path':path,'schema':obj(fields,required)}


_add('representations.validate','math.algebra.representations:representation',{'table':arr(arr(I,64,1),64,1),'matrices':TENSOR})
_add('representations.intertwiners','math.algebra.representations:intertwiners',{'left':TENSOR,'right':TENSOR})
_add('representations.characters','math.algebra.representations:character_inner_product',{'left':V,'right':V})
_add('modules.presentation','math.algebra.modules:presentation',{'relations':M,'generators':I},['relations'])
_add('modules.homomorphism','math.algebra.modules:rational_homomorphism',{'matrix':M})
_add('modules.resolution','math.algebra.modules:finite_free_resolution',{'relations':M})
_add('homological.complex','math.algebra.homological:chain_complex',{'dimensions':arr(I,16,1),'differentials':TENSOR})
_add('homological.chain_map','math.algebra.homological:chain_map',{'source_dimensions':arr(I,16,1),'source_differentials':TENSOR,'target_dimensions':arr(I,16,1),'target_differentials':TENSOR,'maps':TENSOR})
_add('homological.ext_tor','math.algebra.homological:cyclic_ext_tor',{'m':I,'n':I})
_add('schemes.affine','math.geometry.schemes:affine_scheme',{'equations':S,'variables':S})
_add('schemes.eliminate','math.geometry.schemes:eliminate',{'equations':S,'variables':S,'remove':S})
_add('schemes.saturate','math.geometry.schemes:saturate',{'equations':S,'variables':S,'denominator':EX})
_add('schemes.primary','math.geometry.schemes:univariate_primary',{'polynomial':EX,'variable':T},['polynomial'])
_add('schemes.projective_chart','math.geometry.schemes:projective_chart',{'equations':S,'variables':S,'index':I})
_add('sheaves.sections','math.geometry.sheaves:global_sections',{'dimensions':mapping(I),'restrictions':RESTRICTIONS})
_add('sheaves.cech','math.geometry.sheaves:cech_cohomology',{'cover_size':I,'intersections':mapping(T),'dimensions':mapping(I),'restrictions':RESTRICTIONS})
_add('forms.derivative','math.geometry.differential_forms:exterior_derivative',{'coordinates':S,'components':FORM})
_add('forms.wedge','math.geometry.differential_forms:wedge',{'coordinates':S,'left':FORM,'right':FORM})
_add('forms.pullback','math.geometry.differential_forms:pullback',{'source_coordinates':S,'target_coordinates':S,'mapping':S,'components':FORM})
_add('forms.integrate','math.geometry.differential_forms:integrate_box',{'coordinates':S,'components':FORM,'bounds':arr(arr(Q,2,2),8,1)})
_add('bundles.verify','math.geometry.fiber_bundles:verify_bundle',{'charts':S,'transitions':RESTRICTIONS,'triples':arr(arr(T,3,3),256)},['charts','transitions'])
_add('bundles.sections','math.geometry.fiber_bundles:compatible_sections',{'transitions':RESTRICTIONS,'sections':mapping(V)})
_add('bundles.connection','math.geometry.fiber_bundles:gauge_connection',{'coordinates':S,'connection':arr(EM,8),'gauge':EM})
DIRACS=arr(obj({'weight':Q,'point':Q,'order':I}),128)
_add('distributions.pairing','math.analysis.distributions:dirac_pairing',{'terms':DIRACS,'test_function':EX,'variable':T},['terms','test_function'])
_add('distributions.derivative','math.analysis.distributions:derivative',{'terms':DIRACS,'order':I},['terms'])
_add('distributions.fourier','math.analysis.distributions:fourier',{'terms':DIRACS,'frequency':T},['terms'])
_add('distributions.regular','math.analysis.distributions:regular_pairing',{'density':EX,'test_function':EX,'lower':Q,'upper':Q,'variable':T},['density','test_function','lower','upper'])
_add('sobolev.norm','math.analysis.sobolev:polynomial_norm',{'source':EX,'lower':Q,'upper':Q,'order':I,'variable':T},['source'])
_add('sobolev.tail','math.analysis.sobolev:truncation_bound',{'coefficients':V,'tail_l2_bound':Q,'derivative_weights':V})
_add('homotopy.fundamental_group','math.topology.homotopy:fundamental_group',{'facets':FACETS})
_add('homotopy.simplicial_map','math.topology.homotopy:simplicial_map',{'source':FACETS,'target':FACETS,'vertex_map':mapping(I)})
_add('proofs.check','math.logic.proof_theory:check_proof',{'proof':PROOF,'assumptions':arr(PROPOSITION,64),'expected':PROPOSITION,'max_nodes':I},['proof'])
_add('constructive.type_check','math.logic.constructive:type_check',{'term':TERM,'context':mapping(PROPOSITION),'expected':PROPOSITION},['term'])
_add('models.satisfaction','math.logic.model_theory:satisfies',{'domain':arr({'anyOf':[I,T]},32,1),'relations':mapping(obj({'arity':I,'tuples':arr(arr({'anyOf':[I,T]},4),65536)})),'sentence':MODEL,'assignment':mapping({'anyOf':[I,T]})},['domain','relations','sentence'])
HF={'$ref':'#/$defs/hfset'}
_add('sets.operations','math.set_theory.axiomatic:finite_set_operations',{'left':HF,'right':HF})
_add('sets.axiom','math.set_theory.axiomatic:axiom_instance',{'name':T,'parameters':arr(HF,2,1)})
_add('sets.derivation','math.set_theory.axiomatic:verify_derivation',{'proof':PROOF,'axioms':arr(PROPOSITION,64),'conclusion':PROPOSITION})
_add('order.heyting','ops.order_theory:heyting_algebra',{'relation':arr(arr(B,32,1),32,1)})
_add('order.boolean','ops.order_theory:boolean_bitset',{'universe_size':I,'left':I,'right':I})
_add('order.symbolic','ops.order_theory:symbolic_order',{'elements':V,'predicate':T})
OPERATION=obj({'arity':I,'values':arr(I,65536)})
_add('universal.signature','ops.universal_algebra:finite_signature',{'size':I,'operations':mapping(OPERATION),'identities':arr(arr(ALGTERM,2,2),32),'variables':S,'generators':arr(I,16)},['size','operations'])
_add('universal.congruences','ops.universal_algebra:congruences',{'table':arr(arr(I,7,1),7,1)})
_add('universal.free','ops.universal_algebra:free_term_algebra',{'table':arr(arr(I,16,1),16,1),'generators':I,'max_functions':I},['table'])
_add('algebraic.ideals','ops.algebraic_geometry:ideal_analysis',{'equations':S,'variables':S,'remove':S,'denominator':EX},['equations','variables'])
_add('lie.structure','ops.lie_algebra:lie_structure',{'structure':TENSOR,'representation':TENSOR},['structure'])
_add('k.groups','ops.k_theory:k_groups',{'kind':{'enum':['finite_field','complex_sphere']},'parameter':I})
_add('measure.radon_nikodym','ops.measure_theory:radon_nikodym',{'reference':V,'target':V})
_add('measure.product','ops.measure_theory:product_measure',{'left':V,'right':V})
_add('measure.continuous','ops.measure_theory:continuous_integral',{'density':EX,'integrand':EX,'lower':Q,'upper':Q,'variable':T},['density','integrand','lower','upper'])
_add('lie.matrix_group','ops.lie_groups:matrix_group',{'kind':{'enum':['SO','SL','SU','SE3']},'matrix':arr(arr({'anyOf':[N,arr(N,2,2)]},16,1),16,1),'operation':{'enum':['exp','log']},'direction':NM,'tolerance':N},['kind','matrix'])
_add('lie.se3_adjoint','ops.lie_groups:se3_adjoint',{'transform':NM})
_add('lie.integrate','ops.lie_groups:integrate_group',{'generators':arr(NM,10000,1),'step':N,'kind':T},['generators','step'])
_add('potential.green','ops.potential_theory:green_function',{'distance':N,'dimension':I},['distance'])
_add('potential.boundary','ops.potential_theory:boundary_single_layer',{'vertices':NM,'values':NV})
_add('special.precision','ops.special_functions:high_precision',{'kind':T,'x':{'anyOf':[N,arr(N,2,2)]},'parameters':arr({'anyOf':[N,arr(N,8)]},16),'digits':I},['kind','x'])
_add('approximation.spline','ops.approximation_theory:spline',{'nodes':NV,'values':NV,'points':NV,'boundary':T},['nodes','values','points'])
_add('approximation.chebyshev','ops.approximation_theory:chebyshev_fit',{'nodes':NV,'values':NV,'degree':I,'points':NV})
_add('approximation.minimax','ops.approximation_theory:remez_grid',{'nodes':NV,'values':NV,'degree':I})
_add('approximation.pade','ops.approximation_theory:pade',{'coefficients':NV,'denominator_degree':I})
_add('transforms.symbolic','ops.integral_transforms:symbolic_transform',{'kind':T,'source':EX,'variable':T,'parameter':T},['kind','source'])
_add('transforms.oscillatory','ops.integral_transforms:oscillatory_integral',{'source':EX,'lower':Q,'upper':Q,'frequency':Q,'weight':T,'variable':T,'tolerance':N},['source','lower','upper','frequency'])
_add('recurrence.symbolic','ops.difference_equations:variable_recurrence',{'coefficients':EV,'initial':V,'forcing':EX,'variable':T},['coefficients','initial'])
_add('recurrence.system','ops.difference_equations:discrete_system',{'expressions':S,'variables':S,'initial':NV,'steps':I})
_add('integral_equations.nystrom','ops.integral_equations:numerical_integral_equation',{'kernel':EX,'rhs':EX,'lower':N,'upper':N,'coupling':N,'nodes':I,'kind':T,'regularization':N},['kernel','rhs'])
_add('complex.holomorphic_jet','ops.several_complex_variables:holomorphic_jet',{'sources':S,'variables':S,'point':arr({'anyOf':[Q,arr(Q,2,2)]},4,1),'order':I},['sources','variables','point'])
_add('harmonic.group_fourier','ops.abstract_harmonic_analysis:group_fourier',{'table':arr(arr(I,64,1),64,1),'values':arr({'anyOf':[N,arr(N,2,2)]},64,1),'representations':arr(TENSOR,64,1)})
_add('harmonic.convolution','ops.abstract_harmonic_analysis:group_convolution',{'table':arr(arr(I,64,1),64,1),'left':arr({'anyOf':[N,arr(N,2,2)]},64,1),'right':arr({'anyOf':[N,arr(N,2,2)]},64,1)})
_add('functional.series','ops.functional_analysis:orthogonal_series',{'coefficients':V,'weights':V,'tail_bound':Q})
_add('functional.fixed_point','ops.functional_analysis:contraction_fixed_point',{'matrix':NM,'offset':NV,'tolerance':N,'max_iterations':I},['matrix','offset'])
_add('operators.sparse_spectrum','ops.operator_theory:sparse_spectrum',{'size':I,'entries':arr({'type':'array','prefixItems':[I,I,N],'items':False,'minItems':3,'maxItems':3},1000000),'count':I},['size','entries'])
_add('variations.fields','ops.variational_calculus:euler_lagrange_fields',{'lagrangian':EX,'coordinates':S,'fields':S,'order':I},['lagrangian','coordinates','fields'])
_add('manifolds.invariants','ops.manifold_topology:complex_invariants',{'facets':FACETS})
_add('global.de_rham','ops.global_analysis:de_rham_derivative',{'coordinates':S,'components':FORM})
_add('global.weighted_hodge','ops.global_analysis:weighted_hodge',{'facets':FACETS,'degree':I,'weights':M})
_add('ensembles.microcanonical','ops.statistical_mechanics:microcanonical',{'energies':NV,'lower':N,'upper':N,'degeneracies':arr(I),'boltzmann':N},['energies','lower','upper'])
_add('ensembles.grand','ops.statistical_mechanics:grand_canonical',{'energies':NV,'particle_numbers':arr(I),'chemical_potential':N,'temperature':N,'boltzmann':N,'degeneracies':arr(I)},['energies','particle_numbers'])
_add('ensembles.ising','ops.statistical_mechanics:ising_chain',{'size':I,'coupling':N,'field':N,'temperature':N,'periodic':B},['size'])
_add('geophysics.gravity','ops.geophysics:gravity_point_masses',{'points':NM,'masses':NV,'observations':NM})
_add('geophysics.inverse','ops.geophysics:tikhonov_inversion',{'kernel':NM,'observations':NV,'regularization':N,'noise_standard_deviation':N},['kernel','observations'])
_add('spectral.multidimensional','ops.spectral:multidimensional_fft',{'values':{'$ref':'#/$defs/numeric_tensor'},'inverse':B},['values'])
_add('spectral.wavelet','ops.spectral:wavelet_transform',{'values':{'anyOf':[NV,NM]},'wavelet':T,'level':I,'inverse':B},['values'])
_add('spectral.nonuniform','ops.spectral:nonuniform_dft',{'locations':NV,'values':arr({'anyOf':[N,arr(N,2,2)]},4096,1),'frequencies':NV})
_add('spectral.diagnostics','ops.spectral:sampling_diagnostics',{'values':NV,'sample_rate':N})
_add('complex.meromorphic','ops.complex_analysis:meromorphic_analysis',{'source':EX,'variable':T,'point':EX,'order':I},['source'])
_add('complex.clearance','ops.complex_analysis:contour_clearance',{'source':EX,'contour':arr({'anyOf':[N,arr(N,2,2)]},1024,2),'minimum_distance':N},['source','contour'])
_add('geometry.pullback','ops.differential_geometry:coordinate_pullback',{'metric':EM,'coordinates':S,'new_coordinates':S,'mapping':S})
_add('geometry.geodesic','ops.differential_geometry:geodesic',{'metric':EM,'coordinates':S,'position':NV,'velocity':NV,'duration':N,'steps':I},['metric','coordinates','position','velocity'])
_add('geometry.covariant','ops.differential_geometry:covariant_derivative',{'metric':EM,'coordinates':S,'vector':EV})
_add('integers.factor','ops.abstract_algebra:factor_integer',{'value':I,'limit':I},['value'])
_add('integers.certificate','ops.abstract_algebra:pocklington_certificate',{'n':I})
_add('galois.polynomial','math.algebra.galois:polynomial_galois',{'coefficients':V})
_add('fields.primitive','math.algebra.extensions:number_field',{'radicals':S,'polynomial':EX,'variable':T},['radicals'])
_add('groups.permutation','math.algebra.groups:permutation_group',{'generators':arr(arr(I,128,1),32,1),'subgroup_generators':arr(arr(I,128,1),32,1)},['generators'])
_add('topology.integral_homology','math.topology.homology:integral_homology',{'facets':FACETS,'degree':I})
_add('topology.cup','math.topology.homology:cup_product',{'facets':FACETS,'left_degree':I,'left':V,'right_degree':I,'right':V})
_add('topology.continuity','math.topology.general:polynomial_continuity',{'source':EX,'lower':Q,'upper':Q,'variable':T},['source','lower','upper'])
_add('calculus.elementary','math.calculus.risch:integrate_elementary',{'source':EX,'variable':T,'rational_only':B},['source'])
_add('linear.algebraic_spectral','math.linear_algebra.exact_spectral:algebraic_spectral',{'matrix':M})
_add('elliptic.rational_points','math.number_theory.elliptic_curves:rational_points',{'a':Q,'b':Q,'height':I},['a','b'])
_add('elliptic.isogeny','math.number_theory.elliptic_curves:two_isogeny',{'a':Q,'b':Q,'point':{'anyOf':[{'type':'null'},arr(Q,2,2)]}})
_add('stochastic.ito','math.probability.ito:multivariate_ito',{'function':EX,'drift':EV,'diffusion':EM,'variables':S,'time':T},['function','drift','diffusion','variables'])
_add('stochastic.system','math.probability.stochastic:sde_system',{'drift':EV,'diffusion':EM,'variables':S,'initial':NV,'duration':N,'steps':I,'seed':I,'method':T,'jump_rate':N,'jump':NV,'increments':NM},['drift','diffusion','variables','initial'])
_add('stochastic.refinement','math.probability.stochastic:sde_refinement',{'drift':EV,'diffusion':EM,'variables':S,'initial':NV,'duration':N,'steps':I,'seed':I,'method':T},['drift','diffusion','variables','initial'])
_add('ode.stiff','numeric.stiff_ode:solve_stiff_system',{'expressions':EV,'variables':S,'initial':NV,'duration':N,'method':T,'rtol':N,'atol':N,'steps':I,'events':JUMP},['expressions','variables','initial'])
_add('pde.poisson','numeric.pde_general:poisson_cartesian',{'shape':arr(I,3,1),'forcing':{'$ref':'#/$defs/numeric_tensor'},'lengths':NV},['shape','forcing'])
_add('pde.fem','numeric.pde_general:poisson_fem_1d',{'nodes':NV,'forcing':EX,'left':BOUNDARY,'right':BOUNDARY})
_add('autograd.jet','ops.autograd:expression_derivatives',{'source':EX,'variables':S,'point':V,'order':I},['source','variables','point'])
_add('autograd.implicit','ops.autograd:implicit_derivative',{'equations':EV,'parameters':S,'unknowns':S,'point':V})
_add('autograd.solve_vjp','ops.autograd:linear_solve_vjp',{'matrix':NM,'rhs':NV,'cotangent':NV})
_add('bayesian.conjugate','ops.bayesian_inference:conjugate_update',{'kind':T,'data':V,'prior':{'oneOf':[obj({'shape':Q,'rate':Q}),obj({'alpha':V}),obj({'mean':Q,'variance':Q,'observation_variance':Q})]}})
_add('bayesian.hierarchy','ops.bayesian_inference:gaussian_hierarchy',{'design':NM,'response':NV,'prior_mean':NV,'prior_precision':NM,'noise_variance':N},['design','response','prior_mean','prior_precision'])
_add('bayesian.sample','ops.bayesian_inference:sample_posterior',{'log_density':EX,'variables':S,'initials':NM,'samples':I,'burn_in':I,'scale':N,'seed':I},['log_density','variables','initials'])
SOC=obj({'matrix':NM,'offset':NV,'linear':NV,'constant':N})
_add('optimization.conic','ops.convex_optimization:conic_program',{'objective':NV,'inequalities':arr(obj({'matrix':NM,'upper':NV}),64),'second_order':arr(SOC,64),'semidefinite':arr(NM,257),'solver':T},['objective'])
_add('optimization.certificate','ops.convex_optimization:verify_linear_certificate',{'objective':V,'matrix':M,'lower':V,'point':V,'dual':V})
CERTIFICATE={'oneOf':[obj({'kind':{'const':'identity'},'left':T,'right':T}),
    obj({'kind':{'const':'matrix_product'},'left':M,'right':M,'result':M}),
    obj({'kind':{'enum':['matrix_inverse','chain_boundary']},'left':M,'right':M})]}
_add('formal.translate','formal.translate:translate_certificate',{'certificate':CERTIFICATE})
_add('representations.decompose','math.algebra.representations:decompose_character',{'table':arr(arr(I,64,1),64,1),'matrices':TENSOR,'irreducibles':arr(TENSOR,64,1)})
_add('homological.homotopy','math.algebra.homological:chain_homotopy',{'dimensions':arr(I,16,1),'differentials':TENSOR,'left':TENSOR,'right':TENSOR,'homotopies':TENSOR})
_add('bundles.transport','math.geometry.fiber_bundles:parallel_transport',{'coordinates':S,'connection':arr(EM,8),'path':S,'initial':NV,'duration':N,'steps':I},['coordinates','connection','path','initial'])
_add('lie.decomposition','ops.lie_algebra:lie_decomposition',{'structure':TENSOR})
_add('lie.pbw','ops.lie_algebra:pbw_reduce',{'structure':TENSOR,'word':arr(I,10)})
_add('lie.roots','ops.lie_algebra:root_system',{'cartan':M})
_add('k.higher_finite_field','ops.k_theory:finite_field_higher_k',{'prime':I,'degree':I})
_add('variations.density','ops.variational_calculus:euler_lagrange_density',{'lagrangian':EX,'coordinates':S,'fields':S})
_add('pde.adaptive','numeric.pde_general:adaptive_poisson_1d',{'forcing':EX,'left':BOUNDARY,'right':BOUNDARY,'length':N,'tolerance':N,'max_nodes':I},['forcing','left','right'])
_add('geophysics.wave','ops.geophysics:acoustic_wave_2d',{'initial':NM,'velocity':N,'spacing':N,'time_step':N,'steps':I})
_add('approximation.remez','ops.approximation_theory:remez_polynomial',{'coefficients':V,'degree':I,'lower':Q,'upper':Q,'tolerance':N,'max_iterations':I},['coefficients','degree'])
_add('bayesian.diagnostics','ops.bayesian_inference:posterior_diagnostics',{'chains':arr(NM,16,2)})
_add('stochastic.adaptive','math.probability.stochastic:adaptive_sde',{'drift':EV,'diffusion':EM,'variables':S,'initial':NV,'duration':N,'tolerance':N,'max_steps':I,'seed':I,'method':T},['drift','diffusion','variables','initial'])
_add('schemes.radical','math.geometry.schemes:zero_dimensional_radical',{'equations':S,'variables':S})
_add('schemes.primary_zero_dimensional','math.geometry.schemes:zero_dimensional_primary',{'equations':S,'variables':S})
_add('topology.cohomology','math.topology.homology:cohomology_basis',{'facets':FACETS,'degree':I})
_add('topology.integral_cohomology','math.topology.homology:integral_cohomology',{'facets':FACETS,'degree':I})
_add('topology.cup_class','math.topology.homology:cup_class',{'facets':FACETS,'left_degree':I,'left':V,'right_degree':I,'right':V})
LINEAR_PREDICATE=obj({'left':EX,'relation':{'enum':['eq','ne','le','lt','ge','gt']},'right':EX})
_add('models.linear_integers','math.logic.model_theory:decide_linear_integers',{'goal':LINEAR_PREDICATE,'variables':S,'assumptions':arr(LINEAR_PREDICATE,32),'timeout_ms':I},['goal','variables'])
PATH={'anyOf':[arr(T,4096,1),obj({'source':T,'arrows':arr(T,4096)})]}
MORPHISM=obj({'name':T,'source':T,'target':T})
CATEGORY=obj({'objects':S,'morphisms':arr(MORPHISM,64),'identities':mapping(T),'composition':arr(obj({'after':T,'before':T,'result':T}),4096)})
FUNCTOR=obj({'objects':mapping(T),'morphisms':mapping(T)})
_add('categories.paths','math.category_theory.categories:presented_equality',{'objects':S,'generators':arr(MORPHISM,64),'relations':arr(arr(PATH,2,2),128),'left':PATH,'right':PATH})
_add('categories.adjunction','math.category_theory.functors:finite_adjunction',{'source':CATEGORY,'target':CATEGORY,'left':FUNCTOR,'right':FUNCTOR,'unit':mapping(T),'counit':mapping(T)})
_add('fields.arithmetic','math.algebra.extensions:field_arithmetic',{'polynomial':V,'left':V,'right':V,'operation':T,'exponent':I},['polynomial','left'])
_add('sets.progression','math.set_theory.finite:progression',{'modulus':I,'residue':I,'values':arr(I,10000),'lower':I,'count':I,'start':I},['modulus','residue','values'])
_add('elliptic.add','math.number_theory.elliptic_curves:rational_add',{'a':Q,'b':Q,'left':{'anyOf':[{'type':'null'},arr(Q,2,2)]},'right':{'anyOf':[{'type':'null'},arr(Q,2,2)]}})


def definitions():
    proposition={'oneOf':[{'type':'string','pattern':'^[A-Za-z][A-Za-z0-9_]*$','maxLength':64},
        {'type':'array','prefixItems':[{'const':'bottom'}],'items':False,'minItems':1,'maxItems':1},
        {'type':'array','prefixItems':[{'enum':['and','or','imp']},PROPOSITION,PROPOSITION],'items':False,'minItems':3,'maxItems':3}]}
    proof=obj({'rule':{'enum':['assumption','imp_intro','and_intro','and_left','and_right','imp_elim','or_left','or_right','or_elim','bottom_elim']},
               'formula':PROPOSITION,'assumption':PROPOSITION,'other':PROPOSITION,'premises':arr(PROOF,3)},['rule'])
    term=obj({'op':{'enum':['var','lambda','apply','pair','fst','snd','inl','inr','case','absurd']},'name':T,'type':PROPOSITION,'body':TERM,
              'function':TERM,'argument':TERM,'left':TERM,'right':TERM,'value':TERM,'other_type':PROPOSITION,
              'left_name':T,'right_name':T,'left_body':TERM,'right_body':TERM},['op'])
    first_order_term={'oneOf':[obj({'var':T}),obj({'constant':{'anyOf':[I,T]}})]}
    model=obj({'op':{'enum':['relation','equal','not','and','or','imp','forall','exists']},'name':T,'args':arr(first_order_term,4),
               'left':{'anyOf':[MODEL,first_order_term]},'right':{'anyOf':[MODEL,first_order_term]},'body':MODEL,'variable':T},['op'])
    return {'proposition':proposition,'proof':proof,'term':term,'model_formula':model,
            'algebra_term':{'oneOf':[T,obj({'op':T,'args':arr(ALGTERM,4)})]},
            'hfset':arr({'$ref':'#/$defs/hfset'},256),
            'numeric_tensor':{'anyOf':[N,arr({'$ref':'#/$defs/numeric_tensor'},100000)]}}


def schema():
    return {'type':'object','oneOf':[obj({'action':{'const':name},'parameters':entry['schema']}) for name,entry in ACTIONS.items()],
            '$defs':definitions()}


def advanced_math(action,parameters):
    if action not in ACTIONS or not isinstance(parameters,dict):raise ValueError('Unknown advanced mathematics action')
    entry=ACTIONS[action];contract=entry['schema'];required=set(contract['required']);allowed=set(contract['properties'])
    if not required<=parameters.keys() or parameters.keys()-allowed:raise ValueError('Arguments differ from the closed action signature')
    # Depth/node limits apply even to the direct Python/CLI path without jsonschema.
    stack=[(parameters,0)];count=0
    while stack:
        value,depth=stack.pop();count+=1
        if depth>64 or count>100000:raise ValueError('Advanced input structure budget exceeded')
        if isinstance(value,dict):stack.extend((v,depth+1) for v in value.values())
        elif isinstance(value,(list,tuple)):stack.extend((v,depth+1) for v in value)
    module,function=entry['path'].split(':')
    result=getattr(import_module('nablamath.'+module),function)(**parameters)
    from ..math._structured import data
    return {'action':action,'result':data(result),'formal_proof':False,
            'limitations':'Bounded declared algorithm; CAS/numerical output is not universal mathematical acceptance or an independent proof.'}


def calculate(action,**parameters):
    from ..calc import CalculationSession
    return CalculationSession().execute('advanced_math',action=action,parameters=parameters)
