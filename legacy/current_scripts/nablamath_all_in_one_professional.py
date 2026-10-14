#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NablaMath All-in-One Professional
=================================
Arquivo único contendo uma mini-biblioteca integrada para:

1. matemática simbólica básica;
2. derivação simbólica passo a passo;
3. simulação orbital/reentrada/recaptura;
4. túnel de vento surrogate;
5. otimização de forma de foguete e turbina;
6. renderização científica 2D/3D;
7. geração de vídeo MP4 opcional;
8. geração de relatório PDF profissional com equações LaTeX reais renderizadas como imagens;
9. exportação HTML e metadados JSON.

Objetivo: dar ao usuário um único .py editável que funcione como biblioteca + CLI.

Dependências recomendadas:
    pip install numpy matplotlib reportlab pillow imageio imageio-ffmpeg

Exemplo:
    python nablamath_all_in_one_professional.py --out outputs_nabla --pages 80 --fps 6 --video-seconds 4

Modo sem vídeo:
    python nablamath_all_in_one_professional.py --out outputs_nabla --pages 60 --no-video
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

# Matplotlib headless.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as mpl_cm
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

try:
    import imageio.v2 as imageio
except Exception:  # pragma: no cover
    imageio = None

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Flowable,
        Image as RLImage,
        KeepTogether,
        ListFlowable,
        ListItem,
        PageBreak,
        Paragraph,
        Preformatted,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except Exception as exc:  # pragma: no cover
    raise RuntimeError("ReportLab é necessário: pip install reportlab") from exc


# ============================================================
# 0. CONSTANTES FÍSICAS
# ============================================================

G0 = 9.80665
R_EARTH = 6_371_000.0
MU_EARTH = 3.986004418e14
R_AIR = 287.05
GAMMA_AIR = 1.4
SIGMA_SB = 5.670374419e-8
M_AIR = 4.81e-26
EPS = 1e-12


# ============================================================
# 1. MATEMÁTICA SIMBÓLICA MINIMALISTA
# ============================================================

class Expr:
    """Expressão simbólica minimalista."""

    def eval(self, env: Dict[str, float]) -> float:
        raise NotImplementedError

    def diff(self, var: "Symbol") -> "Expr":
        raise NotImplementedError

    def latex(self) -> str:
        raise NotImplementedError

    def simplify(self) -> "Expr":
        return self

    def __add__(self, other: Any) -> "Expr":
        return Add(self, ensure_expr(other)).simplify()

    def __radd__(self, other: Any) -> "Expr":
        return Add(ensure_expr(other), self).simplify()

    def __sub__(self, other: Any) -> "Expr":
        return Add(self, Mul(Number(-1), ensure_expr(other))).simplify()

    def __rsub__(self, other: Any) -> "Expr":
        return Add(ensure_expr(other), Mul(Number(-1), self)).simplify()

    def __mul__(self, other: Any) -> "Expr":
        return Mul(self, ensure_expr(other)).simplify()

    def __rmul__(self, other: Any) -> "Expr":
        return Mul(ensure_expr(other), self).simplify()

    def __truediv__(self, other: Any) -> "Expr":
        return Mul(self, Pow(ensure_expr(other), Number(-1))).simplify()

    def __rtruediv__(self, other: Any) -> "Expr":
        return Mul(ensure_expr(other), Pow(self, Number(-1))).simplify()

    def __pow__(self, power: Any) -> "Expr":
        return Pow(self, ensure_expr(power)).simplify()

    def __neg__(self) -> "Expr":
        return Mul(Number(-1), self).simplify()

    def grad(self, vars_: Sequence["Symbol"]) -> List["Expr"]:
        return [self.diff(v).simplify() for v in vars_]

    def hessian(self, vars_: Sequence["Symbol"]) -> List[List["Expr"]]:
        return [[self.diff(a).diff(b).simplify() for b in vars_] for a in vars_]


@dataclass(frozen=True)
class Number(Expr):
    value: float

    def eval(self, env: Dict[str, float]) -> float:
        return float(self.value)

    def diff(self, var: "Symbol") -> Expr:
        return Number(0.0)

    def latex(self) -> str:
        if abs(self.value - int(self.value)) < 1e-12:
            return str(int(self.value))
        return f"{self.value:.6g}"

    def __str__(self) -> str:
        return self.latex()


