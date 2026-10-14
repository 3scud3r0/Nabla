from pathlib import Path
import json

from nablamath.orbital import (
    OrbitalMissionConfig,
    OrbitalVehicleConfig,
    RocketShapeConfig,
    RocketMaterialConfig,
    WindTunnelConfig,
    TurbineDesignConfig,
    OptimizationConfig,
    VideoRenderConfig,
    ProfessionalDossierConfig,
    build_professional_orbital_dossier,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "generated_reports" / "orbital_v06_professional_demo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

vehicle = OrbitalVehicleConfig(
    name="Asteria-R Professional Reusable Orbital Vehicle",
    mass_initial=134_000.0,
    mass_dry=87_500.0,
    nose_radius=1.25,
    body_radius=4.5,
    body_length=46.0,
    reference_area=63.6,
    drag_coefficient=1.28,
    lift_to_drag=0.24,
    emissivity=0.84,
    landing_isp=330.0,
    landing_burn_start_altitude=2900.0,
    communications_frequency_hz=2.25e9,
)

shape = RocketShapeConfig(
    nose_length_m=9.5,
    body_length_m=39.0,
    body_radius_m=4.55,
    boat_tail_length_m=4.0,
    engine_exit_radius_m=1.28,
    fin_count=4,
    fin_root_chord_m=6.2,
    fin_tip_chord_m=2.3,
    fin_span_m=3.6,
    fin_sweep_deg=29.0,
)

material = RocketMaterialConfig(
    name="brushed stainless hull + black ceramic TPS + copper engine alloy",
    base_rgb=(0.80, 0.81, 0.84),
    accent_rgb=(0.10, 0.10, 0.11),
    engine_rgb=(0.78, 0.50, 0.19),
    glow_rgb=(1.00, 0.47, 0.18),
    metallic=0.92,
    roughness=0.19,
)

config_code = r'''
config = OrbitalMissionConfig(
    mission_name="Asteria-R professional engineering dossier",
    report_title="Asteria-R - Professional orbital, reentry, wind tunnel and turbine dossier",
    vehicle=vehicle,
    shape=shape,
    material=material,
    wind_tunnel=WindTunnelConfig(
        velocities_m_s=(120,250,500,900,1400,2200,3200,3800),
        angles_of_attack_deg=(-6,-2,0,4,8,12),
        altitude_m=2500,
    ),
    turbine=TurbineDesignConfig(
        radius_m=0.42,
        hub_radius_m=0.13,
        blade_count=30,
        chord_root_m=0.12,
        chord_tip_m=0.05,
        twist_root_deg=58,
        twist_tip_deg=18,
        rpm=34500,
        mass_flow_kg_s=44,
        pressure_ratio_target=15,
        stage_temperature_k=990,
    ),
    optimization=OptimizationConfig(enabled=True, random_seed=321, rocket_iterations=80, turbine_iterations=80),
    video=VideoRenderConfig(generate_videos=True, fps=4, mission_duration_s=3.0, wind_tunnel_duration_s=3.0),
    orbit_altitude_m=430000,
    perigee_target_m=36000,
    entry_interface_altitude_m=123000,
    dt_reentry=0.45,
)
'''

config = OrbitalMissionConfig(
    mission_name="Asteria-R professional engineering dossier",
    report_title="Asteria-R - Professional orbital, reentry, wind tunnel and turbine dossier",
    user_objectives=(
        "Generate a long professional dossier with dozens to hundreds of pages, preserving all input code, "
        "showing orbital mechanics, deorbit burn, reentry, pressure, temperature, plasma, blackout, wind tunnel, "
        "shape optimization, turbine optimization, MP4 previews, and a Blender script for cinematic production."
    ),
    user_input_code=config_code,
    vehicle=vehicle,
    shape=shape,
    material=material,
    wind_tunnel=WindTunnelConfig(
        velocities_m_s=(120, 250, 500, 900, 1400, 2200, 3200, 3800),
        angles_of_attack_deg=(-6, -2, 0, 4, 8, 12),
        altitude_m=2500,
    ),
    turbine=TurbineDesignConfig(
        radius_m=0.42,
        hub_radius_m=0.13,
        blade_count=30,
        chord_root_m=0.12,
        chord_tip_m=0.05,
        twist_root_deg=58,
        twist_tip_deg=18,
        rpm=34500,
        mass_flow_kg_s=44,
        pressure_ratio_target=15,
        stage_temperature_k=990,
    ),
    optimization=OptimizationConfig(enabled=True, random_seed=321, rocket_iterations=80, turbine_iterations=80),
    video=VideoRenderConfig(generate_videos=True, fps=4, mission_duration_s=3.0, wind_tunnel_duration_s=3.0, width=960, height=540),
    orbit_altitude_m=430_000.0,
    perigee_target_m=36_000.0,
    entry_interface_altitude_m=123_000.0,
    dt_reentry=0.45,
    max_reentry_time=4900.0,
    reentry_bank_angle_deg=31.0,
    spectral_xray_threshold_k=2.6e5,
)

dossier = ProfessionalDossierConfig(pages_target=100, table_rows_per_page=22)
result = build_professional_orbital_dossier(
    config,
    output_dir=OUTPUT_DIR,
    filename="asteria_r_professional_orbital_dossier",
    dossier=dossier,
)

summary_path = OUTPUT_DIR / "professional_result.json"
summary_path.write_text(json.dumps({
    "success": result.success,
    "message": result.message,
    "pdf_path": str(result.pdf_path),
    "pages_generated": result.pages_generated,
    "blender_script": str(result.blender_script_path) if result.blender_script_path else None,
    "manifest": str(result.manifest_path),
    "assets": result.assets,
}, indent=2, ensure_ascii=False), encoding="utf-8")
print(summary_path)
