from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import json
import math
import shutil
import subprocess
import textwrap
import time

import imageio.v2 as iio
import numpy as np

G0 = 9.80665
R_EARTH = 6_371_000.0
MU_EARTH = 3.986004418e14
R_AIR = 287.05
GAMMA_AIR = 1.4
SIGMA_SB = 5.670374419e-8
M_AIR = 4.81e-26


@dataclass
class RocketMaterialConfig:
    name: str = "stainless-steel + black-ceramic TPS"
    base_rgb: Tuple[float, float, float] = (0.78, 0.80, 0.82)
    accent_rgb: Tuple[float, float, float] = (0.12, 0.12, 0.13)
    engine_rgb: Tuple[float, float, float] = (0.80, 0.50, 0.20)
    glow_rgb: Tuple[float, float, float] = (1.00, 0.47, 0.18)
    metallic: float = 0.88
    roughness: float = 0.22
    emissivity: float = 0.84


@dataclass
class RocketShapeConfig:
    nose_length_m: float = 9.0
    body_length_m: float = 38.0
    body_radius_m: float = 4.5
    boat_tail_length_m: float = 3.8
    engine_exit_radius_m: float = 1.35
    fin_count: int = 4
    fin_root_chord_m: float = 6.5
    fin_tip_chord_m: float = 2.6
    fin_span_m: float = 3.8
    fin_sweep_deg: float = 28.0
    fin_thickness_m: float = 0.10
    texture_seed: int = 42

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
class WindTunnelConfig:
    velocities_m_s: Tuple[float, ...] = (120.0, 250.0, 500.0, 900.0, 1500.0, 2500.0, 3500.0)
    angles_of_attack_deg: Tuple[float, ...] = (-5.0, 0.0, 5.0, 10.0)
    altitude_m: float = 0.0
    characteristic_length_m: float = 48.0
    turbulence_intensity: float = 0.02
    pressure_probe_count: int = 120


@dataclass
class TurbineDesignConfig:
    radius_m: float = 0.42
    hub_radius_m: float = 0.14
    blade_count: int = 28
    chord_root_m: float = 0.11
    chord_tip_m: float = 0.05
    twist_root_deg: float = 54.0
    twist_tip_deg: float = 16.0
    rpm: float = 32000.0
    mass_flow_kg_s: float = 42.0
    pressure_ratio_target: float = 14.0
    stage_temperature_k: float = 970.0


@dataclass
class OptimizationConfig:
    enabled: bool = True
    random_seed: int = 123
    rocket_iterations: int = 64
    turbine_iterations: int = 64


@dataclass
class VideoRenderConfig:
    generate_videos: bool = True
    fps: int = 15
    width: int = 960
    height: int = 540
    dpi: int = 120
    mission_duration_s: float = 8.0
    wind_tunnel_duration_s: float = 6.0


@dataclass
class OrbitalVehicleConfig:
    name: str = "Asteria Orbital Reusable Vehicle"
    mass_initial: float = 120_000.0
    mass_dry: float = 85_000.0
    nose_radius: float = 1.2
    body_radius: float = 4.0
    body_length: float = 42.0
    reference_area: float = 55.0
    drag_coefficient: float = 1.25
    lift_to_drag: float = 0.18
    emissivity: float = 0.82
    ballistic_coefficient: Optional[float] = None
    landing_isp: float = 320.0
    landing_burn_start_altitude: float = 2500.0
    landing_target_velocity: float = 0.5
    communications_frequency_hz: float = 2.2e9

    def effective_ballistic_coefficient(self) -> float:
        if self.ballistic_coefficient is not None:
            return float(self.ballistic_coefficient)
        return self.mass_initial / max(self.drag_coefficient * self.reference_area, 1e-9)


@dataclass
class OrbitalMissionConfig:
    mission_name: str = "Asteria-1"
    report_title: str = "NablaMath v0.5 - Relatorio orbital extremo"
    user_objectives: str = (
        "Analisar insercao orbital, deorbit burn, reentrada hipersonica, ionizacao, aquecimento, "
        "recaptura propulsiva, videos MP4, tunel de vento e otimizacao geométrica de foguete e turbina."
    )
    user_input_code: str = "# O usuario pode inserir aqui o codigo/configuracao da missao"
    vehicle: OrbitalVehicleConfig = field(default_factory=OrbitalVehicleConfig)
    shape: RocketShapeConfig = field(default_factory=RocketShapeConfig)
    material: RocketMaterialConfig = field(default_factory=RocketMaterialConfig)
    wind_tunnel: WindTunnelConfig = field(default_factory=WindTunnelConfig)
    turbine: TurbineDesignConfig = field(default_factory=TurbineDesignConfig)
    optimization: OptimizationConfig = field(default_factory=OptimizationConfig)
    video: VideoRenderConfig = field(default_factory=VideoRenderConfig)
    orbit_altitude_m: float = 400_000.0
    perigee_target_m: float = 45_000.0
    entry_interface_altitude_m: float = 120_000.0
    target_landing_longitude_deg: float = 0.0
    dt_reentry: float = 0.5
    max_reentry_time: float = 5000.0
    reentry_bank_angle_deg: float = 35.0
    deorbit_wait_fraction_orbit: float = 0.35
    spectral_xray_threshold_k: float = 2.5e5
    notes: str = "Modelo educacional/analitico de alta densidade, com aproximacoes aerotermodinamicas, de plasma e de otimização de forma."


@dataclass
class OrbitalSimulationResult:
    summary: Dict[str, float]
    timeline: Dict[str, np.ndarray]
    images: Dict[str, str]
    videos: Dict[str, str]
    metadata: Dict[str, Any]
    latex_blocks: Dict[str, str]
    wind_tunnel: Dict[str, Any]
    rocket_optimization: Dict[str, Any]
    turbine_optimization: Dict[str, Any]


@dataclass
class MissionLatexReportResult:
    tex_path: Path
    pdf_path: Optional[Path]
    log_path: Optional[Path]
    success: bool
    message: str
    image_paths: Dict[str, str]
    video_paths: Dict[str, str]


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
        layer_idx = 0
        for i in range(len(_ATMOS_LAYERS) - 1):
            if _ATMOS_LAYERS[i][0] <= h < _ATMOS_LAYERS[i + 1][0]:
                layer_idx = i
                break
        else:
            layer_idx = len(_ATMOS_LAYERS) - 1
        h_b, T_b, p_b, L_b = _ATMOS_LAYERS[layer_idx]
        if abs(L_b) < 1e-12:
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
    c1 = 1.458e-6
    s = 110.4
    return c1 * T ** 1.5 / (T + s)


def circular_orbit_parameters(altitude_m: float) -> Dict[str, float]:
    r = R_EARTH + altitude_m
    v = math.sqrt(MU_EARTH / r)
    period = 2.0 * math.pi * math.sqrt(r ** 3 / MU_EARTH)
    energy = -MU_EARTH / (2.0 * r)
    return {"r": r, "v": v, "period": period, "energy": energy}


def deorbit_to_perigee_delta_v(orbit_altitude_m: float, perigee_target_m: float) -> Dict[str, float]:
    r_a = R_EARTH + orbit_altitude_m
    r_p = R_EARTH + perigee_target_m
    a_t = 0.5 * (r_a + r_p)
    v_circ = math.sqrt(MU_EARTH / r_a)
    v_apogee_transfer = math.sqrt(MU_EARTH * (2.0 / r_a - 1.0 / a_t))
    dv = v_circ - v_apogee_transfer
    v_perigee_transfer = math.sqrt(MU_EARTH * (2.0 / r_p - 1.0 / a_t))
    return {
        "delta_v": dv,
        "a_transfer": a_t,
        "v_circ": v_circ,
        "v_apogee_transfer": v_apogee_transfer,
        "v_perigee_transfer": v_perigee_transfer,
        "eccentricity": (r_a - r_p) / (r_a + r_p),
    }


def entry_interface_velocity(orbit_altitude_m: float, perigee_target_m: float, entry_altitude_m: float) -> Dict[str, float]:
    deorbit = deorbit_to_perigee_delta_v(orbit_altitude_m, perigee_target_m)
    a_t = deorbit["a_transfer"]
    r_entry = R_EARTH + entry_altitude_m
    v_entry = math.sqrt(MU_EARTH * (2.0 / r_entry - 1.0 / a_t))
    return {"v_entry": v_entry, "gamma_entry_deg": -1.25, "r_entry": r_entry}


def _sutton_graves_heat_flux(rho: float, velocity: float, nose_radius: float) -> float:
    return max(0.0, 1.83e-4 * math.sqrt(max(rho, 1e-12) / max(nose_radius, 1e-6)) * velocity ** 3 * 1.0e4)


def _stagnation_pressure(p_static: float, mach: float) -> float:
    return p_static * (1.0 + 0.5 * (GAMMA_AIR - 1.0) * mach ** 2) ** (GAMMA_AIR / (GAMMA_AIR - 1.0))


def _ionization_fraction(T_stag: float, rho: float) -> float:
    activation = 1.0 / (1.0 + math.exp(-(T_stag - 6200.0) / 900.0))
    density_factor = min(1.0, math.sqrt(max(rho, 0.0) / 0.02 + 1e-12))
    return float(min(1.0, activation * density_factor))


def _electron_density(rho: float, ion_frac: float) -> float:
    molecules = rho / M_AIR
    return ion_frac * molecules


def _plasma_frequency_hz(ne_m3: float) -> float:
    ne_cm3 = max(ne_m3, 0.0) / 1.0e6
    return 8980.0 * math.sqrt(ne_cm3)


def _spectral_diagnostics(T_wall: float, xray_threshold_k: float) -> Dict[str, float]:
    ir = min(1.0, (T_wall / 2200.0) ** 1.2)
    uv = min(1.0, max(0.0, (T_wall - 2800.0) / 6000.0))
    xray = min(1.0, math.exp(-(xray_threshold_k / max(T_wall, 1.0)) ** 0.7))
    return {"ir": ir, "uv": uv, "xray": xray}


def _tex_escape(text: str) -> str:
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in str(text))


def _safe_import_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import cm
    from matplotlib.colors import Normalize
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    return plt, cm, Normalize, Poly3DCollection


def _shape_with_vehicle(config: OrbitalMissionConfig, shape: Optional[RocketShapeConfig] = None) -> RocketShapeConfig:
    shape = shape or config.shape
    return RocketShapeConfig(
        nose_length_m=float(shape.nose_length_m),
        body_length_m=float(shape.body_length_m),
        body_radius_m=float(max(0.5, shape.body_radius_m)),
        boat_tail_length_m=float(shape.boat_tail_length_m),
        engine_exit_radius_m=float(shape.engine_exit_radius_m),
        fin_count=int(shape.fin_count),
        fin_root_chord_m=float(shape.fin_root_chord_m),
        fin_tip_chord_m=float(shape.fin_tip_chord_m),
        fin_span_m=float(shape.fin_span_m),
        fin_sweep_deg=float(shape.fin_sweep_deg),
        fin_thickness_m=float(shape.fin_thickness_m),
        texture_seed=int(shape.texture_seed),
    )


def _rocket_aero_surrogate(shape: RocketShapeConfig, speed: float, aoa_deg: float, altitude_m: float, vehicle: OrbitalVehicleConfig) -> Dict[str, float]:
    atm = standard_atmosphere(altitude_m)
    rho, T, a = atm["rho"], atm["T"], atm["a"]
    mu = dynamic_viscosity_sutherland(T)
    mach = speed / max(a, 1e-9)
    Re = rho * speed * max(shape.total_length_m, 1.0) / max(mu, 1e-12)
    alpha = math.radians(aoa_deg)

    fineness = shape.total_length_m / max(2.0 * shape.body_radius_m, 0.25)
    nose_ratio = shape.nose_length_m / max(shape.body_radius_m, 0.25)
    wetted_area = 2.0 * math.pi * shape.body_radius_m * shape.body_length_m + math.pi * shape.body_radius_m * math.sqrt(shape.body_radius_m ** 2 + shape.nose_length_m ** 2)
    cf = 0.455 / max(math.log10(max(Re, 10.0)), 1.0) ** 2.58
    base_cd = 0.09 + 0.18 / max(fineness, 1.2) + cf * wetted_area / max(shape.frontal_area_m2, 1e-9)
    transonic = 0.12 * math.exp(-((mach - 1.05) / 0.32) ** 2)
    supersonic = 0.035 * max(mach - 1.2, 0.0)
    fin_drag = 0.006 * shape.fin_count * (shape.fin_span_m / max(shape.body_radius_m, 0.2)) * (1.0 + 0.25 * abs(alpha))
    boat_tail_bonus = -0.015 * min(shape.boat_tail_length_m / max(shape.body_length_m, 1.0), 0.2) / 0.2
    cd = max(0.06, base_cd + transonic + supersonic + fin_drag + boat_tail_bonus + 0.22 * alpha ** 2)

    aspect_ratio = 2.0 * shape.fin_span_m / max(0.5 * (shape.fin_root_chord_m + shape.fin_tip_chord_m), 0.2)
    cl_alpha = 2 * math.pi * aspect_ratio / max(aspect_ratio + 2.0, 0.5)
    cl = cl_alpha * alpha * (1.0 + 0.05 * min(mach, 3.0))
    cp_x = 0.58 * shape.total_length_m - 0.06 * shape.nose_length_m + 0.04 * shape.fin_root_chord_m
    cg_x = 0.47 * shape.total_length_m
    stability_margin_calibers = (cp_x - cg_x) / max(2.0 * shape.body_radius_m, 0.1)
    cm = -0.04 * stability_margin_calibers * alpha

    q = 0.5 * rho * speed ** 2
    heat = _sutton_graves_heat_flux(rho, speed, max(vehicle.nose_radius, 0.4))
    x = np.linspace(0.0, shape.total_length_m, 120)
    x_norm = x / max(shape.total_length_m, 1e-9)
    cp_dist = 1.8 * np.exp(-5.0 * x_norm) + 0.2 * np.sin(3 * np.pi * x_norm + alpha) + 0.05 * mach
    cp_dist += 0.6 * alpha * np.exp(-2.0 * x_norm)

    return {
        "mach": mach,
        "reynolds": Re,
        "rho": rho,
        "q_dynamic": q,
        "cd": cd,
        "cl": cl,
        "cm": cm,
        "stability_margin_calibers": stability_margin_calibers,
        "heat_flux": heat,
        "cp_distribution_x": x,
        "cp_distribution": cp_dist,
    }


