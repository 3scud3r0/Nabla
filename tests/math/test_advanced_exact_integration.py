"""Bounded exact-math expansion: identities, edge cases and integration contracts."""
import json
import random
import unittest
from fractions import Fraction

from nablamath.math.exact import (
    Polynomial, RationalMatrix, ExactInterval,
    extended_gcd, is_prime_64, prime_factorization, euler_phi, mobius,
    divisor_sigma, divisors, multiplicative_order, modular_square_roots,
    primitive_root_prime, discrete_log_bsgs, continued_fraction_sqrt,
    pell_min_solution, farey_neighbors,
    ModPolynomial, mod_poly_gcd, mod_poly_extended_gcd,
    is_irreducible, FiniteField, field_profile,
    interval_horner, bernstein_enclosure, subdivision_extrema,
    certified_root_bisection, exact_polynomial_integral,
    shifted_taylor_polynomial, pade_exponential, newton_divided_differences,
    newton_to_polynomial,
    bellman_ford, floyd_warshall, exact_max_flow, bipartite_matching,
    minimum_spanning_tree, optimal_assignment, strongly_connected_components,
    FiniteDistribution, JointDistribution, binomial_law,
    poisson_binomial_law, hypergeometric_probability, dirichlet_predictive,
    unique_markov_stationary, markov_distribution_after,
)
from nablamath.calc.session import CalculationSession, AREAS
from nablamath.calc.catalog import catalog


class NumberTheoryTests(unittest.TestCase):
    def test_bezout(self):
        for a,b in ((240,46),(-12,18),(0,0),(0,-37),(-17,-19)):
            g,x,y = extended_gcd(a,b)
            self.assertEqual(a*x+b*y, g)
            self.assertGreaterEqual(g,0)

    def test_prime_decision_carmichael(self):
        for n in (0,1,4,9,15,341,561,1105,1729,3215031751):
            self.assertFalse(is_prime_64(n))
        for n in (2,3,5,7,97,65537,(1<<61)-1):
            self.assertTrue(is_prime_64(n))

    def test_prime_domain_refuses_unbounded(self):
        with self.assertRaises(ValueError):
            is_prime_64(1<<64)

    def test_factorization_and_totient(self):
        for n in (1, 2, 8, 72, 97, 99991*99991):
            reconstructed = 1
            for p,k in prime_factorization(n):
                self.assertTrue(is_prime_64(p))
                reconstructed *= p**k
            self.assertEqual(reconstructed,n)
            self.assertEqual(euler_phi(n),sum(int(__import__('math').gcd(k,n)==1)
                                             for k in range(1,n+1)) if n <= 100 else euler_phi(n))

    def test_factorization_bound(self):
        with self.assertRaises(ValueError):
            prime_factorization(10**12+1)

    def test_mobius_and_divisor_sum(self):
        self.assertEqual([mobius(n) for n in range(1,7)], [1,-1,-1,0,-1,1])
        self.assertEqual(divisors(12),(1,2,3,4,6,12))
        self.assertEqual(divisor_sigma(12),28)
        self.assertEqual(divisor_sigma(12,0),6)

    def test_multiplicative_order(self):
        self.assertEqual(multiplicative_order(2,7),3)
        self.assertEqual(multiplicative_order(3,7),6)
        with self.assertRaises(ValueError):
            multiplicative_order(2,8)

    def test_modular_square_roots(self):
        self.assertEqual(modular_square_roots(2,7),(3,4))
        self.assertEqual(modular_square_roots(0,7),(0,))
        self.assertEqual(modular_square_roots(3,7),())
        self.assertEqual(modular_square_roots(5,41),(13,28))
        with self.assertRaises(ValueError):
            modular_square_roots(3,9)

    def test_exhaustive_tonelli_small_primes(self):
        for p in (3,5,7,11,13,17,19,23,29,31,41,97):
            for a in range(p):
                roots = modular_square_roots(a,p)
                expected = tuple(x for x in range(p) if x*x%p == a)
                self.assertEqual(roots,expected)

    def test_primitive_roots(self):
        for p in (2,3,5,7,11,17,97):
            root = primitive_root_prime(p)
            self.assertEqual(len({pow(root,i,p) for i in range(p-1)}),p-1)

    def test_discrete_log(self):
        self.assertEqual(discrete_log_bsgs(3,6,7),3)
        self.assertEqual(discrete_log_bsgs(2,3,7),None)
        self.assertEqual(discrete_log_bsgs(1,1,7),0)

    def test_pell(self):
        self.assertEqual(pell_min_solution(2),(3,2))
        self.assertEqual(pell_min_solution(3),(2,1))
        self.assertEqual(pell_min_solution(13),(649,180))
        root,period = continued_fraction_sqrt(2)
        self.assertEqual((root,period),(1,(2,)))
        with self.assertRaises(ValueError):
            pell_min_solution(4)

    def test_farey_neighbor_identity(self):
        self.assertEqual(farey_neighbors("1/2",5),(Fraction(2,5),Fraction(3,5)))


