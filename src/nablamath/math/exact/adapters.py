"""Validated JSON-facing adapters for the advanced exact mathematical modules.

This table is registered by the existing CalculationSession catalog, so the
existing 'nabla calc' CLI, notebook replay, and receipt serialization all use
exactly the same validation and result path. The underlying libraries remain
available for Python use, including functions not exposed as CLI operations.
"""
from __future__ import annotations

from . import advanced_number_theory as nt
from . import finite_fields as ff
from . import rigorous_analysis as an
from . import discrete_optimization as gr
from . import finite_probability as pr
from .laboratory import Polynomial


# Operation => (area, mandatory arguments, optional arguments, finite contract).
OPERATIONS = {
    "nt_primality": ("number_theory", {"n"}, set(), "deterministic Miller-Rabin for uint64, never general primality"),
    "nt_factorization": ("number_theory", {"n"}, set(), "complete trial division <=10^12, exact arithmetic-function values"),
    "nt_modular_roots": ("number_theory", {"a", "prime"}, set(), "Tonelli-Shanks over odd uint64 prime; verified roots"),
    "nt_discrete_log": ("number_theory", {"base", "target", "prime"}, set(), "BSGS exact subgroup discrete log, prime<=10^9"),
    "nt_pell": ("number_theory", {"d"}, set(), "minimal positive Pell solution for nonsquare d<=10^6"),
    "nt_primitive_root": ("number_theory", {"prime"}, set(), "least multiplicative generator for prime<=10^9"),
    "ff_irreducible": ("algebra", {"prime", "coefficients"}, set(), "Rabin irreducibility test for prime field polynomials"),
    "ff_extension": ("algebra", {"prime", "modulus", "element"}, set(), "finite field quotient, inverse, trace and norm"),
    "analysis_interval": ("calculus", {"coefficients", "lower", "upper"}, {"method"}, "exact Horner or Bernstein polynomial image inclusion"),
    "analysis_extrema": ("calculus", {"coefficients", "lower", "upper"}, {"tolerance", "max_segments"}, "rational enclosures for min/max after bounded subdivision"),
    "analysis_root": ("calculus", {"coefficients", "lower", "upper"}, {"steps"}, "exact bisection existence bracket, not uniqueness"),
    "analysis_pade": ("calculus", {"numerator_degree", "denominator_degree"}, set(), "Padé approximant of exp formal Taylor series, not certified global error"),
    "analysis_integral": ("calculus", {"coefficients", "lower", "upper"}, set(), "exact definite integral of polynomial over rational domain"),
    "graph_bellman_ford": ("discrete", {"vertices", "edges", "source"}, set(), "exact shortest paths or reachable negative-cycle refusal"),
    "graph_apsp": ("discrete", {"vertices", "edges"}, set(), "exact Floyd-Warshall all pairs, rejects negative cycles"),
    "graph_max_flow": ("discrete", {"vertices", "edges", "source", "sink"}, set(), "exact max-flow value verified against min-cut"),
    "graph_matching": ("discrete", {"left", "right", "edges"}, set(), "maximum bipartite matching and minimum cover equality"),
    "graph_mst": ("discrete", {"vertices", "edges"}, set(), "exact Kruskal minimum spanning tree for connected undirected graph"),
    "graph_assignment": ("optimization", {"costs"}, set(), "exact assignment by exhaustive subset DP, n<=12"),
    "graph_scc": ("discrete", {"vertices", "edges"}, set(), "deterministic Tarjan strongly connected components"),
    "prob_binomial": ("probability", {"trials", "success_probability"}, set(), "exact finite binomial probability law and moments"),
    "prob_poisson_binomial": ("probability", {"probabilities"}, set(), "exact independent non-identical Bernoulli convolution"),
    "prob_distribution": ("probability", {"mass"}, set(), "normalized integer-valued rational mass and moments"),
    "prob_convolution": ("probability", {"left", "right"}, set(), "independent rational finite-law convolution"),
    "prob_joint": ("probability", {"mass"}, set(), "rational joint mass, covariance, exact independence test"),
    "prob_hypergeometric": ("probability", {"population", "successes", "draws", "observed"}, set(), "without-replacement rational combinatorial probability"),
    "prob_dirichlet": ("probability", {"alpha", "counts"}, set(), "finite categorical exact posterior and predictive"),
    "prob_stationary": ("probability", {"transition"}, set(), "unique rational stationary Markov law or rejection"),
    "prob_propagate": ("probability", {"transition", "initial", "steps"}, set(), "finite-state exact row stochastic propagation"),
}