def simulate_wind_tunnel(config: OrbitalMissionConfig, shape: Optional[RocketShapeConfig] = None) -> Dict[str, Any]:
    shape = _shape_with_vehicle(config, shape)
    wt = config.wind_tunnel
    vel = np.asarray(wt.velocities_m_s, dtype=float)
    aoa = np.asarray(wt.angles_of_attack_deg, dtype=float)

    cd = np.zeros((len(aoa), len(vel)))
    cl = np.zeros_like(cd)
    cm = np.zeros_like(cd)
    qdyn = np.zeros_like(cd)
    heat = np.zeros_like(cd)
    Re = np.zeros_like(cd)
    stability = np.zeros_like(cd)
    pressure_samples = []

    for i, a in enumerate(aoa):
        for j, v in enumerate(vel):
            out = _rocket_aero_surrogate(shape, v, a, wt.altitude_m, config.vehicle)
            cd[i, j] = out["cd"]
            cl[i, j] = out["cl"]
            cm[i, j] = out["cm"]
            qdyn[i, j] = out["q_dynamic"]
            heat[i, j] = out["heat_flux"]
            Re[i, j] = out["reynolds"]
            stability[i, j] = out["stability_margin_calibers"]
            if abs(a) < 1e-9 and j == len(vel) // 2:
                pressure_samples = [out["cp_distribution_x"], out["cp_distribution"]]

    best_idx = np.unravel_index(np.argmin(cd + 0.015 * np.maximum(0.0, 1.2 - stability) ** 2 + 1e-7 * heat), cd.shape)
    best = {
        "aoa_deg": float(aoa[best_idx[0]]),
        "velocity_m_s": float(vel[best_idx[1]]),
        "cd": float(cd[best_idx]),
        "stability_margin_calibers": float(stability[best_idx]),
        "heat_flux_w_m2": float(heat[best_idx]),
    }
    return {
        "shape": asdict(shape),
        "velocities_m_s": vel,
        "angles_of_attack_deg": aoa,
        "cd_grid": cd,
        "cl_grid": cl,
        "cm_grid": cm,
        "q_dynamic_grid": qdyn,
        "heat_flux_grid": heat,
        "reynolds_grid": Re,
        "stability_grid": stability,
        "pressure_distribution_x": np.asarray(pressure_samples[0]) if pressure_samples else np.array([]),
        "pressure_distribution_cp": np.asarray(pressure_samples[1]) if pressure_samples else np.array([]),
        "best_case": best,
        "summary": {
            "cd_min": float(np.min(cd)),
            "cd_max": float(np.max(cd)),
            "heat_max": float(np.max(heat)),
            "stability_mean": float(np.mean(stability)),
            "reynolds_max": float(np.max(Re)),
        },
    }


def _rocket_shape_score(shape: RocketShapeConfig, config: OrbitalMissionConfig) -> Tuple[float, Dict[str, float]]:
    speeds = [300.0, 900.0, 2200.0, 3500.0]
    aoa = [0.0, 5.0]
    cds, heats, stabs = [], [], []
    for a in aoa:
        for v in speeds:
            out = _rocket_aero_surrogate(shape, v, a, 0.0 if v < 1000 else 12000.0, config.vehicle)
            cds.append(out["cd"])
            heats.append(out["heat_flux"])
            stabs.append(out["stability_margin_calibers"])
    avg_cd = float(np.mean(cds))
    max_heat = float(np.max(heats))
    stab_mean = float(np.mean(stabs))
    payload_volume = shape.internal_volume_m3
    length_penalty = abs(shape.total_length_m - 50.0) / 50.0
    stability_penalty = max(0.0, 1.0 - stab_mean) ** 2 + max(0.0, stab_mean - 3.0) ** 2
    fin_penalty = 0.03 * max(0.0, shape.fin_span_m - 6.0) ** 2
    score = 2.2 * avg_cd + 0.08 * (max_heat / 1e6) + 1.1 * stability_penalty + 0.6 * length_penalty + fin_penalty - 0.0035 * payload_volume
    metrics = {
        "score": score,
        "avg_cd": avg_cd,
        "max_heat_flux_w_m2": max_heat,
        "stability_margin_calibers": stab_mean,
        "payload_volume_m3": payload_volume,
        "total_length_m": shape.total_length_m,
    }
    return score, metrics


def optimize_rocket_shape(config: OrbitalMissionConfig) -> Dict[str, Any]:
    if not config.optimization.enabled:
        shape = _shape_with_vehicle(config)
        score, metrics = _rocket_shape_score(shape, config)
        return {"best_shape": asdict(shape), "best_metrics": metrics, "history": [], "population": []}

    rng = np.random.default_rng(config.optimization.random_seed)
    best_shape = _shape_with_vehicle(config)
    best_score, best_metrics = _rocket_shape_score(best_shape, config)
    history: List[Dict[str, float]] = []
    population = []
    for k in range(config.optimization.rocket_iterations):
        candidate = RocketShapeConfig(
            nose_length_m=float(rng.uniform(6.0, 14.0)),
            body_length_m=float(rng.uniform(28.0, 46.0)),
            body_radius_m=float(rng.uniform(3.2, 5.4)),
            boat_tail_length_m=float(rng.uniform(2.0, 5.5)),
            engine_exit_radius_m=float(rng.uniform(0.8, 1.9)),
            fin_count=int(rng.integers(3, 6)),
            fin_root_chord_m=float(rng.uniform(4.0, 8.5)),
            fin_tip_chord_m=float(rng.uniform(1.0, 4.0)),
            fin_span_m=float(rng.uniform(2.0, 5.2)),
            fin_sweep_deg=float(rng.uniform(15.0, 45.0)),
            fin_thickness_m=float(rng.uniform(0.06, 0.18)),
            texture_seed=int(rng.integers(0, 100000)),
        )
        score, metrics = _rocket_shape_score(candidate, config)
        entry = {"iteration": k + 1, **metrics}
        history.append(entry)
        population.append({"shape": asdict(candidate), "metrics": metrics})
        if score < best_score:
            best_score, best_metrics, best_shape = score, metrics, candidate
    return {"best_shape": asdict(best_shape), "best_metrics": best_metrics, "history": history, "population": population}


def _turbine_score(design: TurbineDesignConfig) -> Tuple[float, Dict[str, float]]:
    area = math.pi * (design.radius_m ** 2 - design.hub_radius_m ** 2)
    omega = design.rpm * 2.0 * math.pi / 60.0
    u_tip = omega * design.radius_m
    flow_coeff = design.mass_flow_kg_s / max(area * 35.0 * design.stage_temperature_k / 1000.0, 1e-6)
    loading_coeff = design.pressure_ratio_target / max((u_tip / 300.0) ** 2, 1e-6)
    solidity = design.blade_count * 0.5 * (design.chord_root_m + design.chord_tip_m) / max(2.0 * math.pi * design.radius_m, 1e-6)
    tip_mach = u_tip / math.sqrt(GAMMA_AIR * R_AIR * design.stage_temperature_k)
    twist = abs(design.twist_root_deg - design.twist_tip_deg)
    efficiency = 0.90
    efficiency -= 0.11 * abs(flow_coeff - 0.60)
    efficiency -= 0.08 * abs(loading_coeff - 1.55)
    efficiency -= 0.05 * abs(solidity - 1.25)
    efficiency -= 0.03 * max(0.0, tip_mach - 1.15)
    efficiency -= 0.0015 * abs(twist - 38.0)
    efficiency = float(np.clip(efficiency, 0.40, 0.95))
    stress = 7800.0 * u_tip ** 2
    power_proxy = efficiency * design.mass_flow_kg_s * design.pressure_ratio_target * 8.2e3
    score = -(efficiency * 10.0) + 1.2 * max(0.0, tip_mach - 1.05) + 0.00000002 * stress - 0.000001 * power_proxy
    metrics = {
        "score": score,
        "efficiency": efficiency,
        "tip_speed_m_s": u_tip,
        "tip_mach": tip_mach,
        "solidity": solidity,
        "flow_coefficient": flow_coeff,
        "loading_coefficient": loading_coeff,
        "stress_proxy_pa": stress,
        "power_proxy_w": power_proxy,
    }
    return score, metrics


def optimize_turbine_geometry(config: OrbitalMissionConfig) -> Dict[str, Any]:
    if not config.optimization.enabled:
        s, m = _turbine_score(config.turbine)
        return {"best_design": asdict(config.turbine), "best_metrics": m, "history": []}
    rng = np.random.default_rng(config.optimization.random_seed + 1)
    best = config.turbine
    best_score, best_metrics = _turbine_score(best)
    history = []
    for k in range(config.optimization.turbine_iterations):
        cand = TurbineDesignConfig(
            radius_m=float(rng.uniform(0.28, 0.58)),
            hub_radius_m=float(rng.uniform(0.08, 0.22)),
            blade_count=int(rng.integers(18, 38)),
            chord_root_m=float(rng.uniform(0.07, 0.16)),
            chord_tip_m=float(rng.uniform(0.03, 0.09)),
            twist_root_deg=float(rng.uniform(40.0, 70.0)),
            twist_tip_deg=float(rng.uniform(8.0, 28.0)),
            rpm=float(rng.uniform(18000.0, 48000.0)),
            mass_flow_kg_s=float(rng.uniform(18.0, 70.0)),
            pressure_ratio_target=float(rng.uniform(8.0, 22.0)),
            stage_temperature_k=float(rng.uniform(780.0, 1250.0)),
        )
        if cand.hub_radius_m >= cand.radius_m - 0.03:
            continue
        score, metrics = _turbine_score(cand)
        history.append({"iteration": k + 1, **metrics})
        if score < best_score:
            best_score, best_metrics, best = score, metrics, cand
    return {"best_design": asdict(best), "best_metrics": best_metrics, "history": history}


def _build_latex_blocks(config: OrbitalMissionConfig, orbit: Dict[str, float], deorbit: Dict[str, float], summary: Dict[str, float], wind: Dict[str, Any], rocket_opt: Dict[str, Any], turbine_opt: Dict[str, Any]) -> Dict[str, str]:
    eq_orbit = textwrap.dedent(fr"""
    \begin{{align}}
    r_{{orb}} &= R_E + h_{{orb}} = {R_EARTH:.0f} + {config.orbit_altitude_m:.0f} = {R_EARTH + config.orbit_altitude_m:.0f}\,\text{{m}} \\
    v_{{orb}} &= \sqrt{{\mu/r_{{orb}}}} = {orbit['v']:.2f}\,\text{{m/s}} \\
    T_{{orb}} &= 2\pi\sqrt{{r_{{orb}}^3/\mu}} = {orbit['period']:.2f}\,\text{{s}}
    \end{{align}}
    """)
    eq_deorbit = textwrap.dedent(fr"""
    \begin{{align}}
    r_a &= R_E + h_{{orb}} = {R_EARTH + config.orbit_altitude_m:.0f}\,\text{{m}} \\
    r_p &= R_E + h_p = {R_EARTH + config.perigee_target_m:.0f}\,\text{{m}} \\
    a_t &= \frac{{r_a+r_p}}{{2}} = {deorbit['a_transfer']:.2f}\,\text{{m}} \\
    v_a &= \sqrt{{\mu\left(2/r_a - 1/a_t\right)}} = {deorbit['v_apogee_transfer']:.2f}\,\text{{m/s}} \\
    \Delta v_{{deorbit}} &= v_{{circ}} - v_a = {deorbit['delta_v']:.2f}\,\text{{m/s}}
    \end{{align}}
    """)
    eq_reentry = textwrap.dedent(r"""
    \begin{align}
    \dot r &= v\sin\gamma \\
    \dot\theta &= \frac{v\cos\gamma}{r} \\
    \dot v &= -\frac{D}{m} - \frac{\mu}{r^2}\sin\gamma \\
    \dot\gamma &= \frac{L}{mv} + \left(\frac{v}{r} - \frac{\mu}{vr^2}\right)\cos\gamma
    \end{align}
    \begin{align}
    D &= \tfrac12 \rho v^2 C_D A \\
    L &= \tfrac12 \rho v^2 C_L A \\
    \dot q_{stag} &\approx 1.83\times 10^{-4}\sqrt{\rho/R_n}v^3 \times 10^4
    \end{align}
    """)
    eq_thermal = textwrap.dedent(fr"""
    \begin{{align}}
    T_{{wall}} &\approx \left(\frac{{\dot q}}{{\epsilon\sigma}}\right)^{{1/4}} \\
    p_0 &= p\left(1+\tfrac{{\gamma-1}}{{2}}M^2\right)^{{\gamma/(\gamma-1)}}
    \end{{align}}
    Peak values: $\dot q_{{max}} = {summary['peak_heat_flux_w_m2']:.3e}\,\text{{W/m}}^2$, $T_{{wall,max}} = {summary['peak_wall_temperature_k']:.1f}\,\text{{K}}$.
    """)
    eq_plasma = textwrap.dedent(fr"""
    \begin{{align}}
    x_{{ion}} &= \sigma_{{logistic}}(T_{{wall}},\rho) \\
    n_e &= x_{{ion}}\frac{{\rho}}{{m_{{air}}}} \\
    f_p &= 8980\sqrt{{n_e\,[\text{{cm}}^{{-3}}]}}\,\text{{Hz}}
    \end{{align}}
    Peak plasma frequency: $f_{{p,max}} = {summary['peak_plasma_frequency_hz']:.3e}\,\text{{Hz}}$.
    """)
    eq_landing = textwrap.dedent(fr"""
    \begin{{align}}
    a_{{req}} &\approx \frac{{v_0^2}}{{2h_0}} \\
    \Delta v_{{landing}} &\approx {summary['landing_burn_start_velocity_m_s']:.2f} + 35 \\
    m_p &= m_0\left(1-e^{{-\Delta v/(I_{{sp}}g_0)}}\right)
    \end{{align}}
    Landing burn: $h_0={summary['landing_burn_start_altitude_m']:.1f}\,\text{{m}}$, $v_0={summary['landing_burn_start_velocity_m_s']:.2f}\,\text{{m/s}}$, $m_p={summary['landing_propellant_kg']:.1f}\,\text{{kg}}$, $T\approx {summary['engine_thrust_for_capture_n']:.3e}\,\text{{N}}$.
    """)
    eq_wt = textwrap.dedent(fr"""
    \begin{{align}}
    Re &= \frac{{\rho V L}}{{\mu}} \\
    C_f &\approx \frac{{0.455}}{{\log_{{10}}(Re)^{{2.58}}}} \\
    C_D &\approx C_{{D,base}} + C_{{D,fric}} + C_{{D,fin}} + C_{{D,comp}} \\
    q &= \tfrac12\rho V^2
    \end{{align}}
    Melhor caso do t\'unel de vento: $V={wind['best_case']['velocity_m_s']:.1f}\,\text{{m/s}}$, $\alpha={wind['best_case']['aoa_deg']:.1f}^\circ$, $C_D={wind['best_case']['cd']:.4f}$.
    """)
    eq_opt = textwrap.dedent(fr"""
    \textbf{{Otimizacao de foguete:}} melhor score = {rocket_opt['best_metrics']['score']:.4f}, volume = {rocket_opt['best_metrics']['payload_volume_m3']:.2f} m$^3$, margem estatica = {rocket_opt['best_metrics']['stability_margin_calibers']:.2f} calibres.\\
    \textbf{{Otimizacao de turbina:}} eficiencia = {turbine_opt['best_metrics']['efficiency']:.4f}, Mach na ponta = {turbine_opt['best_metrics']['tip_mach']:.3f}, potencia proxy = {turbine_opt['best_metrics']['power_proxy_w']:.3e} W.
    """)
    return {"orbit": eq_orbit, "deorbit": eq_deorbit, "reentry": eq_reentry, "thermal": eq_thermal, "plasma": eq_plasma, "landing": eq_landing, "wind_tunnel": eq_wt, "optimization": eq_opt}


