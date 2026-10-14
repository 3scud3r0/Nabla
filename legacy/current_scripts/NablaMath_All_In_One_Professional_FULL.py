#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NablaMath All-in-One Professional FULL
======================================
Single-file educational/scientific library + professional report generator.

This file intentionally contains everything in one place:
- minimal symbolic math and derivative engine;
- orbital mechanics calculations;
- reentry, thermal, pressure and plasma estimates;
- wind-tunnel surrogate;
- rocket/turbine optimization surrogates;
- scientific plots;
- equation rendering from LaTeX/mathtext to images;
- professional PDF and HTML report generation.

Run:
    python NablaMath_All_In_One_Professional_FULL.py --out outputs_nabla_full --pages 80 --no-video

The generated report is educational/analytical, not a certified aerospace design tool.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import random
import shutil
import subprocess
import textwrap
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

# ------------------------- optional/report imports -------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as mpl_cm
from matplotlib.colors import Normalize

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle,
    KeepTogether, Preformatted, HRFlowable
)
from reportlab.pdfgen import canvas


# =============================================================================
# 1. MATHEMATICAL CORE - SYMBOLIC EXPRESSIONS
# =============================================================================

class Expr:
    """Tiny symbolic expression object used to show derivations in the report."""
    def eval(self, env: Dict[str, float]) -> float:
        raise NotImplementedError
    def diff(self, var: str) -> "Expr":
        raise NotImplementedError
    def latex(self) -> str:
        raise NotImplementedError
    def __add__(self, other: Any) -> "Expr": return Add(self, to_expr(other))
    def __radd__(self, other: Any) -> "Expr": return Add(to_expr(other), self)
    def __mul__(self, other: Any) -> "Expr": return Mul(self, to_expr(other))
    def __rmul__(self, other: Any) -> "Expr": return Mul(to_expr(other), self)
    def __sub__(self, other: Any) -> "Expr": return Add(self, Mul(Number(-1), to_expr(other)))
    def __rsub__(self, other: Any) -> "Expr": return Add(to_expr(other), Mul(Number(-1), self))
    def __truediv__(self, other: Any) -> "Expr": return Mul(self, Pow(to_expr(other), Number(-1)))
    def __rtruediv__(self, other: Any) -> "Expr": return Mul(to_expr(other), Pow(self, Number(-1)))
    def __pow__(self, power: Any) -> "Expr": return Pow(self, to_expr(power))
    def __neg__(self) -> "Expr": return Mul(Number(-1), self)

@dataclass
class Number(Expr):
    value: float
    def eval(self, env: Dict[str, float]) -> float: return float(self.value)
    def diff(self, var: str) -> Expr: return Number(0)
    def latex(self) -> str:
        if abs(self.value - int(self.value)) < 1e-12: return str(int(self.value))
        return f"{self.value:.6g}"

@dataclass
class Symbol(Expr):
    name: str
    def eval(self, env: Dict[str, float]) -> float: return float(env[self.name])
    def diff(self, var: str) -> Expr: return Number(1 if self.name == var else 0)
    def latex(self) -> str: return self.name

@dataclass
class Add(Expr):
    a: Expr; b: Expr
    def eval(self, env: Dict[str, float]) -> float: return self.a.eval(env) + self.b.eval(env)
    def diff(self, var: str) -> Expr: return Add(self.a.diff(var), self.b.diff(var))
    def latex(self) -> str: return f"{self.a.latex()} + {self.b.latex()}"

@dataclass
class Mul(Expr):
    a: Expr; b: Expr
    def eval(self, env: Dict[str, float]) -> float: return self.a.eval(env) * self.b.eval(env)
    def diff(self, var: str) -> Expr: return Add(Mul(self.a.diff(var), self.b), Mul(self.a, self.b.diff(var)))
    def latex(self) -> str: return f"({self.a.latex()})({self.b.latex()})"

@dataclass
class Pow(Expr):
    base: Expr; exp: Expr
    def eval(self, env: Dict[str, float]) -> float: return self.base.eval(env) ** self.exp.eval(env)
    def diff(self, var: str) -> Expr:
        if isinstance(self.exp, Number):
            return Mul(Mul(self.exp, Pow(self.base, Number(self.exp.value - 1))), self.base.diff(var))
        return Mul(self, Add(Mul(self.exp.diff(var), Log(self.base)), Mul(self.exp, self.base.diff(var) / self.base)))
    def latex(self) -> str: return f"({self.base.latex()})^{{{self.exp.latex()}}}"

@dataclass
class Sin(Expr):
    x: Expr
    def eval(self, env: Dict[str, float]) -> float: return math.sin(self.x.eval(env))
    def diff(self, var: str) -> Expr: return Mul(Cos(self.x), self.x.diff(var))
    def latex(self) -> str: return f"\\sin({self.x.latex()})"

@dataclass
class Cos(Expr):
    x: Expr
    def eval(self, env: Dict[str, float]) -> float: return math.cos(self.x.eval(env))
    def diff(self, var: str) -> Expr: return Mul(Number(-1), Mul(Sin(self.x), self.x.diff(var)))
    def latex(self) -> str: return f"\\cos({self.x.latex()})"

@dataclass
class Log(Expr):
    x: Expr
    def eval(self, env: Dict[str, float]) -> float: return math.log(self.x.eval(env))
    def diff(self, var: str) -> Expr: return self.x.diff(var) / self.x
    def latex(self) -> str: return f"\\ln({self.x.latex()})"


def to_expr(x: Any) -> Expr:
    return x if isinstance(x, Expr) else Number(float(x))

def symbols(names: str) -> Tuple[Symbol, ...]:
    return tuple(Symbol(n.strip()) for n in names.replace(',', ' ').split())

def sin(x: Any) -> Expr: return Sin(to_expr(x))
def cos(x: Any) -> Expr: return Cos(to_expr(x))
def log(x: Any) -> Expr: return Log(to_expr(x))


# =============================================================================
# 2. PHYSICAL CONSTANTS AND CONFIGURATION
# =============================================================================

G0 = 9.80665
R_EARTH = 6_371_000.0
MU_EARTH = 3.986004418e14
R_AIR = 287.05
GAMMA_AIR = 1.4
SIGMA_SB = 5.670374419e-8
M_AIR = 4.81e-26

@dataclass
class Vehicle:
    name: str = "Asteria-R Reusable Orbital Vehicle"
    mass_initial_kg: float = 132_000.0
    mass_dry_kg: float = 86_000.0
    nose_radius_m: float = 1.35
    body_radius_m: float = 4.5
    length_m: float = 52.0
    reference_area_m2: float = 63.6
    cd: float = 1.28
    lift_to_drag: float = 0.22
    emissivity: float = 0.84
    landing_isp_s: float = 330.0
    landing_burn_start_altitude_m: float = 2800.0
    comm_frequency_hz: float = 2.25e9

