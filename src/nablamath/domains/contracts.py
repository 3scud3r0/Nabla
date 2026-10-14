"""SI checks and portable result receipts shared by bounded disciplinary models."""
from fractions import Fraction
from ..core.units import Quantity, ONE, METER, SECOND, KILOGRAM, KELVIN, AMPERE, MOLE, NEWTON, JOULE, VOLT
from ..core.semantic_ir import fingerprint

PASCAL=NEWTON/METER**2
WATT=JOULE/SECOND
OHM=VOLT/AMPERE


def si(quantity,unit,*,positive=False,nonnegative=False):
    if not isinstance(quantity,Quantity):
        raise ValueError('Parâmetro requer Quantity com unidade explícita')
    value=quantity.to(unit).value
    if (positive and value<=0) or (nonnegative and value<0) or abs(value)>10**18:
        raise ValueError('Parâmetro físico fora do domínio')
    return value


def result(domain,model,inputs,outputs,units,checks,limitations):
    from ..core.semantic_ir import canonical_json
    import json
    def clean(value):
        if isinstance(value,Fraction):
            return str(value)
        if isinstance(value,Quantity):
            return {'value':str(value.value),'unit':value.unit.to_data()}
        if isinstance(value,dict):
            return {str(k):clean(v) for k,v in value.items()}
        if isinstance(value,(tuple,list)):
            return [clean(v) for v in value]
        return value
    payload=clean({'schema_version':1,'domain':domain,'model':model,'inputs':inputs,'outputs':outputs,
                   'units':units,'checks':checks,'checks_passed':bool(checks) and all(checks.values()),
                   'limitations':limitations,'experimental_validation':False})
    canonical_json(payload)
    return {**payload,'result_id':fingerprint(payload)}