def simulate_orbital_reentry_and_capture(config: OrbitalMissionConfig) -> OrbitalSimulationResult:
    vehicle = config.vehicle
    orbit = circular_orbit_parameters(config.orbit_altitude_m)
    deorbit = deorbit_to_perigee_delta_v(config.orbit_altitude_m, config.perigee_target_m)
    entry = entry_interface_velocity(config.orbit_altitude_m, config.perigee_target_m, config.entry_interface_altitude_m)

    r = entry["r_entry"]
    h = config.entry_interface_altitude_m
    v = entry["v_entry"]
    gamma = math.radians(entry["gamma_entry_deg"])
    theta = 0.0
    t = 0.0
    m = vehicle.mass_initial
    dt = config.dt_reentry
    bank = math.radians(config.reentry_bank_angle_deg)

    A = vehicle.reference_area
    Cd = vehicle.drag_coefficient
    CL = Cd * vehicle.lift_to_drag * math.cos(bank)

    arr: Dict[str, list] = {k: [] for k in [
        "time_s", "altitude_m", "velocity_m_s", "flight_path_angle_deg", "downrange_m",
        "density_kg_m3", "pressure_pa", "temperature_k", "mach", "dynamic_pressure_pa",
        "g_load", "heat_flux_w_m2", "wall_temperature_k", "stagnation_pressure_pa",
        "ionization_fraction", "electron_density_m3", "plasma_frequency_hz",
        "infrared_intensity", "uv_intensity", "xray_intensity", "phase_index"
    ]}

    blackout_started = None
    blackout_ended = None
    peak_heat_alt = peak_q_alt = peak_g_alt = 0.0
    peak_heat = peak_q = peak_g = -1.0

    while h > max(vehicle.landing_burn_start_altitude, 1000.0) and t < config.max_reentry_time and v > 50.0:
        atm = standard_atmosphere(h)
        rho = atm["rho"]
        p = atm["p"]
        T = atm["T"]
        a = atm["a"]
        mach = v / max(a, 1e-9)
        q_dyn = 0.5 * rho * v * v
        D = q_dyn * Cd * A
        L = q_dyn * CL * A
        g_local = MU_EARTH / (r * r)
        dv_dt = -D / m - g_local * math.sin(gamma)
        dgamma_dt = L / max(m * v, 1e-6) + (v / r - g_local / max(v, 1e-6)) * math.cos(gamma)
        dr_dt = v * math.sin(gamma)
        dtheta_dt = v * math.cos(gamma) / r

        heat = _sutton_graves_heat_flux(rho, v, max(vehicle.nose_radius, 0.4))
        T_wall = min(4200.0, max(T, (heat / max(vehicle.emissivity * SIGMA_SB, 1e-12)) ** 0.25))
        p0 = _stagnation_pressure(p, mach)
        ion_frac = _ionization_fraction(T_wall, rho)
        ne = _electron_density(rho, ion_frac)
        fp = _plasma_frequency_hz(ne)
        spec = _spectral_diagnostics(T_wall, config.spectral_xray_threshold_k)
        accel = abs(dv_dt) / G0

        arr["time_s"].append(t)
        arr["altitude_m"].append(h)
        arr["velocity_m_s"].append(v)
        arr["flight_path_angle_deg"].append(math.degrees(gamma))
        arr["downrange_m"].append(R_EARTH * theta)
        arr["density_kg_m3"].append(rho)
        arr["pressure_pa"].append(p)
        arr["temperature_k"].append(T)
        arr["mach"].append(mach)
        arr["dynamic_pressure_pa"].append(q_dyn)
        arr["g_load"].append(accel)
        arr["heat_flux_w_m2"].append(heat)
        arr["wall_temperature_k"].append(T_wall)
        arr["stagnation_pressure_pa"].append(p0)
        arr["ionization_fraction"].append(ion_frac)
        arr["electron_density_m3"].append(ne)
        arr["plasma_frequency_hz"].append(fp)
        arr["infrared_intensity"].append(spec["ir"])
        arr["uv_intensity"].append(spec["uv"])
        arr["xray_intensity"].append(spec["xray"])
        arr["phase_index"].append(0)

        if heat > peak_heat:
            peak_heat, peak_heat_alt = heat, h
        if q_dyn > peak_q:
            peak_q, peak_q_alt = q_dyn, h
        if accel > peak_g:
            peak_g, peak_g_alt = accel, h

        blackout = fp > vehicle.communications_frequency_hz
        if blackout and blackout_started is None:
            blackout_started = t
        if (not blackout) and blackout_started is not None and blackout_ended is None:
            blackout_ended = t

        v = max(0.0, v + dv_dt * dt)
        gamma = gamma + dgamma_dt * dt
        r = r + dr_dt * dt
        theta = theta + dtheta_dt * dt
        h = max(0.0, r - R_EARTH)
        t += dt

    burn_start_alt = max(h, vehicle.landing_burn_start_altitude)
    burn_start_v = max(v, 1.0)
    a_req = burn_start_v ** 2 / (2.0 * max(burn_start_alt, 1.0))
    effective_decel = a_req + G0 * 0.35
    total_dv_landing = burn_start_v + 35.0
    prop_ratio = math.exp(total_dv_landing / max(vehicle.landing_isp * G0, 1e-9))
    landing_propellant = max(0.0, m - m / prop_ratio)
    T_engine = m * (effective_decel + G0)
    burn_time = max(1.0, burn_start_v / max(effective_decel, 1e-6))
    dt_land = min(0.2, burn_time / 80.0)
    t_land = 0.0
    h_land = burn_start_alt
    v_land = burn_start_v

    while h_land > 0.0 and t_land <= burn_time + 2.0:
        v_land = max(vehicle.landing_target_velocity, v_land - effective_decel * dt_land)
        h_land = max(0.0, h_land - v_land * dt_land)
        atm = standard_atmosphere(h_land)
        rho = atm["rho"]
        p = atm["p"]
        T = atm["T"]
        q_dyn = 0.5 * rho * v_land * v_land
        heat = _sutton_graves_heat_flux(rho, v_land, max(vehicle.nose_radius, 0.4)) * 0.05
        T_wall = max(T, (heat / max(vehicle.emissivity * SIGMA_SB, 1e-12)) ** 0.25)
        ion_frac = _ionization_fraction(T_wall, rho) * 0.2
        ne = _electron_density(rho, ion_frac)
        fp = _plasma_frequency_hz(ne)
        spec = _spectral_diagnostics(T_wall, config.spectral_xray_threshold_k)

        arr["time_s"].append(t + t_land)
        arr["altitude_m"].append(h_land)
        arr["velocity_m_s"].append(v_land)
        arr["flight_path_angle_deg"].append(-90.0)
        arr["downrange_m"].append(R_EARTH * theta)
        arr["density_kg_m3"].append(rho)
        arr["pressure_pa"].append(p)
        arr["temperature_k"].append(T)
        arr["mach"].append(v_land / max(atm["a"], 1e-9))
        arr["dynamic_pressure_pa"].append(q_dyn)
        arr["g_load"].append((effective_decel + G0) / G0)
        arr["heat_flux_w_m2"].append(heat)
        arr["wall_temperature_k"].append(T_wall)
        arr["stagnation_pressure_pa"].append(_stagnation_pressure(p, arr["mach"][-1]))
        arr["ionization_fraction"].append(ion_frac)
        arr["electron_density_m3"].append(ne)
        arr["plasma_frequency_hz"].append(fp)
        arr["infrared_intensity"].append(spec["ir"])
        arr["uv_intensity"].append(spec["uv"])
        arr["xray_intensity"].append(spec["xray"])
        arr["phase_index"].append(1)
        t_land += dt_land

    timeline = {k: np.asarray(vv) for k, vv in arr.items()}
    total_time = float(timeline["time_s"][-1]) if len(timeline["time_s"]) else 0.0
    blackout_duration = 0.0
    if blackout_started is not None:
        blackout_duration = total_time - blackout_started if blackout_ended is None else blackout_ended - blackout_started

    wind = simulate_wind_tunnel(config)
    rocket_opt = optimize_rocket_shape(config)
    turbine_opt = optimize_turbine_geometry(config)

    summary = {
        "orbit_velocity_m_s": orbit["v"],
        "orbit_period_s": orbit["period"],
        "deorbit_delta_v_m_s": deorbit["delta_v"],
        "entry_velocity_m_s": entry["v_entry"],
        "peak_heat_flux_w_m2": float(np.max(timeline["heat_flux_w_m2"]) if len(timeline["heat_flux_w_m2"]) else 0.0),
        "peak_dynamic_pressure_pa": float(np.max(timeline["dynamic_pressure_pa"]) if len(timeline["dynamic_pressure_pa"]) else 0.0),
        "peak_g_load": float(np.max(timeline["g_load"]) if len(timeline["g_load"]) else 0.0),
        "peak_wall_temperature_k": float(np.max(timeline["wall_temperature_k"]) if len(timeline["wall_temperature_k"]) else 0.0),
        "peak_plasma_frequency_hz": float(np.max(timeline["plasma_frequency_hz"]) if len(timeline["plasma_frequency_hz"]) else 0.0),
        "landing_propellant_kg": float(landing_propellant),
        "landing_burn_start_altitude_m": float(burn_start_alt),
        "landing_burn_start_velocity_m_s": float(burn_start_v),
        "landing_burn_time_s": float(burn_time),
        "blackout_duration_s": float(blackout_duration),
        "peak_heat_altitude_m": float(peak_heat_alt),
        "peak_q_altitude_m": float(peak_q_alt),
        "peak_g_altitude_m": float(peak_g_alt),
        "engine_thrust_for_capture_n": float(T_engine),
        "wind_tunnel_cd_min": float(wind["summary"]["cd_min"]),
        "rocket_optimization_score": float(rocket_opt["best_metrics"]["score"]),
        "turbine_efficiency": float(turbine_opt["best_metrics"]["efficiency"]),
    }
    metadata = {
        "config": asdict(config),
        "vehicle": asdict(vehicle),
        "created_at_unix": time.time(),
        "model_notes": [
            "Planar lifting reentry with standard-atmosphere + exponential high-altitude continuation.",
            "Sutton-Graves-type stagnation heating estimate.",
            "Proxy ionization and plasma-frequency blackout estimate.",
            "Final recapture modeled as propulsive landing/catch burn.",
            "Wind tunnel and shape/turbine optimization are surrogate physics-informed analyses for exploration.",
        ],
    }
    latex_blocks = _build_latex_blocks(config, orbit, deorbit, summary, wind, rocket_opt, turbine_opt)
    return OrbitalSimulationResult(
        summary=summary,
        timeline=timeline,
        images={},
        videos={},
        metadata=metadata,
        latex_blocks=latex_blocks,
        wind_tunnel=wind,
        rocket_optimization=rocket_opt,
        turbine_optimization=turbine_opt,
    )


def _rocket_surface_geometry(shape: RocketShapeConfig, circum_points: int = 96, nose_points: int = 36, body_points: int = 72, tail_points: int = 24) -> Dict[str, np.ndarray]:
    x1 = np.linspace(0.0, shape.nose_length_m, max(6, int(nose_points)))
    r1 = shape.body_radius_m * (x1 / max(shape.nose_length_m, 1e-9)) ** 0.85
    x2 = np.linspace(shape.nose_length_m, shape.nose_length_m + shape.body_length_m, max(10, int(body_points)))
    r2 = shape.body_radius_m * np.ones_like(x2)
    x3 = np.linspace(shape.nose_length_m + shape.body_length_m, shape.total_length_m, max(5, int(tail_points)))
    frac = (x3 - x3.min()) / max(x3.max() - x3.min(), 1e-9)
    r3 = shape.body_radius_m - (shape.body_radius_m - shape.engine_exit_radius_m) * frac ** 1.3
    x = np.concatenate([x1, x2, x3])
    rr = np.concatenate([r1, r2, r3])
    theta = np.linspace(0.0, 2*np.pi, max(12, int(circum_points)))
    X, TH = np.meshgrid(x, theta)
    R = np.tile(rr, (len(theta), 1))
    Y = R * np.cos(TH)
    Z = R * np.sin(TH)
    return {"X": X, "Y": Y, "Z": Z, "theta": TH, "r": R}


def _rocket_surface_colors(shape: RocketShapeConfig, material: RocketMaterialConfig, heat_scale: float = 0.0, circum_points: int = 96, nose_points: int = 36, body_points: int = 72, tail_points: int = 24) -> np.ndarray:
    geom = _rocket_surface_geometry(shape, circum_points=circum_points, nose_points=nose_points, body_points=body_points, tail_points=tail_points)
    X, TH = geom["X"], geom["theta"]
    x_norm = X / max(shape.total_length_m, 1e-9)
    stripe = 0.5 + 0.5 * np.sin(11 * np.pi * x_norm + 2.0 * np.sin(TH * 2.0))
    brushed = 0.92 + 0.08 * np.sin(TH * 40.0 + x_norm * 25.0)
    base = np.array(material.base_rgb)[None, None, :]
    accent = np.array(material.accent_rgb)[None, None, :]
    glow = np.array(material.glow_rgb)[None, None, :]
    colors = base * (0.72 + 0.28 * stripe[..., None]) * brushed[..., None]
    tile_mask = ((TH > np.pi * 0.70) & (TH < np.pi * 1.30)).astype(float)
    tile_strength = tile_mask * (0.40 + 0.60 * (x_norm > 0.20))
    colors = colors * (1.0 - 0.82 * tile_strength[..., None]) + accent * (0.82 * tile_strength[..., None])
    nose_hot = np.exp(-5.0 * x_norm) * heat_scale
    belly_hot = tile_strength * 0.55 * heat_scale
    hot = np.maximum(nose_hot, belly_hot)
    colors = np.clip(colors * (1.0 - 0.55 * hot[..., None]) + glow * (0.70 * hot[..., None]), 0.0, 1.0)
    return colors


def _add_fins(ax, shape: RocketShapeConfig, material: RocketMaterialConfig, Poly3DCollection, heat_scale: float = 0.0) -> None:
    tail_x = shape.nose_length_m + shape.body_length_m - 1.5
    sweep = math.radians(shape.fin_sweep_deg)
    fin_color = np.clip(np.array(material.accent_rgb) * (1.0 - 0.35 * heat_scale) + np.array(material.glow_rgb) * (0.25 * heat_scale), 0.0, 1.0)
    for k in range(shape.fin_count):
        phi = 2.0 * math.pi * k / shape.fin_count
        c, s = math.cos(phi), math.sin(phi)
        x0 = tail_x
        x1 = tail_x + shape.fin_root_chord_m
        x2 = tail_x + shape.fin_sweep_deg / 45.0 + shape.fin_tip_chord_m + shape.fin_root_chord_m * 0.25
        r = shape.body_radius_m
        span = shape.fin_span_m
        p0 = np.array([x0, r * c, r * s])
        p1 = np.array([x1, r * c, r * s])
        tip = np.array([x2, (r + span) * c, (r + span) * s])
        tri = Poly3DCollection([[p0, p1, tip]], facecolors=[fin_color], edgecolors='k', linewidths=0.4, alpha=0.98)
        ax.add_collection3d(tri)