@dataclass
class Mission:
    name: str = "Asteria-Professional-Dossier"
    report_title: str = "NablaMath Professional Orbital Dossier"
    orbit_altitude_m: float = 430_000.0
    perigee_target_m: float = 38_000.0
    entry_interface_altitude_m: float = 122_000.0
    dt_s: float = 0.5
    max_time_s: float = 5000.0
    bank_angle_deg: float = 32.0
    xray_threshold_k: float = 260_000.0
    vehicle: Vehicle = field(default_factory=Vehicle)


# =============================================================================
# 3. ATMOSPHERE, ORBITAL MECHANICS AND REENTRY
# =============================================================================

_ATMOS = [
    (0.0, 288.15, 101325.0, -0.0065),
    (11000.0, 216.65, 22632.06, 0.0),
    (20000.0, 216.65, 5474.889, 0.001),
    (32000.0, 228.65, 868.0187, 0.0028),
    (47000.0, 270.65, 110.9063, 0.0),
    (51000.0, 270.65, 66.93887, -0.0028),
    (71000.0, 214.65, 3.956420, -0.002),
    (86000.0, 186.946, 0.3734, 0.0),
]

def atmosphere(h: float) -> Dict[str, float]:
    h = max(0.0, float(h))
    if h <= 86000.0:
        layer = _ATMOS[-1]
        for i in range(len(_ATMOS)-1):
            if _ATMOS[i][0] <= h < _ATMOS[i+1][0]: layer = _ATMOS[i]; break
        hb, Tb, pb, L = layer
        if abs(L) < 1e-12:
            T = Tb
            p = pb * math.exp(-G0 * (h - hb) / (R_AIR * Tb))
        else:
            T = Tb + L * (h - hb)
            p = pb * (T / Tb) ** (-G0 / (L * R_AIR))
        rho = p / (R_AIR * T)
    else:
        base = atmosphere(86000.0)
        H = 7200.0 + 1100.0 * min((h - 86000.0) / 90000.0, 4.0)
        T = max(180.0, 186.946 + 0.0022 * (h - 86000.0))
        rho = base['rho'] * math.exp(-(h - 86000.0) / H)
        p = rho * R_AIR * T
    a = math.sqrt(GAMMA_AIR * R_AIR * T)
    return {'T': T, 'p': p, 'rho': rho, 'a': a}

def circular_orbit(h: float) -> Dict[str, float]:
    r = R_EARTH + h
    v = math.sqrt(MU_EARTH / r)
    T = 2 * math.pi * math.sqrt(r**3 / MU_EARTH)
    eps = -MU_EARTH / (2*r)
    return {'r': r, 'v': v, 'period': T, 'energy': eps}

def deorbit_burn(h_orb: float, h_perigee: float) -> Dict[str, float]:
    ra = R_EARTH + h_orb
    rp = R_EARTH + h_perigee
    at = 0.5 * (ra + rp)
    vc = math.sqrt(MU_EARTH / ra)
    va = math.sqrt(MU_EARTH * (2/ra - 1/at))
    vp = math.sqrt(MU_EARTH * (2/rp - 1/at))
    return {'ra': ra, 'rp': rp, 'a_transfer': at, 'v_circ': vc, 'v_apogee': va, 'v_perigee': vp, 'dv': vc - va, 'ecc': (ra-rp)/(ra+rp)}

def entry_velocity(m: Mission) -> Dict[str, float]:
    db = deorbit_burn(m.orbit_altitude_m, m.perigee_target_m)
    r = R_EARTH + m.entry_interface_altitude_m
    v = math.sqrt(MU_EARTH * (2/r - 1/db['a_transfer']))
    return {'r': r, 'v': v, 'gamma_deg': -1.25}

def sutton_graves(rho: float, v: float, rn: float) -> float:
    # scaled educational W/m^2 estimate
    return 1.83e-4 * math.sqrt(max(rho, 1e-12) / max(rn, 1e-6)) * v**3 * 1e4

def stagnation_pressure(p: float, M: float) -> float:
    return p * (1 + 0.5*(GAMMA_AIR - 1)*M*M) ** (GAMMA_AIR/(GAMMA_AIR - 1))

def ionization_fraction(T_wall: float, rho: float) -> float:
    thermal = 1/(1 + math.exp(-(T_wall - 6200)/900))
    dens = min(1, math.sqrt(max(rho, 0)/0.02 + 1e-12))
    return min(1, thermal * dens)

def plasma_frequency(ne_m3: float) -> float:
    return 8980.0 * math.sqrt(max(ne_m3, 0)/1e6)

def spectral(T_wall: float, threshold: float) -> Dict[str, float]:
    return {
        'ir': min(1, (T_wall/2200)**1.2),
        'uv': min(1, max(0, (T_wall - 2800)/6000)),
        'xray': min(1, math.exp(-(threshold/max(T_wall,1))**0.7)),
    }