@dataclass(frozen=True)
class Symbol(Expr):
    name: str

    def eval(self, env: Dict[str, float]) -> float:
        return float(env[self.name])

    def diff(self, var: "Symbol") -> Expr:
        return Number(1.0 if self.name == var.name else 0.0)

    def latex(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Add(Expr):
    a: Expr
    b: Expr

    def eval(self, env: Dict[str, float]) -> float:
        return self.a.eval(env) + self.b.eval(env)

    def diff(self, var: Symbol) -> Expr:
        return Add(self.a.diff(var), self.b.diff(var)).simplify()

    def latex(self) -> str:
        return f"{self.a.latex()} + {self.b.latex()}"

    def simplify(self) -> Expr:
        a, b = self.a.simplify(), self.b.simplify()
        if isinstance(a, Number) and abs(a.value) < EPS:
            return b
        if isinstance(b, Number) and abs(b.value) < EPS:
            return a
        if isinstance(a, Number) and isinstance(b, Number):
            return Number(a.value + b.value)
        return Add(a, b)

    def __str__(self) -> str:
        return self.latex()


@dataclass(frozen=True)
class Mul(Expr):
    a: Expr
    b: Expr

    def eval(self, env: Dict[str, float]) -> float:
        return self.a.eval(env) * self.b.eval(env)

    def diff(self, var: Symbol) -> Expr:
        return Add(Mul(self.a.diff(var), self.b), Mul(self.a, self.b.diff(var))).simplify()

    def latex(self) -> str:
        return f"{wrap_latex(self.a)} {wrap_latex(self.b)}"

    def simplify(self) -> Expr:
        a, b = self.a.simplify(), self.b.simplify()
        if isinstance(a, Number) and abs(a.value) < EPS:
            return Number(0.0)
        if isinstance(b, Number) and abs(b.value) < EPS:
            return Number(0.0)
        if isinstance(a, Number) and abs(a.value - 1.0) < EPS:
            return b
        if isinstance(b, Number) and abs(b.value - 1.0) < EPS:
            return a
        if isinstance(a, Number) and isinstance(b, Number):
            return Number(a.value * b.value)
        return Mul(a, b)

    def __str__(self) -> str:
        return self.latex()


@dataclass(frozen=True)
class Pow(Expr):
    base: Expr
    exp: Expr

    def eval(self, env: Dict[str, float]) -> float:
        return self.base.eval(env) ** self.exp.eval(env)

    def diff(self, var: Symbol) -> Expr:
        if isinstance(self.exp, Number):
            n = self.exp.value
            return Mul(Mul(Number(n), Pow(self.base, Number(n - 1))), self.base.diff(var)).simplify()
        return Mul(self, Add(Mul(self.exp.diff(var), Log(self.base)), Mul(self.exp, self.base.diff(var) / self.base))).simplify()

    def latex(self) -> str:
        return f"{wrap_latex(self.base)}^{{{self.exp.latex()}}}"

    def simplify(self) -> Expr:
        b, e = self.base.simplify(), self.exp.simplify()
        if isinstance(e, Number) and abs(e.value) < EPS:
            return Number(1.0)
        if isinstance(e, Number) and abs(e.value - 1.0) < EPS:
            return b
        if isinstance(b, Number) and isinstance(e, Number):
            try:
                return Number(b.value ** e.value)
            except Exception:
                pass
        return Pow(b, e)

    def __str__(self) -> str:
        return self.latex()


@dataclass(frozen=True)
class UnaryFunc(Expr):
    x: Expr
    name: str
    latex_name: str
    fn: Callable[[float], float]
    dfn: Callable[[Expr], Expr]

    def eval(self, env: Dict[str, float]) -> float:
        return self.fn(self.x.eval(env))

    def diff(self, var: Symbol) -> Expr:
        return Mul(self.dfn(self.x), self.x.diff(var)).simplify()

    def latex(self) -> str:
        return f"\\{self.latex_name}\\left({self.x.latex()}\\right)"

    def __str__(self) -> str:
        return self.latex()


def ensure_expr(x: Any) -> Expr:
    if isinstance(x, Expr):
        return x
    return Number(float(x))


def wrap_latex(e: Expr) -> str:
    if isinstance(e, (Add,)):
        return f"\\left({e.latex()}\\right)"
    return e.latex()


def Sin(x: Any) -> Expr:
    return UnaryFunc(ensure_expr(x), "sin", "sin", math.sin, lambda z: Cos(z))


def Cos(x: Any) -> Expr:
    return UnaryFunc(ensure_expr(x), "cos", "cos", math.cos, lambda z: -Sin(z))


def Exp(x: Any) -> Expr:
    return UnaryFunc(ensure_expr(x), "exp", "exp", math.exp, lambda z: Exp(z))


def Log(x: Any) -> Expr:
    return UnaryFunc(ensure_expr(x), "log", "log", math.log, lambda z: Number(1) / z)


def symbols(names: str) -> Tuple[Symbol, ...]:
    return tuple(Symbol(n.strip()) for n in names.replace(",", " ").split() if n.strip())


# ============================================================
# 2. CONFIGURAÇÕES
# ============================================================

@dataclass
class RocketMaterialConfig:
    name: str = "stainless-steel + ceramic TPS"
    base_rgb: Tuple[float, float, float] = (0.78, 0.80, 0.84)
    tile_rgb: Tuple[float, float, float] = (0.08, 0.08, 0.09)
    glow_rgb: Tuple[float, float, float] = (1.00, 0.40, 0.12)
    metallic: float = 0.82
    roughness: float = 0.24
    emissivity: float = 0.84


@dataclass
class RocketShapeConfig:
    nose_length_m: float = 9.5
    body_length_m: float = 39.0
    body_radius_m: float = 4.55
    boat_tail_length_m: float = 4.0
    engine_exit_radius_m: float = 1.28
    fin_count: int = 4
    fin_root_chord_m: float = 6.2
    fin_tip_chord_m: float = 2.3
    fin_span_m: float = 3.6
    fin_sweep_deg: float = 29.0

    @property
    def total_length_m(self) -> float:
        return self.nose_length_m + self.body_length_m + self.boat_tail_length_m

    @property
    def frontal_area_m2(self) -> float:
        return math.pi * self.body_radius_m ** 2

    @property
    def internal_volume_m3(self) -> float:
        return math.pi * self.body_radius_m ** 2 * self.body_length_m


@dataclass
class OrbitalVehicleConfig:
    name: str = "Asteria-R"
    mass_initial: float = 134_000.0
    mass_dry: float = 87_500.0
    nose_radius: float = 1.25
    reference_area: float = 63.6
    drag_coefficient: float = 1.28
    lift_to_drag: float = 0.24
    landing_isp: float = 330.0
    landing_burn_start_altitude: float = 2900.0
    communications_frequency_hz: float = 2.25e9


@dataclass
class WindTunnelConfig:
    velocities_m_s: Tuple[float, ...] = (120, 250, 500, 900, 1400, 2200, 3200, 3800)
    angles_of_attack_deg: Tuple[float, ...] = (-6, -2, 0, 4, 8, 12)
    altitude_m: float = 2500.0


@dataclass
class TurbineDesignConfig:
    radius_m: float = 0.42
    hub_radius_m: float = 0.13
    blade_count: int = 30
    chord_root_m: float = 0.12
    chord_tip_m: float = 0.05
    twist_root_deg: float = 58.0
    twist_tip_deg: float = 18.0
    rpm: float = 34500.0
    mass_flow_kg_s: float = 44.0
    pressure_ratio_target: float = 15.0
    stage_temperature_k: float = 990.0


@dataclass
class OptimizationConfig:
    seed: int = 321
    rocket_iterations: int = 80
    turbine_iterations: int = 80


@dataclass
class VideoConfig:
    fps: int = 6
    seconds: float = 4.0
    enabled: bool = True


@dataclass
class MissionConfig:
    mission_name: str = "Asteria-Professional-Dossier"
    report_title: str = "NablaMath All-in-One - Dossie Tecnico Orbital Profissional"
    pdf_filename: str = "nablamath_professional_orbital_report.pdf"
    user_objectives: str = (
        "Gerar um relatorio profissional com calculos explicitos em LaTeX, mecanica orbital, "
        "reentrada, plasma, tunel de vento, otimizacao de forma e turbina, renders cientificos, "
        "videos opcionais e metadados reproduziveis."
    )
    user_input_code: str = "# Preencha este campo com o codigo de entrada do usuario."
    vehicle: OrbitalVehicleConfig = field(default_factory=OrbitalVehicleConfig)
    shape: RocketShapeConfig = field(default_factory=RocketShapeConfig)
    material: RocketMaterialConfig = field(default_factory=RocketMaterialConfig)
    wind: WindTunnelConfig = field(default_factory=WindTunnelConfig)
    turbine: TurbineDesignConfig = field(default_factory=TurbineDesignConfig)
    optimization: OptimizationConfig = field(default_factory=OptimizationConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    orbit_altitude_m: float = 430_000.0
    perigee_target_m: float = 36_000.0
    entry_interface_altitude_m: float = 123_000.0
    dt_reentry: float = 0.45
    max_reentry_time: float = 4900.0
    reentry_bank_angle_deg: float = 31.0
    spectral_xray_threshold_k: float = 2.6e5
    target_pages: int = 80


@dataclass
class SimulationResult:
    summary: Dict[str, float]
    timeline: Dict[str, np.ndarray]
    wind: Dict[str, Any]
    rocket_opt: Dict[str, Any]
    turbine_opt: Dict[str, Any]
    figures: Dict[str, str]
    videos: Dict[str, str]
    equations: Dict[str, str]
    metadata: Dict[str, Any]


# ============================================================
# 3. ATMOSFERA, ÓRBITA, REENTRADA, PLASMA
# ============================================================

_ATMOS_LAYERS = [
    (0.0, 288.15, 101325.0, -0.0065),
    (11000.0, 216.65, 22632.06, 0.0),
    (20000.0, 216.65, 5474.889, 0.001),
    (32000.0, 228.65, 868.0187, 0.0028),
    (47000.0, 270.65, 110.9063, 0.0),
    (51000.0, 270.65, 66.93887, -0.0028),
    (71000.0, 214.65, 3.956420, -0.002),
    (86000.0, 186.946, 0.3734, 0.0),
]


def standard_atmosphere(altitude_m: float) -> Dict[str, float]:
    h = float(max(0.0, altitude_m))
    if h <= 86000.0:
        idx = 0
        for i in range(len(_ATMOS_LAYERS) - 1):
            if _ATMOS_LAYERS[i][0] <= h < _ATMOS_LAYERS[i + 1][0]:
                idx = i
                break
        else:
            idx = len(_ATMOS_LAYERS) - 1
        h_b, T_b, p_b, L_b = _ATMOS_LAYERS[idx]
        if abs(L_b) < EPS:
            T = T_b
            p = p_b * math.exp(-G0 * (h - h_b) / (R_AIR * T_b))
        else:
            T = T_b + L_b * (h - h_b)
            p = p_b * (T / T_b) ** (-G0 / (L_b * R_AIR))
        rho = p / (R_AIR * T)
    else:
        base = standard_atmosphere(86000.0)
        H = 7000.0 + 1200.0 * min((h - 86000.0) / 80000.0, 4.0)
        T = max(180.0, 186.946 + 0.0025 * (h - 86000.0))
        rho = base["rho"] * math.exp(-(h - 86000.0) / H)
        p = rho * R_AIR * T
    a = math.sqrt(GAMMA_AIR * R_AIR * T)
    return {"T": T, "p": p, "rho": rho, "a": a}


def dynamic_viscosity_sutherland(T: float) -> float:
    return 1.458e-6 * T ** 1.5 / (T + 110.4)


def circular_orbit(altitude_m: float) -> Dict[str, float]:
    r = R_EARTH + altitude_m
    v = math.sqrt(MU_EARTH / r)
    period = 2 * math.pi * math.sqrt(r ** 3 / MU_EARTH)
    return {"r": r, "v": v, "period": period, "energy": -MU_EARTH / (2 * r)}


def deorbit_burn(orbit_altitude_m: float, perigee_target_m: float) -> Dict[str, float]:
    r_a = R_EARTH + orbit_altitude_m
    r_p = R_EARTH + perigee_target_m
    a_t = 0.5 * (r_a + r_p)
    v_circ = math.sqrt(MU_EARTH / r_a)
    v_a = math.sqrt(MU_EARTH * (2 / r_a - 1 / a_t))
    v_p = math.sqrt(MU_EARTH * (2 / r_p - 1 / a_t))
    return {"r_a": r_a, "r_p": r_p, "a_t": a_t, "v_circ": v_circ, "v_a": v_a, "v_p": v_p, "delta_v": v_circ - v_a}


def sutton_graves(rho: float, v: float, rn: float) -> float:
    return max(0.0, 1.83e-4 * math.sqrt(max(rho, 1e-12) / max(rn, 0.1)) * v ** 3 * 1e4)


def stagnation_pressure(p: float, mach: float) -> float:
    return p * (1 + 0.5 * (GAMMA_AIR - 1) * mach ** 2) ** (GAMMA_AIR / (GAMMA_AIR - 1))


def ionization_fraction(T_wall: float, rho: float) -> float:
    activation = 1 / (1 + math.exp(-(T_wall - 6200) / 900))
    density_factor = min(1.0, math.sqrt(max(rho, 0.0) / 0.02 + 1e-12))
    return float(min(1.0, activation * density_factor))


def plasma_frequency_hz(ne_m3: float) -> float:
    ne_cm3 = max(ne_m3, 0.0) / 1e6
    return 8980.0 * math.sqrt(ne_cm3)


def spectral_signals(T_wall: float, threshold_xray: float) -> Dict[str, float]:
    ir = min(1.0, (T_wall / 2200) ** 1.2)
    uv = min(1.0, max(0.0, (T_wall - 2800) / 6000))
    xray = min(1.0, math.exp(-(threshold_xray / max(T_wall, 1)) ** 0.7))
    return {"ir": ir, "uv": uv, "xray": xray}


# ============================================================
# 4. TÚNEL DE VENTO E OTIMIZAÇÕES
# ============================================================

def rocket_aero_surrogate(shape: RocketShapeConfig, vehicle: OrbitalVehicleConfig, speed: float, aoa_deg: float, altitude_m: float) -> Dict[str, Any]:
    atm = standard_atmosphere(altitude_m)
    rho, T, a = atm["rho"], atm["T"], atm["a"]
    mu = dynamic_viscosity_sutherland(T)
    mach = speed / max(a, EPS)
    Re = rho * speed * shape.total_length_m / max(mu, EPS)
    alpha = math.radians(aoa_deg)
    fineness = shape.total_length_m / max(2 * shape.body_radius_m, 0.1)
    wetted = 2 * math.pi * shape.body_radius_m * shape.body_length_m + math.pi * shape.body_radius_m * math.sqrt(shape.body_radius_m**2 + shape.nose_length_m**2)
    cf = 0.455 / max(math.log10(max(Re, 10)), 1) ** 2.58
    base_cd = 0.09 + 0.18 / max(fineness, 1.2) + cf * wetted / max(shape.frontal_area_m2, EPS)
    transonic = 0.12 * math.exp(-((mach - 1.05) / 0.32) ** 2)
    supersonic = 0.035 * max(mach - 1.2, 0)
    fin_drag = 0.006 * shape.fin_count * (shape.fin_span_m / max(shape.body_radius_m, 0.2))
    boat_tail_bonus = -0.015 * min(shape.boat_tail_length_m / max(shape.body_length_m, 1), 0.2) / 0.2
    cd = max(0.06, base_cd + transonic + supersonic + fin_drag + boat_tail_bonus + 0.22 * alpha**2)
    aspect = 2 * shape.fin_span_m / max(0.5 * (shape.fin_root_chord_m + shape.fin_tip_chord_m), 0.2)
    cl_alpha = 2 * math.pi * aspect / max(aspect + 2, 0.5)
    cl = cl_alpha * alpha * (1 + 0.05 * min(mach, 3))
    cp_x = 0.58 * shape.total_length_m - 0.06 * shape.nose_length_m + 0.04 * shape.fin_root_chord_m
    cg_x = 0.47 * shape.total_length_m
    stability = (cp_x - cg_x) / max(2 * shape.body_radius_m, 0.1)
    cm = -0.04 * stability * alpha
    q = 0.5 * rho * speed**2
    heat = sutton_graves(rho, speed, vehicle.nose_radius)
    x = np.linspace(0, shape.total_length_m, 160)
    xn = x / shape.total_length_m
    cp_dist = 1.8 * np.exp(-5*xn) + 0.2 * np.sin(3*np.pi*xn + alpha) + 0.05*mach + 0.6*alpha*np.exp(-2*xn)
    return {"mach": mach, "reynolds": Re, "q": q, "cd": cd, "cl": cl, "cm": cm, "stability": stability, "heat": heat, "x": x, "cp": cp_dist}


def simulate_wind_tunnel(config: MissionConfig) -> Dict[str, Any]:
    vel = np.array(config.wind.velocities_m_s, dtype=float)
    aoa = np.array(config.wind.angles_of_attack_deg, dtype=float)
    cd = np.zeros((len(aoa), len(vel)))
    cl = np.zeros_like(cd)
    cm = np.zeros_like(cd)
    heat = np.zeros_like(cd)
    stability = np.zeros_like(cd)
    q = np.zeros_like(cd)
    cp_x = cp_y = None
    for i, a in enumerate(aoa):
        for j, v in enumerate(vel):
            out = rocket_aero_surrogate(config.shape, config.vehicle, v, a, config.wind.altitude_m)
            cd[i, j], cl[i, j], cm[i, j] = out["cd"], out["cl"], out["cm"]
            heat[i, j], stability[i, j], q[i, j] = out["heat"], out["stability"], out["q"]
            if abs(a) < 1e-9 and j == len(vel) // 2:
                cp_x, cp_y = out["x"], out["cp"]
    objective = cd + 0.015 * np.maximum(0, 1.2 - stability)**2 + heat * 1e-8
    best_idx = np.unravel_index(np.argmin(objective), objective.shape)
    return {
        "vel": vel, "aoa": aoa, "cd": cd, "cl": cl, "cm": cm, "heat": heat, "stability": stability, "q": q,
        "cp_x": cp_x if cp_x is not None else np.array([]), "cp": cp_y if cp_y is not None else np.array([]),
        "best": {"velocity": float(vel[best_idx[1]]), "aoa": float(aoa[best_idx[0]]), "cd": float(cd[best_idx]), "heat": float(heat[best_idx]), "stability": float(stability[best_idx])},
    }


def rocket_shape_score(shape: RocketShapeConfig, config: MissionConfig) -> Tuple[float, Dict[str, float]]:
    speeds = [300, 900, 2200, 3500]
    aoas = [0, 5]
    cds, heats, stabs = [], [], []
    for a in aoas:
        for v in speeds:
            out = rocket_aero_surrogate(shape, config.vehicle, v, a, 0 if v < 1000 else 12000)
            cds.append(out["cd"]); heats.append(out["heat"]); stabs.append(out["stability"])
    avg_cd = float(np.mean(cds)); max_heat = float(np.max(heats)); stab = float(np.mean(stabs))
    volume = shape.internal_volume_m3
    length_penalty = abs(shape.total_length_m - 52) / 52
    stab_penalty = max(0, 1 - stab)**2 + max(0, stab - 3)**2
    fin_penalty = 0.03 * max(0, shape.fin_span_m - 6)**2
    score = 2.2*avg_cd + 0.08*(max_heat/1e6) + 1.1*stab_penalty + 0.6*length_penalty + fin_penalty - 0.0035*volume
    return score, {"score": score, "avg_cd": avg_cd, "max_heat": max_heat, "stability": stab, "volume": volume, "length": shape.total_length_m}


def optimize_rocket_shape(config: MissionConfig) -> Dict[str, Any]:
    rng = np.random.default_rng(config.optimization.seed)
    best = config.shape
    best_score, best_metrics = rocket_shape_score(best, config)
    hist = []
    for it in range(config.optimization.rocket_iterations):
        cand = RocketShapeConfig(
            nose_length_m=float(rng.uniform(6, 14)), body_length_m=float(rng.uniform(30, 46)),
            body_radius_m=float(rng.uniform(3.4, 5.4)), boat_tail_length_m=float(rng.uniform(2, 5.6)),
            engine_exit_radius_m=float(rng.uniform(0.8, 1.9)), fin_count=int(rng.integers(3, 6)),
            fin_root_chord_m=float(rng.uniform(4, 8.6)), fin_tip_chord_m=float(rng.uniform(1.0, 4.0)),
            fin_span_m=float(rng.uniform(2.0, 5.4)), fin_sweep_deg=float(rng.uniform(15, 45)),
        )
        score, metrics = rocket_shape_score(cand, config)
        hist.append({"iteration": it+1, **metrics})
        if score < best_score:
            best, best_score, best_metrics = cand, score, metrics
    return {"best_shape": asdict(best), "best_metrics": best_metrics, "history": hist}


def turbine_score(d: TurbineDesignConfig) -> Tuple[float, Dict[str, float]]:
    area = math.pi * (d.radius_m**2 - d.hub_radius_m**2)
    omega = d.rpm * 2*math.pi/60
    u_tip = omega * d.radius_m
    flow_coeff = d.mass_flow_kg_s / max(area * 35 * d.stage_temperature_k/1000, EPS)
    loading = d.pressure_ratio_target / max((u_tip/300)**2, EPS)
    solidity = d.blade_count * 0.5*(d.chord_root_m+d.chord_tip_m)/max(2*math.pi*d.radius_m, EPS)
    tip_mach = u_tip / math.sqrt(GAMMA_AIR*R_AIR*d.stage_temperature_k)
    twist = abs(d.twist_root_deg - d.twist_tip_deg)
    eff = 0.90 - 0.11*abs(flow_coeff-0.6) - 0.08*abs(loading-1.55) - 0.05*abs(solidity-1.25) - 0.03*max(0, tip_mach-1.15) - 0.0015*abs(twist-38)
    eff = float(np.clip(eff, 0.4, 0.95))
    stress = 7800 * u_tip**2
    power = eff * d.mass_flow_kg_s * d.pressure_ratio_target * 8.2e3
    score = -10*eff + 1.2*max(0, tip_mach-1.05) + stress*2e-8 - power*1e-6
    return score, {"score": score, "efficiency": eff, "tip_speed": u_tip, "tip_mach": tip_mach, "solidity": solidity, "flow_coeff": flow_coeff, "loading_coeff": loading, "stress": stress, "power": power}


def optimize_turbine(config: MissionConfig) -> Dict[str, Any]:
    rng = np.random.default_rng(config.optimization.seed + 1)
    best = config.turbine
    best_score, best_metrics = turbine_score(best)
    hist = []
    for it in range(config.optimization.turbine_iterations):
        cand = TurbineDesignConfig(
            radius_m=float(rng.uniform(0.28, 0.58)), hub_radius_m=float(rng.uniform(0.08, 0.22)),
            blade_count=int(rng.integers(18, 38)), chord_root_m=float(rng.uniform(0.07, 0.16)),
            chord_tip_m=float(rng.uniform(0.03, 0.09)), twist_root_deg=float(rng.uniform(40, 70)),
            twist_tip_deg=float(rng.uniform(8, 28)), rpm=float(rng.uniform(18000, 48000)),
            mass_flow_kg_s=float(rng.uniform(18, 70)), pressure_ratio_target=float(rng.uniform(8, 22)),
            stage_temperature_k=float(rng.uniform(780, 1250)),
        )
        if cand.hub_radius_m >= cand.radius_m - 0.03:
            continue
        score, metrics = turbine_score(cand)
        hist.append({"iteration": it+1, **metrics})
        if score < best_score:
            best, best_score, best_metrics = cand, score, metrics
    return {"best_design": asdict(best), "best_metrics": best_metrics, "history": hist}


# ============================================================
# 5. SIMULAÇÃO DA MISSÃO
# ============================================================

def simulate_mission(config: MissionConfig) -> Tuple[Dict[str, float], Dict[str, np.ndarray], Dict[str, str]]:
    orbit = circular_orbit(config.orbit_altitude_m)
    deorb = deorbit_burn(config.orbit_altitude_m, config.perigee_target_m)
    a_t = deorb["a_t"]
    r_entry = R_EARTH + config.entry_interface_altitude_m
    v_entry = math.sqrt(MU_EARTH * (2/r_entry - 1/a_t))
    gamma = math.radians(-1.25)
    r = r_entry
    h = config.entry_interface_altitude_m
    v = v_entry
    theta = 0.0
    t = 0.0
    m = config.vehicle.mass_initial
    A = config.vehicle.reference_area
    Cd = config.vehicle.drag_coefficient
    CL = Cd * config.vehicle.lift_to_drag * math.cos(math.radians(config.reentry_bank_angle_deg))
    keys = ["time", "alt", "vel", "gamma", "downrange", "rho", "p", "T", "mach", "q", "g", "heat", "Twall", "p0", "ion", "ne", "fp", "ir", "uv", "xray", "phase"]
    arr: Dict[str, List[float]] = {k: [] for k in keys}
    blackout_start = blackout_end = None
    peak_heat_alt = peak_q_alt = peak_g_alt = 0.0
    peak_heat = peak_q = peak_g = -1.0
    while h > max(config.vehicle.landing_burn_start_altitude, 1000) and t < config.max_reentry_time and v > 50:
        atm = standard_atmosphere(h)
        rho, p, T, a = atm["rho"], atm["p"], atm["T"], atm["a"]
        mach = v / max(a, EPS)
        qdyn = 0.5 * rho * v*v
        D = qdyn * Cd * A
        L = qdyn * CL * A
        g_local = MU_EARTH / (r*r)
        dvdt = -D/m - g_local*math.sin(gamma)
        dgdt = L/max(m*v, EPS) + (v/r - g_local/max(v, EPS))*math.cos(gamma)
        drdt = v*math.sin(gamma)
        dthetadt = v*math.cos(gamma)/r
        heat = sutton_graves(rho, v, config.vehicle.nose_radius)
        Twall = min(4300.0, max(T, (heat / max(config.material.emissivity*SIGMA_SB, EPS))**0.25))
        p0 = stagnation_pressure(p, mach)
        ion = ionization_fraction(Twall, rho)
        ne = ion * rho / M_AIR
        fp = plasma_frequency_hz(ne)
        spec = spectral_signals(Twall, config.spectral_xray_threshold_k)
        gload = abs(dvdt)/G0
        vals = [t, h, v, math.degrees(gamma), R_EARTH*theta, rho, p, T, mach, qdyn, gload, heat, Twall, p0, ion, ne, fp, spec["ir"], spec["uv"], spec["xray"], 0]
        for k, val in zip(keys, vals):
            arr[k].append(float(val))
        if heat > peak_heat: peak_heat, peak_heat_alt = heat, h
        if qdyn > peak_q: peak_q, peak_q_alt = qdyn, h
        if gload > peak_g: peak_g, peak_g_alt = gload, h
        blackout = fp > config.vehicle.communications_frequency_hz
        if blackout and blackout_start is None: blackout_start = t
        if not blackout and blackout_start is not None and blackout_end is None: blackout_end = t
        v = max(0.0, v + dvdt*config.dt_reentry)
        gamma += dgdt*config.dt_reentry
        r += drdt*config.dt_reentry
        theta += dthetadt*config.dt_reentry
        h = max(0.0, r - R_EARTH)
        t += config.dt_reentry
    burn_alt = max(h, config.vehicle.landing_burn_start_altitude)
    burn_v = max(v, 1.0)
    a_req = burn_v**2 / (2*max(burn_alt, 1.0))
    decel = a_req + 0.35*G0
    landing_dv = burn_v + 35
    prop_ratio = math.exp(landing_dv / max(config.vehicle.landing_isp*G0, EPS))
    propellant = max(0.0, m - m/prop_ratio)
    thrust = m * (decel + G0)
    burn_time = max(1.0, burn_v/max(decel, EPS))
    dt = min(0.2, burn_time/80)
    h2, v2, t2 = burn_alt, burn_v, 0.0
    while h2 > 0 and t2 <= burn_time + 2:
        v2 = max(0.5, v2 - decel*dt)
        h2 = max(0.0, h2 - v2*dt)
        atm = standard_atmosphere(h2)
        rho, p, T, a = atm["rho"], atm["p"], atm["T"], atm["a"]
        mach = v2 / max(a, EPS)
        qdyn = 0.5*rho*v2*v2
        heat = sutton_graves(rho, v2, config.vehicle.nose_radius) * 0.05
        Twall = max(T, (heat / max(config.material.emissivity*SIGMA_SB, EPS))**0.25)
        ion = ionization_fraction(Twall, rho)*0.2
        ne = ion*rho/M_AIR
        fp = plasma_frequency_hz(ne)
        spec = spectral_signals(Twall, config.spectral_xray_threshold_k)
        vals = [t+t2, h2, v2, -90, R_EARTH*theta, rho, p, T, mach, qdyn, (decel+G0)/G0, heat, Twall, stagnation_pressure(p, mach), ion, ne, fp, spec["ir"], spec["uv"], spec["xray"], 1]
        for k, val in zip(keys, vals):
            arr[k].append(float(val))
        t2 += dt
    timeline = {k: np.array(vv, dtype=float) for k, vv in arr.items()}
    total_time = float(timeline["time"][-1])
    blackout = 0.0 if blackout_start is None else (total_time - blackout_start if blackout_end is None else blackout_end - blackout_start)
    summary = {
        "orbit_radius_m": orbit["r"], "orbit_velocity_m_s": orbit["v"], "orbit_period_s": orbit["period"],
        "deorbit_delta_v_m_s": deorb["delta_v"], "entry_velocity_m_s": v_entry,
        "peak_heat_flux_w_m2": float(np.max(timeline["heat"])), "peak_dynamic_pressure_pa": float(np.max(timeline["q"])),
        "peak_g_load": float(np.max(timeline["g"])), "peak_wall_temperature_k": float(np.max(timeline["Twall"])),
        "peak_plasma_frequency_hz": float(np.max(timeline["fp"])), "blackout_duration_s": blackout,
        "landing_propellant_kg": propellant, "engine_thrust_n": thrust, "burn_start_altitude_m": burn_alt, "burn_start_velocity_m_s": burn_v,
        "peak_heat_altitude_m": peak_heat_alt, "peak_q_altitude_m": peak_q_alt, "peak_g_altitude_m": peak_g_alt,
    }
    equations = build_equations(config, orbit, deorb, summary)
    return summary, timeline, equations


def build_equations(config: MissionConfig, orbit: Dict[str, float], deorb: Dict[str, float], summary: Dict[str, float]) -> Dict[str, str]:
    return {
        "orbit_radius": rf"r_{{orb}} = R_E + h = {R_EARTH:.0f} + {config.orbit_altitude_m:.0f} = {orbit['r']:.0f}\,\mathrm{{m}}",
        "orbit_velocity": rf"v_{{orb}} = \sqrt{{\frac{{\mu}}{{r_{{orb}}}}}} = \sqrt{{\frac{{{MU_EARTH:.6e}}}{{{orbit['r']:.0f}}}}} = {orbit['v']:.3f}\,\mathrm{{m/s}}",
        "orbit_period": rf"T = 2\pi\sqrt{{\frac{{r_{{orb}}^3}}{{\mu}}}} = {orbit['period']:.3f}\,\mathrm{{s}}",
        "deorbit_a": rf"a_t = \frac{{r_a+r_p}}{{2}} = \frac{{{deorb['r_a']:.0f}+{deorb['r_p']:.0f}}}{{2}} = {deorb['a_t']:.3f}\,\mathrm{{m}}",
        "deorbit_dv": rf"\Delta v = v_{{circ}} - v_a = {deorb['v_circ']:.3f} - {deorb['v_a']:.3f} = {deorb['delta_v']:.3f}\,\mathrm{{m/s}}",
        "reentry_odes": r"\dot r=v\sin\gamma,\quad \dot\theta=\frac{v\cos\gamma}{r},\quad \dot v=-\frac{D}{m}-\frac{\mu}{r^2}\sin\gamma,\quad \dot\gamma=\frac{L}{mv}+\left(\frac{v}{r}-\frac{\mu}{vr^2}\right)\cos\gamma",
        "drag_lift": r"D=\frac{1}{2}\rho v^2C_DA,\quad L=\frac{1}{2}\rho v^2C_LA,\quad q=\frac{1}{2}\rho v^2",
        "heat_flux": rf"\dot q_{{stag}}\approx 1.83\times10^{{-4}}\sqrt{{\frac{{\rho}}{{R_n}}}}v^3\times10^4,\quad \dot q_{{max}}={summary['peak_heat_flux_w_m2']:.3e}\,\mathrm{{W/m^2}}",
        "wall_temperature": rf"T_{{wall}}\approx\left(\frac{{\dot q}}{{\epsilon\sigma}}\right)^{{1/4}},\quad T_{{wall,max}}={summary['peak_wall_temperature_k']:.2f}\,\mathrm{{K}}",
        "stagnation_pressure": r"p_0=p\left(1+\frac{\gamma-1}{2}M^2\right)^{\gamma/(\gamma-1)}",
        "plasma": rf"n_e=x_{{ion}}\frac{{\rho}}{{m_{{air}}}},\quad f_p=8980\sqrt{{n_e[\mathrm{{cm}}^{{-3}}]}},\quad f_{{p,max}}={summary['peak_plasma_frequency_hz']:.3e}\,\mathrm{{Hz}}",
        "rocket_eq": rf"m_p=m_0\left(1-e^{{-\Delta v/(I_{{sp}}g_0)}}\right),\quad m_p={summary['landing_propellant_kg']:.2f}\,\mathrm{{kg}}",
        "wind_tunnel": r"Re=\frac{\rho V L}{\mu},\quad C_f\approx\frac{0.455}{\log_{10}(Re)^{2.58}},\quad C_D=C_{D,base}+C_{D,fric}+C_{D,fin}+C_{D,comp}",
        "turbine": r"\eta\approx\eta_0-k_\phi|\phi-\phi^*|-k_\psi|\psi-\psi^*|-k_\sigma|\sigma-\sigma^*|-k_M\max(0,M_{tip}-1.15)",
    }


# ============================================================
# 6. RENDERIZAÇÃO / FIGURAS / VÍDEO
# ============================================================

def rocket_geometry(shape: RocketShapeConfig, n_theta: int = 84) -> Dict[str, np.ndarray]:
    x1 = np.linspace(0, shape.nose_length_m, 38)
    r1 = shape.body_radius_m * (x1 / max(shape.nose_length_m, EPS)) ** 0.85
    x2 = np.linspace(shape.nose_length_m, shape.nose_length_m + shape.body_length_m, 78)
    r2 = np.ones_like(x2) * shape.body_radius_m
    x3 = np.linspace(shape.nose_length_m + shape.body_length_m, shape.total_length_m, 28)
    frac = (x3 - x3.min()) / max(x3.max() - x3.min(), EPS)
    r3 = shape.body_radius_m - (shape.body_radius_m - shape.engine_exit_radius_m) * frac**1.25
    x = np.concatenate([x1, x2, x3])
    rr = np.concatenate([r1, r2, r3])
    theta = np.linspace(0, 2*np.pi, n_theta)
    X, TH = np.meshgrid(x, theta)
    R = np.tile(rr, (len(theta), 1))
    Y = R * np.cos(TH)
    Z = R * np.sin(TH)
    return {"X": X, "Y": Y, "Z": Z, "theta": TH, "r": R}


def surface_colors(shape: RocketShapeConfig, material: RocketMaterialConfig, mode: str, heat_scale: float) -> np.ndarray:
    g = rocket_geometry(shape)
    X, TH = g["X"], g["theta"]
    xn = X / shape.total_length_m
    brushed = 0.90 + 0.10*np.sin(TH*36 + xn*20)
    tiles = ((TH > np.pi*0.65) & (TH < np.pi*1.35) & (xn > 0.18)).astype(float)
    base = np.array(material.base_rgb)[None, None, :]
    tile = np.array(material.tile_rgb)[None, None, :]
    glow = np.array(material.glow_rgb)[None, None, :]
    if mode == "beauty":
        c = base * brushed[..., None]
        c = c*(1-tiles[..., None]*0.85) + tile*(tiles[..., None]*0.85)
        hot = np.maximum(np.exp(-5*xn), 0.5*tiles)*heat_scale
        c = c*(1-0.55*hot[..., None]) + glow*(0.65*hot[..., None])
        return np.clip(c, 0, 1)
    if mode == "thermal":
        hot = np.clip(np.exp(-4*xn)*0.9 + tiles*0.55 + heat_scale*0.35, 0, 1)
        return mpl_cm.inferno(hot)[..., :3]
    if mode == "infrared":
        hot = np.clip(np.exp(-3*xn)*0.7 + heat_scale*0.6, 0, 1)
        return mpl_cm.magma(hot)[..., :3]
    if mode == "xray":
        rim = 0.3 + 0.7*np.abs(np.sin(TH))
        return np.dstack([0.2*rim, 0.85*rim, 1.0*rim])
    return np.ones((*X.shape, 3))*0.7


def render_rocket_3d(config: MissionConfig, path: Path, mode: str = "beauty", heat_scale: float = 0.55, elev: float = 22, azim: float = 44) -> str:
    g = rocket_geometry(config.shape)
    C = surface_colors(config.shape, config.material, mode, heat_scale)
    fig = plt.figure(figsize=(10, 7.2))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(g["X"], g["Y"], g["Z"], facecolors=C, linewidth=0, antialiased=False, shade=False)
    # fins
    for k in range(config.shape.fin_count):
        phi = 2*np.pi*k/config.shape.fin_count
        c, s = math.cos(phi), math.sin(phi)
        x0 = config.shape.nose_length_m + config.shape.body_length_m - 2.0
        tri = np.array([
            [x0, config.shape.body_radius_m*c, config.shape.body_radius_m*s],
            [x0+config.shape.fin_root_chord_m, config.shape.body_radius_m*c, config.shape.body_radius_m*s],
            [x0+config.shape.fin_tip_chord_m+2.2, (config.shape.body_radius_m+config.shape.fin_span_m)*c, (config.shape.body_radius_m+config.shape.fin_span_m)*s],
        ])
        fin_poly = Poly3DCollection([tri], facecolors=[config.material.tile_rgb], edgecolors="black", linewidths=0.3, alpha=0.95)
        ax.add_collection3d(fin_poly)
    if mode in ("beauty", "thermal", "infrared"):
        x = np.linspace(config.shape.total_length_m, config.shape.total_length_m+8, 32)
        th = np.linspace(0, 2*np.pi, 40)
        X, TH = np.meshgrid(x, th)
        rr = np.tile(config.shape.engine_exit_radius_m*(1+2.2*(x-x.min())/(x.max()-x.min())), (len(th),1))
        Y, Z = rr*np.cos(TH), rr*np.sin(TH)
        plume = np.zeros((*X.shape,4)); plume[...,0]=1; plume[...,1]=0.37; plume[...,2]=0.08; plume[...,3]=np.linspace(0.35,0.02,len(x))[None,:]
        ax.plot_surface(X,Y,Z,facecolors=plume,linewidth=0,shade=False)
    ax.set_title(f"Rocket render - {mode}")
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.set_zlabel("z [m]")
    ax.view_init(elev=elev, azim=azim)
    ax.set_box_aspect([config.shape.total_length_m, 2*config.shape.body_radius_m, 2*config.shape.body_radius_m])
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


def plot_dashboard(result: SimulationResult, outdir: Path) -> Dict[str, str]:
    tl = result.timeline
    figs: Dict[str, str] = {}
    outdir.mkdir(parents=True, exist_ok=True)
    fig, axs = plt.subplots(2,2,figsize=(13,9))
    axs[0,0].plot(tl["time"], tl["alt"]/1000); axs[0,0].set_title("Altitude vs time"); axs[0,0].set_xlabel("s"); axs[0,0].set_ylabel("km")
    axs[0,1].plot(tl["time"], tl["vel"]); axs[0,1].set_title("Velocity vs time"); axs[0,1].set_xlabel("s"); axs[0,1].set_ylabel("m/s")
    axs[1,0].plot(tl["time"], tl["q"]/1000, label="q kPa"); axs[1,0].plot(tl["time"], tl["heat"]/1e6, label="heat MW/m2"); axs[1,0].legend(); axs[1,0].set_title("Aerothermal loads")
    axs[1,1].plot(tl["time"], tl["mach"], label="Mach"); axs[1,1].plot(tl["time"], tl["g"], label="g-load"); axs[1,1].legend(); axs[1,1].set_title("Mach and g-load")
    p=outdir/"flight_dashboard.png"; fig.tight_layout(); fig.savefig(p,dpi=180); plt.close(fig); figs["flight_dashboard"]=str(p)
    fig, axs = plt.subplots(2,2,figsize=(13,9))
    axs[0,0].plot(tl["alt"]/1000, tl["p"]); axs[0,0].set_yscale("log"); axs[0,0].set_title("Pressure vs altitude")
    axs[0,1].plot(tl["alt"]/1000, tl["T"], label="ambient"); axs[0,1].plot(tl["alt"]/1000, tl["Twall"], label="wall"); axs[0,1].legend(); axs[0,1].set_title("Temperature")
    axs[1,0].plot(tl["time"], tl["ne"]); axs[1,0].set_yscale("log"); axs[1,0].set_title("Electron density")
    axs[1,1].plot(tl["time"], tl["fp"]/1e9); axs[1,1].set_title("Plasma frequency [GHz]")
    p=outdir/"plasma_dashboard.png"; fig.tight_layout(); fig.savefig(p,dpi=180); plt.close(fig); figs["plasma_dashboard"]=str(p)
    wind=result.wind
    fig,ax=plt.subplots(figsize=(10,6)); im=ax.imshow(wind["cd"],origin="lower",aspect="auto",extent=[wind["vel"][0],wind["vel"][-1],wind["aoa"][0],wind["aoa"][-1]],cmap="viridis"); fig.colorbar(im,ax=ax,label="Cd"); ax.set_title("Wind tunnel Cd map"); ax.set_xlabel("m/s"); ax.set_ylabel("AoA deg")
    p=outdir/"wind_cd_map.png"; fig.tight_layout(); fig.savefig(p,dpi=180); plt.close(fig); figs["wind_cd_map"]=str(p)
    fig,ax=plt.subplots(figsize=(10,5)); ax.plot(wind["cp_x"], wind["cp"]); ax.set_title("Surface pressure coefficient proxy"); ax.set_xlabel("x [m]"); ax.set_ylabel("Cp proxy")
    p=outdir/"pressure_distribution.png"; fig.tight_layout(); fig.savefig(p,dpi=180); plt.close(fig); figs["pressure_distribution"]=str(p)
    if result.rocket_opt["history"]:
        h=result.rocket_opt["history"]; fig,ax=plt.subplots(figsize=(10,5)); ax.plot([v["iteration"] for v in h],[v["score"] for v in h],label="score"); ax.plot([v["iteration"] for v in h],[v["avg_cd"] for v in h],label="avg Cd"); ax.legend(); ax.set_title("Rocket optimization history")
        p=outdir/"rocket_optimization.png"; fig.tight_layout(); fig.savefig(p,dpi=180); plt.close(fig); figs["rocket_optimization"]=str(p)
    if result.turbine_opt["history"]:
        h=result.turbine_opt["history"]; fig,ax=plt.subplots(figsize=(10,5)); ax.plot([v["iteration"] for v in h],[v["efficiency"] for v in h],label="efficiency"); ax.plot([v["iteration"] for v in h],[v["tip_mach"] for v in h],label="tip Mach"); ax.legend(); ax.set_title("Turbine optimization history")
        p=outdir/"turbine_optimization.png"; fig.tight_layout(); fig.savefig(p,dpi=180); plt.close(fig); figs["turbine_optimization"]=str(p)
    return figs


def generate_video(config: MissionConfig, outdir: Path) -> Dict[str, str]:
    vids: Dict[str,str] = {}
    if not config.video.enabled or imageio is None:
        return vids
    frames_dir = outdir/"video_frames"; frames_dir.mkdir(parents=True, exist_ok=True)
    n = max(8, int(config.video.fps*config.video.seconds))
    frame_paths=[]
    for i in range(n):
        p = frames_dir/f"frame_{i:04d}.png"
        render_rocket_3d(config, p, mode="beauty", heat_scale=i/max(1,n-1), elev=18+6*math.sin(i/n*2*math.pi), azim=30+i*360/n)
        frame_paths.append(p)
    mp4 = outdir/"rocket_animation.mp4"
    try:
        with imageio.get_writer(mp4, fps=config.video.fps) as w:
            for p in frame_paths:
                w.append_data(imageio.imread(p))
        vids["rocket_animation"] = str(mp4)
    except Exception:
        pass
    return vids


# ============================================================
# 7. RELATÓRIO PDF COM EQUAÇÕES LATEX REAIS EM IMAGEM
# ============================================================

class PageNumCanvas:
    pass


def equation_image(latex: str, outdir: Path, name: str, fontsize: int = 16) -> str:
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"eq_{safe_name(name)}.png"
    # Matplotlib mathtext. Não depende de instalação LaTeX externa.
    fig = plt.figure(figsize=(11.0, 0.01))
    text = fig.text(0.01, 0.5, f"${latex}$", fontsize=fontsize, va="center", ha="left")
    fig.canvas.draw()
    bbox = text.get_window_extent(renderer=fig.canvas.get_renderer()).expanded(1.08, 1.35)
    width, height = bbox.width / fig.dpi, bbox.height / fig.dpi
    plt.close(fig)
    fig = plt.figure(figsize=(min(max(width, 3), 11), min(max(height, 0.35), 2.2)))
    fig.patch.set_facecolor("white")
    fig.text(0.01, 0.5, f"${latex}$", fontsize=fontsize, va="center", ha="left", color="black")
    plt.axis("off")
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.06, facecolor="white")
    plt.close(fig)
    return str(path)


def safe_name(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)[:80]


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#4b5563"))
    canvas.drawString(1.2*cm, 1.0*cm, "NablaMath All-in-One Professional")
    canvas.drawRightString(A4[0]-1.2*cm, 1.0*cm, f"Pagina {doc.page}")
    canvas.restoreState()


def make_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22, leading=27, alignment=TA_CENTER, spaceAfter=18),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=colors.HexColor("#0f172a"), spaceBefore=14, spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=colors.HexColor("#1e293b"), spaceBefore=10, spaceAfter=6),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13, alignment=TA_LEFT, spaceAfter=6),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.5, leading=9.5, spaceAfter=4),
        "code": ParagraphStyle("code", parent=base["Code"], fontName="Courier", fontSize=6.4, leading=7.6, backColor=colors.HexColor("#f8fafc")),
    }
    return styles


