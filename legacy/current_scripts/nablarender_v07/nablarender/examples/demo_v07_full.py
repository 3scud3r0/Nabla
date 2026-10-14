from pathlib import Path
from nablarender import export_all_three, RocketSpec, RenderReportConfig, build_render_report
out=Path(__file__).resolve().parent.parent/'generated_demo_v07'
bundle=export_all_three(str(out), RocketSpec(total_length_m=56.0,body_radius_m=4.6,fin_count=4,circum_segments=32))
pdf=build_render_report(RenderReportConfig(output_pdf=str(out/'nablarender_v07_professional_report.pdf'),target_pages=55), bundle, str(out), {'demo':'v0.7 full'})
bundle.report_pdf=pdf
print(bundle)
print('report_pdf=', pdf)