def simulate_mission(m: Mission) -> Dict[str, Any]:
    vcfg = m.vehicle
    entry = entry_velocity(m)
    r = entry['r']; h = m.entry_interface_altitude_m; v = entry['v']; gamma = math.radians(entry['gamma_deg'])
    theta = 0.0; t = 0.0; mass = vcfg.mass_initial_kg
    A = vcfg.reference_area_m2; Cd = vcfg.cd; CL = Cd * vcfg.lift_to_drag * math.cos(math.radians(m.bank_angle_deg))
    rows: Dict[str, list] = {k: [] for k in ['t','h','v','gamma','downrange','rho','p','T','Mach','q','gload','heat','Twall','p0','ion','ne','fp','ir','uv','xray','phase']}
    blackout_start = None; blackout_end = None
    while h > max(vcfg.landing_burn_start_altitude_m, 1000) and t < m.max_time_s and v > 50:
        atm = atmosphere(h); rho = atm['rho']; p = atm['p']; T = atm['T']; a = atm['a']; Mach = v/max(a,1e-9)
        q = 0.5*rho*v*v; D = q*Cd*A; L = q*CL*A; gl = MU_EARTH/(r*r)
        dv = -D/mass - gl*math.sin(gamma)
        dg = L/max(mass*v,1e-6) + (v/r - gl/max(v,1e-6))*math.cos(gamma)
        dr = v*math.sin(gamma); dtheta = v*math.cos(gamma)/r
        heat = sutton_graves(rho, v, vcfg.nose_radius_m)
        Twall = min(4200, max(T, (heat/max(vcfg.emissivity*SIGMA_SB,1e-12))**0.25))
        p0 = stagnation_pressure(p, Mach)
        ion = ionization_fraction(Twall, rho); ne = ion*rho/M_AIR; fp = plasma_frequency(ne); sp = spectral(Twall, m.xray_threshold_k)
        gload = abs(dv)/G0
        for k,val in [('t',t),('h',h),('v',v),('gamma',math.degrees(gamma)),('downrange',R_EARTH*theta),('rho',rho),('p',p),('T',T),('Mach',Mach),('q',q),('gload',gload),('heat',heat),('Twall',Twall),('p0',p0),('ion',ion),('ne',ne),('fp',fp),('ir',sp['ir']),('uv',sp['uv']),('xray',sp['xray']),('phase',0)]: rows[k].append(val)
        if fp > vcfg.comm_frequency_hz and blackout_start is None: blackout_start = t
        if fp <= vcfg.comm_frequency_hz and blackout_start is not None and blackout_end is None: blackout_end = t
        v = max(0, v + dv*m.dt_s); gamma += dg*m.dt_s; r += dr*m.dt_s; theta += dtheta*m.dt_s; h = max(0, r - R_EARTH); t += m.dt_s
    burn_h = max(h, vcfg.landing_burn_start_altitude_m); burn_v = max(v, 1.0)
    a_req = burn_v**2/(2*max(burn_h,1)); decel = a_req + 0.35*G0
    landing_dv = burn_v + 35; prop_ratio = math.exp(landing_dv/(vcfg.landing_isp_s*G0)); prop = max(0, mass - mass/prop_ratio)
    thrust = mass*(decel + G0); burn_time = max(1, burn_v/max(decel,1e-6))
    tl = {k: np.array(v, dtype=float) for k,v in rows.items()}
    blackout_duration = 0 if blackout_start is None else ((tl['t'][-1] if blackout_end is None else blackout_end) - blackout_start)
    summary = {
        'orbit': circular_orbit(m.orbit_altitude_m),
        'deorbit': deorbit_burn(m.orbit_altitude_m, m.perigee_target_m),
        'entry': entry,
        'peak_heat': float(np.max(tl['heat'])),
        'peak_q': float(np.max(tl['q'])),
        'peak_g': float(np.max(tl['gload'])),
        'peak_Twall': float(np.max(tl['Twall'])),
        'peak_fp': float(np.max(tl['fp'])),
        'blackout_duration': float(blackout_duration),
        'landing_propellant': float(prop),
        'landing_thrust': float(thrust),
        'landing_burn_time': float(burn_time),
        'landing_burn_start_h': float(burn_h),
        'landing_burn_start_v': float(burn_v),
    }
    return {'timeline': tl, 'summary': summary, 'mission': asdict(m)}


# =============================================================================
# 4. WIND TUNNEL AND OPTIMIZATION SURROGATES
# =============================================================================

@dataclass
class Shape:
    nose_len: float = 9.5
    body_len: float = 39.0
    radius: float = 4.55
    tail_len: float = 4.0
    fin_span: float = 3.6
    fin_count: int = 4
    fin_root: float = 6.2
    fin_tip: float = 2.3
    engine_radius: float = 1.28
    @property
    def length(self) -> float: return self.nose_len + self.body_len + self.tail_len
    @property
    def area(self) -> float: return math.pi*self.radius**2
    @property
    def volume(self) -> float: return math.pi*self.radius**2*self.body_len

def aero_surrogate(shape: Shape, V: float, aoa_deg: float, altitude: float=0.0) -> Dict[str,float]:
    atm = atmosphere(altitude); rho = atm['rho']; T = atm['T']; a = atm['a']; Mach = V/max(a,1e-9)
    mu = 1.458e-6*T**1.5/(T+110.4)
    Re = rho*V*shape.length/max(mu,1e-12)
    alpha = math.radians(aoa_deg)
    fineness = shape.length/max(2*shape.radius,0.1)
    wetted = 2*math.pi*shape.radius*shape.body_len + math.pi*shape.radius*math.sqrt(shape.radius**2+shape.nose_len**2)
    cf = 0.455/max(math.log10(max(Re,10)),1)**2.58
    cd = max(0.05, 0.09 + 0.18/max(fineness,1.2) + cf*wetted/max(shape.area,1e-9) + 0.13*math.exp(-((Mach-1.05)/0.34)**2) + 0.032*max(Mach-1.2,0) + 0.22*alpha*alpha + 0.006*shape.fin_count*shape.fin_span/max(shape.radius,0.1))
    ar = 2*shape.fin_span/max(0.5*(shape.fin_root+shape.fin_tip),0.2)
    cl = (2*math.pi*ar/max(ar+2,0.5))*alpha*(1+0.05*min(Mach,3))
    stability = (0.58*shape.length - 0.47*shape.length)/max(2*shape.radius,0.1) + 0.04*shape.fin_root
    q = 0.5*rho*V*V
    return {'Mach':Mach,'Re':Re,'rho':rho,'q':q,'Cd':cd,'Cl':cl,'stability':stability,'heat':sutton_graves(rho,V,1.35)}

def wind_tunnel(shape: Shape) -> Dict[str,Any]:
    speeds = np.array([120,250,500,900,1400,2200,3200,3800], dtype=float)
    aoas = np.array([-6,-2,0,4,8,12], dtype=float)
    Cd = np.zeros((len(aoas),len(speeds))); Cl=np.zeros_like(Cd); Heat=np.zeros_like(Cd); Stab=np.zeros_like(Cd)
    for i,a in enumerate(aoas):
        for j,V in enumerate(speeds):
            o=aero_surrogate(shape,V,a,2500 if V<1400 else 12000)
            Cd[i,j]=o['Cd']; Cl[i,j]=o['Cl']; Heat[i,j]=o['heat']; Stab[i,j]=o['stability']
    score = Cd + 1e-7*Heat + 0.01*np.maximum(0,1.1-Stab)**2
    idx=np.unravel_index(np.argmin(score),score.shape)
    return {'speeds':speeds,'aoas':aoas,'Cd':Cd,'Cl':Cl,'Heat':Heat,'Stab':Stab,'best':{'V':float(speeds[idx[1]]),'aoa':float(aoas[idx[0]]),'Cd':float(Cd[idx]),'heat':float(Heat[idx]),'stability':float(Stab[idx])}}

def optimize_shape(seed: int=123, iters: int=80) -> Dict[str,Any]:
    rng=random.Random(seed); best=None; hist=[]
    for i in range(iters):
        s=Shape(nose_len=rng.uniform(6,14), body_len=rng.uniform(28,46), radius=rng.uniform(3.2,5.4), tail_len=rng.uniform(2,5.5), fin_span=rng.uniform(2,5.2), fin_count=rng.randint(3,5), fin_root=rng.uniform(4,8.5), fin_tip=rng.uniform(1,4), engine_radius=rng.uniform(0.8,1.9))
        vals=[aero_surrogate(s,V,a,12000 if V>1000 else 0) for V in [300,900,2200,3500] for a in [0,5]]
        avg_cd=float(np.mean([v['Cd'] for v in vals])); max_heat=float(np.max([v['heat'] for v in vals])); stab=float(np.mean([v['stability'] for v in vals]))
        score=2.0*avg_cd+0.08*(max_heat/1e6)+max(0,1-stab)**2-0.003*s.volume/10
        item={'i':i+1,'score':score,'avg_cd':avg_cd,'max_heat':max_heat,'stability':stab,'volume':s.volume,'shape':asdict(s)}
        hist.append(item)
        if best is None or score<best['score']: best=item
    return {'best':best,'history':hist}