class FiniteFieldTests(unittest.TestCase):
    def test_coefficient_reduction(self):
        self.assertEqual(ModPolynomial((7,-1,0),5),ModPolynomial((2,4),5))
        with self.assertRaises(ValueError):
            ModPolynomial((1,1),4)

    def test_mod_polynomial_euclidean_identity(self):
        random.seed(4081)
        for _ in range(35):
            a=ModPolynomial(tuple(random.randint(0,4) for _ in range(7)),5)
            b=ModPolynomial((random.randint(0,4),2,1),5)
            q,r=a.divmod(b)
            self.assertEqual(a,q*b+r)
            self.assertLess(r.degree,b.degree)

    def test_modular_bezout(self):
        a,b=ModPolynomial((1,2,0,1),5),ModPolynomial((2,0,1),5)
        g,s,t=mod_poly_extended_gcd(a,b)
        self.assertEqual(s*a+t*b,g)
        self.assertEqual(mod_poly_gcd(a,b),g)

    def test_irreducible_and_reducible(self):
        self.assertTrue(is_irreducible(ModPolynomial((1,1,1),2)))
        self.assertFalse(is_irreducible(ModPolynomial((1,0,1),2)))
        self.assertTrue(is_irreducible(ModPolynomial((1,0,1),3)))
        self.assertFalse(is_irreducible(ModPolynomial((1,),3)))

    def test_f4_inverse_trace_norm(self):
        field=FiniteField(ModPolynomial((1,1,1),2))
        x=field.element((0,1))
        self.assertEqual(x*x, x+1)
        self.assertEqual(x*x.inverse(),field.one())
        self.assertEqual(x.trace(),1)
        self.assertEqual(x.norm(),1)
        self.assertEqual(field.element((0,)).trace(),0)
        self.assertEqual(field.element((0,)).norm(),0)

    def test_all_elements_of_f9_have_inverse(self):
        field=FiniteField(ModPolynomial((1,0,1),3))
        for a in range(3):
            for b in range(3):
                element=field.element((a,b))
                if element != field.zero():
                    self.assertEqual(element*element.inverse(),field.one())
                    self.assertEqual(element**8,field.one())
                    self.assertEqual(element.trace(),element.trace()%3)
                    self.assertEqual(element.norm(),element.norm()%3)

    def test_field_profile_round_trip(self):
        data=field_profile(2,(1,1,1),(0,1))
        self.assertEqual(data["field_size"],4)
        self.assertEqual(data["trace"],1)
        self.assertEqual(data["norm"],1)

    def test_invalid_modulus_refused(self):
        with self.assertRaises(ValueError):
            FiniteField(ModPolynomial((1,0,1),2))

    def test_cross_field_refused(self):
        a=FiniteField(ModPolynomial((1,1,1),2)).one()
        b=FiniteField(ModPolynomial((1,0,1),3)).one()
        with self.assertRaises(ValueError):
            _=a+b


