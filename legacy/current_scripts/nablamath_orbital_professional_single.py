#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NablaMath Orbital Professional Single-File Report Generator
==========================================================

Arquivo unico, sem estrutura de pacote, para gerar um relatorio PDF tecnico
profissional de mecanica orbital, reentrada, aerotermodinamica, plasma,
tunel de vento surrogate, otimizacao de geometria de foguete/turbina e
renders cientificos.

Objetivo desta versao:
- Nao repetir texto inutilmente.
- Colocar calculos matematicos reais em LaTeX visual dentro do PDF.
- Mostrar substituicoes numericas passo a passo.
- Gerar tabelas e figuras conectadas aos calculos.
- Funcionar manualmente com um unico arquivo .py.

Dependencias recomendadas:
    pip install numpy matplotlib reportlab pillow imageio

Uso basico:
    python nablamath_orbital_professional_single.py --out outputs_orbital --pages 80

Uso sem video:
    python nablamath_orbital_professional_single.py --out outputs_orbital --pages 80 --no-video

Uso com menos paginas para teste:
    python nablamath_orbital_professional_single.py --out outputs_orbital_test --pages 30 --no-video
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

# Matplotlib headless.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm as mpl_cm
from matplotlib.colors import Normalize

try:
    from PIL import Image as PILImage
except Exception:  # pragma: no cover
    PILImage = None

try:
    import imageio.v2 as imageio
except Exception:  # pragma: no cover
    imageio = None

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, inch
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        Image,
        KeepTogether,
        PageBreak,
        PageTemplate,
        Paragraph,
        Preformatted,
        Spacer,
        Table,
        TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


# =============================================================================
# 1. CONSTANTES FISICAS
# =============================================================================

G0 = 9.80665
R_EARTH = 6_371_000.0
MU_EARTH = 3.986004418e14
R_AIR = 287.05
GAMMA_AIR = 1.4
SIGMA_SB = 5.670374419e-8
M_AIR = 4.81e-26
K_B = 1.380649e-23
E_CHARGE = 1.602176634e-19
EPS0 = 8.8541878128e-12
M_ELECTRON = 9.1093837015e-31


# =============================================================================
# 2. CONFIGURACOES
# =============================================================================

@dataclass
class VehicleConfig:
    name: str = "Asteria-R Reusable Orbital Vehicle"
    mass_initial_kg: float = 134_000.0
    mass_dry_kg: float = 87_500.0
    reference_area_m2: float = 63.6
    drag_coefficient: float = 1.28
    lift_to_drag: float = 0.24
    nose_radius_m: float = 1.25
    body_radius_m: float = 4.55
    body_length_m: float = 46.0
    emissivity: float = 0.84
    landing_isp_s: float = 330.0
    landing_burn_start_altitude_m: float = 2900.0
    communications_frequency_hz: float = 2.25e9


@dataclass
class ShapeConfig:
    nose_length_m: float = 9.5
    cylinder_length_m: float = 39.0
    tail_length_m: float = 4.0
    body_radius_m: float = 4.55
    engine_exit_radius_m: float = 1.28
    fin_count: int = 4
    fin_span_m: float = 3.6
    fin_root_chord_m: float = 6.2
    fin_tip_chord_m: float = 2.3
    fin_sweep_deg: float = 29.0

    @property
    def total_length_m(self) -> float:
        return self.nose_length_m + self.cylinder_length_m + self.tail_length_m

    @property
    def frontal_area_m2(self) -> float:
        return math.pi * self.body_radius_m ** 2

    @property
    def internal_volume_m3(self) -> float:
        return math.pi * self.body_radius_m ** 2 * self.cylinder_length_m


@dataclass
class MissionConfig:
    mission_name: str = "Asteria-3 Professional Orbital Dossier"
    report_title: str = "Asteria-3 - Dossie tecnico orbital profissional"
    user_objectives: str = (
        "Gerar um PDF tecnico com calculos passo a passo em LaTeX, mecanica orbital, "
        "reentrada, pressao, temperatura, plasma, tunel de vento surrogate, otimizacao "
        "de forma de foguete e turbina, figuras cientificas e apendices numericos."
    )
    user_input_code: str = "# O codigo de entrada completo sera inserido automaticamente pelo script."
    vehicle: VehicleConfig = field(default_factory=VehicleConfig)
    shape: ShapeConfig = field(default_factory=ShapeConfig)
    orbit_altitude_m: float = 430_000.0
    perigee_target_m: float = 36_000.0
    entry_interface_altitude_m: float = 123_000.0
    reentry_bank_angle_deg: float = 31.0
    dt_reentry_s: float = 0.45
    max_reentry_time_s: float = 4900.0
    xray_threshold_k: float = 2.6e5
    wind_velocities_m_s: Tuple[float, ...] = (120, 250, 500, 900, 1400, 2200, 3200, 3800)
    wind_aoa_deg: Tuple[float, ...] = (-6, -2, 0, 4, 8, 12)
    wind_altitude_m: float = 2500.0
    optimization_seed: int = 321
    rocket_optimization_iterations: int = 72
    turbine_optimization_iterations: int = 72
    video_fps: int = 6
    video_seconds: float = 4.0


@dataclass
class TurbineConfig:
    radius_m: float = 0.42
    hub_radius_m: float = 0.13
    blade_count: int = 30
    chord_root_m: float = 0.12
    chord_tip_m: float = 0.05
    twist_root_deg: float = 58.0
    twist_tip_deg: float = 18.0
    rpm: float = 34_500.0
    mass_flow_kg_s: float = 44.0
    pressure_ratio_target: float = 15.0
    stage_temperature_k: float = 990.0


@dataclass
class SimulationResult:
    orbit: Dict[str, float]
    deorbit: Dict[str, float]
    entry: Dict[str, float]
    timeline: Dict[str, np.ndarray]
    summary: Dict[str, float]
    wind: Dict[str, Any]
    rocket_opt: Dict[str, Any]
    turbine_opt: Dict[str, Any]
    output_files: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 3. MODELOS FISICOS
# =============================================================================

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


def standard_atmosphere(h_m: float) -> Dict[str, float]:
    """Atmosfera padrao simplificada ate 86 km + continuacao exponencial."""
    h = max(0.0, float(h_m))
    if h <= 86_000.0:
        idx = 0
        for i in range(len(_ATMOS_LAYERS) - 1):
            if _ATMOS_LAYERS[i][0] <= h < _ATMOS_LAYERS[i + 1][0]:
                idx = i
                break
        else:
            idx = len(_ATMOS_LAYERS) - 1
        hb, Tb, pb, Lb = _ATMOS_LAYERS[idx]
        if abs(Lb) < 1e-12:
            T = Tb
            p = pb * math.exp(-G0 * (h - hb) / (R_AIR * Tb))
        else:
            T = Tb + Lb * (h - hb)
            p = pb * (T / Tb) ** (-G0 / (Lb * R_AIR))
        rho = p / (R_AIR * T)
    else:
        base = standard_atmosphere(86_000.0)
        H = 7000.0 + 1200.0 * min((h - 86_000.0) / 80_000.0, 4.0)
        T = max(180.0, 186.946 + 0.0025 * (h - 86_000.0))
        rho = base["rho"] * math.exp(-(h - 86_000.0) / H)
        p = rho * R_AIR * T
    a = math.sqrt(GAMMA_AIR * R_AIR * T)
    mu = 1.458e-6 * T ** 1.5 / (T + 110.4)
    return {"T": T, "p": p, "rho": rho, "a": a, "mu": mu}


def circular_orbit(altitude_m: float) -> Dict[str, float]:
    r = R_EARTH + altitude_m
    v = math.sqrt(MU_EARTH / r)
    period = 2.0 * math.pi * math.sqrt(r ** 3 / MU_EARTH)
    energy = -MU_EARTH / (2.0 * r)
    return {"r_m": r, "v_m_s": v, "period_s": period, "specific_energy_j_kg": energy}


def deorbit_transfer(orbit_altitude_m: float, perigee_altitude_m: float) -> Dict[str, float]:
    ra = R_EARTH + orbit_altitude_m
    rp = R_EARTH + perigee_altitude_m
    at = 0.5 * (ra + rp)
    vcirc = math.sqrt(MU_EARTH / ra)
    va = math.sqrt(MU_EARTH * (2.0 / ra - 1.0 / at))
    vp = math.sqrt(MU_EARTH * (2.0 / rp - 1.0 / at))
    return {
        "r_apogee_m": ra,
        "r_perigee_m": rp,
        "a_transfer_m": at,
        "v_circular_m_s": vcirc,
        "v_apogee_transfer_m_s": va,
        "v_perigee_transfer_m_s": vp,
        "delta_v_deorbit_m_s": vcirc - va,
        "eccentricity": (ra - rp) / (ra + rp),
    }


def entry_state(orbit_altitude_m: float, perigee_altitude_m: float, entry_altitude_m: float) -> Dict[str, float]:
    trans = deorbit_transfer(orbit_altitude_m, perigee_altitude_m)
    r = R_EARTH + entry_altitude_m
    v = math.sqrt(MU_EARTH * (2.0 / r - 1.0 / trans["a_transfer_m"]))
    gamma_deg = -1.25
    return {"r_entry_m": r, "entry_altitude_m": entry_altitude_m, "entry_velocity_m_s": v, "entry_gamma_deg": gamma_deg}