def optimize_turbine(seed:int=321,iters:int=80)->Dict[str,Any]:
    rng=random.Random(seed); best=None; hist=[]
    for i in range(iters):
        radius=rng.uniform(0.28,0.58); hub=rng.uniform(0.08,min(0.24,radius-0.04)); blades=rng.randint(18,38); rpm=rng.uniform(18000,48000); flow=rng.uniform(18,70); pr=rng.uniform(8,22); temp=rng.uniform(780,1250); chord=(rng.uniform(0.07,0.16)+rng.uniform(0.03,0.09))/2
        omega=rpm*2*math.pi/60; utip=omega*radius; tipM=utip/math.sqrt(GAMMA_AIR*R_AIR*temp); area=math.pi*(radius*radius-hub*hub)
        solidity=blades*chord/max(2*math.pi*radius,1e-9); flow_coeff=flow/max(area*35*temp/1000,1e-9); loading=pr/max((utip/300)**2,1e-9)
        eff=0.91-0.11*abs(flow_coeff-0.6)-0.08*abs(loading-1.55)-0.05*abs(solidity-1.25)-0.04*max(0,tipM-1.08)
        eff=float(np.clip(eff,0.4,0.95)); score=-eff+0.08*max(0,tipM-1.1)
        item={'i':i+1,'score':score,'eff':eff,'radius':radius,'hub':hub,'blades':blades,'rpm':rpm,'flow':flow,'pressure_ratio':pr,'tip_mach':tipM,'solidity':solidity,'loading':loading}
        hist.append(item)
        if best is None or score<best['score']: best=item
    return {'best':best,'history':hist}


# =============================================================================
# 5. PLOTTING AND RENDERING
# =============================================================================

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True); return p

def savefig(path: Path) -> str:
    plt.tight_layout(); plt.savefig(path, dpi=190); plt.close(); return str(path)

def rocket_surface(shape: Shape, mode: str, out: Path) -> str:
    theta=np.linspace(0,2*np.pi,80); x=np.linspace(0,shape.length,130)
    X,TH=np.meshgrid(x,theta)
    R=np.piecewise(X,[X<shape.nose_len,(X>=shape.nose_len)&(X<shape.nose_len+shape.body_len),X>=shape.nose_len+shape.body_len],[lambda z: shape.radius*(z/shape.nose_len)**0.75, shape.radius, lambda z: shape.radius-(shape.radius-shape.engine_radius)*((z-(shape.nose_len+shape.body_len))/shape.tail_len)**1.2])
    Y=R*np.cos(TH); Z=R*np.sin(TH); xn=X/shape.length
    if mode=='beauty':
        val=0.6+0.35*np.sin(18*xn+25*TH)**2; cmap='Greys'; title='Procedural metallic/ceramic rocket render'
    elif mode=='thermal':
        val=np.exp(-5*xn)+0.45*((TH>np.pi*0.7)&(TH<np.pi*1.3)); cmap='inferno'; title='Thermal surface load render'
    elif mode=='infrared':
        val=np.exp(-3*xn); cmap='magma'; title='Infrared diagnostic render'
    else:
        val=(1-xn)**0.4 + 0.15*np.sin(8*TH)**2; cmap='cividis'; title='X-ray analytic proxy render'
    fig=plt.figure(figsize=(9,6)); ax=fig.add_subplot(111,projection='3d'); norm=Normalize(float(np.min(val)),float(np.max(val))); colors_rgba=mpl_cm.get_cmap(cmap)(norm(val))
    ax.plot_surface(X,Y,Z,facecolors=colors_rgba,linewidth=0,antialiased=False,shade=False)
    ax.set_title(title); ax.set_xlabel('x [m]'); ax.set_ylabel('y [m]'); ax.set_zlabel('z [m]'); ax.view_init(elev=24,azim=43)
    return savefig(out)

def make_figures(data: Dict[str,Any], out_dir: Path) -> Dict[str,str]:
    figs={}; tl=data['timeline']; shape=Shape()
    plt.figure(figsize=(10,7)); plt.subplot(2,2,1); plt.plot(tl['t'],tl['h']/1000); plt.xlabel('t [s]'); plt.ylabel('h [km]'); plt.title('Altitude')
    plt.subplot(2,2,2); plt.plot(tl['t'],tl['v']); plt.xlabel('t [s]'); plt.ylabel('v [m/s]'); plt.title('Velocity')
    plt.subplot(2,2,3); plt.plot(tl['t'],tl['q']/1000,label='q kPa'); plt.plot(tl['t'],tl['heat']/1e6,label='heat MW/m^2'); plt.legend(); plt.title('Loads')
    plt.subplot(2,2,4); plt.plot(tl['t'],tl['Mach'],label='Mach'); plt.plot(tl['t'],tl['gload'],label='g-load'); plt.legend(); plt.title('State')
    figs['profiles']=savefig(out_dir/'profiles_dashboard.png')
    plt.figure(figsize=(10,7)); plt.subplot(2,2,1); plt.semilogy(tl['h']/1000,tl['p']); plt.xlabel('h [km]'); plt.ylabel('p [Pa]'); plt.title('Pressure')
    plt.subplot(2,2,2); plt.plot(tl['h']/1000,tl['T'],label='ambient'); plt.plot(tl['h']/1000,tl['Twall'],label='wall'); plt.legend(); plt.title('Temperature')
    plt.subplot(2,2,3); plt.semilogy(tl['t'],tl['ne']); plt.title('Electron density'); plt.xlabel('t [s]')
    plt.subplot(2,2,4); plt.plot(tl['t'],tl['fp']/1e9); plt.axhline(data['mission']['vehicle']['comm_frequency_hz']/1e9,ls='--'); plt.title('Plasma frequency [GHz]')
    figs['plasma']=savefig(out_dir/'thermo_plasma_dashboard.png')
    # trajectory 3D
    fig=plt.figure(figsize=(9,7)); ax=fig.add_subplot(111,projection='3d'); ang=tl['downrange']/R_EARTH; r=R_EARTH+tl['h']; lat=np.deg2rad(18); x=r*np.cos(ang)*np.cos(lat); y=r*np.sin(ang)*np.cos(lat); z=r*np.sin(lat)
    ax.plot(x/1000,y/1000,z/1000); ax.scatter(x/1000,y/1000,z/1000,c=tl['Twall'],s=8,cmap='inferno'); ax.set_title('3D trajectory colored by wall temperature'); ax.set_xlabel('x km'); ax.set_ylabel('y km'); ax.set_zlabel('z km')
    figs['trajectory']=savefig(out_dir/'trajectory_3d.png')
    for mode in ['beauty','thermal','infrared','xray']: figs[mode]=rocket_surface(shape,mode,out_dir/f'rocket_{mode}.png')
    # wind and optimization
    wt=wind_tunnel(shape); plt.figure(figsize=(8,5)); plt.imshow(wt['Cd'],origin='lower',aspect='auto',extent=[wt['speeds'][0],wt['speeds'][-1],wt['aoas'][0],wt['aoas'][-1]],cmap='viridis'); plt.colorbar(label='Cd'); plt.xlabel('V [m/s]'); plt.ylabel('AoA deg'); plt.title('Wind tunnel Cd map'); figs['wind_cd']=savefig(out_dir/'wind_tunnel_cd.png')
    opt=data['shape_opt']; plt.figure(figsize=(8,5)); plt.plot([h['i'] for h in opt['history']],[h['score'] for h in opt['history']],label='score'); plt.plot([h['i'] for h in opt['history']],[h['avg_cd'] for h in opt['history']],label='avg Cd'); plt.legend(); plt.title('Rocket shape optimization'); figs['shape_opt']=savefig(out_dir/'shape_optimization.png')
    turb=data['turbine_opt']; plt.figure(figsize=(8,5)); plt.plot([h['i'] for h in turb['history']],[h['eff'] for h in turb['history']],label='eff'); plt.plot([h['i'] for h in turb['history']],[h['tip_mach'] for h in turb['history']],label='tip Mach'); plt.legend(); plt.title('Turbine optimization'); figs['turb_opt']=savefig(out_dir/'turbine_optimization.png')
    return figs


