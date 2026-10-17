"""Additive catalog entries for the scientific ecosystem adapters."""
OPERATIONS = {
    'tensor': ('tensor', {'kind','values'}, {'other','axis','shape','axes'}, 'bounded floating point N-D tensor operations'),
    'autograd': ('tensor', {'nodes','inputs','output'}, set(), 'closed scalar DAG reverse-mode differentiation; no arbitrary source'),
    'mcmc_normal': ('probability', {'mean','standard_deviation'}, {'samples','burn_in','thin','proposal_scale','seed'}, 'seeded Metropolis normal sampling; convergence not established'),
    'beta_binomial': ('probability', {'successes','trials'}, {'alpha','beta'}, 'exact conjugate Beta-Binomial update'),
    'sequence_align': ('bioinformatics', {'first','second'}, {'match','mismatch','gap'}, 'global alignment with linear gaps; no biological interpretation'),
    'geo_distance': ('geospatial', {'first','second'}, {'radius'}, 'spherical great-circle distance in meters; input longitude/latitude degrees'),
    'quantum_circuit': ('quantum', {'qubits','gates'}, {'shots','seed','density_matrix'}, 'bounded ideal unitary state-vector simulation'),
}


def execute(operation, arguments):
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
