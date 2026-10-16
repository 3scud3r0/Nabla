"""Advanced finite-domain mathematics, with one canonical import namespace.

No global package symbols or legacy classes are overwritten. Functions here
are experimental additions and are also reachable through CalculationSession
for bounded JSON arguments using the 29 operation names in adapters.OPERATIONS.
"""
from .laboratory import *  # noqa: F401,F403
from .advanced_number_theory import *  # noqa: F401,F403
from .finite_fields import *  # noqa: F401,F403
from .rigorous_analysis import *  # noqa: F401,F403
from .discrete_optimization import *  # noqa: F401,F403
from .finite_probability import *  # noqa: F401,F403

from . import laboratory, advanced_number_theory, finite_fields
from . import rigorous_analysis, discrete_optimization, finite_probability

__all__ = list(dict.fromkeys(
    laboratory.__all__ + advanced_number_theory.__all__ + finite_fields.__all__
    + rigorous_analysis.__all__ + discrete_optimization.__all__
    + finite_probability.__all__
))