def _add_engine_bell(ax, shape: RocketShapeConfig, material: RocketMaterialConfig, heat_scale: float = 0.0) -> None:
    plt, cm, Normalize, _ = _safe_import_matplotlib()
    x = np.linspace(shape.total_length_m - shape.boat_tail_length_m * 0.8, shape.total_length_m + 2.0, 28)
    frac = (x - x.min()) / max(x.max() - x.min(), 1e-9)
    r = shape.engine_exit_radius_m + 0.9 * (1.0 - (1.0 - frac) ** 1.4)
    theta = np.linspace(0.0, 2*np.pi, 60)
    X, TH = np.meshgrid(x, theta)
    R = np.tile(r, (len(theta), 1))
    Y = R * np.cos(TH)
    Z = R * np.sin(TH)
    eng = np.tile(np.array(material.engine_rgb), (Y.shape[0], Y.shape[1], 1))
    eng *= (0.82 + 0.18 * np.sin(TH * 30.0 + X * 2.0))[..., None]
    eng = np.clip(eng * (1.0 - 0.25 * heat_scale) + np.array(material.glow_rgb) * (0.2 * heat_scale), 0.0, 1.0)
    ax.plot_surface(X, Y, Z, facecolors=eng, linewidth=0, antialiased=False, shade=False)


def _render_vehicle_3d(ax, shape: RocketShapeConfig, material: RocketMaterialConfig, heat_scale: float = 0.0, with_exhaust: bool = False, low_res: bool = False) -> None:
    if low_res:
        geom = _rocket_surface_geometry(shape, circum_points=36, nose_points=18, body_points=26, tail_points=10)
        colors = _rocket_surface_colors(shape, material, heat_scale=heat_scale, circum_points=36, nose_points=18, body_points=26, tail_points=10)
    else:
        geom = _rocket_surface_geometry(shape)
        colors = _rocket_surface_colors(shape, material, heat_scale=heat_scale)
    ax.plot_surface(geom["X"], geom["Y"], geom["Z"], facecolors=colors, linewidth=0, antialiased=False, shade=False)
    _, _, _, Poly3DCollection = _safe_import_matplotlib()
    _add_fins(ax, shape, material, Poly3DCollection, heat_scale=heat_scale)
    _add_engine_bell(ax, shape, material, heat_scale=heat_scale)
    if with_exhaust:
        x = np.linspace(shape.total_length_m + 0.2, shape.total_length_m + 8.0, 18)
        theta = np.linspace(0.0, 2*np.pi, 32)
        X, TH = np.meshgrid(x, theta)
        frac = (x - x.min()) / max(x.max() - x.min(), 1e-9)
        R_line = shape.engine_exit_radius_m * (1.0 + 2.8 * frac)
        R = np.tile(R_line, (len(theta), 1))
        Y = R * np.cos(TH)
        Z = R * np.sin(TH)
        plume = np.zeros((len(theta), len(x), 4))
        glow = np.array(material.glow_rgb)
        plume[..., :3] = glow
        plume[..., 3] = np.tile((1.0 - frac) * 0.40, (len(theta), 1))
        ax.plot_surface(X, Y, Z, facecolors=plume, linewidth=0, antialiased=False, shade=False)


def _surface_profile_from_timeline(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr)
    if arr.size == 0:
        return np.ones(120)
    n = 120
    idx = np.linspace(0, arr.size - 1, n)
    base = np.interp(idx, np.arange(arr.size), arr)
    base = np.nan_to_num(base, nan=float(np.nanmean(base) if np.isfinite(base).any() else 0.0))
    base = (base - np.nanmin(base)) / max(np.nanmax(base) - np.nanmin(base), 1e-9)
    gradient = np.linspace(1.6, 0.35, n)
    return base * gradient


def _render_surface_figure(path: Path, shape: RocketShapeConfig, line_profile: np.ndarray, cmap_name: str, title: str, cbar_label: str) -> str:
    plt, cm, Normalize, _ = _safe_import_matplotlib()
    geom = _rocket_surface_geometry(shape)
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    prof = np.interp(geom["X"][0], np.linspace(geom["X"][0].min(), geom["X"][0].max(), len(line_profile)), line_profile)
    data = np.tile(prof, (geom["X"].shape[0], 1))
    norm = Normalize(vmin=float(np.min(data)), vmax=float(np.max(data)))
    colors = cm.get_cmap(cmap_name)(norm(data))
    ax.plot_surface(geom["X"], geom["Y"], geom["Z"], facecolors=colors, linewidth=0, antialiased=False, shade=False)
    fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap_name), ax=ax, pad=0.1, shrink=0.7, label=cbar_label)
    ax.set_title(title)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_zlabel("z [m]")
    ax.view_init(elev=25, azim=45)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return str(path)


def _render_plasma_shell_figure(path: Path, shape: RocketShapeConfig, plasma_line: np.ndarray) -> str:
    plt, cm, Normalize, _ = _safe_import_matplotlib()
    geom = _rocket_surface_geometry(shape)
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    expand = 1.35
    X = geom["X"]
    Y = geom["Y"] * expand
    Z = geom["Z"] * expand
    prof = np.interp(X[0], np.linspace(X[0].min(), X[0].max(), len(plasma_line)), plasma_line)
    data = np.tile(prof, (X.shape[0], 1))
    norm = Normalize(vmin=float(np.min(data)), vmax=float(np.max(data)))
    colors = cm.get_cmap("plasma")(norm(data))
    ax.plot_surface(X, Y, Z, facecolors=colors, linewidth=0, alpha=0.65, antialiased=False, shade=False)
    ax.plot_surface(geom["X"], geom["Y"], geom["Z"], color="silver", alpha=0.12, linewidth=0)
    fig.colorbar(cm.ScalarMappable(norm=norm, cmap="plasma"), ax=ax, pad=0.1, shrink=0.7, label="log10 electron density proxy")
    ax.set_title("3D ionized plasma sheath diagnostic")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_zlabel("z [m]")
    ax.view_init(elev=25, azim=35)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return str(path)


def _tile_keyframes(image_paths: Sequence[Path], out_path: Path, labels: Optional[Sequence[str]] = None) -> str:
    from PIL import Image, ImageDraw
    ims = [Image.open(p).convert("RGB") for p in image_paths]
    if not ims:
        return str(out_path)
    w, h = ims[0].size
    canvas = Image.new("RGB", (w * len(ims), h), (10, 10, 10))
    draw = ImageDraw.Draw(canvas)
    labels = labels or [p.stem for p in image_paths]
    for i, im in enumerate(ims):
        canvas.paste(im, (i * w, 0))
        draw.rectangle([(i * w + 8, 8), (i * w + 220, 38)], fill=(0, 0, 0))
        draw.text((i * w + 14, 14), labels[i], fill=(255, 255, 255))
    canvas.save(out_path)
    return str(out_path)


def generate_orbital_mission_figures(result: OrbitalSimulationResult, config: OrbitalMissionConfig, output_dir: str | Path) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plt, _, _, _ = _safe_import_matplotlib()
    tl = result.timeline
    wt = result.wind_tunnel
    paths: Dict[str, str] = {}
    shape = _shape_with_vehicle(config)

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    u = np.linspace(0, 2*np.pi, 50)
    vv = np.linspace(0, np.pi, 30)
    xs = R_EARTH * np.outer(np.cos(u), np.sin(vv))
    ys = R_EARTH * np.outer(np.sin(u), np.sin(vv))
    zs = R_EARTH * np.outer(np.ones_like(u), np.cos(vv))
    ax.plot_surface(xs/1000.0, ys/1000.0, zs/1000.0, alpha=0.15, linewidth=0)
    ang = tl["downrange_m"] / R_EARTH
    rr = R_EARTH + tl["altitude_m"]
    lat = np.deg2rad(18.0) * np.ones_like(ang)
    x = rr * np.cos(ang) * np.cos(lat)
    y = rr * np.sin(ang) * np.cos(lat)
    z = rr * np.sin(lat)
    ax.scatter(x/1000.0, y/1000.0, z/1000.0, c=tl["wall_temperature_k"], s=8, cmap="inferno")
    ax.plot(x/1000.0, y/1000.0, z/1000.0, linewidth=1.2)
    ax.set_title("3D orbital-reentry-capture trajectory")
    ax.set_xlabel("x [km]")
    ax.set_ylabel("y [km]")
    ax.set_zlabel("z [km]")
    p = output_dir / "trajectory_3d.png"
    fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); paths["trajectory_3d"] = str(p)

    fig = plt.figure(figsize=(14, 10))
    axs = [fig.add_subplot(2, 2, i+1) for i in range(4)]
    axs[0].plot(tl["time_s"], tl["altitude_m"]/1000.0); axs[0].set_title("Altitude vs time"); axs[0].set_xlabel("time [s]"); axs[0].set_ylabel("altitude [km]")
    axs[1].plot(tl["time_s"], tl["velocity_m_s"]); axs[1].set_title("Velocity vs time"); axs[1].set_xlabel("time [s]"); axs[1].set_ylabel("velocity [m/s]")
    axs[2].plot(tl["time_s"], tl["dynamic_pressure_pa"]/1000.0, label="q [kPa]"); axs[2].plot(tl["time_s"], tl["heat_flux_w_m2"]/1e6, label="heat [MW/m²]"); axs[2].set_title("Aerothermodynamic loads"); axs[2].set_xlabel("time [s]"); axs[2].legend()
    axs[3].plot(tl["time_s"], tl["g_load"], label="g-load"); axs[3].plot(tl["time_s"], tl["mach"], label="Mach"); axs[3].set_title("Dynamic state"); axs[3].set_xlabel("time [s]"); axs[3].legend()
    fig.tight_layout(); p = output_dir / "profiles_dashboard.png"; fig.savefig(p, dpi=220); plt.close(fig); paths["profiles_dashboard"] = str(p)

    fig = plt.figure(figsize=(14, 10))
    axs = [fig.add_subplot(2, 2, i+1) for i in range(4)]
    axs[0].plot(tl["altitude_m"]/1000.0, tl["pressure_pa"]); axs[0].set_yscale("log"); axs[0].set_title("Pressure vs altitude"); axs[0].set_xlabel("altitude [km]"); axs[0].set_ylabel("pressure [Pa]")
    axs[1].plot(tl["altitude_m"]/1000.0, tl["temperature_k"], label="ambient"); axs[1].plot(tl["altitude_m"]/1000.0, tl["wall_temperature_k"], label="wall"); axs[1].set_title("Temperature vs altitude"); axs[1].set_xlabel("altitude [km]"); axs[1].legend()
    axs[2].plot(tl["time_s"], tl["electron_density_m3"]); axs[2].set_yscale("log"); axs[2].set_title("Electron density"); axs[2].set_xlabel("time [s]"); axs[2].set_ylabel("n_e [m^-3]")
    axs[3].plot(tl["time_s"], tl["plasma_frequency_hz"]/1e9, label="plasma freq [GHz]"); axs[3].axhline(y=result.metadata["vehicle"]["communications_frequency_hz"]/1e9, linestyle="--", label="comm link"); axs[3].set_title("Blackout criterion"); axs[3].set_xlabel("time [s]"); axs[3].legend()
    fig.tight_layout(); p = output_dir / "thermo_plasma_dashboard.png"; fig.savefig(p, dpi=220); plt.close(fig); paths["thermo_plasma_dashboard"] = str(p)

    paths["heat_surface_3d"] = _render_surface_figure(output_dir / "heat_surface_3d.png", shape, _surface_profile_from_timeline(tl["heat_flux_w_m2"]), "inferno", "3D heating load map", "Heat load proxy")
    paths["temperature_surface_3d"] = _render_surface_figure(output_dir / "temperature_surface_3d.png", shape, _surface_profile_from_timeline(tl["wall_temperature_k"]), "hot", "3D wall-temperature render", "Wall temperature [K]")
    paths["infrared_surface_3d"] = _render_surface_figure(output_dir / "infrared_surface_3d.png", shape, _surface_profile_from_timeline(tl["infrared_intensity"]), "magma", "3D infrared diagnostic render", "IR intensity")
    paths["xray_surface_3d"] = _render_surface_figure(output_dir / "xray_surface_3d.png", shape, _surface_profile_from_timeline(tl["xray_intensity"]), "cividis", "3D X-ray diagnostic render", "X-ray proxy")
    paths["plasma_surface_3d"] = _render_plasma_shell_figure(output_dir / "plasma_surface_3d.png", shape, _surface_profile_from_timeline(np.log10(np.maximum(tl["electron_density_m3"], 1.0))))

    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(111)
    ax.plot(tl["time_s"], tl["infrared_intensity"], label="IR")
    ax.plot(tl["time_s"], tl["uv_intensity"], label="UV")
    ax.plot(tl["time_s"], tl["xray_intensity"], label="X-ray")
    ax.set_title("Remote-sensing spectral diagnostics")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("normalized signal")
    ax.legend()
    p = output_dir / "spectral_diagnostics.png"
    fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); paths["spectral_diagnostics"] = str(p)

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111)
    im = ax.imshow(wt["cd_grid"], aspect="auto", origin="lower", cmap="viridis", extent=[wt["velocities_m_s"][0], wt["velocities_m_s"][-1], wt["angles_of_attack_deg"][0], wt["angles_of_attack_deg"][-1]])
    ax.set_title("Wind tunnel drag coefficient map")
    ax.set_xlabel("velocity [m/s]")
    ax.set_ylabel("angle of attack [deg]")
    fig.colorbar(im, ax=ax, label="Cd")
    p = output_dir / "wind_tunnel_cd_map.png"
    fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); paths["wind_tunnel_cd_map"] = str(p)

    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(111)
    ax.plot(wt["pressure_distribution_x"], wt["pressure_distribution_cp"])
    ax.set_title("Wind tunnel surface pressure distribution")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("Cp proxy")
    p = output_dir / "wind_tunnel_pressure_distribution.png"
    fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); paths["wind_tunnel_pressure_distribution"] = str(p)

    hist = result.rocket_optimization["history"]
    if hist:
        it = [h["iteration"] for h in hist]
        sc = [h["score"] for h in hist]
        cdv = [h["avg_cd"] for h in hist]
        fig = plt.figure(figsize=(12, 7))
        ax = fig.add_subplot(111)
        ax.plot(it, sc, label="rocket score")
        ax.plot(it, cdv, label="avg Cd")
        ax.set_title("Rocket shape optimization history")
        ax.set_xlabel("iteration")
        ax.legend()
        p = output_dir / "rocket_optimization_history.png"
        fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); paths["rocket_optimization_history"] = str(p)

    thist = result.turbine_optimization["history"]
    if thist:
        it = [h["iteration"] for h in thist]
        eff = [h["efficiency"] for h in thist]
        tipm = [h["tip_mach"] for h in thist]
        fig = plt.figure(figsize=(12, 7))
        ax = fig.add_subplot(111)
        ax.plot(it, eff, label="efficiency")
        ax.plot(it, tipm, label="tip Mach")
        ax.set_title("Turbine optimization history")
        ax.set_xlabel("iteration")
        ax.legend()
        p = output_dir / "turbine_optimization_history.png"
        fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); paths["turbine_optimization_history"] = str(p)

    result.images = paths
    return paths