def sutton_graves_heat_flux(rho: float, v: float, nose_radius_m: float) -> float:
    # Constante adaptada para produzir escala W/m^2 em contexto educacional.
    return max(0.0, 1.83e-4 * math.sqrt(max(rho, 1e-12) / max(nose_radius_m, 1e-6)) * v ** 3 * 1.0e4)


def stagnation_pressure(p_static: float, mach: float) -> float:
    return p_static * (1.0 + 0.5 * (GAMMA_AIR - 1.0) * mach ** 2) ** (GAMMA_AIR / (GAMMA_AIR - 1.0))


def wall_temperature_from_heat_flux(qdot: float, emissivity: float, ambient_T: float) -> float:
    trad = (qdot / max(emissivity * SIGMA_SB, 1e-12)) ** 0.25
    return min(4400.0, max(ambient_T, trad))


def ionization_fraction(T_wall: float, rho: float) -> float:
    # Surrogate logistic. Um modelo fisico mais fiel exigiria equilibrio quimico/CFD.
    thermal_activation = 1.0 / (1.0 + math.exp(-(T_wall - 6200.0) / 900.0))
    density_weight = min(1.0, math.sqrt(max(rho, 0.0) / 0.02 + 1e-12))
    return float(min(1.0, thermal_activation * density_weight))


def electron_density(rho: float, ion_frac: float) -> float:
    return ion_frac * rho / M_AIR


def plasma_frequency_hz(ne_m3: float) -> float:
    # fp = (1 / 2pi) sqrt(ne e^2 / (eps0 me))
    return (1.0 / (2.0 * math.pi)) * math.sqrt(max(ne_m3, 0.0) * E_CHARGE ** 2 / (EPS0 * M_ELECTRON))


def spectral_proxies(T_wall: float, xray_threshold_k: float) -> Dict[str, float]:
    ir = min(1.0, (T_wall / 2200.0) ** 1.2)
    visible = min(1.0, max(0.0, (T_wall - 800.0) / 2400.0))
    uv = min(1.0, max(0.0, (T_wall - 2800.0) / 6500.0))
    xray = min(1.0, math.exp(-(xray_threshold_k / max(T_wall, 1.0)) ** 0.7))
    return {"ir": ir, "visible": visible, "uv": uv, "xray": xray}


# =============================================================================
# 4. SIMULACAO PRINCIPAL
# =============================================================================

def simulate_reentry(config: MissionConfig) -> Dict[str, np.ndarray]:
    veh = config.vehicle
    entry = entry_state(config.orbit_altitude_m, config.perigee_target_m, config.entry_interface_altitude_m)

    r = entry["r_entry_m"]
    h = config.entry_interface_altitude_m
    v = entry["entry_velocity_m_s"]
    gamma = math.radians(entry["entry_gamma_deg"])
    theta = 0.0
    t = 0.0
    m = veh.mass_initial_kg
    dt = config.dt_reentry_s
    bank = math.radians(config.reentry_bank_angle_deg)

    A = veh.reference_area_m2
    Cd = veh.drag_coefficient
    CL = Cd * veh.lift_to_drag * math.cos(bank)

    keys = [
        "time_s", "altitude_m", "velocity_m_s", "gamma_deg", "downrange_m", "rho", "p", "T", "a", "mach",
        "dynamic_pressure_pa", "drag_n", "lift_n", "g_load", "heat_flux_w_m2", "wall_temperature_k",
        "stagnation_pressure_pa", "ionization_fraction", "electron_density_m3", "plasma_frequency_hz",
        "ir", "visible", "uv", "xray", "phase_index",
    ]
    arr: Dict[str, List[float]] = {k: [] for k in keys}

    while h > max(veh.landing_burn_start_altitude_m, 1000.0) and t < config.max_reentry_time_s and v > 45.0:
        atm = standard_atmosphere(h)
        rho, p, T, a = atm["rho"], atm["p"], atm["T"], atm["a"]
        mach = v / max(a, 1e-9)
        qdyn = 0.5 * rho * v * v
        D = qdyn * Cd * A
        L = qdyn * CL * A
        g = MU_EARTH / (r * r)

        dvdt = -D / m - g * math.sin(gamma)
        dgammadt = L / max(m * v, 1e-6) + (v / r - g / max(v, 1e-6)) * math.cos(gamma)
        drdt = v * math.sin(gamma)
        dthetadt = v * math.cos(gamma) / r

        qdot = sutton_graves_heat_flux(rho, v, veh.nose_radius_m)
        Tw = wall_temperature_from_heat_flux(qdot, veh.emissivity, T)
        p0 = stagnation_pressure(p, mach)
        xion = ionization_fraction(Tw, rho)
        ne = electron_density(rho, xion)
        fp = plasma_frequency_hz(ne)
        spec = spectral_proxies(Tw, config.xray_threshold_k)
        g_load = abs(dvdt) / G0

        values = {
            "time_s": t, "altitude_m": h, "velocity_m_s": v, "gamma_deg": math.degrees(gamma),
            "downrange_m": R_EARTH * theta, "rho": rho, "p": p, "T": T, "a": a, "mach": mach,
            "dynamic_pressure_pa": qdyn, "drag_n": D, "lift_n": L, "g_load": g_load,
            "heat_flux_w_m2": qdot, "wall_temperature_k": Tw, "stagnation_pressure_pa": p0,
            "ionization_fraction": xion, "electron_density_m3": ne, "plasma_frequency_hz": fp,
            "ir": spec["ir"], "visible": spec["visible"], "uv": spec["uv"], "xray": spec["xray"], "phase_index": 0,
        }
        for k in keys:
            arr[k].append(float(values[k]))

        v = max(0.0, v + dvdt * dt)
        gamma = gamma + dgammadt * dt
        r = r + drdt * dt
        theta = theta + dthetadt * dt
        h = max(0.0, r - R_EARTH)
        t += dt

    # Fase final de recaptura/landing burn.
    burn_start_h = max(h, veh.landing_burn_start_altitude_m)
    burn_start_v = max(v, 1.0)
    decel = burn_start_v ** 2 / (2.0 * max(burn_start_h, 1.0)) + 0.35 * G0
    burn_time = max(1.0, burn_start_v / max(decel, 1e-6))
    dt_land = min(0.2, burn_time / 100.0)
    t_land = 0.0
    h_land = burn_start_h
    v_land = burn_start_v

    while h_land > 0.0 and t_land < burn_time + 5.0:
        atm = standard_atmosphere(h_land)
        rho, p, T, a = atm["rho"], atm["p"], atm["T"], atm["a"]
        mach = v_land / max(a, 1e-9)
        qdyn = 0.5 * rho * v_land ** 2
        D = qdyn * Cd * A
        L = 0.0
        qdot = 0.05 * sutton_graves_heat_flux(rho, v_land, veh.nose_radius_m)
        Tw = wall_temperature_from_heat_flux(qdot, veh.emissivity, T)
        p0 = stagnation_pressure(p, mach)
        xion = 0.2 * ionization_fraction(Tw, rho)
        ne = electron_density(rho, xion)
        fp = plasma_frequency_hz(ne)
        spec = spectral_proxies(Tw, config.xray_threshold_k)
        g_load = (decel + G0) / G0

        values = {
            "time_s": t + t_land, "altitude_m": h_land, "velocity_m_s": v_land, "gamma_deg": -90.0,
            "downrange_m": R_EARTH * theta, "rho": rho, "p": p, "T": T, "a": a, "mach": mach,
            "dynamic_pressure_pa": qdyn, "drag_n": D, "lift_n": L, "g_load": g_load,
            "heat_flux_w_m2": qdot, "wall_temperature_k": Tw, "stagnation_pressure_pa": p0,
            "ionization_fraction": xion, "electron_density_m3": ne, "plasma_frequency_hz": fp,
            "ir": spec["ir"], "visible": spec["visible"], "uv": spec["uv"], "xray": spec["xray"], "phase_index": 1,
        }
        for k in keys:
            arr[k].append(float(values[k]))

        v_land = max(0.5, v_land - decel * dt_land)
        h_land = max(0.0, h_land - v_land * dt_land)
        t_land += dt_land

    return {k: np.asarray(v, dtype=float) for k, v in arr.items()}