# =============================================================================
# 6. EQUATION RENDERING AND PROFESSIONAL REPORT
# =============================================================================

class EquationRenderer:
    def __init__(self, out_dir: Path):
        self.out_dir=ensure_dir(out_dir); self.count=0
    def render(self, latex: str, fontsize: int=18) -> str:
        self.count += 1; path=self.out_dir/f'eq_{self.count:03d}.png'
        fig=plt.figure(figsize=(0.01,0.01)); fig.text(0,0,f"${latex}$",fontsize=fontsize)
        fig.canvas.draw(); bbox=fig.get_tightbbox(fig.canvas.get_renderer())
        w=max(4,bbox.width); h=max(0.7,bbox.height)
        plt.close(fig)
        fig=plt.figure(figsize=(min(12,w+0.7),h+0.35))
        fig.patch.set_alpha(0); fig.text(0.02,0.5,f"${latex}$",fontsize=fontsize,va='center')
        plt.axis('off'); plt.savefig(path,dpi=190,transparent=True,bbox_inches='tight',pad_inches=0.12); plt.close(fig)
        return str(path)

def header_footer(canv: canvas.Canvas, doc: SimpleDocTemplate):
    canv.saveState(); canv.setFont('Helvetica',8); canv.setFillColor(colors.HexColor('#4b5563'))
    canv.drawString(1.4*cm, A4[1]-0.75*cm, 'NablaMath All-in-One Professional FULL')
    canv.drawRightString(A4[0]-1.4*cm, 0.75*cm, f'Page {doc.page}')
    canv.restoreState()

def para_styles():
    ss=getSampleStyleSheet()
    ss.add(ParagraphStyle(name='TitlePro', parent=ss['Title'], fontSize=22, leading=28, alignment=TA_CENTER, textColor=colors.HexColor('#0f172a'), spaceAfter=14))
    ss.add(ParagraphStyle(name='H1Pro', parent=ss['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#111827'), spaceBefore=16, spaceAfter=8))
    ss.add(ParagraphStyle(name='H2Pro', parent=ss['Heading2'], fontSize=13, leading=16, textColor=colors.HexColor('#1f2937'), spaceBefore=10, spaceAfter=6))
    ss.add(ParagraphStyle(name='BodyPro', parent=ss['BodyText'], fontSize=9.6, leading=13, alignment=TA_JUSTIFY, spaceAfter=6))
    ss.add(ParagraphStyle(name='Caption', parent=ss['BodyText'], fontSize=8.3, leading=10, textColor=colors.HexColor('#4b5563'), alignment=TA_CENTER, spaceAfter=8))
    return ss

def _rl_img(path: str, width_cm: float) -> Image:
    from PIL import Image as PILImage
    im = PILImage.open(path)
    wpx, hpx = im.size
    width = width_cm * cm
    height = width * (hpx / max(wpx, 1))
    return Image(path, width=width, height=height)

def eq_flow(eq_renderer: EquationRenderer, latex: str, width_cm: float=16.0, fontsize:int=17) -> Image:
    return _rl_img(eq_renderer.render(latex, fontsize=fontsize), width_cm)

def small_table(rows: List[List[Any]], col_widths: Optional[List[float]]=None) -> Table:
    t=Table(rows, colWidths=[w*cm for w in col_widths] if col_widths else None, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0f172a')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONT',(0,0),(-1,0),'Helvetica-Bold',8),
        ('FONT',(0,1),(-1,-1),'Helvetica',7.5),('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#cbd5e1')),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f8fafc')])
    ])); return t

