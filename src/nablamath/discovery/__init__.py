"""Bounded hypothesis investigation, not automatic scientific discovery."""
from .hypothesis import Hypothesis, Observation, ObservationSet, assess
from .symbolic_regression import fit_models, fit_and_evaluate
from .experimental_design import propose_experiment
from .novelty_screen import screen_novelty

__all__=['Hypothesis','Observation','ObservationSet','assess','fit_models','fit_and_evaluate','propose_experiment','screen_novelty']