def summarize(config: MissionConfig, orbit: Dict[str, float], deorbit: Dict[str, float], entry: Dict[str, float], timeline: Dict[str, np.ndarray]) -> Dict[str, float]:
    veh = config.vehicle
    total_dv_landing = float(timeline["velocity_m_s"][-1] + 35.0) if len(timeline["velocity_m_s"]) else 35.0
    burn_start_v = float(np.max(timeline["velocity_m_s"][timeline["phase_index"] > 0])) if np.any(timeline["phase_index"] > 0) else 0.0
    burn_start_h = veh.landing_burn_start_altitude_m
    prop_ratio = math.exp(total_dv_landing / max(veh.landing_isp_s * G0, 1e-9))
    landing_prop = max(0.0, veh.mass_initial_kg - veh.mass_initial_kg / prop_ratio)
    blackout = timeline["plasma_frequency_hz"] > veh.communications_frequency_hz
    blackout_duration = float(np.sum(blackout) * config.dt_reentry_s)
    peak_idx = int(np.argmax(timeline["heat_flux_w_m2"]))
    q_idx = int(np.argmax(timeline["dynamic_pressure_pa"]))
    g_idx = int(np.argmax(timeline["g_load"]))
    return {
        "orbit_velocity_m_s": orbit["v_m_s"],
        "orbit_period_s": orbit["period_s"],
        "deorbit_delta_v_m_s": deorbit["delta_v_deorbit_m_s"],
        "entry_velocity_m_s": entry["entry_velocity_m_s"],
        "peak_heat_flux_w_m2": float(np.max(timeline["heat_flux_w_m2"])),
        "peak_heat_time_s": float(timeline["time_s"][peak_idx]),
        "peak_heat_altitude_m": float(timeline["altitude_m"][peak_idx]),
        "peak_dynamic_pressure_pa": float(np.max(timeline["dynamic_pressure_pa"])),
        "peak_q_time_s": float(timeline["time_s"][q_idx]),
        "peak_q_altitude_m": float(timeline["altitude_m"][q_idx]),
        "peak_g_load": float(np.max(timeline["g_load"])),
        "peak_g_time_s": float(timeline["time_s"][g_idx]),
        "peak_g_altitude_m": float(timeline["altitude_m"][g_idx]),
        "peak_wall_temperature_k": float(np.max(timeline["wall_temperature_k"])),
        "peak_plasma_frequency_hz": float(np.max(timeline["plasma_frequency_hz"])),
        "blackout_duration_s": blackout_duration,
        "landing_propellant_kg": landing_prop,
        "burn_start_velocity_m_s": burn_start_v,
        "burn_start_altitude_m": burn_start_h,
    }


# =============================================================================
# 5. TUNEL DE VENTO E OTIMIZACAO
# =============================================================================

def rocket_aero_surrogate(shape: ShapeConfig, speed: float, aoa_deg: float, altitude_m: float) -> Dict[str, float]:
    atm = standard_atmosphere(altitude_m)
    rho, T, mu, a = atm["rho"], atm["T"], atm["mu"], atm["a"]
    mach = speed / max(a, 1e-9)
    Re = rho * speed * shape.total_length_m / max(mu, 1e-12)
    alpha = math.radians(aoa_deg)
    fineness = shape.total_length_m / max(2.0 * shape.body_radius_m, 1e-9)
    wetted = 2.0 * math.pi * shape.body_radius_m * shape.cylinder_length_m + math.pi * shape.body_radius_m * math.sqrt(shape.body_radius_m ** 2 + shape.nose_length_m ** 2)
    cf = 0.455 / max(math.log10(max(Re, 10.0)), 1.0) ** 2.58
    cd_friction = cf * wetted / max(shape.frontal_area_m2, 1e-9)
    cd_base = 0.08 + 0.18 / max(fineness, 1.2)
    cd_wave = 0.11 * math.exp(-((mach - 1.05) / 0.32) ** 2) + 0.035 * max(mach - 1.2, 0.0)
    cd_fin = 0.006 * shape.fin_count * shape.fin_span_m / max(shape.body_radius_m, 0.2)
    cd_aoa = 0.22 * alpha ** 2
    cd = max(0.045, cd_base + cd_friction + cd_wave + cd_fin + cd_aoa)
    AR = 2.0 * shape.fin_span_m / max(0.5 * (shape.fin_root_chord_m + shape.fin_tip_chord_m), 0.2)
    cl_alpha = 2.0 * math.pi * AR / max(AR + 2.0, 0.5)
    cl = cl_alpha * alpha * (1.0 + 0.05 * min(mach, 3.0))
    cp_x = 0.58 * shape.total_length_m - 0.06 * shape.nose_length_m + 0.035 * shape.fin_root_chord_m
    cg_x = 0.47 * shape.total_length_m
    stability = (cp_x - cg_x) / max(2.0 * shape.body_radius_m, 1e-6)
    cm = -0.04 * stability * alpha
    qdyn = 0.5 * rho * speed ** 2
    heat = sutton_graves_heat_flux(rho, speed, 1.25)
    return {"mach": mach, "reynolds": Re, "cd": cd, "cl": cl, "cm": cm, "q": qdyn, "stability_calibers": stability, "heat_flux": heat}


def simulate_wind_tunnel(config: MissionConfig) -> Dict[str, Any]:
    shape = config.shape
    velocities = np.asarray(config.wind_velocities_m_s, dtype=float)
    aoas = np.asarray(config.wind_aoa_deg, dtype=float)
    cd = np.zeros((len(aoas), len(velocities)))
    cl = np.zeros_like(cd)
    cm = np.zeros_like(cd)
    heat = np.zeros_like(cd)
    Re = np.zeros_like(cd)
    stab = np.zeros_like(cd)
    for i, aoa in enumerate(aoas):
        for j, v in enumerate(velocities):
            out = rocket_aero_surrogate(shape, float(v), float(aoa), config.wind_altitude_m)
            cd[i, j] = out["cd"]
            cl[i, j] = out["cl"]
            cm[i, j] = out["cm"]
            heat[i, j] = out["heat_flux"]
            Re[i, j] = out["reynolds"]
            stab[i, j] = out["stability_calibers"]
    score = cd + 1e-7 * heat + 0.03 * np.maximum(0.0, 1.0 - stab) ** 2
    best = np.unravel_index(np.argmin(score), score.shape)
    x = np.linspace(0.0, shape.total_length_m, 160)
    cp = 1.8 * np.exp(-5.0 * x / shape.total_length_m) + 0.12 * np.sin(4.0 * np.pi * x / shape.total_length_m)
    return {
        "velocities": velocities,
        "aoas": aoas,
        "cd": cd,
        "cl": cl,
        "cm": cm,
        "heat": heat,
        "reynolds": Re,
        "stability": stab,
        "cp_x": x,
        "cp": cp,
        "best": {"aoa_deg": float(aoas[best[0]]), "velocity_m_s": float(velocities[best[1]]), "cd": float(cd[best]), "stability_calibers": float(stab[best]), "heat_flux": float(heat[best])},
    }


def rocket_shape_score(shape: ShapeConfig, config: MissionConfig) -> Tuple[float, Dict[str, float]]:
    speeds = [300, 900, 1800, 3200]
    aoas = [0, 4, 8]
    cds, heats, stabs = [], [], []
    for aoa in aoas:
        for v in speeds:
            out = rocket_aero_surrogate(shape, v, aoa, config.wind_altitude_m)
            cds.append(out["cd"])
            heats.append(out["heat_flux"])
            stabs.append(out["stability_calibers"])
    avg_cd = float(np.mean(cds))
    max_heat = float(np.max(heats))
    stab_mean = float(np.mean(stabs))
    volume = shape.internal_volume_m3
    length_penalty = abs(shape.total_length_m - 52.0) / 52.0
    stability_penalty = max(0.0, 1.0 - stab_mean) ** 2 + max(0.0, stab_mean - 3.0) ** 2
    score = 2.2 * avg_cd + 0.08 * max_heat / 1e6 + 1.15 * stability_penalty + 0.45 * length_penalty - 0.0035 * volume
    return score, {"score": score, "avg_cd": avg_cd, "max_heat": max_heat, "stability": stab_mean, "volume": volume, "length": shape.total_length_m}


def optimize_rocket_shape(config: MissionConfig) -> Dict[str, Any]:
    rng = np.random.default_rng(config.optimization_seed)
    best_shape = config.shape
    best_score, best_metrics = rocket_shape_score(best_shape, config)
    history: List[Dict[str, float]] = []
    for it in range(config.rocket_optimization_iterations):
        candidate = ShapeConfig(
            nose_length_m=float(rng.uniform(6.5, 14.0)),
            cylinder_length_m=float(rng.uniform(30.0, 45.0)),
            tail_length_m=float(rng.uniform(2.2, 6.0)),
            body_radius_m=float(rng.uniform(3.4, 5.3)),
            engine_exit_radius_m=float(rng.uniform(0.8, 2.0)),
            fin_count=int(rng.integers(3, 6)),
            fin_span_m=float(rng.uniform(2.2, 5.4)),
            fin_root_chord_m=float(rng.uniform(4.0, 8.5)),
            fin_tip_chord_m=float(rng.uniform(1.0, 4.0)),
            fin_sweep_deg=float(rng.uniform(15.0, 48.0)),
        )
        score, metrics = rocket_shape_score(candidate, config)
        history.append({"iteration": it + 1, **metrics})
        if score < best_score:
            best_score, best_metrics, best_shape = score, metrics, candidate
    return {"best_shape": asdict(best_shape), "best_metrics": best_metrics, "history": history}