def build_report(data: Dict[str,Any], figs: Dict[str,str], out_pdf: Path, out_html: Path, pages_target: int=60) -> None:
    styles=para_styles(); eqr=EquationRenderer(out_pdf.parent/'equations')
    story=[]; s=data['summary']; m=data['mission']; v=m['vehicle']
    def H1(t): story.append(Paragraph(t,styles['H1Pro']))
    def H2(t): story.append(Paragraph(t,styles['H2Pro']))
    def P(t): story.append(Paragraph(t,styles['BodyPro']))
    def IMG(path, w=16.5, caption=''):
        story.append(_rl_img(path, w))
        if caption: story.append(Paragraph(caption,styles['Caption']))
    story.append(Paragraph(m['report_title'],styles['TitlePro']))
    story.append(Paragraph('Dossie técnico com cálculos em LaTeX, derivacoes passo a passo, tabelas numericas, renderizacoes cientificas e apendices de reproducibilidade.',styles['BodyPro']))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#94a3b8'))); story.append(Spacer(1,0.3*cm))
    P('<b>Resumo:</b> Este PDF foi gerado por um unico arquivo Python que contem a biblioteca matematica, os modelos orbitais, o tunel de vento surrogate, otimizadores, gerador de figuras, renderizador de equacoes e montador de relatorio. As equacoes abaixo sao renderizadas como imagens matematicas, nao apenas texto comum.')
    rows=[['Metrica','Valor'],['Velocidade orbital',f"{s['orbit']['v']:.3f} m/s"],['Delta-v de deorbit',f"{s['deorbit']['dv']:.3f} m/s"],['Velocidade na interface',f"{s['entry']['v']:.3f} m/s"],['Pico de calor',f"{s['peak_heat']:.3e} W/m²"],['Pico q dinamico',f"{s['peak_q']:.3e} Pa"],['Pico g-load',f"{s['peak_g']:.3f} g"],['Pico temperatura parede',f"{s['peak_Twall']:.2f} K"],['Pico plasma',f"{s['peak_fp']:.3e} Hz"],['Blackout',f"{s['blackout_duration']:.2f} s"],['Propelente recaptura',f"{s['landing_propellant']:.2f} kg"]]
    story.append(small_table(rows,[6,9])); story.append(PageBreak())

    H1('1. Entrada completa e constantes físicas')
    P('A seção preserva a configuracao da missao e explicita as constantes. Isto e importante porque um relatorio cientifico profissional precisa ser reproduzivel: a mesma entrada deve gerar os mesmos numeros, graficos e tabelas.')
    story.append(Preformatted(json.dumps(m,indent=2,ensure_ascii=False),styles['Code']))
    H2('Constantes fundamentais')
    story.append(small_table([['Constante','Valor','Uso'],['g0','9.80665 m/s²','gravidade padrao'],['R_E',f'{R_EARTH:.0f} m','raio medio terrestre'],['mu_E',f'{MU_EARTH:.9e} m³/s²','parametro gravitacional'],['R_air',f'{R_AIR:.2f} J/(kg K)','gas ideal ar'],['gamma',f'{GAMMA_AIR:.2f}','razao cp/cv'],['sigma',f'{SIGMA_SB:.9e}','Stefan-Boltzmann']], [4,4,7]))

    H1('2. Derivacao da orbita circular')
    P('Para uma orbita circular, a aceleracao centripeta deve ser igual a aceleracao gravitacional newtoniana. Comecamos com a igualdade entre forca gravitacional e massa vezes aceleracao centripeta.')
    story += [eq_flow(eqr,r"\frac{m v^2}{r}=\frac{\mu m}{r^2}"), eq_flow(eqr,r"v^2=\frac{\mu}{r}"), eq_flow(eqr,r"v_{orb}=\sqrt{\frac{\mu}{R_E+h_{orb}}}")]
    P(f"Substituindo h_orb = {m['orbit_altitude_m']:.0f} m e R_E = {R_EARTH:.0f} m, obtemos r_orb = {s['orbit']['r']:.0f} m e v_orb = {s['orbit']['v']:.3f} m/s.")
    story += [eq_flow(eqr,fr"r_{{orb}}={R_EARTH:.0f}+{m['orbit_altitude_m']:.0f}={s['orbit']['r']:.0f}\;\mathrm{{m}}"), eq_flow(eqr,fr"v_{{orb}}=\sqrt{{\frac{{{MU_EARTH:.6e}}}{{{s['orbit']['r']:.0f}}}}}={s['orbit']['v']:.3f}\;\mathrm{{m/s}}")]
    P('O periodo orbital segue de T = distancia / velocidade = 2*pi*r/v, ou diretamente T = 2*pi*sqrt(r^3/mu).')
    story += [eq_flow(eqr,r"T=\frac{2\pi r}{v}=2\pi\sqrt{\frac{r^3}{\mu}}"), eq_flow(eqr,fr"T_{{orb}}={s['orbit']['period']:.3f}\;\mathrm{{s}}={s['orbit']['period']/60:.3f}\;\mathrm{{min}}")]

    H1('3. Deorbit burn e transferencia eliptica')
    P('A manobra de deorbit reduz a velocidade tangencial no apogeu da orbita circular, colocando o veiculo em uma elipse com apogeu na orbita inicial e perigeu mais baixo. A equacao chave e a vis-viva.')
    story += [eq_flow(eqr,r"v^2=\mu\left(\frac{2}{r}-\frac{1}{a}\right)"), eq_flow(eqr,r"a_t=\frac{r_a+r_p}{2}"), eq_flow(eqr,r"\Delta v_{deorbit}=v_{circ}-v_a")]
    db=s['deorbit']; story += [eq_flow(eqr,fr"a_t=\frac{{{db['ra']:.0f}+{db['rp']:.0f}}}{{2}}={db['a_transfer']:.3f}\;\mathrm{{m}}"), eq_flow(eqr,fr"v_a=\sqrt{{\mu\left(\frac{{2}}{{r_a}}-\frac{{1}}{{a_t}}\right)}}={db['v_apogee']:.3f}\;\mathrm{{m/s}}"), eq_flow(eqr,fr"\Delta v={db['v_circ']:.3f}-{db['v_apogee']:.3f}={db['dv']:.3f}\;\mathrm{{m/s}}")]
    IMG(figs['trajectory'],15.5,'Figura 1 - Trajetoria tridimensional colorida pela temperatura de parede durante a reentrada.')

    H1('4. Dinamica de reentrada: equacoes diferenciais')
    P('A reentrada e modelada com estado planar (r, theta, v, gamma). O objetivo aqui nao e substituir CFD/6-DOF certificado, mas produzir um modelo educacional auditavel onde cada termo possui significado fisico.')
    for eq in [r"\dot r=v\sin\gamma", r"\dot\theta=\frac{v\cos\gamma}{r}", r"\dot v=-\frac{D}{m}-\frac{\mu}{r^2}\sin\gamma", r"\dot\gamma=\frac{L}{mv}+\left(\frac{v}{r}-\frac{\mu}{vr^2}\right)\cos\gamma", r"D=\frac{1}{2}\rho v^2 C_D A", r"L=\frac{1}{2}\rho v^2 C_L A"]: story.append(eq_flow(eqr,eq))
    IMG(figs['profiles'],16.5,'Figura 2 - Perfis temporais de altitude, velocidade, carga aerotermica, Mach e g-load.')

    H1('5. Atmosfera, pressao dinamica e Mach')
    P('A pressao dinamica mede a energia cinetica do escoamento por unidade de volume e cresce com a densidade e com o quadrado da velocidade. O numero de Mach compara velocidade do veiculo e velocidade local do som.')
    story += [eq_flow(eqr,r"q=\frac{1}{2}\rho v^2"), eq_flow(eqr,r"a=\sqrt{\gamma R T}"), eq_flow(eqr,r"M=\frac{v}{a}")]
    idx=int(np.argmax(data['timeline']['q'])); tl=data['timeline']
    story += [eq_flow(eqr,fr"q_{{max}}=\frac{{1}}{{2}}({tl['rho'][idx]:.3e})({tl['v'][idx]:.3f})^2={s['peak_q']:.3e}\;\mathrm{{Pa}}")]
    rows=[['t s','h km','v m/s','Mach','q kPa','heat MW/m²','Twall K']]
    for i in np.linspace(0,len(tl['t'])-1,16).astype(int): rows.append([f"{tl['t'][i]:.1f}",f"{tl['h'][i]/1000:.2f}",f"{tl['v'][i]:.1f}",f"{tl['Mach'][i]:.2f}",f"{tl['q'][i]/1000:.2f}",f"{tl['heat'][i]/1e6:.3f}",f"{tl['Twall'][i]:.1f}"])
    story.append(small_table(rows,[1.7,1.7,2.0,1.4,1.7,2.2,1.8]))

    H1('6. Aquecimento aerotermico e temperatura de parede')
    P('O fluxo de calor de estagnacao e estimado por uma forma Sutton-Graves simplificada. A temperatura de parede e estimada por equilibrio radiativo: potencia termica incidente versus emissao por Stefan-Boltzmann.')
    story += [eq_flow(eqr,r"\dot q_s \approx 1.83\times 10^{-4}\sqrt{\frac{\rho}{R_n}}v^3\times 10^4"), eq_flow(eqr,r"\dot q_{rad}=\epsilon\sigma T_{wall}^4"), eq_flow(eqr,r"T_{wall}\approx \left(\frac{\dot q_s}{\epsilon\sigma}\right)^{1/4}")]
    idx=int(np.argmax(tl['heat'])); story += [eq_flow(eqr,fr"\dot q_{{max}}={s['peak_heat']:.3e}\;\mathrm{{W/m^2}}"), eq_flow(eqr,fr"T_{{wall,max}}\approx\left(\frac{{{s['peak_heat']:.3e}}}{{{v['emissivity']:.3f}\cdot {SIGMA_SB:.3e}}}\right)^{{1/4}}={s['peak_Twall']:.2f}\;\mathrm{{K}}")]
    IMG(figs['thermal'],12.5,'Figura 3 - Render termico 3D com mapa de aquecimento superficial.')
    IMG(figs['plasma'],16.5,'Figura 4 - Pressao, temperatura, densidade eletronica e frequencia de plasma.')

    H1('7. Pressao de estagnacao')
    P('A pressao de estagnacao idealiza a pressao obtida se o escoamento fosse desacelerado isentropicamente ate velocidade zero. E uma quantidade util para estimar carga no nariz e regioes de impacto do escoamento.')
    story += [eq_flow(eqr,r"p_0=p\left(1+\frac{\gamma-1}{2}M^2\right)^{\gamma/(\gamma-1)}"), eq_flow(eqr,fr"p_{{0,max}}={float(np.max(tl['p0'])):.3e}\;\mathrm{{Pa}}")]

    H1('8. Ionizacao, plasma e blackout')
    P('O modulo usa uma funcao logistica educacional para estimar fracao ionizada com base na temperatura de parede e densidade. A frequencia de plasma determina quando uma onda eletromagnetica pode sofrer bloqueio/blackout.')
    story += [eq_flow(eqr,r"x_{ion}=\frac{1}{1+e^{-(T_{wall}-6200)/900}}\sqrt{\frac{\rho}{0.02}}"), eq_flow(eqr,r"n_e=x_{ion}\frac{\rho}{m_{air}}"), eq_flow(eqr,r"f_p=8980\sqrt{n_e[cm^{-3}]}\;\mathrm{Hz}"), eq_flow(eqr,fr"f_{{p,max}}={s['peak_fp']:.3e}\;\mathrm{{Hz}}")]
    P(f"Quando fp > {v['comm_frequency_hz']:.3e} Hz, o relatorio marca uma janela de blackout. Nesta simulacao, a duracao estimada foi {s['blackout_duration']:.2f} s.")
    IMG(figs['infrared'],12.5,'Figura 5 - Modo infravermelho analitico.')
    IMG(figs['xray'],12.5,'Figura 6 - Modo raio-X proxy, usado como camada diagnostica, nao como radiografia fisica literal.')

    H1('9. Recaptura propulsiva')
    P('A fase final e tratada como uma queima de recaptura verticalizada. A aproximacao usa cinemática basica para estimar desaceleracao requerida, delta-v final e propelente pela equacao do foguete.')
    story += [eq_flow(eqr,r"a_{req}\approx\frac{v_0^2}{2h_0}"), eq_flow(eqr,r"\Delta v_{land}\approx v_0+35"), eq_flow(eqr,r"m_p=m_0\left(1-e^{-\Delta v/(I_{sp}g_0)}\right)"), eq_flow(eqr,fr"m_p\approx {s['landing_propellant']:.2f}\;\mathrm{{kg}}"), eq_flow(eqr,fr"T\approx m(a_{{req}}+g_0)={s['landing_thrust']:.3e}\;\mathrm{{N}}")]

    H1('10. Tunel de vento surrogate')
    P('O tunel de vento surrogate calcula uma grade de velocidades e angulos de ataque. O objetivo e oferecer diagnostico visual rapido: arrasto, sustentacao, estabilidade e aquecimento aproximado.')
    wt=wind_tunnel(Shape()); story += [eq_flow(eqr,r"Re=\frac{\rho V L}{\mu}"), eq_flow(eqr,r"C_f\approx\frac{0.455}{\log_{10}(Re)^{2.58}}"), eq_flow(eqr,r"C_D\approx C_{D,base}+C_{D,fric}+C_{D,fin}+C_{D,comp}+C_{D,\alpha}")]
    P(f"Melhor caso da grade: V={wt['best']['V']:.1f} m/s, AoA={wt['best']['aoa']:.1f} graus, Cd={wt['best']['Cd']:.4f}, estabilidade={wt['best']['stability']:.2f} calibres.")
    IMG(figs['wind_cd'],15,'Figura 7 - Mapa de Cd no tunel de vento surrogate.')

    H1('11. Otimizacao de forma do foguete')
    P('A funcao objetivo combina arrasto medio, fluxo de calor maximo, penalidade de estabilidade e bonus de volume util. Isto nao substitui otimizacao multidisciplinar real, mas demonstra o ciclo completo: gerar candidato, avaliar, registrar metricas, selecionar melhor e reportar.')
    story += [eq_flow(eqr,r"J_{rocket}=2\bar C_D+0.08\frac{\dot q_{max}}{10^6}+\max(0,1-S)^2-0.003\frac{V_{int}}{10}"), eq_flow(eqr,fr"J_{{best}}={data['shape_opt']['best']['score']:.4f}")]
    story.append(Preformatted(json.dumps(data['shape_opt']['best'],indent=2)[:3500],styles['Code']))
    IMG(figs['shape_opt'],15,'Figura 8 - Historico da otimizacao da forma do foguete.')

    H1('12. Otimizacao de turbina')
    P('A turbina e modelada por proxies de eficiencia, Mach de ponta, solidez, coeficiente de fluxo e carregamento. A funcao objetivo seleciona configuracoes com maior eficiencia e menor risco por Mach de ponta excessivo.')
    story += [eq_flow(eqr,r"U_{tip}=\omega R=\frac{2\pi\,RPM}{60}R"), eq_flow(eqr,r"M_{tip}=\frac{U_{tip}}{\sqrt{\gamma R T}}"), eq_flow(eqr,r"\sigma=\frac{N_b c}{2\pi R}"), eq_flow(eqr,fr"\eta_{{best}}={data['turbine_opt']['best']['eff']:.4f}")]
    story.append(Preformatted(json.dumps(data['turbine_opt']['best'],indent=2)[:3500],styles['Code']))
    IMG(figs['turb_opt'],15,'Figura 9 - Historico da otimizacao da turbina.')

    H1('13. Renderizacao cientifica e modos visuais')
    P('O renderizador 3D nativo usa malha procedural de revolucao, mapas escalares por modo e paletas cientificas. Beauty demonstra textura metalica/ceramica; thermal mostra carga termica; infrared e x-ray sao modos analiticos para relatorio.')
    IMG(figs['beauty'],13,'Figura 10 - Render beauty procedural.')
    IMG(figs['thermal'],13,'Figura 11 - Render thermal.')
    IMG(figs['infrared'],13,'Figura 12 - Render infrared.')
    IMG(figs['xray'],13,'Figura 13 - Render X-ray proxy.')

    H1('14. Exemplo de derivada simbolica dentro da biblioteca')
    x,y=symbols('x y'); f=(x**2+y-11)**2+(x+y**2-7)**2
    P('A biblioteca unica tambem contem nucleo simbolico minimalista. O exemplo abaixo usa a funcao de Himmelblau para demonstrar gradiente simbolico. Para manter o PDF limpo, o relatorio mostra a forma simplificada das derivadas.')
    story += [
        eq_flow(eqr,r"f(x,y)=(x^2+y-11)^2+(x+y^2-7)^2", fontsize=15),
        eq_flow(eqr,r"\frac{\partial f}{\partial x}=4x(x^2+y-11)+2(x+y^2-7)", fontsize=15),
        eq_flow(eqr,r"\frac{\partial f}{\partial y}=2(x^2+y-11)+4y(x+y^2-7)", fontsize=15),
    ]
    P(f"No ponto (3,-2), f={f.eval({'x':3,'y':-2}):.6f}. O exemplo mostra como o mesmo arquivo combina matematica simbolica e simulacao numerica.")

    # Appendices to reach requested length without repeated generic filler: tables and equations.
    appendix_count=max(4, int((pages_target-28)/4))
    for a in range(appendix_count):
        H1(f'Apendice {a+1}: auditoria numerica expandida')
        P('Esta pagina de apendice contem amostras numericas adicionais da trajetoria, mantendo rastreabilidade dos calculos. A repeticao aqui e tabular e auditavel, nao texto decorativo: cada linha deriva da simulacao e pode ser comparada com os graficos.')
        start=int(a*len(tl['t'])/appendix_count); end=int((a+1)*len(tl['t'])/appendix_count); inds=np.linspace(start,max(start,end-1),12).astype(int)
        rows=[['t','h km','v','M','rho','p','q','Twall']]
        for i in inds: rows.append([f'{tl["t"][i]:.1f}',f'{tl["h"][i]/1000:.2f}',f'{tl["v"][i]:.1f}',f'{tl["Mach"][i]:.2f}',f'{tl["rho"][i]:.2e}',f'{tl["p"][i]:.2e}',f'{tl["q"][i]:.2e}',f'{tl["Twall"][i]:.1f}'])
        story.append(small_table(rows,[1.4,1.5,1.8,1.2,1.7,1.7,1.7,1.7]))
        story += [eq_flow(eqr,r"q_i=\frac{1}{2}\rho_i v_i^2",fontsize=15), eq_flow(eqr,r"T_{wall,i}=\left(\frac{\dot q_i}{\epsilon\sigma}\right)^{1/4}",fontsize=15)]

    H1('Apendice final: metadados completos')
    story.append(Preformatted(json.dumps({'summary':s,'mission':m},indent=2,ensure_ascii=False)[:12000],styles['Code']))
    doc=SimpleDocTemplate(str(out_pdf),pagesize=A4,rightMargin=1.35*cm,leftMargin=1.35*cm,topMargin=1.25*cm,bottomMargin=1.25*cm)
    doc.build(story,onFirstPage=header_footer,onLaterPages=header_footer)
    # HTML companion
    html=f"""<!doctype html><meta charset='utf-8'><title>{m['report_title']}</title><body style='font-family:system-ui;max-width:1000px;margin:40px auto;line-height:1.55'><h1>{m['report_title']}</h1><p>PDF profissional gerado por NablaMath All-in-One Professional FULL.</p><h2>Resumo</h2><pre>{json.dumps(s,indent=2)}</pre><h2>Figuras</h2>{''.join([f'<h3>{k}</h3><img src="{Path(v).name}" style="max-width:100%">' for k,v in figs.items()])}</body>"""
    out_html.write_text(html,encoding='utf-8')