def execute(operation: str, args: dict) -> dict:
    """Dispatch a validated operation and return only JSON encodable results."""
    if operation not in OPERATIONS:
        raise ValueError("Unknown advanced mathematical operation")
    a = args
    if operation == "nt_primality":
        return {"prime": nt.is_prime_64(a["n"]), "domain": "unsigned-64-bit", "deterministic": True}
    if operation == "nt_factorization":
        n = a["n"]
        return {"factors": [list(row) for row in nt.prime_factorization(n)],
                "totient": nt.euler_phi(n), "mobius": nt.mobius(n),
                "divisor_count": len(nt.divisors(n)),
                "factorization_complete": True}
    if operation == "nt_modular_roots":
        return {"roots": list(nt.modular_square_roots(a["a"], a["prime"])),
                "modulus": a["prime"], "verified": True}
    if operation == "nt_discrete_log":
        return {"exponent": nt.discrete_log_bsgs(a["base"], a["target"], a["prime"]),
                "arithmetic": "exact finite prime field"}
    if operation == "nt_pell":
        x, y = nt.pell_min_solution(a["d"])
        return {"x": str(x), "y": str(y), "identity": "x*x-d*y*y=1"}
    if operation == "nt_primitive_root":
        return {"generator": nt.primitive_root_prime(a["prime"])}
    if operation == "ff_irreducible":
        f = ff.ModPolynomial(tuple(a["coefficients"]), a["prime"])
        return {"irreducible": ff.is_irreducible(f), "polynomial": f.to_data()}
    if operation == "ff_extension":
        return ff.field_profile(a["prime"], tuple(a["modulus"]),
                                tuple(a["element"]))
    if operation.startswith("analysis_"):
        if operation == "analysis_pade":
            p, q = an.pade_exponential(a["numerator_degree"], a["denominator_degree"])
            return {"numerator": p.to_data(), "denominator": q.to_data(),
                    "origin_taylor_order": a["numerator_degree"] + a["denominator_degree"],
                    "limitation": "Not a globally certified exponential error bound"}
        p = Polynomial(tuple(a["coefficients"]))
        domain = an.ExactInterval(a["lower"], a["upper"])
        if operation == "analysis_interval":
            method = a.get("method", "bernstein")
            if method not in ("bernstein", "horner"):
                raise ValueError("Unknown exact interval method")
            enclosure = (an.bernstein_enclosure(p, domain) if method == "bernstein"
                         else an.interval_horner(p, domain))
            return {"enclosure": enclosure.to_data(), "method": method}
        if operation == "analysis_extrema":
            return an.subdivision_extrema(
                p, domain, tolerance=a.get("tolerance", "1/64"),
                max_segments=a.get("max_segments", 128))
        if operation == "analysis_root":
            return an.certified_root_bisection(p, domain, steps=a.get("steps", 64))
        return {"integral": str(an.exact_polynomial_integral(p, domain)),
                "arithmetic": "exact polynomial antiderivative"}
    if operation.startswith("graph_"):
        if operation == "graph_assignment":
            return gr.optimal_assignment(tuple(tuple(row) for row in a["costs"]))
        if operation == "graph_matching":
            return gr.bipartite_matching(tuple(a["left"]), tuple(a["right"]),
                                         tuple(tuple(row) for row in a["edges"]))
        vertices = tuple(a["vertices"])
        edges = tuple(tuple(row) for row in a["edges"])
        if operation == "graph_bellman_ford":
            return gr.bellman_ford(vertices, edges, a["source"])
        if operation == "graph_apsp":
            return gr.floyd_warshall(vertices, edges)
        if operation == "graph_max_flow":
            return gr.exact_max_flow(vertices, edges, a["source"], a["sink"])
        if operation == "graph_mst":
            return gr.minimum_spanning_tree(vertices, edges)
        return {"components": [list(row) for row in gr.strongly_connected_components(
            vertices, edges)]}
    if operation == "prob_binomial":
        return pr.binomial_law(a["trials"], a["success_probability"]).to_data()
    if operation == "prob_poisson_binomial":
        return pr.poisson_binomial_law(a["probabilities"]).to_data()
    if operation == "prob_distribution":
        return pr.FiniteDistribution(tuple(tuple(row) for row in a["mass"])).to_data()
    if operation == "prob_convolution":
        left = pr.FiniteDistribution(tuple(tuple(row) for row in a["left"]))
        right = pr.FiniteDistribution(tuple(tuple(row) for row in a["right"]))
        return left.convolve(right).to_data()
    if operation == "prob_joint":
        return pr.JointDistribution(tuple(tuple(row) for row in a["mass"])).to_data()
    if operation == "prob_hypergeometric":
        return {"probability": str(pr.hypergeometric_probability(
            a["population"], a["successes"], a["draws"], a["observed"]))}
    if operation == "prob_dirichlet":
        return pr.dirichlet_predictive(a["alpha"], a["counts"])
    if operation == "prob_stationary":
        return pr.unique_markov_stationary(a["transition"])
    if operation == "prob_propagate":
        return pr.markov_distribution_after(a["transition"], a["initial"], a["steps"])
    raise AssertionError("An advanced mathematical operation lacks its dispatcher")


__all__ = ["OPERATIONS", "execute"]