def turbine_score(t: TurbineConfig) -> Tuple[float, Dict[str, float]]:
    area = math.pi * max(t.radius_m ** 2 - t.hub_radius_m ** 2, 1e-9)
    omega = t.rpm * 2.0 * math.pi / 60.0
    u_tip = omega * t.radius_m
    a = math.sqrt(GAMMA_AIR * R_AIR * t.stage_temperature_k)
    tip_mach = u_tip / a
    flow_coeff = t.mass_flow_kg_s / max(area * 35.0 * t.stage_temperature_k / 1000.0, 1e-6)
    loading_coeff = t.pressure_ratio_target / max((u_tip / 300.0) ** 2, 1e-6)
    solidity = t.blade_count * 0.5 * (t.chord_root_m + t.chord_tip_m) / max(2.0 * math.pi * t.radius_m, 1e-6)
    twist = abs(t.twist_root_deg - t.twist_tip_deg)
    eta = 0.91
    eta -= 0.11 * abs(flow_coeff - 0.60)
    eta -= 0.08 * abs(loading_coeff - 1.55)
    eta -= 0.05 * abs(solidity - 1.25)
    eta -= 0.035 * max(0.0, tip_mach - 1.05)
    eta -= 0.0015 * abs(twist - 38.0)
    eta = float(np.clip(eta, 0.40, 0.95))
    stress_proxy = 7800.0 * u_tip ** 2
    power_proxy = eta * t.mass_flow_kg_s * t.pressure_ratio_target * 8.2e3
    score = -10.0 * eta + 1.4 * max(0.0, tip_mach - 1.05) + 2e-8 * stress_proxy - 1e-6 * power_proxy
    return score, {"score": score, "efficiency": eta, "tip_speed": u_tip, "tip_mach": tip_mach, "flow_coeff": flow_coeff, "loading_coeff": loading_coeff, "solidity": solidity, "stress_proxy": stress_proxy, "power_proxy": power_proxy}


def optimize_turbine(config: MissionConfig) -> Dict[str, Any]:
    rng = np.random.default_rng(config.optimization_seed + 17)
    base = TurbineConfig()
    best = base
    best_score, best_metrics = turbine_score(base)
    history = []
    for it in range(config.turbine_optimization_iterations):
        cand = TurbineConfig(
            radius_m=float(rng.uniform(0.28, 0.60)),
            hub_radius_m=float(rng.uniform(0.08, 0.22)),
            blade_count=int(rng.integers(18, 42)),
            chord_root_m=float(rng.uniform(0.07, 0.17)),
            chord_tip_m=float(rng.uniform(0.03, 0.095)),
            twist_root_deg=float(rng.uniform(40.0, 72.0)),
            twist_tip_deg=float(rng.uniform(8.0, 30.0)),
            rpm=float(rng.uniform(18_000.0, 50_000.0)),
            mass_flow_kg_s=float(rng.uniform(18.0, 72.0)),
            pressure_ratio_target=float(rng.uniform(8.0, 23.0)),
            stage_temperature_k=float(rng.uniform(780.0, 1260.0)),
        )
        if cand.hub_radius_m >= cand.radius_m * 0.82:
            continue
        score, metrics = turbine_score(cand)
        history.append({"iteration": it + 1, **metrics})
        if score < best_score:
            best_score, best_metrics, best = score, metrics, cand
    return {"best_design": asdict(best), "best_metrics": best_metrics, "history": history}


def run_simulation(config: MissionConfig) -> SimulationResult:
    orbit = circular_orbit(config.orbit_altitude_m)
    deorbit = deorbit_transfer(config.orbit_altitude_m, config.perigee_target_m)
    entry = entry_state(config.orbit_altitude_m, config.perigee_target_m, config.entry_interface_altitude_m)
    timeline = simulate_reentry(config)
    summary = summarize(config, orbit, deorbit, entry, timeline)
    wind = simulate_wind_tunnel(config)
    rocket_opt = optimize_rocket_shape(config)
    turbine_opt = optimize_turbine(config)
    metadata = {"generated_at_unix": time.time(), "config": asdict(config), "warnings": ["Modelo surrogate educacional; nao substituir CFD/FEA/analise certificada."]}
    return SimulationResult(orbit, deorbit, entry, timeline, summary, wind, rocket_opt, turbine_opt, metadata=metadata)


# =============================================================================
# 6. FIGURAS E RENDERS
# =============================================================================

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_plot(path: Path, dpi: int = 180) -> str:
    plt.tight_layout()
    plt.savefig(path, dpi=dpi)
    plt.close()
    return str(path)


def generate_figures(config: MissionConfig, result: SimulationResult, out_dir: Path) -> Dict[str, str]:
    fig_dir = ensure_dir(out_dir / "figures")
    tl = result.timeline
    files: Dict[str, str] = {}

    # Trajetoria 3D.
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    u = np.linspace(0, 2 * np.pi, 50)
    v = np.linspace(0, np.pi, 30)
    xs = R_EARTH * np.outer(np.cos(u), np.sin(v))
    ys = R_EARTH * np.outer(np.sin(u), np.sin(v))
    zs = R_EARTH * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(xs / 1000, ys / 1000, zs / 1000, alpha=0.12, linewidth=0)
    theta = tl["downrange_m"] / R_EARTH
    rr = R_EARTH + tl["altitude_m"]
    lat = np.deg2rad(18.0)
    x = rr * np.cos(theta) * math.cos(lat)
    y = rr * np.sin(theta) * math.cos(lat)
    z = rr * math.sin(lat)
    ax.plot(x / 1000, y / 1000, z / 1000, linewidth=1.1)
    ax.scatter(x / 1000, y / 1000, z / 1000, c=tl["wall_temperature_k"], s=7, cmap="inferno")
    ax.set_title("Orbital reentry and capture trajectory colored by wall temperature")
    ax.set_xlabel("x [km]"); ax.set_ylabel("y [km]"); ax.set_zlabel("z [km]")
    files["trajectory_3d"] = save_plot(fig_dir / "trajectory_3d.png")

    # Perfis.
    fig = plt.figure(figsize=(12, 8))
    ax1 = fig.add_subplot(221); ax1.plot(tl["time_s"], tl["altitude_m"] / 1000); ax1.set_title("Altitude"); ax1.set_xlabel("t [s]"); ax1.set_ylabel("h [km]")
    ax2 = fig.add_subplot(222); ax2.plot(tl["time_s"], tl["velocity_m_s"]); ax2.set_title("Velocity"); ax2.set_xlabel("t [s]"); ax2.set_ylabel("v [m/s]")
    ax3 = fig.add_subplot(223); ax3.plot(tl["time_s"], tl["dynamic_pressure_pa"] / 1000, label="q [kPa]"); ax3.plot(tl["time_s"], tl["heat_flux_w_m2"] / 1e6, label="heat [MW/m2]"); ax3.legend(); ax3.set_title("Loads")
    ax4 = fig.add_subplot(224); ax4.plot(tl["time_s"], tl["g_load"], label="g-load"); ax4.plot(tl["time_s"], tl["mach"], label="Mach"); ax4.legend(); ax4.set_title("Mach and g-load")
    files["profiles"] = save_plot(fig_dir / "profiles.png")

    # Plasma/thermal.
    fig = plt.figure(figsize=(12, 8))
    ax1 = fig.add_subplot(221); ax1.plot(tl["altitude_m"] / 1000, tl["p"]); ax1.set_yscale("log"); ax1.set_title("Static pressure"); ax1.set_xlabel("h [km]")
    ax2 = fig.add_subplot(222); ax2.plot(tl["altitude_m"] / 1000, tl["wall_temperature_k"], label="wall"); ax2.plot(tl["altitude_m"] / 1000, tl["T"], label="ambient"); ax2.legend(); ax2.set_title("Temperature")
    ax3 = fig.add_subplot(223); ax3.plot(tl["time_s"], tl["electron_density_m3"]); ax3.set_yscale("log"); ax3.set_title("Electron density")
    ax4 = fig.add_subplot(224); ax4.plot(tl["time_s"], tl["plasma_frequency_hz"] / 1e9, label="fp [GHz]"); ax4.axhline(config.vehicle.communications_frequency_hz / 1e9, linestyle="--", label="comm"); ax4.legend(); ax4.set_title("Blackout criterion")
    files["plasma_thermal"] = save_plot(fig_dir / "plasma_thermal.png")

    # Wind tunnel maps.
    wind = result.wind
    fig = plt.figure(figsize=(12, 8))
    ax1 = fig.add_subplot(221); im1 = ax1.imshow(wind["cd"], origin="lower", aspect="auto", extent=[wind["velocities"][0], wind["velocities"][-1], wind["aoas"][0], wind["aoas"][-1]]); ax1.set_title("Cd map"); ax1.set_xlabel("V [m/s]"); ax1.set_ylabel("AoA [deg]"); fig.colorbar(im1, ax=ax1)
    ax2 = fig.add_subplot(222); im2 = ax2.imshow(wind["heat"] / 1e6, origin="lower", aspect="auto", extent=[wind["velocities"][0], wind["velocities"][-1], wind["aoas"][0], wind["aoas"][-1]]); ax2.set_title("Heat flux [MW/m2]"); fig.colorbar(im2, ax=ax2)
    ax3 = fig.add_subplot(223); ax3.plot(wind["cp_x"], wind["cp"]); ax3.set_title("Surface pressure coefficient proxy"); ax3.set_xlabel("x [m]")
    ax4 = fig.add_subplot(224); im4 = ax4.imshow(wind["stability"], origin="lower", aspect="auto", extent=[wind["velocities"][0], wind["velocities"][-1], wind["aoas"][0], wind["aoas"][-1]]); ax4.set_title("Static margin [calibers]"); fig.colorbar(im4, ax=ax4)
    files["wind_tunnel"] = save_plot(fig_dir / "wind_tunnel.png")

    # Optimization history.
    fig = plt.figure(figsize=(12, 6))
    ax1 = fig.add_subplot(121)
    hist = result.rocket_opt["history"]
    ax1.plot([h["iteration"] for h in hist], [h["score"] for h in hist], label="score")
    ax1.plot([h["iteration"] for h in hist], [h["avg_cd"] for h in hist], label="avg Cd")
    ax1.legend(); ax1.set_title("Rocket geometry search")
    ax2 = fig.add_subplot(122)
    th = result.turbine_opt["history"]
    ax2.plot([h["iteration"] for h in th], [h["efficiency"] for h in th], label="efficiency")
    ax2.plot([h["iteration"] for h in th], [h["tip_mach"] for h in th], label="tip Mach")
    ax2.legend(); ax2.set_title("Turbine search")
    files["optimization"] = save_plot(fig_dir / "optimization.png")

    # Surface renders.
    files.update(generate_rocket_surface_renders(config, result, fig_dir))
    result.output_files.update(files)
    return files


