"""Additive catalog entries for the scientific ecosystem adapters."""
OPERATIONS = {
    'advanced_math': ('mathematics', {'action','parameters'}, set(), 'allowlisted advanced algebra, geometry, analysis, logic and numerical profiles; closed per-action schemas, explicit domains and no universal proof claim'),
    'spectral': ('spectral', {'kind','values'}, {'other','levels','sample_rate','cutoff','window_size','hop'}, 'O(n log n) numerical FFT/Bluestein, Haar, convolution and sampled signal processing'),
    'complex_analysis': ('complex_analysis', {'kind'}, {'source','contour','points','coefficients','tolerance','max_evaluations','closed'}, 'adaptive contour quadrature or conformal Mobius map; numerical estimates, not certified holomorphy'),
    'differential_geometry': ('geometry', {'metric'}, {'coordinates','point','first','second'}, 'exact metric two-jets or optional symbolic local Levi-Civita curvature; coordinate domain required'),
    'abstract_algebra': ('algebra', {'kind'}, {'n','value','exponent','modulus','rounds','prime','polynomial','left','right','field_operation','certificate'}, 'finite Galois fields, 4096-bit modular arithmetic and explicitly classified prime evidence'),
    'tensor': ('tensor', {'kind','values'}, {'other','axis','shape','axes'}, 'bounded floating point N-D tensor operations'),
    'autograd': ('tensor', {'nodes','inputs','output'}, set(), 'closed scalar DAG reverse-mode differentiation; no arbitrary source'),
    'mcmc_normal': ('probability', {'mean','standard_deviation'}, {'samples','burn_in','thin','proposal_scale','seed'}, 'seeded Metropolis normal sampling; convergence not established'),
    'beta_binomial': ('probability', {'successes','trials'}, {'alpha','beta'}, 'exact conjugate Beta-Binomial update'),
    'sequence_align': ('bioinformatics', {'first','second'}, {'match','mismatch','gap'}, 'global alignment with linear gaps; no biological interpretation'),
    'geo_distance': ('geospatial', {'first','second'}, {'radius'}, 'spherical great-circle distance in meters; input longitude/latitude degrees'),
    'quantum_circuit': ('quantum', {'qubits','gates'}, {'shots','seed','density_matrix'}, 'bounded ideal unitary state-vector simulation'),
}

from .area_catalog import OPERATIONS as AREA_OPERATIONS,execute as execute_area
OPERATIONS.update(AREA_OPERATIONS)

from .v1_catalog import OPERATIONS as V1_OPERATIONS, execute as execute_v1
OPERATIONS.update(V1_OPERATIONS)


def execute(operation, arguments):
    if operation in V1_OPERATIONS:
        return execute_v1(operation,arguments)
    if operation == 'advanced_math':
        from .advanced_math import advanced_math
        return advanced_math(**arguments)
    if operation in AREA_OPERATIONS:
        return execute_area(operation,arguments)
    if operation in {'spectral','complex_analysis','differential_geometry','abstract_algebra'}:
        from importlib import import_module
        return getattr(import_module('.'+operation,__package__),operation)(**arguments)
    from .tensor_math import tensor_operation
    from .autograd import differentiate_graph
    from .mcmc import sample_normal
    from .bayesian_inference import beta_binomial
    from .convex_optimization import minimize_linear
    from ..domain.bioinformatics import align_sequences
    from ..domain.geospatial import haversine
    from ..domain.quantum import simulate_circuit
    functions = {'tensor':tensor_operation, 'autograd':differentiate_graph,
                 'mcmc_normal':sample_normal, 'beta_binomial':beta_binomial,
                 'sequence_align':align_sequences, 'quantum_circuit':simulate_circuit,
                 'linear_optimize':minimize_linear}
    if operation == 'geo_distance':
        return {'distance':haversine(**arguments),'unit':'m','model':'mean_radius_sphere'}
    return functions[operation](**arguments)
