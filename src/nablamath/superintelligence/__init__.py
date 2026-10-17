"""Lazy imports keep procedural generation independent of neural backends."""
from importlib import import_module

__all__ = [
    "OmniEngine", "NeuralOperatorModule", "CausalBayesianModule",
    "PhotorealisticRadiativeModule", "MassiveDataStreamModule", "FormalMCTSModule",
    "SyntheticForgeModule", "ProcessRewardModule", "RamanujanConjectureModule",
    "SelfPlayCurriculumModule", "RLVRExporterModule", "SimulatedReasoningTrace",
]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    module = '.synthetic_cot_unroller' if name == 'SimulatedReasoningTrace' else '.omni_engine'
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value
    return value