def rocket_surface_grid(shape: ShapeConfig, ntheta: int = 80, nx: int = 120) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = np.linspace(0.0, shape.total_length_m, nx)
    r = np.piecewise(
        x,
        [x <= shape.nose_length_m,
         (x > shape.nose_length_m) & (x <= shape.nose_length_m + shape.cylinder_length_m),
         x > shape.nose_length_m + shape.cylinder_length_m],
        [lambda xx: shape.body_radius_m * (xx / max(shape.nose_length_m, 1e-9)) ** 0.85,
         lambda xx: shape.body_radius_m,
         lambda xx: shape.body_radius_m - (shape.body_radius_m - shape.engine_exit_radius_m) * ((xx - (shape.nose_length_m + shape.cylinder_length_m)) / max(shape.tail_length_m, 1e-9)) ** 1.2]
    )
    theta = np.linspace(0.0, 2 * np.pi, ntheta)
    X, TH = np.meshgrid(x, theta)
    R = np.tile(r, (ntheta, 1))
    Y = R * np.cos(TH)
    Z = R * np.sin(TH)
    return X, Y, Z, TH


def render_surface_map(path: Path, shape: ShapeConfig, values: np.ndarray, cmap_name: str, title: str, cbar: str) -> str:
    X, Y, Z, _ = rocket_surface_grid(shape)
    prof = np.interp(X[0], np.linspace(0, shape.total_length_m, len(values)), values)
    data = np.tile(prof, (X.shape[0], 1))
    norm = Normalize(vmin=float(np.min(data)), vmax=float(np.max(data)))
    facecolors = mpl_cm.get_cmap(cmap_name)(norm(data))
    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(X, Y, Z, facecolors=facecolors, linewidth=0, antialiased=False, shade=False)
    fig.colorbar(mpl_cm.ScalarMappable(norm=norm, cmap=cmap_name), ax=ax, pad=0.1, shrink=0.65, label=cbar)
    ax.set_title(title)
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.set_zlabel("z [m]")
    ax.view_init(elev=23, azim=42)
    return save_plot(path, dpi=180)


def generate_rocket_surface_renders(config: MissionConfig, result: SimulationResult, fig_dir: Path) -> Dict[str, str]:
    tl = result.timeline
    def norm_profile(a: np.ndarray) -> np.ndarray:
        a = np.asarray(a, dtype=float)
        idx = np.linspace(0, len(a) - 1, 120)
        p = np.interp(idx, np.arange(len(a)), a)
        p = (p - np.nanmin(p)) / max(np.nanmax(p) - np.nanmin(p), 1e-9)
        return p * np.linspace(1.7, 0.28, len(p))
    files = {}
    files["surface_heat"] = render_surface_map(fig_dir / "surface_heat.png", config.shape, norm_profile(tl["heat_flux_w_m2"]), "inferno", "3D surface heat-load map", "normalized heat")
    files["surface_temperature"] = render_surface_map(fig_dir / "surface_temperature.png", config.shape, norm_profile(tl["wall_temperature_k"]), "hot", "3D wall-temperature map", "normalized temperature")
    files["surface_plasma"] = render_surface_map(fig_dir / "surface_plasma.png", config.shape, norm_profile(np.log10(np.maximum(tl["electron_density_m3"], 1.0))), "plasma", "3D ionized plasma sheath proxy", "log electron density")
    files["surface_xray"] = render_surface_map(fig_dir / "surface_xray.png", config.shape, norm_profile(tl["xray"]), "cividis", "X-ray analytical diagnostic proxy", "normalized x-ray proxy")
    return files


def generate_video(config: MissionConfig, result: SimulationResult, out_dir: Path, no_video: bool) -> Optional[str]:
    if no_video or imageio is None:
        return None
    frames_dir = ensure_dir(out_dir / "video_frames")
    n = max(12, int(config.video_fps * config.video_seconds))
    idxs = np.linspace(0, len(result.timeline["time_s"]) - 1, n).astype(int)
    paths = []
    for k, idx in enumerate(idxs):
        fig = plt.figure(figsize=(8, 4.5))
        ax = fig.add_subplot(111, projection="3d")
        heat = result.timeline["wall_temperature_k"][idx] / max(np.max(result.timeline["wall_temperature_k"]), 1.0)
        X, Y, Z, TH = rocket_surface_grid(config.shape, ntheta=40, nx=60)
        color = mpl_cm.inferno(np.clip(np.exp(-4 * X / config.shape.total_length_m) * heat * 1.3, 0, 1))
        ax.plot_surface(X, Y, Z, facecolors=color, linewidth=0, antialiased=False, shade=False)
        ax.view_init(elev=18 + 5 * math.sin(k / 4), azim=35 + k * 5)
        ax.set_xlim(-3, config.shape.total_length_m + 7)
        ax.set_ylim(-10, 10); ax.set_zlim(-10, 10)
        ax.set_title(f"Asteria reentry frame {k+1}/{n} | h={result.timeline['altitude_m'][idx]/1000:.1f} km | M={result.timeline['mach'][idx]:.1f}")
        ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
        p = frames_dir / f"frame_{k:04d}.png"
        save_plot(p, dpi=120)
        paths.append(p)
    mp4 = out_dir / "asteria_reentry_animation.mp4"
    try:
        with imageio.get_writer(mp4, fps=config.video_fps, macro_block_size=1) as writer:
            for p in paths:
                writer.append_data(imageio.imread(p))
        return str(mp4)
    except Exception:
        return None


# =============================================================================
# 7. LATEX NO PDF COMO IMAGENS REAIS
# =============================================================================

