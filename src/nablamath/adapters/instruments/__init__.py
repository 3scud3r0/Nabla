"""Offline calibrated sensor CSV ingestion; no implicit device/network access."""
from dataclasses import dataclass
import csv
import hashlib
import io
from ...core.semantic_ir import fingerprint, rational
from ...core.units import Quantity,Unit,SECOND,VOLT,KELVIN


@dataclass(frozen=True)
class LinearCalibration:
    gain: Quantity
    offset: Quantity
    output_unit: Unit
    provenance: str

    def __post_init__(self):
        if self.gain.unit.dimensions!=(self.output_unit/VOLT).dimensions or self.offset.unit.dimensions!=self.output_unit.dimensions:
            raise ValueError('Calibração requer ganho unidade/V e offset na unidade de saída')
        if not self.provenance.strip() or self.gain.value==0:
            raise ValueError('Ganho não nulo e procedência obrigatórios')

    def apply(self,signal,uncertainty):
        signal=signal.to(VOLT);uncertainty=uncertainty.to(VOLT)
        if uncertainty.value<0:
            raise ValueError('Incerteza não pode ser negativa')
        value=(self.gain*signal+self.offset).to(self.output_unit)
        spread=Quantity(abs(self.gain.value)*uncertainty.value,self.gain.unit*VOLT).to(self.output_unit)
        return value,spread

    def to_data(self):
        return {'gain':{'value':str(self.gain.value),'unit':self.gain.unit.to_data()},
                'offset':{'value':str(self.offset.value),'unit':self.offset.unit.to_data()},
                'output_unit':self.output_unit.to_data(),'provenance':self.provenance}


def ingest_csv(text,calibration,*,source,device_id):
    if not source.strip() or not device_id.strip() or len(text.encode())>4*1024*1024:
        raise ValueError('Fonte, identificador e tamanho de arquivo válidos obrigatórios')
    reader=csv.DictReader(io.StringIO(text))
    if reader.fieldnames!=['time_s','signal_V','uncertainty_V']:
        raise ValueError('CSV requer cabeçalho time_s,signal_V,uncertainty_V')
    rows=[];last=None
    for row in reader:
        if len(rows)>=10000 or set(row)!=set(reader.fieldnames) or any(v is None for v in row.values()):
            raise ValueError('Linha CSV inválida ou orçamento excedido')
        time=rational(row['time_s'])
        if time<0 or (last is not None and time<=last):
            raise ValueError('Tempo requer sequência estritamente crescente')
        value,uncertainty=calibration.apply(Quantity(rational(row['signal_V']),VOLT),Quantity(rational(row['uncertainty_V']),VOLT))
        rows.append({'time':str(time),'value':str(value.value),'uncertainty':str(uncertainty.value)})
        last=time
    if not rows:
        raise ValueError('Medições vazias')
    payload={'schema_version':1,'source':source,'device_id':device_id,'source_sha256':hashlib.sha256(text.encode()).hexdigest(),
             'calibration':calibration.to_data(),'time_unit':SECOND.to_data(),'output_unit':calibration.output_unit.to_data(),
             'measurements':rows,'device_authentication_performed':False,
             'limitations':'Offline declared calibration; provenance and instrument accuracy are not authenticated.'}
    return {**payload,'measurement_id':fingerprint(payload)}