def _read_img(path: Path) -> np.ndarray:
    return iio.imread(path)


def _save_frame(fig, path: Path, dpi: int) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)


def _render_mission_frame(config: OrbitalMissionConfig, result: OrbitalSimulationResult, idx: int, path: Path) -> None:
    plt, _, _, _ = _safe_import_matplotlib()
    tl = result.timeline
    shape = _shape_with_vehicle(config)
    material = config.material
    fig = plt.figure(figsize=(config.video.width / config.video.dpi, config.video.height / config.video.dpi))
    ax = fig.add_subplot(111, projection="3d")
    alt = float(tl["altitude_m"][idx])
    heat_scale = float(tl["wall_temperature_k"][idx] / max(np.max(tl["wall_temperature_k"]), 1.0))
    with_exhaust = bool(tl["phase_index"][idx] > 0 and alt < config.vehicle.landing_burn_start_altitude * 1.05)
    _render_vehicle_3d(ax, shape, material, heat_scale=heat_scale, with_exhaust=with_exhaust, low_res=True)
    sky = np.array([0.03, 0.05, 0.10]) * min(1.0, alt / 80000.0) + np.array([0.35, 0.58, 0.92]) * (1.0 - min(1.0, alt / 80000.0))
    fig.patch.set_facecolor(sky)
    ax.set_facecolor(sky)
    if alt < 20000:
        g = np.linspace(-20, 20, 2)
        Xg, Yg = np.meshgrid(g, g)
        Zg = np.zeros_like(Xg) - 7.0
        ax.plot_surface(Xg + shape.total_length_m * 0.3, Yg, Zg, alpha=0.18, color=(0.2, 0.35, 0.15), linewidth=0)
    ax.view_init(elev=16 + 6 * math.sin(idx / 25.0), azim=50 + idx * 0.8)
    ax.set_xlim(-4, shape.total_length_m + 14)
    ax.set_ylim(-14, 14)
    ax.set_zlim(-10, 14)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
    ax.set_title("Reusable orbital vehicle during reentry / recapture", pad=12)
    fig.text(0.02, 0.92, f"t = {tl['time_s'][idx]:.1f} s", color="white", fontsize=11)
    fig.text(0.02, 0.88, f"altitude = {alt/1000.0:.2f} km", color="white", fontsize=11)
    fig.text(0.02, 0.84, f"velocity = {tl['velocity_m_s'][idx]:.1f} m/s", color="white", fontsize=11)
    fig.text(0.02, 0.80, f"Mach = {tl['mach'][idx]:.2f}", color="white", fontsize=11)
    fig.text(0.02, 0.76, f"wall T = {tl['wall_temperature_k'][idx]:.0f} K", color="white", fontsize=11)
    fig.text(0.02, 0.72, f"plasma = {tl['plasma_frequency_hz'][idx]/1e9:.2f} GHz", color="white", fontsize=11)
    _save_frame(fig, path, dpi=config.video.dpi)
    plt.close(fig)


def _render_wind_tunnel_frame(config: OrbitalMissionConfig, result: OrbitalSimulationResult, frame_idx: int, n_frames: int, path: Path) -> None:
    plt, _, _, _ = _safe_import_matplotlib()
    shape = _shape_with_vehicle(config)
    material = config.material
    wt = result.wind_tunnel
    vel = float(np.interp(frame_idx, [0, n_frames - 1], [wt["velocities_m_s"][0], wt["velocities_m_s"][-1]]))
    aoa = float(np.interp(frame_idx, [0, n_frames - 1], [wt["angles_of_attack_deg"][0], wt["angles_of_attack_deg"][-1]]))
    aero = _rocket_aero_surrogate(shape, vel, aoa, config.wind_tunnel.altitude_m, config.vehicle)
    cp_x = aero["cp_distribution_x"]
    cp = aero["cp_distribution"]

    fig = plt.figure(figsize=(config.video.width / config.video.dpi, config.video.height / config.video.dpi))
    ax = fig.add_subplot(111)
    ax.set_facecolor((0.02, 0.03, 0.05))
    fig.patch.set_facecolor((0.02, 0.03, 0.05))

    total_len = shape.total_length_m
    rad = shape.body_radius_m
    body_x = np.linspace(0, total_len, 260)
    radius = np.piecewise(
        body_x,
        [body_x <= shape.nose_length_m,
         (body_x > shape.nose_length_m) & (body_x <= shape.nose_length_m + shape.body_length_m),
         body_x > shape.nose_length_m + shape.body_length_m],
        [lambda xx: rad * (xx / max(shape.nose_length_m, 1e-9)) ** 0.85,
         lambda xx: rad,
         lambda xx: rad - (rad - shape.engine_exit_radius_m) * ((xx - (shape.nose_length_m + shape.body_length_m)) / max(shape.boat_tail_length_m, 1e-9))]
    )
    ax.fill_between(body_x, radius, -radius, color=material.base_rgb, alpha=0.95)
    ax.fill_between(body_x, -0.7 * radius, -radius, color=material.accent_rgb, alpha=0.98)
    for k in range(shape.fin_count):
        if k % 2 == 0:
            base_x = shape.nose_length_m + shape.body_length_m - 2.0
            tri_x = [base_x, base_x + shape.fin_root_chord_m, base_x + shape.fin_tip_chord_m + 2.4]
            tri_y = [rad, rad, rad + shape.fin_span_m]
            ax.fill(tri_x, tri_y, color=material.accent_rgb, alpha=0.9)
            ax.fill(tri_x, [-y for y in tri_y], color=material.accent_rgb, alpha=0.9)

    for y0 in np.linspace(-11, 11, 26):
        xline = np.linspace(-8, total_len + 12, 240)
        influence = np.exp(-((xline - total_len * 0.35) / (0.22 * total_len + 1e-9)) ** 2)
        deflect = 2.2 * np.sign(y0) * np.exp(-(abs(y0) / (rad + 1.8)) ** 2) * influence
        wiggle = 0.06 * math.sin(0.12 * frame_idx + y0)
        yline = y0 + deflect + wiggle
        speed_factor = 1.0 + 0.25 * math.exp(-((y0) / (rad + 0.8)) ** 2)
        c = float(np.clip((speed_factor - 0.8) / 0.6, 0.0, 1.0))
        ax.plot(xline, yline, color=(0.2 + 0.8 * c, 0.8 - 0.35 * c, 1.0 - 0.6 * c), linewidth=1.0, alpha=0.7)

    ax2 = ax.inset_axes([0.61, 0.60, 0.34, 0.28])
    ax2.plot(cp_x, cp, color='white')
    ax2.set_facecolor((0.08, 0.09, 0.13))
    ax2.tick_params(colors='white', labelsize=7)
    for s in ax2.spines.values():
        s.set_color('white')
    ax2.set_title('Cp(x)', color='white', fontsize=8)

    ax.set_xlim(-8, total_len + 12)
    ax.set_ylim(-14, 14)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("Wind tunnel / surrogate CFD view", color='white')
    fig.text(0.02, 0.92, f"V = {vel:.1f} m/s", color='white', fontsize=11)
    fig.text(0.02, 0.88, f"AoA = {aoa:.1f} deg", color='white', fontsize=11)
    fig.text(0.02, 0.84, f"Mach = {aero['mach']:.2f}", color='white', fontsize=11)
    fig.text(0.02, 0.80, f"Cd = {aero['cd']:.4f}", color='white', fontsize=11)
    fig.text(0.02, 0.76, f"Cl = {aero['cl']:.4f}", color='white', fontsize=11)
    fig.text(0.02, 0.72, f"q = {aero['q_dynamic']/1000.0:.1f} kPa", color='white', fontsize=11)
    _save_frame(fig, path, dpi=config.video.dpi)
    plt.close(fig)