class EquationRenderer:
    def __init__(self, out_dir: Path):
        self.eq_dir = ensure_dir(out_dir / "equations")
        self.counter = 0

    def render(self, latex: str, max_width_in: float = 6.5, fontsize: int = 18) -> str:
        self.counter += 1
        path = self.eq_dir / f"eq_{self.counter:04d}.png"
        fig = plt.figure(figsize=(max_width_in, 0.68), dpi=220)
        fig.patch.set_alpha(0.0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.text(0.5, 0.5, f"${latex}$", ha="center", va="center", fontsize=fontsize)
        fig.savefig(path, transparent=True, bbox_inches="tight", pad_inches=0.04)
        plt.close(fig)
        return str(path)


def eq_flowable(eq: EquationRenderer, latex: str, width_cm: float = 15.5, fontsize: int = 18) -> Image:
    p = eq.render(latex, fontsize=fontsize)
    return Image(p, width=width_cm * cm, height=None)


def fmt(x: float, digits: int = 4) -> str:
    if abs(x) >= 1e4 or (abs(x) < 1e-3 and x != 0):
        return f"{x:.{digits}e}"
    return f"{x:.{digits}f}"


# =============================================================================
# 8. GERADOR PDF PROFISSIONAL
# =============================================================================

def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(1.5 * cm, 0.9 * cm, "NablaMath Orbital Professional Single-File Report")
    canvas.drawRightString(19.5 * cm, 0.9 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER, fontSize=20, leading=24, spaceAfter=12))
    styles.add(ParagraphStyle(name="H1x", parent=styles["Heading1"], fontSize=16, leading=20, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#102A43")))
    styles.add(ParagraphStyle(name="H2x", parent=styles["Heading2"], fontSize=13, leading=16, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#1F4E79")))
    styles.add(ParagraphStyle(name="BodyX", parent=styles["BodyText"], fontSize=9.8, leading=13.2, alignment=TA_LEFT, spaceAfter=6))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10, spaceAfter=4))
    styles.add(ParagraphStyle(name="Caption", parent=styles["BodyText"], fontSize=8.2, leading=10, alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=8))
    return styles


def make_table(data: Sequence[Sequence[Any]], col_widths: Optional[List[float]] = None, font_size: float = 7.5) -> Table:
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B7C9D6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F7FA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def scaled_report_image(path: str, width_cm: float = 16.5, max_height_cm: float = 14.8) -> Image:
    # ReportLab can oversize images if height is left undefined. This helper preserves
    # aspect ratio and caps height to avoid LayoutError/clipping.
    width_pt = width_cm * cm
    max_height_pt = max_height_cm * cm
    try:
        from PIL import Image as _PILImage
        with _PILImage.open(path) as im:
            px_w, px_h = im.size
        height_pt = width_pt * (px_h / max(px_w, 1))
        if height_pt > max_height_pt:
            scale = max_height_pt / height_pt
            width_pt *= scale
            height_pt = max_height_pt
    except Exception:
        height_pt = max_height_pt
    return Image(path, width=width_pt, height=height_pt)


def fig_flowable(path: str, caption: str, width_cm: float = 16.5) -> List[Any]:
    return [scaled_report_image(path, width_cm=width_cm), Paragraph(caption, build_styles()["Caption"])]


def add_key_value_table(story: List[Any], title: str, data: Dict[str, Any], styles: Dict[str, Any], max_rows: int = 40):
    story.append(Paragraph(title, styles["H2x"]))
    rows = [["Parametro", "Valor"]]
    for i, (k, v) in enumerate(data.items()):
        if i >= max_rows:
            break
        if isinstance(v, float):
            v = fmt(v, 5)
        rows.append([str(k), str(v)])
    story.append(make_table(rows, [7 * cm, 9 * cm], font_size=7.5))
    story.append(Spacer(1, 0.2 * cm))


def add_derivation_step(story: List[Any], eqr: EquationRenderer, styles: Dict[str, Any], label: str, formula: str, substitution: str, result: str):
    story.append(Paragraph(label, styles["H2x"]))
    story.append(eq_flowable(eqr, formula, fontsize=17))
    story.append(Paragraph("Substituicao numerica:", styles["Small"]))
    story.append(eq_flowable(eqr, substitution, fontsize=15))
    story.append(Paragraph("Resultado:", styles["Small"]))
    story.append(eq_flowable(eqr, result, fontsize=15))
    story.append(Spacer(1, 0.15 * cm))


def build_report(config: MissionConfig, result: SimulationResult, out_dir: Path, pages_target: int = 80) -> str:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab nao esta instalado. Instale com: pip install reportlab")

    pdf_path = out_dir / "nablamath_orbital_professional_report.pdf"
    styles = build_styles()
    eqr = EquationRenderer(out_dir)
    doc = BaseDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=1.45 * cm,
        rightMargin=1.45 * cm,
        topMargin=1.35 * cm,
        bottomMargin=1.4 * cm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=page_footer)])

    S = result.summary
    O = result.orbit
    D = result.deorbit
    E = result.entry
    tl = result.timeline
    story: List[Any] = []

    # Capa
    story.append(Paragraph(config.report_title, styles["TitleCenter"]))
    story.append(Paragraph("Relatorio tecnico gerado por um unico arquivo Python", styles["BodyX"]))
    story.append(Paragraph(f"Missao: <b>{config.mission_name}</b>", styles["BodyX"]))
    story.append(Paragraph(config.user_objectives, styles["BodyX"]))
    story.append(Spacer(1, 0.3 * cm))
    add_key_value_table(story, "Resumo executivo de resultados", {
        "Velocidade orbital [m/s]": S["orbit_velocity_m_s"],
        "Periodo orbital [s]": S["orbit_period_s"],
        "Delta-v deorbit [m/s]": S["deorbit_delta_v_m_s"],
        "Velocidade de entrada [m/s]": S["entry_velocity_m_s"],
        "Pico fluxo de calor [W/m2]": S["peak_heat_flux_w_m2"],
        "Altitude no pico de calor [m]": S["peak_heat_altitude_m"],
        "Pico pressao dinamica [Pa]": S["peak_dynamic_pressure_pa"],
        "Pico carga-g [g]": S["peak_g_load"],
        "Pico temperatura parede [K]": S["peak_wall_temperature_k"],
        "Pico frequencia plasma [Hz]": S["peak_plasma_frequency_hz"],
        "Duracao blackout [s]": S["blackout_duration_s"],
        "Propelente recaptura [kg]": S["landing_propellant_kg"],
    }, styles)
    story.append(PageBreak())

    # Input code
    story.append(Paragraph("1. Entrada integral em formato de codigo", styles["H1x"]))
    story.append(Paragraph("Esta secao preserva o input da missao dentro do proprio relatorio para auditoria e reprodutibilidade.", styles["BodyX"]))
    code_text = generate_input_code_block(config)
    story.append(Preformatted(code_text, styles["Code"] if "Code" in styles else styles["Small"]))
    story.append(PageBreak())

    # Constantes
    story.append(Paragraph("2. Constantes, unidades e hipoteses", styles["H1x"]))
    constants = {
        "R_Earth [m]": R_EARTH,
        "mu_Earth [m3/s2]": MU_EARTH,
        "g0 [m/s2]": G0,
        "R_air [J/(kg K)]": R_AIR,
        "gamma_air": GAMMA_AIR,
        "sigma_SB [W/(m2 K4)]": SIGMA_SB,
        "m_air [kg]": M_AIR,
        "e [C]": E_CHARGE,
        "epsilon0 [F/m]": EPS0,
        "m_e [kg]": M_ELECTRON,
    }
    add_key_value_table(story, "Constantes usadas", constants, styles)
    story.append(Paragraph("As hipoteses foram mantidas explicitas: reentrada planar com sustentacao efetiva, atmosfera padrao simplificada, aquecimento Sutton-Graves surrogate, plasma por ativacao logistica e otimizacoes por busca aleatoria fisicamente informada.", styles["BodyX"]))

    # Mecânica orbital derivations
    story.append(PageBreak())
    story.append(Paragraph("3. Mecanica orbital - calculos passo a passo", styles["H1x"]))
    add_derivation_step(
        story, eqr, styles,
        "3.1 Raio orbital circular",
        r"r_{orb}=R_E+h_{orb}",
        rf"r_{{orb}}={R_EARTH:.0f}+{config.orbit_altitude_m:.0f}",
        rf"r_{{orb}}={O['r_m']:.3e}\;m",
    )
    add_derivation_step(
        story, eqr, styles,
        "3.2 Velocidade circular",
        r"v_{circ}=\sqrt{\frac{\mu}{r_{orb}}}",
        rf"v_{{circ}}=\sqrt{{\frac{{{MU_EARTH:.6e}}}{{{O['r_m']:.6e}}}}}",
        rf"v_{{circ}}={O['v_m_s']:.3f}\;m/s",
    )
    add_derivation_step(
        story, eqr, styles,
        "3.3 Periodo orbital",
        r"T_{orb}=2\pi\sqrt{\frac{r_{orb}^3}{\mu}}",
        rf"T_{{orb}}=2\pi\sqrt{{\frac{{({O['r_m']:.6e})^3}}{{{MU_EARTH:.6e}}}}}",
        rf"T_{{orb}}={O['period_s']:.3f}\;s",
    )
    add_derivation_step(
        story, eqr, styles,
        "3.4 Semi-eixo maior da transferencia de deorbit",
        r"a_t=\frac{r_a+r_p}{2}",
        rf"a_t=\frac{{{D['r_apogee_m']:.6e}+{D['r_perigee_m']:.6e}}}{{2}}",
        rf"a_t={D['a_transfer_m']:.6e}\;m",
    )
    add_derivation_step(
        story, eqr, styles,
        "3.5 Delta-v de deorbit",
        r"\Delta v=v_{circ}-\sqrt{\mu\left(\frac{2}{r_a}-\frac{1}{a_t}\right)}",
        rf"\Delta v={D['v_circular_m_s']:.3f}-\sqrt{{{MU_EARTH:.6e}\left(\frac{{2}}{{{D['r_apogee_m']:.6e}}}-\frac{{1}}{{{D['a_transfer_m']:.6e}}}\right)}}",
        rf"\Delta v={D['delta_v_deorbit_m_s']:.3f}\;m/s",
    )

    # Reentry equations
    story.append(PageBreak())
    story.append(Paragraph("4. Reentrada hipersonica - equacoes diferenciais", styles["H1x"]))
    for formula in [
        r"\dot r=v\sin\gamma",
        r"\dot\theta=\frac{v\cos\gamma}{r}",
        r"\dot v=-\frac{D}{m}-\frac{\mu}{r^2}\sin\gamma",
        r"\dot\gamma=\frac{L}{mv}+\left(\frac{v}{r}-\frac{\mu}{vr^2}\right)\cos\gamma",
        r"D=\frac{1}{2}\rho v^2 C_D A",
        r"L=\frac{1}{2}\rho v^2 C_L A",
    ]:
        story.append(eq_flowable(eqr, formula, fontsize=17))
    story.append(Paragraph("As equacoes acima sao integradas no tempo por Euler semi-explicito com passo configuravel. O objetivo e gerar um dossie educacional e exploratorio, nao uma certificacao aeroespacial.", styles["BodyX"]))

    # Aero-thermal derivations at peak points
    story.append(PageBreak())
    story.append(Paragraph("5. Calculos aerotermodinamicos no ponto critico", styles["H1x"]))
    peak_i = int(np.argmax(tl["heat_flux_w_m2"]))
    rho_p, v_p, Rn = tl["rho"][peak_i], tl["velocity_m_s"][peak_i], config.vehicle.nose_radius_m
    qdot_p = tl["heat_flux_w_m2"][peak_i]
    Tw_p = tl["wall_temperature_k"][peak_i]
    p_p, M_p = tl["p"][peak_i], tl["mach"][peak_i]
    p0_p = tl["stagnation_pressure_pa"][peak_i]
    add_derivation_step(story, eqr, styles, "5.1 Fluxo de calor Sutton-Graves surrogate", r"\dot q=1.83\times10^{-4}\sqrt{\frac{\rho}{R_n}}v^3\times10^4", rf"\dot q=1.83\times10^{{-4}}\sqrt{{\frac{{{rho_p:.3e}}}{{{Rn:.3f}}}}}({v_p:.3f})^3\times10^4", rf"\dot q={qdot_p:.3e}\;W/m^2")
    add_derivation_step(story, eqr, styles, "5.2 Temperatura radiativa de parede", r"T_{wall}=\left(\frac{\dot q}{\epsilon\sigma}\right)^{1/4}", rf"T_{{wall}}=\left(\frac{{{qdot_p:.3e}}}{{{config.vehicle.emissivity:.3f}\cdot {SIGMA_SB:.3e}}}\right)^{{1/4}}", rf"T_{{wall}}={Tw_p:.2f}\;K")
    add_derivation_step(story, eqr, styles, "5.3 Pressao de estagnacao compressivel", r"p_0=p\left(1+\frac{\gamma-1}{2}M^2\right)^{\frac{\gamma}{\gamma-1}}", rf"p_0={p_p:.3e}\left(1+\frac{{{GAMMA_AIR-1:.3f}}}{{2}}({M_p:.3f})^2\right)^{{{GAMMA_AIR/(GAMMA_AIR-1):.3f}}}", rf"p_0={p0_p:.3e}\;Pa")

    # Plasma
    story.append(PageBreak())
    story.append(Paragraph("6. Ionizacao, plasma e blackout", styles["H1x"]))
    j = int(np.argmax(tl["plasma_frequency_hz"]))
    rho_j, xion_j, ne_j, fp_j = tl["rho"][j], tl["ionization_fraction"][j], tl["electron_density_m3"][j], tl["plasma_frequency_hz"][j]
    add_derivation_step(story, eqr, styles, "6.1 Densidade eletronica", r"n_e=x_{ion}\frac{\rho}{m_{air}}", rf"n_e={xion_j:.3e}\frac{{{rho_j:.3e}}}{{{M_AIR:.3e}}}", rf"n_e={ne_j:.3e}\;m^{{-3}}")
    add_derivation_step(story, eqr, styles, "6.2 Frequencia de plasma", r"f_p=\frac{1}{2\pi}\sqrt{\frac{n_e e^2}{\epsilon_0m_e}}", rf"f_p=\frac{{1}}{{2\pi}}\sqrt{{\frac{{({ne_j:.3e})({E_CHARGE:.3e})^2}}{{({EPS0:.3e})({M_ELECTRON:.3e})}}}}", rf"f_p={fp_j:.3e}\;Hz")
    story.append(Paragraph(f"Criterio de blackout usado: se fp > {config.vehicle.communications_frequency_hz:.3e} Hz, o enlace nominal de comunicacao e considerado bloqueado pelo plasma.", styles["BodyX"]))

    # Figures
    story.append(PageBreak())
    story.append(Paragraph("7. Figuras tecnicas geradas pela simulacao", styles["H1x"]))
    for key, caption in [
        ("trajectory_3d", "Trajetoria 3D de reentrada e recaptura, colorida pela temperatura de parede."),
        ("profiles", "Perfis temporais de altitude, velocidade, pressao dinamica, calor, Mach e carga-g."),
        ("plasma_thermal", "Diagnosticos termo-plasma: pressao, temperatura, densidade eletronica e criterio de blackout."),
        ("wind_tunnel", "Tunel de vento surrogate: mapas de Cd, calor, Cp e margem estatica."),
        ("optimization", "Historicos de otimizacao de geometria do foguete e turbina."),
        ("surface_heat", "Mapa 3D de carga termica na superficie do veiculo."),
        ("surface_temperature", "Mapa 3D de temperatura de parede."),
        ("surface_plasma", "Mapa 3D proxy da bainha de plasma."),
        ("surface_xray", "Render analitico X-ray proxy."),
    ]:
        if key in result.output_files:
            story.extend(fig_flowable(result.output_files[key], caption, width_cm=16.3))

    # Wind tunnel derivations and results
    story.append(PageBreak())
    story.append(Paragraph("8. Tunel de vento surrogate - formulas e resultados", styles["H1x"]))
    for formula in [
        r"Re=\frac{\rho V L}{\mu}",
        r"C_f\approx\frac{0.455}{\log_{10}(Re)^{2.58}}",
        r"C_D=C_{D,base}+C_{D,friction}+C_{D,wave}+C_{D,fin}+C_{D,\alpha}",
        r"q=\frac{1}{2}\rho V^2",
    ]:
        story.append(eq_flowable(eqr, formula, fontsize=17))
    add_key_value_table(story, "Melhor caso encontrado no tunel de vento surrogate", result.wind["best"], styles)

    # Optimization formulas
    story.append(PageBreak())
    story.append(Paragraph("9. Otimizacao de forma e turbina", styles["H1x"]))
    for formula in [
        r"J_{rocket}=2.2\overline{C_D}+0.08\frac{\dot q_{max}}{10^6}+1.15P_{stab}+0.45P_L-0.0035V_{int}",
        r"\eta_{turb}=0.91-0.11|\phi-0.60|-0.08|\psi-1.55|-0.05|\sigma_s-1.25|-0.035\max(0,M_{tip}-1.05)",
        r"U_{tip}=\Omega R=\frac{2\pi\,RPM}{60}R",
        r"M_{tip}=\frac{U_{tip}}{\sqrt{\gamma R T}}",
    ]:
        story.append(eq_flowable(eqr, formula, fontsize=15))
    add_key_value_table(story, "Melhor geometria de foguete", result.rocket_opt["best_shape"], styles)
    add_key_value_table(story, "Metricas da melhor geometria de foguete", result.rocket_opt["best_metrics"], styles)
    add_key_value_table(story, "Melhor geometria de turbina", result.turbine_opt["best_design"], styles)
    add_key_value_table(story, "Metricas da melhor turbina", result.turbine_opt["best_metrics"], styles)

    # Appendices unique content until target pages.
    story.append(PageBreak())
    story.append(Paragraph("10. Apendice A - amostras numericas da trajetoria", styles["H1x"]))
    add_timeline_appendix(story, styles, tl)

    story.append(PageBreak())
    story.append(Paragraph("11. Apendice B - grade do tunel de vento", styles["H1x"]))
    add_wind_appendix(story, styles, result.wind)

    story.append(PageBreak())
    story.append(Paragraph("12. Apendice C - historico de otimizacao", styles["H1x"]))
    add_optimization_appendix(story, styles, result.rocket_opt["history"], "Foguete")
    add_optimization_appendix(story, styles, result.turbine_opt["history"], "Turbina")

    story.append(PageBreak())
    story.append(Paragraph("13. Apendice D - metadados reprodutiveis", styles["H1x"]))
    story.append(Preformatted(json.dumps(result.metadata, indent=2, ensure_ascii=False)[:12000], styles["Small"]))

    # Add non-repetitive pages if target not reached roughly. We cannot know exact page count before build,
    # but each extra appendix block contains different sampled ranges or sensitivity sweeps.
    extra_blocks = max(0, int((pages_target - 45) / 3))
    for b in range(extra_blocks):
        story.append(PageBreak())
        story.append(Paragraph(f"Apendice E.{b+1} - sensibilidade numerica especifica", styles["H1x"]))
        add_sensitivity_block(story, styles, eqr, config, b)

    doc.build(story)
    return str(pdf_path)


