from decimal import Decimal
from fractions import Fraction as F
import json
from pathlib import Path
import tempfile
import unittest

from nablamath.core.types import ScientificType,ScalarDomain
from nablamath.core.units import Unit,Quantity,METER,KILOMETER,SECOND,HOUR,AMPERE,KELVIN,MOLE,CANDELA,ONE,infer_unit
from nablamath.core.precision import PrecisionPolicy,RationalInterval
from nablamath.core.semantic_ir import SemanticExpression,canonical_json,fingerprint
from nablamath.core.obligations import Obligation,domain_obligations,require_obligations
from nablamath.expression import parse_expr,evaluate
from nablamath.math.linear_algebra import Matrix,solve_linear,lu_decomposition,orthogonal_basis,condition_number_inf,characteristic_polynomial
from nablamath.math.polynomials.univariate import Polynomial
from nablamath.math.polynomials.factorization import factor_rational
from nablamath.math.calculus import derivative,primitive,definite_integral,limit,series
from nablamath.calc import CalculationSession,Notebook,AREAS
from nablamath.cli import main


class SemanticAndUnitsTests(unittest.TestCase):
    def test_notation_independent_identity_and_type_validation(self):
        self.assertEqual(SemanticExpression.parse('x^2').content_id,SemanticExpression.parse('x**2').content_id)
        a=SemanticExpression.parse('distance/time',{'distance':ScientificType(unit=METER),'time':ScientificType(unit=SECOND)})
        self.assertEqual(a.result_type.unit.dimensions,(0,1,-1,0,0,0,0))
        self.assertEqual(len(a.obligations),1)
        with self.assertRaises(ValueError):
            SemanticExpression.parse('x+y',{'x':ScientificType(unit=METER),'y':ScientificType(unit=SECOND)})
        with self.assertRaises(ValueError):
            SemanticExpression.parse('x',{'x':ScientificType(shape=(2,))})
        with self.assertRaises(ValueError):
            ScientificType(shape=(0,))
        with self.assertRaises(ValueError):
            ScientificType(domain=ScalarDomain.BOOLEAN,unit=METER)
        with self.assertRaises(ValueError):
            SemanticExpression.parse('((x**16)**16)**16')

    def test_all_seven_si_dimensions_and_exact_conversions(self):
        units=(METER,SECOND,AMPERE,KELVIN,MOLE,CANDELA)
        self.assertEqual(len({unit.dimensions for unit in units}),6)
        speed=Quantity(72,KILOMETER)/Quantity(1,HOUR)
        self.assertEqual(speed.to(METER/SECOND).value,20)
        self.assertEqual((Quantity(1,KILOMETER)+Quantity(500,METER)).value,F(3,2))
        self.assertEqual((Quantity(2,METER)**2).value,4)
        with self.assertRaises(ValueError):
            Quantity(1,METER).to(SECOND)
        with self.assertRaises(ValueError):
            Unit((1,2))
        with self.assertRaises(ValueError):
            Quantity(.5)

    def test_obligations_distinguish_missing_violated_and_satisfied(self):
        obligations=domain_obligations(parse_expr('(x**0)/(y-1)'))
        self.assertEqual(len(obligations),2)
        statuses=[o.check({'x':1,'y':2}) for o in obligations]
        self.assertEqual(statuses,['satisfied','satisfied'])
        self.assertEqual(Obligation(parse_expr('x')).check({}),'unresolved')
        self.assertEqual(Obligation(parse_expr('x')).check({'x':0}),'violated')
        self.assertEqual(Obligation(parse_expr('1/x')).check({'x':0}),'violated')
        with self.assertRaises(ValueError):
            require_obligations(obligations,{'x':0,'y':2})

    def test_rounding_error_and_outward_bounds(self):
        policy=PrecisionPolicy(8)
        for value in (F(1,3),F(-2,7),F(100,3)):
            row=policy.approximate(value)
            self.assertEqual(F(row['absolute_error']),abs(F(Decimal(row['decimal']))-value))
            lower,upper=policy.interval(value)
            self.assertLessEqual(F(lower),value)
            self.assertGreaterEqual(F(upper),value)
        with self.assertRaises(ValueError):
            PrecisionPolicy(7)
        a=RationalInterval(-2,3);b=RationalInterval(4,5)
        self.assertEqual(a*b,RationalInterval(-10,15))
        self.assertEqual(b/RationalInterval(2,4),RationalInterval(1,F(5,2)))
        with self.assertRaises(ValueError):
            a/RationalInterval(-1,1)


