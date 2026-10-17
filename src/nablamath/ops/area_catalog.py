"""Named bounded computational profiles for additional MSC major branches."""
OPERATIONS = {
 'order_theory':('order_theory',{'relation'},set(),'finite partial orders, Hasse covers and lattice joins/meets; 64 elements'),
 'universal_algebra':('algebra',{'tables'},{'generators','partition'},'finite binary algebras, generated subalgebras and congruence quotients'),
 'algebraic_geometry':('geometry',{'equations','variables','point'},set(),'rational points and Zariski tangent spaces of explicitly generated affine schemes'),
 'lie_algebra':('algebra',{'structure'},{'left','right'},'rational Lie brackets, Jacobi verification, center and Killing form; dimension at most six'),
 'k_theory':('algebra',{'adjacency'},set(),'exact K0 presentation of finite graph Leavitt path algebras, not general higher K-theory'),
 'measure_theory':('analysis',{'weights','values'},{'partition'},'finite atomic measure integrals and exact conditional expectation'),
 'lie_groups':('geometry',{'rotation_vector'},set(),'numerical SO(3) exponential, quaternion and left Jacobian in radians'),
 'potential_theory':('analysis',{'conductance','boundary'},set(),'exact finite weighted-graph Dirichlet solution, residuals and energy'),
 'special_functions':('analysis',{'kind','x'},{'y','order'},'real Gamma/Beta/error functions and optional SciPy Bessel/Legendre/Airy evaluation'),
 'difference_equations':('analysis',{'coefficients','initial','index'},{'forcing'},'exact affine constant-coefficient recurrence with explicit index and bit budgets'),
 'approximation_theory':('analysis',{'nodes','values','points'},set(),'exact rational barycentric interpolation and query Lebesgue amplification'),
 'integral_transforms':('analysis',{'kind','values','parameter'},set(),'exact polynomial Laplace/unit-Mellin and finite real rational Z transforms'),
 'integral_equations':('analysis',{'kernel','rhs'},{'lower','upper','coupling'},'exact nonsingular second-kind Fredholm equation with polynomial finite-rank kernel'),
 'several_complex_variables':('complex_analysis',{'sources','variables','point'},set(),'exact Gaussian-rational holomorphic polynomial Jacobians and local inverse criterion'),
 'abstract_harmonic_analysis':('spectral',{'group_orders','values'},{'inverse'},'numerical Fourier characters on finite products of cyclic groups'),
 'functional_analysis':('analysis',{'basis','target'},{'weights'},'exact finite weighted-Hilbert projection, orthogonality and Pythagoras identity'),
 'operator_theory':('analysis',{'matrix'},{'parameter'},'finite rational operators, adjoints, induced norms, positivity and resolvents'),
 'variational_calculus':('calculus',{'lagrangian'},set(),'exact scalar polynomial first-order Euler-Lagrange equation, momentum and energy'),
 'manifold_topology':('topology',{'facets'},set(),'finite triangulated surface links, boundaries, orientability and closed orientable genus'),
 'global_analysis':('topology',{'facets'},{'degree','form'},'finite simplicial Hodge Laplacian and exact harmonic projection'),
 'statistical_mechanics':('statistical_mechanics',{'energies'},{'temperature','boltzmann','degeneracies'},'stable finite canonical ensemble in caller-consistent units; no thermodynamic limit'),
 'geophysics':('geophysics',{'kind'},{'thicknesses','velocities','densities','density','height'},'vertical layered acoustic times/reflections or infinite Bouguer slab in SI units'),
}


def execute(operation,arguments):
    from importlib import import_module
    if operation not in OPERATIONS:raise ValueError('Unknown mathematical area')
    return getattr(import_module('.'+operation,__package__),operation)(**arguments)