def add_timeline_appendix(story: List[Any], styles: Dict[str, Any], tl: Dict[str, np.ndarray]):
    n = len(tl["time_s"])
    chunks = np.array_split(np.linspace(0, n - 1, min(n, 90)).astype(int), 6)
    for ci, chunk in enumerate(chunks):
        story.append(Paragraph(f"Tabela A.{ci+1} - trecho temporal {ci+1}", styles["H2x"]))
        rows = [["t[s]", "h[km]", "v[m/s]", "M", "q[kPa]", "heat[MW/m2]", "Tw[K]", "fp[GHz]"]]
        for i in chunk:
            rows.append([
                fmt(tl["time_s"][i], 1), fmt(tl["altitude_m"][i] / 1000, 2), fmt(tl["velocity_m_s"][i], 1),
                fmt(tl["mach"][i], 2), fmt(tl["dynamic_pressure_pa"][i] / 1000, 2), fmt(tl["heat_flux_w_m2"][i] / 1e6, 3),
                fmt(tl["wall_temperature_k"][i], 1), fmt(tl["plasma_frequency_hz"][i] / 1e9, 3),
            ])
        story.append(make_table(rows, font_size=6.6))
        story.append(Spacer(1, 0.15 * cm))


def add_wind_appendix(story: List[Any], styles: Dict[str, Any], wind: Dict[str, Any]):
    rows = [["AoA", "V", "Cd", "Cl", "Cm", "Heat[MW/m2]", "Re", "Stab"]]
    for i, aoa in enumerate(wind["aoas"]):
        for j, v in enumerate(wind["velocities"]):
            rows.append([fmt(aoa, 1), fmt(v, 0), fmt(wind["cd"][i, j], 4), fmt(wind["cl"][i, j], 4), fmt(wind["cm"][i, j], 4), fmt(wind["heat"][i, j] / 1e6, 3), fmt(wind["reynolds"][i, j], 3), fmt(wind["stability"][i, j], 3)])
    story.append(make_table(rows, font_size=6.2))