class LinearAlgebraAndCalculusTests(unittest.TestCase):
    def test_rectangular_unique_underdetermined_and_inconsistent(self):
        unique=solve_linear(Matrix(((1,0),(0,1),(1,1))),(2,3,5))
        self.assertEqual(unique.status,'unique')
        self.assertEqual(unique.particular,(2,3))
        result=solve_linear(Matrix(((1,2,3),(2,4,6))),(1,2))
        self.assertEqual(result.status,'underdetermined')
        self.assertEqual(result.rank,1)
        self.assertEqual(len(result.nullspace),2)
        for vector in result.nullspace:
            self.assertEqual(sum(a*b for a,b in zip((1,2,3),vector)),0)
        self.assertEqual(solve_linear(Matrix(((1,),(1,))),(1,2)).status,'inconsistent')

    def test_pivoted_lu_orthogonal_basis_and_condition(self):
        matrix=Matrix(((0,2,1),(1,1,0),(2,0,1)))
        decomposition=lu_decomposition(matrix)
        self.assertTrue(decomposition.verify(matrix))
        basis=orthogonal_basis(((1,1,0),(1,0,1),(2,1,1)))
        self.assertEqual(len(basis),2)
        self.assertEqual(sum(a*b for a,b in zip(*basis)),0)
        self.assertEqual(condition_number_inf(Matrix(((2,0),(0,1)))),2)
        self.assertEqual(characteristic_polynomial(Matrix(((2,1),(1,2)))) ,(F(3),F(-4),F(1)))
        with self.assertRaises(ValueError):
            lu_decomposition(Matrix(((1,2),(2,4))))

    def test_calculus_with_exact_reference_values(self):
        self.assertEqual(evaluate(derivative('x**3').derivative,{'x':F(2)}),12)
        self.assertTrue(primitive('3*x**2').verify())
        self.assertEqual(definite_integral('3*x**2',0,2),8)
        self.assertEqual(limit('x*x-1','x-1',1).value,2)
        self.assertEqual(series('1/(1-x)',0,4).coefficients,(1,1,1,1,1))
        with self.assertRaises(ValueError):
            primitive('1/x')
        with self.assertRaises(ValueError):
            series('x',order=9)

    def test_rational_factorization_multiplicity_and_unresolved_residual(self):
        result=factor_rational(Polynomial((0,2,-3,1)))
        self.assertTrue(result.complete)
        self.assertEqual(result.roots,(0,1,2))
        result=factor_rational(Polynomial((F(1,2),-2,2)))
        self.assertEqual(result.roots,(F(1,2),F(1,2)))
        self.assertEqual(result.leading,2)
        self.assertFalse(factor_rational(Polynomial((1,0,1))).complete)
        with self.assertRaises(ValueError):
            factor_rational(Polynomial((1000000000000000001,1)),divisor_budget=10)


class SessionAndNotebookTests(unittest.TestCase):
    def test_session_bindings_convert_to_si_and_reject_domain_errors(self):
        session=CalculationSession().bind('distance',72,KILOMETER).bind('time',1,HOUR)
        row=session.evaluate('distance/time').to_data()
        self.assertEqual(row['result']['value'],'20')
        self.assertEqual(row['result']['unit']['scale'],'1')
        with self.assertRaises(ValueError):
            session.evaluate('1/x',{'x':0})
        with self.assertRaises(ValueError):
            session.execute('arbitrary_python',code='print(1)')

    def test_all_registered_operations_are_executed_and_replayed(self):
        requests={
          'evaluate':{'source':'x+x','values':{'x':2}},'simplify':{'source':'x+0'},
          'factor':{'coefficients':[-1,0,1]},'solve_linear':{'matrix':[[1,1],[1,-1]],'rhs':[3,1]},
          'lu':{'matrix':[[0,1],[1,2]]},'orthogonal_basis':{'vectors':[[1,1],[1,0]]},
          'condition':{'matrix':[[1,0],[0,2]]},'differentiate':{'source':'x*x'},
          'integrate':{'source':'x*x'},'limit':{'numerator':'x*x-1','denominator':'x-1','point':1},
          'series':{'source':'1/(1-x)'},'binomial':{'n':6,'k':2},
          'topological_sort':{'vertices':['a','b'],'edges':[['a','b']]},
          'markov':{'transition':[['1/2','1/2'],['1/4','3/4']],'distribution':[1,0],'steps':2},
          'statistics':{'values':[1,2,3],'sample':True,'window':2,'median':0,'population_variance':1,'radius':2},'approximate':{'value':'1/3'},
          'optimize':{'objective':[1,1],'x_bounds':[0,2],'y_bounds':[0,3]},
          'geometry':{'points':[[0,0],[2,0],[0,2]]},
          'conic':{'coefficients':[1,0,1,0,0,-1]},
          'quadratic_optimize':{'hessian':[[2]],'linear':[-4],'constraints':[[1]],'upper':[1]},
          'ode_adaptive':{'model':'exponential_decay','initial':[1],'rtol':1e-8},
          'ode':{'model':'exponential_decay','initial':[1],'steps':4}}
        from nablamath.calc.catalog import OPERATIONS
        self.assertEqual(set(requests) | set(OPERATIONS),set(AREAS))
        notebook=Notebook('all operations')
        for operation,args in requests.items():
            with self.subTest(operation=operation):
                calculation=CalculationSession().execute(operation,**args)
                self.assertFalse(calculation.to_data()['formal_proof'])
                notebook.append(calculation)
        self.assertEqual(notebook.replay(),len(requests))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'notebook.json';notebook.save(path)
            self.assertEqual(Notebook.load(path).replay(),len(requests))
            with self.assertRaises(FileExistsError):
                notebook.save(path)
            data=json.loads(path.read_text())
            data['cells'][0]['calculation']['result']['value']='999'
            # Rehash every layer: operation replay must still reject false results.
            previous=None
            for cell in data['cells']:
                calc=cell['calculation'];calc.pop('content_id')
                calc['content_id']=fingerprint(calc)
                cell['previous']=previous
                cell['cell_id']=fingerprint({'previous':previous,'calculation':calc})
                previous=cell['cell_id']
            data.pop('content_id');data['content_id']=fingerprint(data)
            path.write_text(canonical_json(data))
            with self.assertRaises(ValueError):
                Notebook.load(path)

    def test_cli_notebook_and_bad_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'n.json'
            self.assertEqual(main(['calc','statistics','--arguments','{"values":[1,2,3]}','--notebook',str(path)]),0)
            self.assertEqual(main(['replay-notebook',str(path)]),0)
            self.assertEqual(main(['calc','evaluate','--arguments','[]']),1)


