from fractions import Fraction as F
import unittest
from nablamath.core.units import Quantity as Q,ONE,METER,SECOND,KILOGRAM,KELVIN,AMPERE,MOLE,NEWTON,JOULE,VOLT
from nablamath.domains.contracts import PASCAL,WATT,OHM
from nablamath.domains.engineering import axial_bar,cantilever_tip
from nablamath.domains.materials import thermoelastic
from nablamath.domains.chemistry import balance_reaction,composition,two_species_equilibrium
from nablamath.domains.control import StateSpace
from nablamath.domains.earth import hydrostatic_pressure
from nablamath.domains.biology import logistic,sir
from nablamath.worlds.multiphysics import electrothermal
from nablamath.adapters.instruments import LinearCalibration,ingest_csv
from nablamath.knowledge.provenance_audit import replay_domain


class DomainTests(unittest.TestCase):
    def test_engineering_and_materials_known_values_and_units(self):
        report=axial_bar(Q(100,NEWTON),Q(2,METER),Q('1/100',METER**2),Q(1000000,PASCAL))
        self.assertEqual(F(report['outputs']['stress']),10000)
        self.assertEqual(F(report['outputs']['extension']),F(1,50))
        self.assertTrue(replay_domain(report))
        beam=cantilever_tip(Q(1,NEWTON),Q(1,METER),Q(1000000,PASCAL),Q('1/1000',METER**4))
        self.assertEqual(F(beam['outputs']['tip_deflection']),F(1,3000))
        self.assertTrue(replay_domain(beam))
        material=thermoelastic(Q(200000000000,PASCAL),Q('1/100000',ONE/KELVIN),Q(10,KELVIN),Q(0,ONE))
        self.assertEqual(F(material['outputs']['stress']),-20000000)
        self.assertTrue(replay_domain(material))
        with self.assertRaises(ValueError):axial_bar(Q(1,METER),Q(1,METER),Q(1,METER**2),Q(1,PASCAL))
        with self.assertRaises(ValueError):axial_bar(Q(100,NEWTON),Q(1,METER),Q(1,METER**2),Q(1,PASCAL))

    def test_chemistry_balances_atoms_and_rejects_underdetermined_or_charged(self):
        reaction=balance_reaction(('Fe','O2'),('Fe2O3',))
        self.assertEqual(reaction['outputs']['coefficients'],[4,3,2])
        self.assertTrue(replay_domain(reaction))
        self.assertEqual(composition('Ca(OH)2'),{'Ca':1,'H':2,'O':2})
        self.assertEqual(balance_reaction(('C2H6','O2'),('CO2','H2O'))['outputs']['coefficients'],[2,7,4,6])
        for reactants,products in [(('H2',),('CO2',)),(('C','O2'),('CO','CO2'))]:
            with self.assertRaises(ValueError):balance_reaction(reactants,products)
        for formula in ('Na+','H0','(OH','H2)O','2H','Xx2'):
            with self.assertRaises(ValueError):composition(formula)
        equilibrium=two_species_equilibrium(Q(3,MOLE),Q(2,ONE))
        self.assertEqual(equilibrium['outputs']['A'],'1');self.assertTrue(replay_domain(equilibrium))

    def test_control_hurwitz_and_reference_first_order(self):
        import math
        system=StateSpace(((-1,),),(1,),(1,))
        analysis=system.analyze();self.assertTrue(analysis['outputs']['asymptotically_stable'])
        self.assertTrue(replay_domain(analysis))
        simulation=system.simulate_step(duration=1,steps=100)
        self.assertAlmostEqual(simulation['outputs'][-1],1-math.exp(-1),places=8)
        stable=StateSpace(((0,1),(-2,-3)),(0,1),(1,0)).analyze()
        self.assertTrue(stable['outputs']['asymptotically_stable'])
        self.assertEqual(stable['outputs']['controllability_rank'],2)
        self.assertFalse(StateSpace(((1,),),(1,),(1,)).analyze()['outputs']['asymptotically_stable'])

    def test_earth_biology_and_coupled_energy(self):
        earth=hydrostatic_pressure(Q(1000,KILOGRAM/METER**3),Q('981/100',METER/SECOND**2),Q(10,METER),Q(101325,PASCAL))
        self.assertEqual(earth['outputs']['pressure'],'199425');self.assertTrue(replay_domain(earth))
        population=logistic(Q(10,ONE),Q(100,ONE),Q(1,ONE/SECOND),Q(2,SECOND))
        self.assertLess(population['outputs']['absolute_error'],1e-6);self.assertTrue(replay_domain(population))
        epidemic=sir(('99/100','1/100','0'),Q('3/10',ONE/SECOND),Q('1/10',ONE/SECOND),Q(10,SECOND))
        self.assertTrue(epidemic['checks_passed']);self.assertTrue(replay_domain(epidemic))
        heat=electrothermal(Q(2,AMPERE),Q(10,OHM),Q(100,JOULE/KELVIN),Q(5,WATT/KELVIN),Q('1/1000',ONE/KELVIN),Q(10,SECOND))
        self.assertTrue(heat['checks_passed']);self.assertTrue(replay_domain(heat))
        self.assertLess(heat['outputs']['integrated_energy_residual'],.01)
        with self.assertRaises(ValueError):electrothermal(Q(100,AMPERE),Q(10,OHM),Q(100,JOULE/KELVIN),Q(1,WATT/KELVIN),Q(1,ONE/KELVIN),Q(1,SECOND))

    def test_instrument_calibration_preserves_uncertainty_and_source(self):
        calibration=LinearCalibration(Q(10,KELVIN/VOLT),Q(273,KELVIN),KELVIN,'synthetic calibration fixture')
        report=ingest_csv('time_s,signal_V,uncertainty_V\n0,1,1/100\n1,2,1/50\n',calibration,source='fixture',device_id='sensor-1')
        self.assertEqual(report['measurements'][0]['value'],'283')
        self.assertEqual(report['measurements'][0]['uncertainty'],'1/10')
        self.assertFalse(report['device_authentication_performed'])
        with self.assertRaises(ValueError):ingest_csv('time_s,signal_V,uncertainty_V\n1,1,0\n0,1,0\n',calibration,source='fixture',device_id='sensor-1')