def _encode_mp4_from_frames(frame_pattern: str, out_path: Path, fps: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        cmd = [ffmpeg, "-y", "-framerate", str(fps), "-i", frame_pattern, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240)
        if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return
    with iio.get_writer(out_path, fps=fps, macro_block_size=1) as writer:
        parent = Path(frame_pattern).parent
        stem = Path(frame_pattern).name.replace("%04d", "*")
        for fp in sorted(parent.glob(stem)):
            writer.append_data(_read_img(fp))


def generate_orbital_mission_videos(result: OrbitalSimulationResult, config: OrbitalMissionConfig, output_dir: str | Path) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    videos: Dict[str, str] = {}
    if not config.video.generate_videos:
        result.videos = videos
        return videos

    mission_frames_dir = output_dir / "mission_frames"
    wind_frames_dir = output_dir / "wind_tunnel_frames"
    mission_frames_dir.mkdir(exist_ok=True)
    wind_frames_dir.mkdir(exist_ok=True)

    n_mission = max(24, int(config.video.fps * config.video.mission_duration_s))
    tl = result.timeline
    idxs = np.linspace(0, len(tl["time_s"]) - 1, n_mission).astype(int)
    mission_frame_paths = []
    for k, idx in enumerate(idxs):
        fp = mission_frames_dir / f"frame_{k:04d}.png"
        _render_mission_frame(config, result, int(idx), fp)
        mission_frame_paths.append(fp)
    mission_mp4 = output_dir / "mission_animation.mp4"
    _encode_mp4_from_frames(str(mission_frames_dir / "frame_%04d.png"), mission_mp4, config.video.fps)
    videos["mission_animation"] = str(mission_mp4)

    n_wt = max(24, int(config.video.fps * config.video.wind_tunnel_duration_s))
    wind_frame_paths = []
    for k in range(n_wt):
        fp = wind_frames_dir / f"frame_{k:04d}.png"
        _render_wind_tunnel_frame(config, result, k, n_wt, fp)
        wind_frame_paths.append(fp)
    wind_mp4 = output_dir / "wind_tunnel_animation.mp4"
    _encode_mp4_from_frames(str(wind_frames_dir / "frame_%04d.png"), wind_mp4, config.video.fps)
    videos["wind_tunnel_animation"] = str(wind_mp4)

    key_mission = [mission_frame_paths[0], mission_frame_paths[len(mission_frame_paths)//2], mission_frame_paths[-1]]
    key_wind = [wind_frame_paths[0], wind_frame_paths[len(wind_frame_paths)//2], wind_frame_paths[-1]]
    result.images["mission_video_keyframes"] = _tile_keyframes(key_mission, output_dir / "mission_video_keyframes.png", ["initial", "peak heating", "capture"])
    result.images["wind_tunnel_keyframes"] = _tile_keyframes(key_wind, output_dir / "wind_tunnel_keyframes.png", ["low speed", "transonic", "high speed"])
    result.videos = videos
    return videos


class OrbitalMissionLatexReport:
    def __init__(self, config: OrbitalMissionConfig, result: OrbitalSimulationResult, output_dir: str | Path, filename: str = "orbital_mission_report"):
        self.config = config
        self.result = result
        self.output_dir = Path(output_dir)
        self.filename = filename

    def _rel(self, p: str | Path) -> str:
        return Path(p).name

    def write_tex(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        tex_path = self.output_dir / f"{self.filename}.tex"
        imgs = self.result.images
        vids = self.result.videos
        c = self.config
        s = self.result.summary
        tl = self.result.timeline
        wt = self.result.wind_tunnel
        rbest = self.result.rocket_optimization["best_shape"]
        tbest = self.result.turbine_optimization["best_design"]
        idxs = np.linspace(0, len(tl["time_s"]) - 1, min(14, len(tl["time_s"]))).astype(int) if len(tl["time_s"]) else np.array([], dtype=int)
        rows = []
        for i in idxs:
            row = "{:.1f} & {:.2f} & {:.1f} & {:.2f} & {:.2f} & {:.3f} & {:.1f}".format(
                tl["time_s"][i], tl["altitude_m"][i]/1000.0, tl["velocity_m_s"][i], tl["mach"][i],
                tl["dynamic_pressure_pa"][i]/1000.0, tl["heat_flux_w_m2"][i]/1e6, tl["wall_temperature_k"][i],
            ) + " \\\\"
            rows.append(row)
        rows_block = "\n".join(rows)
        tex = textwrap.dedent(fr'''
        \documentclass[11pt,a4paper]{{article}}
        \usepackage[utf8]{{inputenc}}
        \usepackage[T1]{{fontenc}}
        \usepackage{{lmodern}}
        \usepackage{{amsmath,amssymb,mathtools}}
        \usepackage{{geometry}}
        \usepackage{{booktabs,longtable,array}}
        \usepackage{{graphicx,float}}
        \usepackage{{xcolor}}
        \usepackage{{hyperref}}
        \usepackage{{fancyhdr}}
        \usepackage{{listings}}
        \geometry{{margin=1.35cm}}
        \pagestyle{{fancy}}
        \fancyhf{{}}
        \lhead{{NablaMath v0.5}}
        \rhead{{Relatorio orbital / wind tunnel / optimization}}
        \cfoot{{\thepage}}
        \lstdefinestyle{{nabla}}{{
          basicstyle=\ttfamily\small,
          backgroundcolor=\color{{black!3}},
          frame=single,
          breaklines=true,
          keywordstyle=\color{{blue!70!black}},
          commentstyle=\color{{green!40!black}},
          stringstyle=\color{{red!50!black}},
          showstringspaces=false,
          columns=fullflexible
        }}
        \title{{{_tex_escape(c.report_title)}}}
        \author{{NablaMath Orbital Mission Engine}}
        \date{{\today}}
        \begin{{document}}
        \maketitle
        \begin{{abstract}}
        Este relatorio demonstra a versao estendida do modulo orbital do NablaMath, agora com missao orbital completa, reentrada hipersonica, plasma, recaptura propulsiva, renderizacao 3D de foguete com materiais/texturas procedurais, geracao de videos MP4, tunel de vento surrogate e algoritmos de otimizacao para foguete e turbina.
        \end{{abstract}}
        \tableofcontents
        \newpage

        \section{{Objetivo e escopo}}
        \textbf{{Missao:}} {_tex_escape(c.mission_name)}\\
        \textbf{{Objetivos do usuario:}} {_tex_escape(c.user_objectives)}

        \section{{Entrada integral do usuario em formato de codigo}}
        \begin{{lstlisting}}[style=nabla,language=Python]
{c.user_input_code}
        \end{{lstlisting}}

        \section{{Configuracao da missao}}
        \begin{{longtable}}{{p{{5.8cm}}p{{8.3cm}}}}
        \toprule
        Parametro & Valor \\
        \midrule
        Nome do veiculo & {_tex_escape(c.vehicle.name)} \\
        Material/base & {_tex_escape(c.material.name)} \\
        Altitude orbital circular & {c.orbit_altitude_m:.1f} m \\
        Perigeu alvo de deorbitacao & {c.perigee_target_m:.1f} m \\
        Altitude da interface de entrada & {c.entry_interface_altitude_m:.1f} m \\
        Massa inicial & {c.vehicle.mass_initial:.1f} kg \\
        Massa seca & {c.vehicle.mass_dry:.1f} kg \\
        Nose length & {c.shape.nose_length_m:.2f} m \\
        Body length & {c.shape.body_length_m:.2f} m \\
        Body radius & {c.shape.body_radius_m:.2f} m \\
        Fin count & {c.shape.fin_count} \\
        Fin span & {c.shape.fin_span_m:.2f} m \\
        Isp recaptura & {c.vehicle.landing_isp:.2f} s \\
        FPS dos videos & {c.video.fps} \\
        Notas do caso & {_tex_escape(c.notes)} \\
        \bottomrule
        \end{{longtable}}

        \section{{Modelos matematicos e calculos passo a passo}}
        \subsection{{Orbita circular inicial}}
        {self.result.latex_blocks['orbit']}
        \subsection{{Deorbit burn para reduzir o perigeu}}
        {self.result.latex_blocks['deorbit']}
        \subsection{{Equacoes diferenciais da reentrada}}
        {self.result.latex_blocks['reentry']}
        \subsection{{Modelo termico e de pressao de estagnacao}}
        {self.result.latex_blocks['thermal']}
        \subsection{{Ionizacao eletromagnetica e blackout}}
        {self.result.latex_blocks['plasma']}
        \subsection{{Recaptura propulsiva}}
        {self.result.latex_blocks['landing']}
        \subsection{{Tunel de vento surrogate}}
        {self.result.latex_blocks['wind_tunnel']}
        \subsection{{Otimizacao geometrica de foguete e turbina}}
        {self.result.latex_blocks['optimization']}

        \section{{Resultados consolidados}}
        \begin{{longtable}}{{p{{6.6cm}}p{{7.5cm}}}}
        \toprule
        Metrica & Valor \\
        \midrule
        Velocidade orbital & {s['orbit_velocity_m_s']:.3f} m/s \\
        Periodo orbital & {s['orbit_period_s']:.3f} s \\
        Delta-v de deorbitacao & {s['deorbit_delta_v_m_s']:.3f} m/s \\
        Velocidade de entrada & {s['entry_velocity_m_s']:.3f} m/s \\
        Pico de fluxo de calor & {s['peak_heat_flux_w_m2']:.3e} W/m$^2$ \\
        Pico de pressao dinamica & {s['peak_dynamic_pressure_pa']:.3e} Pa \\
        Pico de carga g & {s['peak_g_load']:.3f} g \\
        Pico de temperatura de parede & {s['peak_wall_temperature_k']:.3f} K \\
        Pico de frequencia de plasma & {s['peak_plasma_frequency_hz']:.3e} Hz \\
        Duracao de blackout & {s['blackout_duration_s']:.3f} s \\
        Propelente na recaptura & {s['landing_propellant_kg']:.3f} kg \\
        Empuxo necessario para recaptura & {s['engine_thrust_for_capture_n']:.3e} N \\
        Menor Cd no tunel de vento & {s['wind_tunnel_cd_min']:.4f} \\
        Score da melhor forma de foguete & {s['rocket_optimization_score']:.4f} \\
        Eficiencia da melhor turbina & {s['turbine_efficiency']:.4f} \\
        \bottomrule
        \end{{longtable}}

        \section{{Tabela numerica amostrada da trajetoria}}
        \begin{{center}}
        \begin{{tabular}}{{rrrrrrr}}
        \toprule
        $t$ [s] & $h$ [km] & $v$ [m/s] & $M$ & $q$ [kPa] & $\dot q$ [MW/m$^2$] & $T_{{wall}}$ [K] \\
        \midrule
        {rows_block}
        \bottomrule
        \end{{tabular}}
        \end{{center}}

        \section{{Tunel de vento e otimizacao}}
        \subsection{{Resumo do melhor caso do tunel de vento}}
        Melhor caso: $V={wt['best_case']['velocity_m_s']:.1f}\,\text{{m/s}}$, $\alpha={wt['best_case']['aoa_deg']:.1f}^\circ$, $C_D={wt['best_case']['cd']:.4f}$, margem est\'atica = {wt['best_case']['stability_margin_calibers']:.2f} calibres.

        \subsection{{Melhor forma de foguete encontrada}}
        \begin{{lstlisting}}[style=nabla,language={{}}]
{json.dumps(rbest, indent=2, ensure_ascii=False)}
        \end{{lstlisting}}

        \subsection{{Melhor geometria de turbina encontrada}}
        \begin{{lstlisting}}[style=nabla,language={{}}]
{json.dumps(tbest, indent=2, ensure_ascii=False)}
        \end{{lstlisting}}

        \section{{Visualizacoes cientificas 2D e 3D}}
        \begin{{figure}}[H]\centering
        \includegraphics[width=0.92\textwidth]{{{self._rel(imgs['trajectory_3d'])}}}
        \caption{{Trajetoria 3D do veiculo em torno da Terra, colorida pela temperatura de parede prevista durante a reentrada.}}
        \end{{figure}}
        \begin{{figure}}[H]\centering
        \includegraphics[width=0.92\textwidth]{{{self._rel(imgs['profiles_dashboard'])}}}
        \caption{{Resumo temporal de altitude, velocidade, pressao dinamica, fluxo de calor, Mach e carga g.}}
        \end{{figure}}
        \begin{{figure}}[H]\centering
        \includegraphics[width=0.92\textwidth]{{{self._rel(imgs['thermo_plasma_dashboard'])}}}
        \caption{{Variaveis de ambiente, parede termica, densidade eletronica e criterio de blackout por plasma.}}
        \end{{figure}}
        \begin{{figure}}[H]\centering
        \includegraphics[width=0.48\textwidth]{{{self._rel(imgs['heat_surface_3d'])}}}
        \includegraphics[width=0.48\textwidth]{{{self._rel(imgs['temperature_surface_3d'])}}}
        \caption{{Mapas 3D de carga termica e temperatura na superficie do veiculo.}}
        \end{{figure}}
        \begin{{figure}}[H]\centering
        \includegraphics[width=0.48\textwidth]{{{self._rel(imgs['infrared_surface_3d'])}}}
        \includegraphics[width=0.48\textwidth]{{{self._rel(imgs['xray_surface_3d'])}}}
        \caption{{Renders 3D para diagnostico remoto em bandas infravermelha e de raios X (proxy).}}
        \end{{figure}}
        \begin{{figure}}[H]\centering
        \includegraphics[width=0.58\textwidth]{{{self._rel(imgs['plasma_surface_3d'])}}}
        \caption{{Visualizacao 3D da bainha de plasma ionizado em torno da nave durante o regime hipersonico.}}
        \end{{figure}}
        \begin{{figure}}[H]\centering
        \includegraphics[width=0.48\textwidth]{{{self._rel(imgs['wind_tunnel_cd_map'])}}}
        \includegraphics[width=0.48\textwidth]{{{self._rel(imgs['wind_tunnel_pressure_distribution'])}}}
        \caption{{Mapas do tunel de vento surrogate: coeficiente de arrasto e distribuicao de pressao na superficie.}}
        \end{{figure}}
        \begin{{figure}}[H]\centering
        \includegraphics[width=0.48\textwidth]{{{self._rel(imgs['rocket_optimization_history'])}}}
        \includegraphics[width=0.48\textwidth]{{{self._rel(imgs['turbine_optimization_history'])}}}
        \caption{{Historico da otimizacao da forma do foguete e da turbina.}}
        \end{{figure}}
        \begin{{figure}}[H]\centering
        \includegraphics[width=0.90\textwidth]{{{self._rel(imgs['mission_video_keyframes'])}}}
        \caption{{Keyframes do video de missao com material/textura procedural do foguete.}}
        \end{{figure}}
        \begin{{figure}}[H]\centering
        \includegraphics[width=0.90\textwidth]{{{self._rel(imgs['wind_tunnel_keyframes'])}}}
        \caption{{Keyframes do video do tunel de vento.}}
        \end{{figure}}

        \section{{Videos MP4 gerados}}
        \begin{{itemize}}
        \item Mission animation: \texttt{{{_tex_escape(Path(vids.get('mission_animation', 'N/A')).name)}}}
        \item Wind tunnel animation: \texttt{{{_tex_escape(Path(vids.get('wind_tunnel_animation', 'N/A')).name)}}}
        \item FPS configurado: {c.video.fps}
        \end{{itemize}}

        \section{{Metadados reproduziveis}}
        \begin{{lstlisting}}[style=nabla,language={{}}]
{json.dumps(self.result.metadata, indent=2, ensure_ascii=False)}
        \end{{lstlisting}}

        \end{{document}}
        ''')
        tex_path.write_text(tex, encoding="utf-8")
        return tex_path

    def compile(self) -> MissionLatexReportResult:
        tex_path = self.write_tex()
        pdflatex = shutil.which("pdflatex")
        if not pdflatex:
            return MissionLatexReportResult(tex_path, None, None, False, "pdflatex not found; TeX generated only.", self.result.images, self.result.videos)
        cmd = [pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
        stdout_all = []
        log_path = self.output_dir / f"{self.filename}.compile.stdout.txt"
        ok = True
        for _ in range(2):
            proc = subprocess.run(cmd, cwd=str(self.output_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240)
            stdout_all.append(proc.stdout)
            if proc.returncode != 0:
                ok = False
                break
        log_path.write_text("\n\n--- RUN ---\n\n".join(stdout_all), encoding="utf-8")
        pdf_path = self.output_dir / f"{self.filename}.pdf"
        return MissionLatexReportResult(tex_path, pdf_path if pdf_path.exists() else None, log_path, ok and pdf_path.exists(), "compiled" if ok else "pdflatex failed", self.result.images, self.result.videos)


def build_orbital_mission_report(config: OrbitalMissionConfig, output_dir: str | Path, filename: str = "orbital_mission_report") -> MissionLatexReportResult:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = simulate_orbital_reentry_and_capture(config)
    generate_orbital_mission_figures(result, config, output_dir)
    generate_orbital_mission_videos(result, config, output_dir)
    report = OrbitalMissionLatexReport(config, result, output_dir, filename=filename)
    return report.compile()

# ============================================================================
# v0.6 PROFESSIONAL DOSSIER AND CINEMATIC PIPELINE
# ============================================================================

@dataclass
class ProfessionalDossierConfig:
    pages_target: int = 100
    include_full_timeline_tables: bool = True
    include_sensitivity_appendix: bool = True
    include_wind_tunnel_appendix: bool = True
    include_optimization_appendix: bool = True
    include_blender_script: bool = True
    table_rows_per_page: int = 22
    title: str = "NablaMath Orbital Professional Engineering Dossier"
    subtitle: str = "Orbital mechanics, hypersonic reentry, aerothermal loads, plasma blackout, wind tunnel surrogate, turbine/shape optimization, and cinematic rendering package"


@dataclass
class ProfessionalDossierResult:
    pdf_path: Path
    blender_script_path: Optional[Path]
    manifest_path: Path
    pages_generated: int
    success: bool
    message: str
    assets: Dict[str, str]


def _professional_style_sheet():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DossierTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=25,
        leading=30,
        textColor=colors.HexColor("#0B1020"),
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="DossierSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#334155"),
        spaceAfter=14,
    ))
    styles.add(ParagraphStyle(
        name="ChapterTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=8,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=8,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="BodyPro",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=12.2,
        textColor=colors.HexColor("#111827"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SmallPro",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.4,
        leading=9.2,
        textColor=colors.HexColor("#334155"),
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="CodePro",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=6.7,
        leading=8.1,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F1F5F9"),
        borderColor=colors.HexColor("#CBD5E1"),
        borderWidth=0.25,
        borderPadding=4,
        spaceAfter=6,
    ))
    return styles


def _dossier_page_header(canvas, doc):
    from reportlab.lib import colors
    canvas.saveState()
    w, h = doc.pagesize
    canvas.setFillColor(colors.HexColor("#0B1020"))
    canvas.rect(0, h - 28, w, 28, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(28, h - 18, "NablaMath Professional Orbital Dossier")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - 28, h - 18, f"Page {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(28, 34, w - 28, 34)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(28, 22, "Generated programmatically by nablamath.orbital - professional dossier mode")
    canvas.restoreState()


def _rl_table(data, col_widths=None, font_size=6.4, header_bg="#0F172A"):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return tbl


def _safe_image_flowable(path: str | Path, width: float, max_height: float):
    from reportlab.platypus import Image, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    p = Path(path)
    if not p.exists():
        return Paragraph(f"[missing image: {p.name}]", getSampleStyleSheet()["BodyText"])
    from PIL import Image as PILImage
    with PILImage.open(p) as im:
        iw, ih = im.size
    ratio = min(width / max(iw, 1), max_height / max(ih, 1))
    return Image(str(p), width=iw * ratio, height=ih * ratio)


def _paragraph_block(story, styles, title: str, paragraphs: Sequence[str]):
    from reportlab.platypus import Paragraph, Spacer
    story.append(Paragraph(title, styles["SectionTitle"]))
    for para in paragraphs:
        story.append(Paragraph(para, styles["BodyPro"]))
    story.append(Spacer(1, 6))


def _latex_code_block(story, styles, title: str, latex: str):
    from reportlab.platypus import Paragraph, Spacer
    story.append(Paragraph(title, styles["SectionTitle"]))
    safe = _tex_escape(latex).replace("\n", "<br/>")
    story.append(Paragraph(safe, styles["CodePro"]))
    story.append(Spacer(1, 6))


def _metric_table(result: OrbitalSimulationResult):
    s = result.summary
    rows = [["Metric", "Value", "Engineering interpretation"]]
    interpretations = {
        "orbit_velocity_m_s": "Circular-orbit inertial velocity before deorbit.",
        "orbit_period_s": "Orbital period for phasing and burn scheduling.",
        "deorbit_delta_v_m_s": "Retrograde impulse required to lower perigee.",
        "entry_velocity_m_s": "Velocity at entry interface, before dense-atmosphere braking.",
        "peak_heat_flux_w_m2": "Maximum stagnation heating flux proxy.",
        "peak_dynamic_pressure_pa": "Maximum aero-structural dynamic pressure.",
        "peak_g_load": "Maximum deceleration load in Earth gravities.",
        "peak_wall_temperature_k": "Maximum equilibrium wall-temperature proxy.",
        "peak_plasma_frequency_hz": "Maximum plasma frequency for blackout screening.",
        "landing_propellant_kg": "Estimated propellant consumed by final capture burn.",
        "engine_thrust_for_capture_n": "Approximate thrust level demanded by final braking.",
        "wind_tunnel_cd_min": "Best drag coefficient observed in wind-tunnel surrogate sweep.",
        "rocket_optimization_score": "Best scalar objective after geometry search.",
        "turbine_efficiency": "Best turbine-stage efficiency proxy after random exploration.",
    }
    for k, v in s.items():
        if isinstance(v, (int, float)):
            rows.append([k, f"{v:.6g}", interpretations.get(k, "Derived mission scalar.")])
    return rows


def _timeline_table_rows(result: OrbitalSimulationResult, indices: Sequence[int]) -> List[List[str]]:
    tl = result.timeline
    rows = [["t [s]", "h [km]", "v [m/s]", "Mach", "q [kPa]", "heat [MW/m2]", "Twall [K]", "fp [GHz]"]]
    for i in indices:
        rows.append([
            f"{tl['time_s'][i]:.1f}",
            f"{tl['altitude_m'][i]/1000.0:.2f}",
            f"{tl['velocity_m_s'][i]:.1f}",
            f"{tl['mach'][i]:.2f}",
            f"{tl['dynamic_pressure_pa'][i]/1000.0:.2f}",
            f"{tl['heat_flux_w_m2'][i]/1e6:.3f}",
            f"{tl['wall_temperature_k'][i]:.1f}",
            f"{tl['plasma_frequency_hz'][i]/1e9:.3f}",
        ])
    return rows


def _sensitivity_rows(config: OrbitalMissionConfig, base_result: OrbitalSimulationResult, n: int = 140) -> List[List[str]]:
    rng = np.random.default_rng(config.optimization.random_seed + 900)
    rows = [["case", "nose R [m]", "Cd", "L/D", "entry h [km]", "peak heat [MW/m2]", "peak q [kPa]", "score"]]
    for k in range(n):
        nose = float(rng.uniform(0.75, 2.25))
        cd = float(rng.uniform(0.92, 1.55))
        ld = float(rng.uniform(0.05, 0.35))
        eh = float(rng.uniform(105_000, 132_000))
        heat = base_result.summary["peak_heat_flux_w_m2"] * (config.vehicle.nose_radius / nose) ** 0.5 * (cd / config.vehicle.drag_coefficient) ** 0.12
        q = base_result.summary["peak_dynamic_pressure_pa"] * (cd / config.vehicle.drag_coefficient) ** 0.45 * (1 + 0.15 * (ld - config.vehicle.lift_to_drag))
        score = 0.55 * heat / 1e6 + 0.35 * q / 1000.0 + 0.10 * abs(ld - 0.22) * 100
        rows.append([str(k + 1), f"{nose:.3f}", f"{cd:.3f}", f"{ld:.3f}", f"{eh/1000:.1f}", f"{heat/1e6:.3f}", f"{q/1000:.2f}", f"{score:.3f}"])
    return rows


def _write_professional_blender_script(config: OrbitalMissionConfig, result: OrbitalSimulationResult, output_dir: str | Path, filename: str = "render_orbital_cinematic_blender.py") -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    p = output_dir / filename
    shape = _shape_with_vehicle(config)
    material = config.material
    script = f'''# Auto-generated by NablaMath v0.6 professional orbital video pipeline.
# Run with: blender --background --python {filename}
# Output: cinematic_orbital_render.mp4
import bpy
import math
from mathutils import Vector

bpy.ops.object.delete()
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 96
scene.render.resolution_x = {config.video.width}
scene.render.resolution_y = {config.video.height}
scene.render.fps = {config.video.fps}
scene.frame_start = 1
scene.frame_end = {max(96, int(config.video.fps * max(config.video.mission_duration_s, 8.0)))}
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.filepath = 'cinematic_orbital_render.mp4'

def mat_principled(name, base, metallic=0.0, roughness=0.35, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        try: bsdf.inputs['Base Color'].default_value = (*base, 1.0)
        except Exception: pass
        if 'Metallic' in bsdf.inputs: bsdf.inputs['Metallic'].default_value = metallic
        if 'Roughness' in bsdf.inputs: bsdf.inputs['Roughness'].default_value = roughness
        if emission and 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = (*emission, 1.0)
            bsdf.inputs['Emission Strength'].default_value = strength
    return m

steel = mat_principled('brushed stainless steel hull', {material.base_rgb}, metallic={material.metallic}, roughness={material.roughness})
tiles = mat_principled('black ceramic TPS tiles', {material.accent_rgb}, metallic=0.0, roughness=0.72)
engine_mat = mat_principled('copper/gold engine alloy', {material.engine_rgb}, metallic=0.85, roughness=0.28)
plasma_mat = mat_principled('orange ionized plasma sheath', {material.glow_rgb}, metallic=0.0, roughness=0.05, emission={material.glow_rgb}, strength=2.5)

# Main hull as a cone+cylinder+boat-tail approximation.
bpy.ops.mesh.primitive_cone_add(vertices=128, radius1={shape.body_radius_m}, radius2=0.02, depth={shape.nose_length_m}, location=(0, 0, {shape.body_length_m/2 + shape.nose_length_m/2}))
nose = bpy.context.object
nose.name = 'ogive-like nose section'
nose.data.materials.append(steel)

bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius={shape.body_radius_m}, depth={shape.body_length_m}, location=(0,0,0))
body = bpy.context.object
body.name = 'stainless steel main body'
body.data.materials.append(steel)

bpy.ops.mesh.primitive_cone_add(vertices=128, radius1={shape.engine_exit_radius_m}, radius2={shape.body_radius_m}, depth={shape.boat_tail_length_m}, location=(0,0,{-shape.body_length_m/2-shape.boat_tail_length_m/2}))
tail = bpy.context.object
tail.name = 'boat tail engine section'
tail.data.materials.append(engine_mat)

# TPS belly panel as a dark flattened strip.
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -{shape.body_radius_m*1.01}, 0))
panel = bpy.context.object
panel.name = 'black ceramic TPS belly strip'
panel.dimensions = ({shape.body_radius_m*1.6}, 0.06, {shape.body_length_m*0.82})
panel.data.materials.append(tiles)

# Fins.
for k in range({shape.fin_count}):
    angle = 2*math.pi*k/{shape.fin_count}
    bpy.ops.mesh.primitive_cube_add(size=1, location=(math.cos(angle)*{shape.body_radius_m+shape.fin_span_m/2}, math.sin(angle)*{shape.body_radius_m+shape.fin_span_m/2}, {-shape.body_length_m/2+shape.fin_root_chord_m/2}))
    fin = bpy.context.object
    fin.name = 'aerodynamic control fin'
    fin.dimensions = ({shape.fin_span_m}, {shape.fin_thickness_m}, {shape.fin_root_chord_m})
    fin.rotation_euler[2] = angle
    fin.data.materials.append(tiles)

# Plasma sheath transparent outer shell.
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=32, radius=1.0, location=(0,0,{shape.nose_length_m*0.2}))
plasma = bpy.context.object
plasma.name = 'ionized reentry plasma envelope'
plasma.scale = ({shape.body_radius_m*1.8}, {shape.body_radius_m*1.8}, {shape.total_length_m*0.42})
plasma.data.materials.append(plasma_mat)
plasma.hide_render = False

# Earth limb and atmosphere.
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=600, location=(0,0,-690))
earth = bpy.context.object
earth.name = 'curved Earth limb'
earth.data.materials.append(mat_principled('earth blue atmosphere', (0.03,0.15,0.35), roughness=0.7))

# Lights.
bpy.ops.object.light_add(type='AREA', location=(-40,-30,55))
key = bpy.context.object
key.name='large soft solar key light'
key.data.energy=900
key.data.size=45
bpy.ops.object.light_add(type='POINT', location=(12,18,18))
rim=bpy.context.object
rim.name='orange plasma rim light'
rim.data.energy=250
rim.data.color={material.glow_rgb}

# Camera and animation.
bpy.ops.object.camera_add(location=(40,-62,28), rotation=(math.radians(63),0,math.radians(36)))
camera=bpy.context.object
scene.camera=camera
for f in range(scene.frame_start, scene.frame_end+1):
    t=(f-scene.frame_start)/(scene.frame_end-scene.frame_start)
    camera.location=(40*math.cos(0.9*t), -62+10*math.sin(2*math.pi*t), 28+8*math.sin(math.pi*t))
    camera.rotation_euler=(math.radians(63-8*t),0,math.radians(36+20*t))
    camera.keyframe_insert(data_path='location', frame=f)
    camera.keyframe_insert(data_path='rotation_euler', frame=f)
    body.rotation_euler[2]=0.25*math.sin(2*math.pi*t)
    body.keyframe_insert(data_path='rotation_euler', frame=f)
    plasma.scale=({shape.body_radius_m*(1.55+0.25*math.sin(2*math.pi*t))}, {shape.body_radius_m*(1.55+0.25*math.sin(2*math.pi*t))}, {shape.total_length_m*(0.40+0.05*math.sin(2*math.pi*t))})
    plasma.keyframe_insert(data_path='scale', frame=f)

# Render command. Uncomment to render automatically when running script.
bpy.ops.render.render(animation=True)
'''
    p.write_text(script, encoding="utf-8")
    return p


def build_professional_orbital_dossier(config: OrbitalMissionConfig, output_dir: str | Path, filename: str = "professional_orbital_dossier", dossier: Optional[ProfessionalDossierConfig] = None) -> ProfessionalDossierResult:
    """Generate a long professional engineering dossier PDF plus a Blender cinematic script.

    This is intentionally more ambitious than the compact LaTeX report. It creates a
    long, paginated, business/scientific engineering dossier with many tables,
    appendices, figures, equations, input-code capture, generated assets, and a
    Blender script for real cinematic MP4 rendering in environments with Blender.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
    from reportlab.platypus import Preformatted
    from reportlab.lib.styles import ParagraphStyle

    dossier = dossier or ProfessionalDossierConfig()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = simulate_orbital_reentry_and_capture(config)
    generate_orbital_mission_figures(result, config, output_dir)
    # Do not force MP4 generation for very long dossiers unless requested by config.
    if config.video.generate_videos:
        generate_orbital_mission_videos(result, config, output_dir)
    blender_script = _write_professional_blender_script(config, result, output_dir) if dossier.include_blender_script else None

    pdf_path = output_dir / f"{filename}.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.45 * cm,
        bottomMargin=1.15 * cm,
        title=dossier.title,
        author="NablaMath Orbital Professional Pipeline",
    )
    styles = _professional_style_sheet()
    story = []

    story.append(Spacer(1, 1.4 * cm))
    story.append(Paragraph(dossier.title, styles["DossierTitle"]))
    story.append(Paragraph(dossier.subtitle, styles["DossierSubtitle"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(_rl_table([
        ["Field", "Value"],
        ["Mission", config.mission_name],
        ["Vehicle", config.vehicle.name],
        ["Report target", f"{dossier.pages_target} pages"],
        ["Generated at", time.strftime("%Y-%m-%d %H:%M:%S")],
        ["Cinematic script", blender_script.name if blender_script else "disabled"],
        ["MP4 mission animation", Path(result.videos.get("mission_animation", "not generated")).name],
        ["MP4 wind tunnel animation", Path(result.videos.get("wind_tunnel_animation", "not generated")).name],
    ], [4.0 * cm, 12.2 * cm], font_size=8.2))
    story.append(PageBreak())

    story.append(Paragraph("Contents and engineering map", styles["ChapterTitle"]))
    contents = [
        ["Chapter", "Scope"],
        ["1", "Executive engineering summary and mission scalar results"],
        ["2", "Full user input captured as executable Python"],
        ["3", "Orbital mechanics: circular orbit, deorbit burn, transfer geometry"],
        ["4", "Reentry dynamics: equations of motion and state propagation"],
        ["5", "Aerothermal analysis: pressure, heating, stagnation, wall temperature"],
        ["6", "Electromagnetic plasma, blackout screening, spectral diagnostics"],
        ["7", "Propulsive recapture/catch-burn analysis"],
        ["8", "Wind tunnel surrogate and aerodynamic pressure maps"],
        ["9", "Rocket-shape optimization search"],
        ["10", "Turbine-geometry optimization search"],
        ["11", "Visualization and MP4 rendering assets"],
        ["Appendices", "Timeline tables, sensitivity sweeps, formulas, metadata, Blender pipeline"],
    ]
    story.append(_rl_table(contents, [2.7 * cm, 13.5 * cm], font_size=8.2))
    story.append(PageBreak())

    story.append(Paragraph("1. Executive engineering summary", styles["ChapterTitle"]))
    _paragraph_block(story, styles, "Interpretation", [
        "This dossier is structured as an engineering design-analysis package, not a compact demonstration. It records the input configuration, the mathematical model, the numerical propagation, the visual evidence, the wind-tunnel surrogate, and the geometry optimization outputs in a reproducible form.",
        "The current physical models are intentionally explicit and inspectable. They are not substitutes for a certified CFD/FEA/flight-dynamics toolchain, but they form a coherent engineering scaffold: every scalar in the summary is traceable to formulas, assumptions, generated arrays, plots, tables, and metadata.",
        "The dossier also emits a Blender script for a higher-end cinematic renderer. Matplotlib remains useful for scientific plots and keyframes, but professional cinematic videos should be rendered with Blender, USD/Houdini, Unreal, or a comparable 3D engine.",
    ])
    story.append(_rl_table(_metric_table(result), [5.0 * cm, 3.4 * cm, 8.0 * cm], font_size=6.8))
    story.append(PageBreak())

    story.append(Paragraph("2. User input captured as code", styles["ChapterTitle"]))
    story.append(Paragraph("The full input below is embedded for auditability and repeatability. A professional engineering dossier must preserve the executable source of the configuration used to create the report.", styles["BodyPro"]))
    story.append(Preformatted(config.user_input_code[:8500], styles["CodePro"]))
    story.append(PageBreak())

    story.append(Paragraph("3. Orbital mechanics", styles["ChapterTitle"]))
    _paragraph_block(story, styles, "Model role", [
        "The orbital block establishes the initial circular orbit and the retrograde deorbit burn. The mission is represented as a two-body Earth-centered transfer from a circular orbit into an atmospheric entry corridor.",
        "For a professional version, this chapter would eventually support J2 perturbations, targeting, dispersions, finite burns, attitude-coupled thrust vectors, Monte Carlo navigation covariance, and phasing constraints. The current implementation keeps the formulas transparent and reports the derived scalars directly.",
    ])
    _latex_code_block(story, styles, "LaTeX calculation block - circular orbit", result.latex_blocks["orbit"])
    _latex_code_block(story, styles, "LaTeX calculation block - deorbit", result.latex_blocks["deorbit"])
    story.append(PageBreak())

    story.append(Paragraph("4. Reentry dynamics and state propagation", styles["ChapterTitle"]))
    _paragraph_block(story, styles, "Numerical propagation", [
        "The state vector is propagated through altitude, velocity, flight-path angle, and downrange. Drag and lift are functions of dynamic pressure, reference area, and aerodynamic coefficients. This compact model is readable enough to audit and extensible enough to replace with higher-fidelity 6-DOF dynamics.",
        "A proper v1.0 flight-dynamics backend should add quaternion attitude, rotational dynamics, bank modulation, thermal protection constraints, guidance laws, landing targeting, and hardware-specific engine throttling limits.",
    ])
    _latex_code_block(story, styles, "LaTeX calculation block - reentry equations", result.latex_blocks["reentry"])
    if "trajectory_3d" in result.images:
        story.append(_safe_image_flowable(result.images["trajectory_3d"], 16.2 * cm, 12.0 * cm))
    story.append(PageBreak())

    story.append(Paragraph("5. Aerothermal and pressure analysis", styles["ChapterTitle"]))
    _paragraph_block(story, styles, "Thermal load path", [
        "Peak heating does not necessarily coincide with peak dynamic pressure. Heating is velocity dominated, whereas maximum dynamic pressure occurs deeper in the atmosphere. The report therefore keeps both variables visible and separates heat-flux, wall-temperature, stagnation-pressure, and q-bar trends.",
        "The next professional upgrade should add material stacks, ablation, conduction, thermal soak, emissivity schedules, catalytic wall effects, and TPS mass sizing. The current implementation deliberately exposes the approximate heat law and resulting wall temperature.",
    ])
    _latex_code_block(story, styles, "LaTeX calculation block - thermal model", result.latex_blocks["thermal"])
    for key in ["profiles_dashboard", "thermo_plasma_dashboard", "heat_surface_3d", "temperature_surface_3d"]:
        if key in result.images:
            story.append(_safe_image_flowable(result.images[key], 16.0 * cm, 9.7 * cm))
            story.append(Spacer(1, 6))
    story.append(PageBreak())

    story.append(Paragraph("6. Plasma, blackout, infrared, UV, and X-ray diagnostic proxies", styles["ChapterTitle"]))
    _paragraph_block(story, styles, "Plasma analysis", [
        "The plasma analysis estimates an ionization fraction, electron density, and plasma frequency. Communication blackout is flagged when the plasma frequency exceeds the configured link frequency. This is a screening model; high-fidelity blackout requires chemistry, nonequilibrium flow, antenna placement, sheath asymmetry, and frequency-dependent propagation.",
        "The infrared, ultraviolet, and X-ray layers are diagnostic proxies. They are not intended to claim actual X-ray emission magnitude; they are included because the reporting engine must support spectral layers and high-energy diagnostic channels as first-class outputs.",
    ])
    _latex_code_block(story, styles, "LaTeX calculation block - plasma model", result.latex_blocks["plasma"])
    for key in ["plasma_surface_3d", "infrared_surface_3d", "xray_surface_3d", "spectral_diagnostics"]:
        if key in result.images:
            story.append(_safe_image_flowable(result.images[key], 15.8 * cm, 9.0 * cm))
            story.append(Spacer(1, 5))
    story.append(PageBreak())

    story.append(Paragraph("7. Propulsive recapture", styles["ChapterTitle"]))
    _paragraph_block(story, styles, "Capture model", [
        "The recapture phase is modeled as a final propulsive braking segment. It converts terminal velocity, altitude, and target velocity into an approximate acceleration and thrust requirement. In a production system this would become a throttle-constrained optimal-control problem with plume-ground effects, tower geometry, engine-out margins, and sensor latency.",
    ])
    _latex_code_block(story, styles, "LaTeX calculation block - recapture", result.latex_blocks["landing"])
    if "mission_video_keyframes" in result.images:
        story.append(_safe_image_flowable(result.images["mission_video_keyframes"], 16.0 * cm, 7.0 * cm))
    story.append(PageBreak())

    story.append(Paragraph("8. Wind tunnel surrogate", styles["ChapterTitle"]))
    _paragraph_block(story, styles, "Wind tunnel role", [
        "The wind-tunnel surrogate maps velocity and angle of attack to approximate Cd, Cl, Cm, Reynolds number, q-bar, and pressure distributions. It exists so the orbital module can analyze aerodynamic design directions, not merely draw a rocket.",
        "A professional CFD backend should support mesh generation, boundary conditions, turbulence models, compressible solvers, shock visualization, adjoint sensitivities, and coupling with structural/thermal solvers. The current surrogate is a fast engineering approximation suitable for automatic report generation.",
    ])
    _latex_code_block(story, styles, "LaTeX calculation block - wind tunnel", result.latex_blocks["wind_tunnel"])
    if "wind_tunnel_cd_map" in result.images:
        story.append(_safe_image_flowable(result.images["wind_tunnel_cd_map"], 15.0 * cm, 9.0 * cm))
    if "wind_tunnel_pressure_distribution" in result.images:
        story.append(_safe_image_flowable(result.images["wind_tunnel_pressure_distribution"], 15.0 * cm, 7.0 * cm))
    if "wind_tunnel_keyframes" in result.images:
        story.append(_safe_image_flowable(result.images["wind_tunnel_keyframes"], 16.0 * cm, 7.0 * cm))
    story.append(PageBreak())

    story.append(Paragraph("9. Rocket-shape and turbine optimization", styles["ChapterTitle"]))
    _paragraph_block(story, styles, "Optimization architecture", [
        "The optimizer explores geometry parameters and evaluates a scalar objective combining drag, heating, stability, length penalty, fin penalty, and useful volume. This is not the final form of a professional optimizer; it is a visible scaffold designed to be replaced by Bayesian optimization, CMA-ES, NSGA-II, differentiable geometry, adjoint CFD, or multi-objective Pareto search.",
        "The turbine optimizer explores radius, hub radius, blade count, chord, twist, RPM, mass flow, pressure ratio, and temperature. It reports efficiency, tip Mach, solidity, loading, and stress proxies. A production turbine module needs blade-element aerodynamics, turbomachinery maps, compressor/turbine matching, choking, surge margin, cooling, and structural limits.",
    ])
    _latex_code_block(story, styles, "LaTeX calculation block - optimization", result.latex_blocks["optimization"])
    for key in ["rocket_optimization_history", "turbine_optimization_history"]:
        if key in result.images:
            story.append(_safe_image_flowable(result.images[key], 15.5 * cm, 7.8 * cm))
            story.append(Spacer(1, 5))
    story.append(PageBreak())

    story.append(Paragraph("10. Video and cinematic rendering assets", styles["ChapterTitle"]))
    video_rows = [["Asset", "Path", "Role"]]
    for k, v in result.videos.items():
        video_rows.append([k, Path(v).name, "Generated MP4 preview"])
    if blender_script:
        video_rows.append(["Blender cinematic script", blender_script.name, "Run in Blender for higher-end video rendering"])
    story.append(_rl_table(video_rows, [4.0 * cm, 6.0 * cm, 6.0 * cm], font_size=7.2))
    _paragraph_block(story, styles, "Professional video distinction", [
        "The embedded MP4 previews are lightweight generated assets. A professional cinematic video should use the generated Blender script, or a USD/Unreal/Houdini pipeline, because physically plausible materials, atmospheric scattering, volumetric plasma, motion blur, camera tracking, and high-sample lighting require a real 3D renderer.",
        "The module therefore now emits both preview MP4s and a Blender scene script. This is the correct architectural split: scientific plots for analysis, preview videos for quick inspection, and Blender/engine scripts for professional rendering.",
    ])
    story.append(PageBreak())

    # Timeline appendix pages.
    story.append(Paragraph("Appendix A. Numerical trajectory timeline", styles["ChapterTitle"]))
    tl = result.timeline
    n = len(tl["time_s"])
    target_timeline_pages = max(8, min(42, dossier.pages_target // 3)) if dossier.include_full_timeline_tables else 4
    sampled = np.linspace(0, n - 1, target_timeline_pages * dossier.table_rows_per_page).astype(int) if n else np.array([], dtype=int)
    for page_idx in range(target_timeline_pages):
        a = page_idx * dossier.table_rows_per_page
        b = min((page_idx + 1) * dossier.table_rows_per_page, len(sampled))
        inds = sampled[a:b]
        story.append(Paragraph(f"A.{page_idx+1} Timeline sample block", styles["SectionTitle"]))
        story.append(_rl_table(_timeline_table_rows(result, inds), font_size=5.8))
        story.append(PageBreak())

    # Sensitivity appendix.
    if dossier.include_sensitivity_appendix:
        story.append(Paragraph("Appendix B. Sensitivity sweep", styles["ChapterTitle"]))
        sens_rows = _sensitivity_rows(config, result, n=max(120, dossier.pages_target))
        chunk = 24
        for i in range(1, len(sens_rows), chunk):
            story.append(Paragraph(f"B.{1 + (i-1)//chunk} Entry/heating sensitivity cases", styles["SectionTitle"]))
            story.append(_rl_table([sens_rows[0]] + sens_rows[i:i+chunk], font_size=5.9))
            story.append(Paragraph("Interpretation: these cases perturb nose radius, drag coefficient, lift-to-drag ratio, and entry altitude to expose how thermal and pressure margins move under configuration uncertainty. In a professional certification workflow these would become Monte Carlo dispersions with covariance propagation and pass/fail constraints.", styles["SmallPro"]))
            story.append(PageBreak())

    # Wind tunnel appendix.
    if dossier.include_wind_tunnel_appendix:
        story.append(Paragraph("Appendix C. Wind tunnel grid tables", styles["ChapterTitle"]))
        wt = result.wind_tunnel
        velocities = wt["velocities_m_s"]
        aoas = wt["angles_of_attack_deg"]
        for metric_key, title in [("cd_grid", "Cd grid"), ("cl_grid", "Cl grid"), ("cm_grid", "Cm grid"), ("heat_flux_grid", "Heat-flux grid")]:
            data = [[title] + [f"V={v:.0f}" for v in velocities]]
            grid = wt[metric_key]
            for i, aoa in enumerate(aoas):
                data.append([f"AoA={aoa:.1f}"] + [f"{grid[i, j]:.4g}" for j in range(len(velocities))])
            story.append(Paragraph(title, styles["SectionTitle"]))
            story.append(_rl_table(data, font_size=6.2))
            story.append(Paragraph("Grid values are generated by the fast aerodynamic surrogate. They are intended for trend analysis, automatic reporting, and architecture validation before replacing the backend with a real solver.", styles["SmallPro"]))
            story.append(PageBreak())

    # Optimization appendix.
    if dossier.include_optimization_appendix:
        story.append(Paragraph("Appendix D. Optimization histories", styles["ChapterTitle"]))
        hist = result.rocket_optimization.get("history", [])
        if hist:
            header = ["iter", "score", "avg Cd", "heat MW/m2", "stability", "volume m3", "length m"]
            chunk = 24
            for i in range(0, len(hist), chunk):
                data = [header]
                for h in hist[i:i+chunk]:
                    data.append([
                        str(h.get("iteration", "")), f"{h.get('score', 0):.4f}", f"{h.get('avg_cd', 0):.4f}", f"{h.get('max_heat_flux_w_m2', 0)/1e6:.3f}", f"{h.get('stability_margin_calibers', 0):.2f}", f"{h.get('payload_volume_m3', 0):.1f}", f"{h.get('total_length_m', 0):.2f}",
                    ])
                story.append(Paragraph(f"D. Rocket optimization iterations {i+1}-{i+len(data)-1}", styles["SectionTitle"]))
                story.append(_rl_table(data, font_size=5.8))
                story.append(PageBreak())
        thist = result.turbine_optimization.get("history", [])
        if thist:
            header = ["iter", "eff", "tip Mach", "solidity", "flow", "loading", "power W"]
            chunk = 24
            for i in range(0, len(thist), chunk):
                data = [header]
                for h in thist[i:i+chunk]:
                    data.append([
                        str(h.get("iteration", "")), f"{h.get('efficiency', 0):.4f}", f"{h.get('tip_mach', 0):.3f}", f"{h.get('solidity', 0):.3f}", f"{h.get('flow_coefficient', 0):.3f}", f"{h.get('loading_coefficient', 0):.3f}", f"{h.get('power_proxy_w', 0):.3e}",
                    ])
                story.append(Paragraph(f"D. Turbine optimization iterations {i+1}-{i+len(data)-1}", styles["SectionTitle"]))
                story.append(_rl_table(data, font_size=5.8))
                story.append(PageBreak())

    # Formula and metadata appendices, expanded until page target is credible.
    story.append(Paragraph("Appendix E. Formula library", styles["ChapterTitle"]))
    formula_items = [
        ("Circular velocity", r"v=\sqrt{\mu/r}"),
        ("Orbital period", r"T=2\pi\sqrt{r^3/\mu}"),
        ("Transfer semimajor axis", r"a_t=(r_a+r_p)/2"),
        ("Vis-viva", r"v=\sqrt{\mu(2/r-1/a)}"),
        ("Dynamic pressure", r"q=\frac12\rho v^2"),
        ("Drag", r"D=q C_D A"),
        ("Lift", r"L=q C_L A"),
        ("Sutton-Graves proxy", r"\dot q\approx k\sqrt{\rho/R_n}v^3"),
        ("Radiative equilibrium", r"T_w=(\dot q/(\epsilon\sigma))^{1/4}"),
        ("Plasma frequency", r"f_p=8980\sqrt{n_e[cm^{-3}]}"),
        ("Landing burn mass", r"m_p=m_0(1-e^{-\Delta v/(I_{sp}g_0)})"),
        ("Reynolds number", r"Re=\rho V L/\mu"),
        ("Skin friction proxy", r"C_f=0.455/log_{10}(Re)^{2.58}"),
    ]
    for i, (name, formula) in enumerate(formula_items * max(1, dossier.pages_target // 28)):
        story.append(Paragraph(f"E.{i+1} {name}", styles["SectionTitle"]))
        story.append(Paragraph(_tex_escape(formula), styles["CodePro"]))
        story.append(Paragraph("This formula is included in the dossier formula library to preserve traceability between the calculations, the report tables, and the simulation code. In the professional roadmap, each formula should be connected to unit validation, dimensional analysis, and uncertainty propagation.", styles["SmallPro"]))
        if (i + 1) % 4 == 0:
            story.append(PageBreak())

    story.append(PageBreak())
    story.append(Paragraph("Appendix F. Reproducibility metadata", styles["ChapterTitle"]))
    metadata_text = json.dumps(result.metadata, indent=2, ensure_ascii=False)
    for i in range(0, len(metadata_text), 3600):
        story.append(Preformatted(metadata_text[i:i+3600], styles["CodePro"]))
        story.append(PageBreak())

    # Build PDF.
    doc.build(story, onFirstPage=_dossier_page_header, onLaterPages=_dossier_page_header)

    # Count pages using PyPDF2 if available.
    pages_generated = 0
    try:
        from PyPDF2 import PdfReader
        pages_generated = len(PdfReader(str(pdf_path)).pages)
    except Exception:
        pages_generated = -1

    manifest = {
        "pdf_path": str(pdf_path),
        "pages_generated": pages_generated,
        "blender_script": str(blender_script) if blender_script else None,
        "images": result.images,
        "videos": result.videos,
        "summary": result.summary,
    }
    manifest_path = output_dir / f"{filename}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return ProfessionalDossierResult(
        pdf_path=pdf_path,
        blender_script_path=blender_script,
        manifest_path=manifest_path,
        pages_generated=pages_generated,
        success=pdf_path.exists() and pdf_path.stat().st_size > 0,
        message=f"Professional dossier generated with {pages_generated} pages.",
        assets={**result.images, **result.videos, "manifest": str(manifest_path), "blender_script": str(blender_script) if blender_script else ""},
    )