class AdvancedPhaseOneTests(unittest.TestCase):
    def test_conics_transformations_and_constructions(self):
        from nablamath.math.geometry.conics import Conic,affine_transform,circumcenter
        from nablamath.math.geometry.euclidean import Point2
        cases=[((1,0,1,0,0,-1),'ellipse'),((1,0,1,0,0,1),'empty'),
               ((1,0,-1,0,0,-1),'hyperbola'),((1,0,0,0,-1,0),'parabola'),
               ((1,0,-1,0,0,0),'degenerate')]
        for coefficients,expected in cases:
            self.assertEqual(Conic(coefficients).classify(),expected)
        self.assertEqual(circumcenter(Point2(0,0),Point2(2,0),Point2(0,2)),Point2(1,1))
        self.assertEqual(affine_transform(Point2(1,2),Matrix(((0,-1),(1,0))),(3,0)),Point2(1,1))
        with self.assertRaises(ValueError):
            circumcenter(Point2(0,0),Point2(1,0),Point2(2,0))

    def test_exact_inference_and_time_series(self):
        from nablamath.math.statistics.inference import sign_test,mean_confidence_bound,exact_moving_average
        self.assertEqual(sign_test((1,2,3,4,5))['p_value'],F(1,16))
        self.assertEqual(sign_test((0,0))['p_value'],1)
        result=mean_confidence_bound((1,2,3,4),1,2)
        self.assertEqual(result['confidence_at_least'],F(15,16))
        self.assertEqual(result['interval'],(F(1,2),F(9,2)))
        self.assertEqual(exact_moving_average((1,2,3),2),(F(3,2),F(5,2)))

    def test_constrained_quadratic_kkt_and_infeasibility(self):
        from nablamath.math.optimization.quadratic import minimize_quadratic
        result=minimize_quadratic(Matrix(((2,),)),(-4,),((1,),),(1,))
        self.assertEqual(result.point,(1,))
        self.assertEqual(result.multipliers,(2,))
        self.assertEqual(result.value,-3)
        self.assertTrue(result.kkt_verified)
        with self.assertRaises(ValueError):
            minimize_quadratic(Matrix(((2,),)),(0,),((1,),(-1,)),(0,-1))
        with self.assertRaises(ValueError):
            minimize_quadratic(Matrix(((-2,),)),(0,))

    def test_session_rejects_missing_or_unknown_arguments(self):
        for operation,arguments in [('evaluate',{}),('integrate',{'source':'x','start':0}),
                ('statistics',{'values':[1,2],'radius':1}),('conic',{'coefficients':[1,0,1,0,0,-1],'execute':'bad'})]:
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                CalculationSession().execute(operation,**arguments)
        self.assertEqual(main(['calc','evaluate']),1)