class AnalysisTests(unittest.TestCase):
    def test_interval_product_division(self):
        a=ExactInterval(-2,3)
        b=ExactInterval(4,5)
        self.assertEqual(a*b,ExactInterval(-10,15))
        self.assertEqual(b.reciprocal(),ExactInterval(Fraction(1,5),Fraction(1,4)))
        with self.assertRaises(ZeroDivisionError):
            a.reciprocal()

    def test_even_and_odd_powers(self):
        self.assertEqual(ExactInterval(-2,3)**2,ExactInterval(0,9))
        self.assertEqual(ExactInterval(-2,3)**3,ExactInterval(-8,27))
        self.assertEqual(ExactInterval(2,4)**-1,ExactInterval(Fraction(1,4),Fraction(1,2)))

    def test_intersection(self):
        self.assertEqual(ExactInterval(0,2).intersection(ExactInterval(1,3)),ExactInterval(1,2))
        self.assertIsNone(ExactInterval(0,1).intersection(ExactInterval(2,3)))

    def test_horner_and_bernstein_are_inclusions(self):
        p=Polynomial((1,-2,1))
        domain=ExactInterval(0,2)
        for method in (interval_horner,bernstein_enclosure):
            enclosure=method(p,domain)
            for i in range(33):
                self.assertTrue(enclosure.contains(p(Fraction(i,16))))

    def test_subdivision_extrema(self):
        result=subdivision_extrema(Polynomial((0,0,1)),ExactInterval(-1,1),
                                   tolerance=Fraction(1,8),max_segments=128)
        low,high=result['minimum'],result['maximum']
        self.assertLessEqual(Fraction(low['lower']),0)
        self.assertGreaterEqual(Fraction(low['upper']),0)
        self.assertLessEqual(Fraction(high['lower']),1)
        self.assertGreaterEqual(Fraction(high['upper']),1)

    def test_subdivision_rejects_unachieved_tolerance(self):
        with self.assertRaises(ArithmeticError):
            subdivision_extrema(Polynomial((0,1)),ExactInterval(0,1),
                                tolerance=Fraction(1,100),max_segments=1)

    def test_bisection_root_existence(self):
        result=certified_root_bisection(Polynomial((-2,0,1)),ExactInterval(1,2),steps=20)
        bounds=result["interval"]
        low,high=Fraction(bounds["lower"]),Fraction(bounds["upper"])
        self.assertLessEqual(low*low,2)
        self.assertGreaterEqual(high*high,2)
        self.assertLessEqual(high-low,Fraction(1,1<<20))
        self.assertFalse(result["uniqueness"])

    def test_bisection_rejects_no_sign_change(self):
        with self.assertRaises(ValueError):
            certified_root_bisection(Polynomial((1,0,1)),ExactInterval(-1,1))

    def test_integral_and_taylor(self):
        p=Polynomial((1,2,3))
        self.assertEqual(exact_polynomial_integral(p,ExactInterval(0,1)),3)
        self.assertEqual(shifted_taylor_polynomial(p,2),Polynomial((17,14,3)))

    def test_pade_taylor_order(self):
        p,q=pade_exponential(1,1)
        self.assertEqual(p,Polynomial((1,Fraction(1,2))))
        self.assertEqual(q,Polynomial((1,Fraction(-1,2))))
        p2,q2=pade_exponential(2,2)
        self.assertEqual(p2,Polynomial((1,Fraction(1,2),Fraction(1,12))))
        self.assertEqual(q2,Polynomial((1,Fraction(-1,2),Fraction(1,12))))

    def test_newton_interpolation(self):
        nodes=((0,1),(1,2),(2,5))
        coefficients=newton_divided_differences(nodes)
        self.assertEqual(coefficients,(1,1,1))
        self.assertEqual(newton_to_polynomial((0,1,2),coefficients),
                         Polynomial((1,0,1)))


class DiscreteTests(unittest.TestCase):
    def test_bellman_ford_negative_edges(self):
        result=bellman_ford(("a","b","c","d"),
                            (("a","b",3),("a","c",10),("b","c",-5)), "a")
        self.assertEqual(result["distances"],{"a":"0","b":"3","c":"-2","d":None})

    def test_reachable_negative_cycle_refused(self):
        edges=(("a","b",1),("b","a",-2))
        with self.assertRaises(ValueError):
            bellman_ford(("a","b"),edges,"a")

    def test_floyd_warshall(self):
        result=floyd_warshall(("a","b","c"),
                               (("a","b",2),("b","c",-1)))
        self.assertEqual(result["distances"][0][2],"1")
        with self.assertRaises(ValueError):
            floyd_warshall(("a","b"),(("a","b",-2),("b","a",1)))

    def test_max_flow_equals_cut(self):
        result=exact_max_flow(("s","a","b","t"),(
            ("s","a",3),("s","b",2),("a","b",1),
            ("a","t",2),("b","t",3)),"s","t")
        self.assertEqual(result["value"],"5")
        self.assertEqual(result["cut_capacity"],"5")
        self.assertIn("s",result["source_side"])
        self.assertIn("t",result["sink_side"])

    def test_antiparallel_flow(self):
        result=exact_max_flow(("s","v","t"),(
            ("s","v","3/2"),("v","s",1),("v","t","3/2")),"s","t")
        self.assertEqual(result["value"],"3/2")

    def test_matching_cover_duality(self):
        result=bipartite_matching(("a","b"),("x","y"),
                                  (("a","x"),("a","y"),("b","x")))
        self.assertEqual(result["cardinality"],2)
        cover=result["minimum_vertex_cover"]
        self.assertEqual(len(cover["left"])+len(cover["right"]),2)

    def test_disconnected_mst_refused(self):
        with self.assertRaises(ValueError):
            minimum_spanning_tree(("a","b","c"),(("a","b",1),))

    def test_exact_mst(self):
        result=minimum_spanning_tree(("a","b","c"),(
            ("a","b",2),("a","c",3),("b","c",1)))
        self.assertEqual(result["weight"],"3")
        self.assertEqual(len(result["edges"]),2)

    def test_assignment(self):
        result=optimal_assignment(((4,1),(2,3)))
        self.assertEqual(result["minimum_cost"],"3")
        self.assertEqual(result["assignment"],[1,0])

    def test_scc(self):
        result=strongly_connected_components(("a","b","c"),
                                              (("a","b"),("b","a"),("b","c")))
        self.assertEqual(result,(("a","b"),("c",)))