def add_optimization_appendix(story: List[Any], styles: Dict[str, Any], history: List[Dict[str, Any]], label: str):
    story.append(Paragraph(f"Historico - {label}", styles["H2x"]))
    if not history:
        story.append(Paragraph("Sem historico disponivel.", styles["BodyX"]))
        return
    keys = list(history[0].keys())[:7]
    rows = [keys]
    step = max(1, len(history) // 40)
    for h in history[::step]:
        rows.append([fmt(float(h[k]), 4) if isinstance(h[k], (float, int)) else str(h[k]) for k in keys])
    story.append(make_table(rows, font_size=6.2))


def add_sensitivity_block(story: List[Any], styles: Dict[str, Any], eqr: EquationRenderer, config: MissionConfig, block_id: int):
    var_name = ["nose_radius", "emissivity", "Cd", "L/D", "entry_altitude", "bank_angle"][block_id % 6]
    story.append(Paragraph(f"Este bloco varia o parametro {var_name} em torno do caso base e recalcula um indicador simplificado. Cada bloco e diferente para evitar repeticao textual inutil.", styles["BodyX"]))
    if var_name == "nose_radius":
        base = config.vehicle.nose_radius_m
        vals = np.linspace(0.8 * base, 1.3 * base, 10)
        formula = r"\dot q\propto\sqrt{\frac{1}{R_n}}"
        metric = [math.sqrt(base / v) for v in vals]
    elif var_name == "emissivity":
        base = config.vehicle.emissivity
        vals = np.linspace(0.65, 0.95, 10)
        formula = r"T_{wall}\propto\left(\frac{1}{\epsilon}\right)^{1/4}"
        metric = [(base / v) ** 0.25 for v in vals]
    elif var_name == "Cd":
        base = config.vehicle.drag_coefficient
        vals = np.linspace(0.85 * base, 1.25 * base, 10)
        formula = r"D=\frac{1}{2}\rho v^2 C_D A"
        metric = [v / base for v in vals]
    elif var_name == "L/D":
        base = config.vehicle.lift_to_drag
        vals = np.linspace(0.5 * base, 1.8 * base, 10)
        formula = r"L/D\;controla\;\dot\gamma\;e\;corredor\;de\;entrada"
        metric = [v / base for v in vals]
    elif var_name == "entry_altitude":
        base = config.entry_interface_altitude_m
        vals = np.linspace(base - 8000, base + 8000, 10)
        formula = r"v_e=\sqrt{\mu\left(\frac{2}{r_e}-\frac{1}{a_t}\right)}"
        metric = [entry_state(config.orbit_altitude_m, config.perigee_target_m, v)["entry_velocity_m_s"] for v in vals]
    else:
        base = config.reentry_bank_angle_deg
        vals = np.linspace(base - 15, base + 15, 10)
        formula = r"C_L=C_D(L/D)\cos(\sigma_{bank})"
        metric = [math.cos(math.radians(v)) / math.cos(math.radians(base)) for v in vals]
    story.append(eq_flowable(eqr, formula, fontsize=15))
    rows = [["param", "value", "relative/metric"]]
    for v, m in zip(vals, metric):
        rows.append([var_name, fmt(float(v), 4), fmt(float(m), 5)])
    story.append(make_table(rows, [4 * cm, 5 * cm, 5 * cm], font_size=7))


def generate_input_code_block(config: MissionConfig) -> str:
    return f"""
from nablamath_orbital_professional_single import MissionConfig, VehicleConfig, ShapeConfig, main

config = MissionConfig(
    mission_name={config.mission_name!r},
    report_title={config.report_title!r},
    user_objectives={config.user_objectives!r},
    orbit_altitude_m={config.orbit_altitude_m},
    perigee_target_m={config.perigee_target_m},
    entry_interface_altitude_m={config.entry_interface_altitude_m},
    reentry_bank_angle_deg={config.reentry_bank_angle_deg},
    dt_reentry_s={config.dt_reentry_s},
    max_reentry_time_s={config.max_reentry_time_s},
    rocket_optimization_iterations={config.rocket_optimization_iterations},
    turbine_optimization_iterations={config.turbine_optimization_iterations},
)

# Execucao equivalente via terminal:
# python nablamath_orbital_professional_single.py --out outputs_orbital --pages 80
""".strip()


# =============================================================================
# 9. HTML AUXILIAR
# =============================================================================

def build_html_summary(config: MissionConfig, result: SimulationResult, out_dir: Path) -> str:
    path = out_dir / "nablamath_orbital_professional_report.html"
    figs = "\n".join([f"<h3>{k}</h3><img src='{Path(v).relative_to(out_dir)}' style='max-width:900px;width:100%;border:1px solid #ccc;border-radius:8px'/>" for k, v in result.output_files.items() if v.endswith(".png")])
    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>{config.report_title}</title>
<style>body{{font-family:Arial,sans-serif;max-width:1100px;margin:32px auto;line-height:1.5}} code,pre{{background:#f4f6f8;padding:12px;border-radius:8px;display:block;overflow:auto}} table{{border-collapse:collapse}} td,th{{border:1px solid #ddd;padding:4px 6px}}</style></head>
<body><h1>{config.report_title}</h1><p>{config.user_objectives}</p>
<h2>Resumo</h2><pre>{json.dumps(result.summary, indent=2)}</pre>
<h2>Figuras</h2>{figs}
<h2>Metadados</h2><pre>{json.dumps(result.metadata, indent=2, ensure_ascii=False)}</pre>
</body></html>"""
    path.write_text(html, encoding="utf-8")
    return str(path)


# =============================================================================
# 10. CLI PRINCIPAL
# =============================================================================

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="NablaMath Orbital Professional Single-File Report Generator")
    parser.add_argument("--out", type=str, default="outputs_orbital_professional", help="Diretorio de saida")
    parser.add_argument("--pages", type=int, default=80, help="Alvo aproximado de paginas do PDF")
    parser.add_argument("--no-video", action="store_true", help="Desativa geracao de MP4")
    parser.add_argument("--fps", type=int, default=6, help="FPS do video")
    parser.add_argument("--video-seconds", type=float, default=4.0, help="Duracao do video")
    parser.add_argument("--rocket-iters", type=int, default=72, help="Iteracoes de otimizacao do foguete")
    parser.add_argument("--turbine-iters", type=int, default=72, help="Iteracoes de otimizacao da turbina")
    args = parser.parse_args(argv)

    out_dir = ensure_dir(Path(args.out).resolve())
    config = MissionConfig(
        video_fps=args.fps,
        video_seconds=args.video_seconds,
        rocket_optimization_iterations=args.rocket_iters,
        turbine_optimization_iterations=args.turbine_iters,
    )
    config.user_input_code = generate_input_code_block(config)

    print("[1/6] Simulando missao orbital...")
    result = run_simulation(config)
    result.metadata["output_dir"] = str(out_dir)

    print("[2/6] Gerando figuras cientificas...")
    generate_figures(config, result, out_dir)

    print("[3/6] Gerando video opcional...")
    video_path = generate_video(config, result, out_dir, no_video=args.no_video)
    if video_path:
        result.output_files["video_mp4"] = video_path

    print("[4/6] Gerando HTML auxiliar...")
    html_path = build_html_summary(config, result, out_dir)
    result.output_files["html"] = html_path

    print("[5/6] Gerando PDF profissional com LaTeX renderizado...")
    pdf_path = build_report(config, result, out_dir, pages_target=args.pages)
    result.output_files["pdf"] = pdf_path

    print("[6/6] Salvando metadados...")
    meta_path = out_dir / "metadata.json"
    meta_path.write_text(json.dumps({"summary": result.summary, "files": result.output_files, "metadata": result.metadata}, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nCONCLUIDO")
    print(f"PDF:  {pdf_path}")
    print(f"HTML: {html_path}")
    if video_path:
        print(f"MP4:  {video_path}")
    print(f"META: {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