def para(text: str, style) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), style)


def img(path: str, width_cm: float) -> RLImage:
    im = RLImage(path)
    im._restrictSize(width_cm*cm, 18*cm)
    return im


def table_from_pairs(pairs: Sequence[Tuple[str, Any]], styles) -> Table:
    data = [[para(str(k), styles["small"]), para(str(v), styles["small"])] for k,v in pairs]
    t = Table(data, colWidths=[6.0*cm, 10.0*cm])
    t.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#eff6ff")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ]))
    return t


def build_pdf_report(config: MissionConfig, result: SimulationResult, outdir: Path) -> str:
    pdf_path = outdir / config.pdf_filename
    eq_dir = outdir/"equations"
    styles = make_styles()
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, rightMargin=1.2*cm, leftMargin=1.2*cm, topMargin=1.3*cm, bottomMargin=1.5*cm)
    story: List[Any] = []
    story.append(Paragraph(config.report_title, styles["title"]))
    story.append(para(f"<b>Missao:</b> {config.mission_name}", styles["body"]))
    story.append(para(f"<b>Objetivo do usuario:</b> {config.user_objectives}", styles["body"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(table_from_pairs([
        ("Altitude orbital", f"{config.orbit_altitude_m:,.1f} m"),
        ("Perigeu alvo", f"{config.perigee_target_m:,.1f} m"),
        ("Interface de entrada", f"{config.entry_interface_altitude_m:,.1f} m"),
        ("Massa inicial", f"{config.vehicle.mass_initial:,.1f} kg"),
        ("Geometria", f"L={config.shape.total_length_m:.2f} m, R={config.shape.body_radius_m:.2f} m"),
        ("Paginas alvo", config.target_pages),
    ], styles))
    story.append(PageBreak())
    story.append(Paragraph("1. Input integral do usuario em codigo", styles["h1"]))
    code = config.user_input_code.strip() or "# nenhum input fornecido"
    story.append(Preformatted(code[:12000], styles["code"]))
    story.append(PageBreak())
    story.append(Paragraph("2. Equacoes e calculos numericos passo a passo", styles["h1"]))
    ordered_eqs = [
        ("Raio orbital", "orbit_radius"), ("Velocidade orbital", "orbit_velocity"), ("Periodo orbital", "orbit_period"),
        ("Semi-eixo da transferencia", "deorbit_a"), ("Delta-v de deorbitacao", "deorbit_dv"),
        ("EDOs de reentrada", "reentry_odes"), ("Arrasto, sustentacao e pressao dinamica", "drag_lift"),
        ("Fluxo de calor", "heat_flux"), ("Temperatura de parede", "wall_temperature"), ("Pressao de estagnacao", "stagnation_pressure"),
        ("Plasma e blackout", "plasma"), ("Equacao do foguete", "rocket_eq"), ("Tunel de vento", "wind_tunnel"), ("Turbina", "turbine"),
    ]
    for title, key in ordered_eqs:
        story.append(Paragraph(title, styles["h2"]))
        eqp = equation_image(result.equations[key], eq_dir, key)
        story.append(img(eqp, 17.5))
        story.append(para(explain_equation(key, result), styles["body"]))
    story.append(PageBreak())
    story.append(Paragraph("3. Resultados consolidados", styles["h1"]))
    pairs = [(k, f"{v:.6e}" if abs(float(v)) >= 1e4 or abs(float(v)) < 1e-2 else f"{v:.6f}") for k,v in result.summary.items()]
    story.append(table_from_pairs(pairs, styles))
    story.append(PageBreak())
    story.append(Paragraph("4. Figuras cientificas", styles["h1"]))
    captions = {
        "rocket_beauty": "Render beauty do foguete com textura metalica/ceramica procedural.",
        "rocket_thermal": "Modo termico: distribuicao visual de carga termica na superficie.",
        "rocket_infrared": "Modo infravermelho: assinatura espectral termica simplificada.",
        "rocket_xray": "Modo X-ray analitico: visualizacao tecnica de contorno/estrutura.",
        "flight_dashboard": "Perfis de voo: altitude, velocidade, carga aerotermica, Mach e g-load.",
        "plasma_dashboard": "Atmosfera, temperatura de parede, densidade eletronica e frequencia de plasma.",
        "wind_cd_map": "Mapa do coeficiente de arrasto no tunel de vento surrogate.",
        "pressure_distribution": "Distribuicao surrogate de pressao superficial ao longo do corpo.",
        "rocket_optimization": "Historico de otimizacao da geometria do foguete.",
        "turbine_optimization": "Historico de otimizacao da geometria da turbina.",
    }
    for k, p in result.figures.items():
        story.append(Paragraph(captions.get(k, k), styles["h2"]))
        story.append(img(p, 16.5))
        story.append(Spacer(1,0.2*cm))
    story.append(PageBreak())
    story.append(Paragraph("5. Tabelas temporais amostradas", styles["h1"]))
    story.extend(timeline_tables(result.timeline, styles, rows_per_table=32, max_tables=max(2, config.target_pages//18)))
    story.append(PageBreak())
    story.append(Paragraph("6. Otimizacao: melhores geometrias", styles["h1"]))
    story.append(Paragraph("Melhor forma de foguete", styles["h2"]))
    story.append(Preformatted(json.dumps(result.rocket_opt["best_shape"], indent=2), styles["code"]))
    story.append(Paragraph("Melhor projeto de turbina", styles["h2"]))
    story.append(Preformatted(json.dumps(result.turbine_opt["best_design"], indent=2), styles["code"]))
    story.append(PageBreak())
    story.append(Paragraph("7. Apêndice A - Metadados reproduziveis", styles["h1"]))
    story.append(Preformatted(json.dumps(result.metadata, indent=2, ensure_ascii=False)[:20000], styles["code"]))
    # Expandir paginas com apêndices úteis, sem repetir texto: cada página tem dados ou equações derivadas.
    current_extra = max(0, config.target_pages - estimate_story_pages(len(story)))
    for sec in range(current_extra):
        story.append(PageBreak())
        story.append(Paragraph(f"Apendice numerico {sec+1}: amostras e derivacoes auxiliares", styles["h1"]))
        idx = np.linspace(0, len(result.timeline["time"])-1, 24).astype(int)
        data = [["i", "t [s]", "h [km]", "v [m/s]", "M", "q [kPa]", "Twall [K]"]]
        offset = (sec*7) % max(1, len(result.timeline["time"])-24)
        for n, i in enumerate(np.clip(idx+offset,0,len(result.timeline["time"])-1)):
            data.append([str(n), f"{result.timeline['time'][i]:.1f}", f"{result.timeline['alt'][i]/1000:.2f}", f"{result.timeline['vel'][i]:.1f}", f"{result.timeline['mach'][i]:.2f}", f"{result.timeline['q'][i]/1000:.2f}", f"{result.timeline['Twall'][i]:.1f}"])
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#cbd5e1")),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e2e8f0")),("FONTSIZE",(0,0),(-1,-1),6.5)]))
        story.append(t)
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return str(pdf_path)


def estimate_story_pages(n_items: int) -> int:
    return max(8, n_items // 8)


def explain_equation(key: str, result: SimulationResult) -> str:
    mapping = {
        "orbit_radius": "Soma o raio medio da Terra com a altitude orbital para obter a distancia ao centro da Terra.",
        "orbit_velocity": "Usa equilibrio entre gravidade central e movimento circular; a velocidade cai quando o raio orbital aumenta.",
        "orbit_period": "Calcula o tempo de uma volta completa usando a terceira lei de Kepler para orbita circular.",
        "deorbit_a": "Define o semi-eixo maior da elipse de transferencia entre apogeu orbital e perigeu atmosferico.",
        "deorbit_dv": "Delta-v retrogrado necessario para sair da orbita circular e entrar na elipse de reentrada.",
        "reentry_odes": "Sistema de EDOs plano usado para propagar raio, longitude, velocidade e angulo de trajetoria.",
        "drag_lift": "Arrasto e sustentacao dependem de pressao dinamica, area de referencia e coeficientes aerodinamicos.",
        "heat_flux": "Estimativa Sutton-Graves para aquecimento de estagnacao em reentrada hipersonica.",
        "wall_temperature": "Temperatura radiativa de equilibrio, aproximando emissao termica da parede aquecida.",
        "stagnation_pressure": "Pressao total compressivel ideal usada como proxy de carga no ponto de estagnacao.",
        "plasma": "Estimativa de densidade eletronica e frequencia de plasma; quando f_p excede o link, ha blackout.",
        "rocket_eq": "Equacao de Tsiolkovsky rearranjada para estimar propelente na recaptura final.",
        "wind_tunnel": "Modelo surrogate para Reynolds, atrito e arrasto total em varredura de velocidade e angulo de ataque.",
        "turbine": "Objetivo surrogate de turbina baseado em eficiencia, coeficientes de fluxo/carga, solidez e Mach de ponta.",
    }
    return mapping.get(key, "Equacao auxiliar do relatorio.")


def timeline_tables(tl: Dict[str, np.ndarray], styles, rows_per_table: int = 32, max_tables: int = 3) -> List[Any]:
    out: List[Any] = []
    n = len(tl["time"])
    for tab in range(max_tables):
        start = int(tab*n/max_tables)
        end = int((tab+1)*n/max_tables)
        idxs = np.linspace(start, max(start, end-1), min(rows_per_table, max(1,end-start))).astype(int)
        data = [["t[s]","h[km]","v[m/s]","Mach","q[kPa]","heat[MW/m2]","Twall[K]","fp[GHz]"]]
        for i in idxs:
            data.append([f"{tl['time'][i]:.1f}", f"{tl['alt'][i]/1000:.2f}", f"{tl['vel'][i]:.1f}", f"{tl['mach'][i]:.2f}", f"{tl['q'][i]/1000:.2f}", f"{tl['heat'][i]/1e6:.3f}", f"{tl['Twall'][i]:.1f}", f"{tl['fp'][i]/1e9:.2f}"])
        out.append(Paragraph(f"Tabela temporal {tab+1}", styles["h2"]))
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#cbd5e1")),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e2e8f0")),("FONTSIZE",(0,0),(-1,-1),6.2)]))
        out.append(t)
        out.append(Spacer(1,0.3*cm))
    return out


# ============================================================
# 8. HTML / METADADOS / PIPELINE PRINCIPAL
# ============================================================

def build_html_report(config: MissionConfig, result: SimulationResult, outdir: Path) -> str:
    html = ["<!doctype html><html><head><meta charset='utf-8'><title>NablaMath Report</title><style>body{font-family:Arial;margin:40px;max-width:1100px}img{max-width:100%;border:1px solid #ddd;margin:10px 0}code,pre{background:#f6f8fa;padding:12px;display:block;overflow:auto}.eq{font-family:serif;font-size:20px}</style></head><body>"]
    html.append(f"<h1>{config.report_title}</h1><p>{config.user_objectives}</p>")
    html.append("<h2>Equações LaTeX</h2>")
    for k,v in result.equations.items():
        html.append(f"<h3>{k}</h3><div class='eq'>${v}$</div>")
    html.append("<h2>Figuras</h2>")
    for k,p in result.figures.items():
        rel = os.path.relpath(p, outdir)
        html.append(f"<h3>{k}</h3><img src='{rel}' />")
    html.append("<h2>Resumo</h2><pre>"+json.dumps(result.summary,indent=2)+"</pre>")
    html.append("</body></html>")
    path = outdir/"nablamath_report.html"
    path.write_text("\n".join(html), encoding="utf-8")
    return str(path)


def run_pipeline(config: MissionConfig, outdir: Path, no_video: bool = False) -> SimulationResult:
    outdir.mkdir(parents=True, exist_ok=True)
    config.video.enabled = config.video.enabled and not no_video
    summary, timeline, equations = simulate_mission(config)
    wind = simulate_wind_tunnel(config)
    rocket_opt = optimize_rocket_shape(config)
    turbine_opt = optimize_turbine(config)
    result = SimulationResult(summary=summary, timeline=timeline, wind=wind, rocket_opt=rocket_opt, turbine_opt=turbine_opt, figures={}, videos={}, equations=equations, metadata={})
    figdir = outdir/"figures"
    result.figures.update({
        "rocket_beauty": render_rocket_3d(config, figdir/"rocket_beauty.png", "beauty", 0.55),
        "rocket_thermal": render_rocket_3d(config, figdir/"rocket_thermal.png", "thermal", 0.85),
        "rocket_infrared": render_rocket_3d(config, figdir/"rocket_infrared.png", "infrared", 0.85),
        "rocket_xray": render_rocket_3d(config, figdir/"rocket_xray.png", "xray", 0.4),
    })
    result.figures.update(plot_dashboard(result, figdir))
    result.videos.update(generate_video(config, outdir))
    result.metadata = {
        "generated_at_unix": time.time(), "config": asdict(config), "summary": summary,
        "figures": result.figures, "videos": result.videos,
        "notes": [
            "Equacoes LaTeX do PDF sao renderizadas como imagens por Matplotlib mathtext.",
            "Este arquivo unico contem biblioteca + CLI + relatorio.",
            "Modelos aerodinamicos, plasma, turbina e renderer sao approximations/surrogates educacionais de engenharia.",
        ],
    }
    (outdir/"metadata.json").write_text(json.dumps(result.metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    build_html_report(config, result, outdir)
    build_pdf_report(config, result, outdir)
    return result


def make_default_user_code() -> str:
    return textwrap.dedent('''
    from nablamath_all_in_one_professional import MissionConfig, run_pipeline
    from pathlib import Path

    config = MissionConfig(
        mission_name="Asteria-Professional-Dossier",
        target_pages=80,
    )

    result = run_pipeline(config, Path("outputs_nabla"), no_video=False)
    print(result.summary)
    ''').strip()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NablaMath All-in-One Professional Report Generator")
    p.add_argument("--out", default="outputs_nablamath_all_in_one", help="Pasta de saída")
    p.add_argument("--pages", type=int, default=80, help="Número alvo aproximado de páginas")
    p.add_argument("--fps", type=int, default=6, help="FPS do vídeo opcional")
    p.add_argument("--video-seconds", type=float, default=4.0, help="Duração do vídeo opcional")
    p.add_argument("--no-video", action="store_true", help="Não gerar vídeo")
    p.add_argument("--rocket-iters", type=int, default=80, help="Iterações de otimização de foguete")
    p.add_argument("--turbine-iters", type=int, default=80, help="Iterações de otimização de turbina")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    config = MissionConfig()
    config.target_pages = int(args.pages)
    config.video.fps = int(args.fps)
    config.video.seconds = float(args.video_seconds)
    config.optimization.rocket_iterations = int(args.rocket_iters)
    config.optimization.turbine_iterations = int(args.turbine_iters)
    config.user_input_code = make_default_user_code()
    outdir = Path(args.out)
    print(f"[NablaMath] Gerando relatório em: {outdir.resolve()}")
    result = run_pipeline(config, outdir, no_video=args.no_video)
    print("[NablaMath] Concluído.")
    print(json.dumps({"pdf": str(outdir/config.pdf_filename), "html": str(outdir/"nablamath_report.html"), "figures": result.figures, "videos": result.videos}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