class ProbabilityTests(unittest.TestCase):
    def test_finite_law_moments(self):
        d=FiniteDistribution(((0,"1/4"),(2,"3/4")))
        self.assertEqual(d.expected_value,Fraction(3,2))
        self.assertEqual(d.variance,Fraction(3,4))
        self.assertEqual(d.cdf(1),Fraction(1,4))
        self.assertEqual(d.quantile("1/2"),2)

    def test_probability_must_normalize(self):
        with self.assertRaises(ValueError):
            FiniteDistribution(((0,"1/2"),(1,"1/3")))

    def test_convolution_pgfs(self):
        die=FiniteDistribution(tuple((i,Fraction(1,6)) for i in range(1,7)))
        sum2=die.convolve(die)
        self.assertEqual(sum2.probability(7),Fraction(1,6))
        self.assertEqual(sum2.expected_value,7)
        self.assertEqual(die.iid_sum(2),sum2)
        self.assertEqual(die.probability_generating_polynomial()(1),1)

    def test_scale_zero_merges_support(self):
        die=FiniteDistribution(((1,Fraction(1,2)),(2,Fraction(1,2))))
        self.assertEqual(die.scale(0),FiniteDistribution.certain(0))

    def test_binomial(self):
        d=binomial_law(4,Fraction(1,2))
        self.assertEqual(d.probability(2),Fraction(3,8))
        self.assertEqual(d.expected_value,2)
        self.assertEqual(d.variance,1)

    def test_poisson_binomial_vs_binomial(self):
        d=poisson_binomial_law((Fraction(1,3),)*5)
        self.assertEqual(d,binomial_law(5,Fraction(1,3)))

    def test_hypergeometric(self):
        self.assertEqual(hypergeometric_probability(10,5,2,2),Fraction(2,9))
        self.assertEqual(hypergeometric_probability(10,5,2,9),0)

    def test_joint_independence_and_covariance(self):
        independent=JointDistribution(tuple(
            (x,y,Fraction(1,4)) for x in (0,1) for y in (0,1)))
        self.assertTrue(independent.independent())
        self.assertEqual(independent.covariance(),0)
        coupled=JointDistribution(((0,0,Fraction(1,2)),(1,1,Fraction(1,2))))
        self.assertFalse(coupled.independent())
        self.assertEqual(coupled.covariance(),Fraction(1,4))
        self.assertEqual(coupled.conditional_y_given_x(1),
                         FiniteDistribution.certain(1))

    def test_dirichlet(self):
        result=dirichlet_predictive(("1/2","1/2"),(2,0))
        self.assertEqual(result["predictive"],["5/6","1/6"])
        self.assertEqual(result["sample_size"],2)

    def test_stationary(self):
        result=unique_markov_stationary((("1/2","1/2"),("1/4","3/4")))
        self.assertEqual(result["stationary"],["1/3","2/3"])
        with self.assertRaises(ValueError):
            unique_markov_stationary(((1,0),(0,1)))

    def test_propagation(self):
        result=markov_distribution_after((("1/2","1/2"),("1/4","3/4")),(1,0),2)
        self.assertEqual(result["distribution"],["3/8","5/8"])
        self.assertTrue(result["mass_conservation"])


class SessionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.session=CalculationSession()

    def call(self,operation,**kwargs):
        result=self.session.execute(operation,**kwargs).to_data()
        self.assertEqual(result["request"]["operation"],operation)
        self.assertFalse(result["formal_proof"])
        self.assertEqual(result["result"],json.loads(json.dumps(result["result"])))
        return result["result"]

    def test_all_advanced_operations_cataloged(self):
        from nablamath.math.exact.adapters import OPERATIONS
        registered={row["name"] for row in catalog()["operations"]}
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                self.assertIn(operation, AREAS)
                self.assertIn(operation, registered)
        self.assertEqual(len(OPERATIONS),29)

    def test_number_theory_dispatch(self):
        self.assertTrue(self.call("nt_primality",n=97)["prime"])
        self.assertEqual(self.call("nt_factorization",n=12)["totient"],4)
        self.assertEqual(self.call("nt_modular_roots",a=2,prime=7)["roots"],[3,4])
        self.assertEqual(self.call("nt_discrete_log",base=3,target=6,prime=7)["exponent"],3)
        self.assertEqual(self.call("nt_pell",d=2)["x"],"3")
        self.assertEqual(self.call("nt_primitive_root",prime=7)["generator"],3)

    def test_field_dispatch(self):
        self.assertTrue(self.call("ff_irreducible",prime=2,coefficients=[1,1,1])["irreducible"])
        self.assertEqual(self.call("ff_extension",prime=2,modulus=[1,1,1],
                                   element=[0,1])["norm"],1)

    def test_analysis_dispatch(self):
        args=dict(coefficients=[-2,0,1],lower=1,upper=2)
        self.assertEqual(self.call("analysis_root",**args,steps=2)["existence"],True)
        self.assertEqual(self.call("analysis_integral",coefficients=[0,0,1],
                                   lower=0,upper=1)["integral"],"1/3")
        self.assertEqual(self.call("analysis_interval",**args)["method"],"bernstein")
        self.assertEqual(self.call("analysis_pade",numerator_degree=1,
                                   denominator_degree=1)["origin_taylor_order"],2)
        self.assertIn("minimum",self.call("analysis_extrema",coefficients=[0,1],
                                          lower=0,upper=1,tolerance="1/4"))

    def test_graph_dispatch(self):
        vertices=["s","t"]
        edges=[["s","t","3/2"]]
        self.assertEqual(self.call("graph_bellman_ford",vertices=vertices,edges=edges,
                                   source="s")["distances"]["t"],"3/2")
        self.assertEqual(self.call("graph_apsp",vertices=vertices,edges=edges)["distances"][0][1],"3/2")
        self.assertEqual(self.call("graph_max_flow",vertices=vertices,edges=edges,
                                   source="s",sink="t")["value"],"3/2")
        self.assertEqual(self.call("graph_mst",vertices=vertices,edges=edges)["weight"],"3/2")
        self.assertEqual(self.call("graph_matching",left=["a"],right=["b"],
                                   edges=[["a","b"]])["cardinality"],1)
        self.assertEqual(self.call("graph_assignment",costs=[[1]])["minimum_cost"],"1")
        self.assertEqual(len(self.call("graph_scc",vertices=vertices,
                                       edges=[["s","t"]])["components"]),2)

    def test_probability_dispatch(self):
        self.assertEqual(self.call("prob_binomial",trials=2,
                                   success_probability="1/2")["expectation"],"1")
        self.assertEqual(self.call("prob_poisson_binomial",
                                   probabilities=["1/2","1/2"])["variance"],"1/2")
        mass=[[0,"1/2"],[1,"1/2"]]
        self.assertEqual(self.call("prob_distribution",mass=mass)["variance"],"1/4")
        self.assertEqual(self.call("prob_convolution",left=mass,right=mass)["expectation"],"1")
        self.assertTrue(self.call("prob_joint",mass=[[0,0,"1"]])["independent"])
        self.assertEqual(self.call("prob_hypergeometric",population=10,successes=5,
                                   draws=2,observed=2)["probability"],"2/9")
        self.assertEqual(self.call("prob_dirichlet",alpha=[1,1],
                                   counts=[1,0])["predictive"],["2/3","1/3"])
        self.assertTrue(self.call("prob_stationary",
                                  transition=[["1/2","1/2"],["1/4","3/4"]])["uniqueness"])
        self.assertEqual(self.call("prob_propagate",transition=[[1,0],[0,1]],
                                   initial=[1,0],steps=4)["distribution"],["1","0"])

    def test_unknown_fields_refused(self):
        with self.assertRaises(ValueError):
            self.session.execute("nt_primality",n=13,ignored=True)

    def test_rational_float_inputs_refused(self):
        with self.assertRaises(TypeError):
            self.session.execute("prob_binomial",trials=2,success_probability=0.5)


if __name__ == "__main__":
    unittest.main()