def run(out: Path, pages: int=60, no_video: bool=True, rocket_iters:int=80, turbine_iters:int=80) -> Dict[str,str]:
    ensure_dir(out); figs_dir=ensure_dir(out/'figures')
    mission=Mission(); data=simulate_mission(mission); data['shape_opt']=optimize_shape(iters=rocket_iters); data['turbine_opt']=optimize_turbine(iters=turbine_iters)
    figs=make_figures(data,figs_dir)
    pdf=out/'NablaMath_Professional_FULL_Report.pdf'; html=out/'NablaMath_Professional_FULL_Report.html'
    build_report(data,figs,pdf,html,pages_target=pages)
    meta=out/'metadata.json'; meta.write_text(json.dumps({'generated_at':time.time(),'pdf':str(pdf),'html':str(html),'figures':figs},indent=2),encoding='utf-8')
    return {'pdf':str(pdf),'html':str(html),'metadata':str(meta),**figs}


def main() -> None:
    ap=argparse.ArgumentParser(description='NablaMath All-in-One Professional FULL report generator')
    ap.add_argument('--out',default='outputs_nablamath_full',help='output directory')
    ap.add_argument('--pages',type=int,default=80,help='target report length; adds audit appendices')
    ap.add_argument('--no-video',action='store_true',help='reserved flag for compatibility')
    ap.add_argument('--rocket-iters',type=int,default=80)
    ap.add_argument('--turbine-iters',type=int,default=80)
    args=ap.parse_args()
    result=run(Path(args.out),pages=args.pages,no_video=args.no_video,rocket_iters=args.rocket_iters,turbine_iters=args.turbine_iters)
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
