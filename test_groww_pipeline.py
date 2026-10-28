import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from groww_collector import collect_all_groww_sources
from sip_discovery_engine import run_sip_pipeline, get_opportunity_summary

data = collect_all_groww_sources(max_per_source=10)
print(f"Collected: {len(data['records'])} records from Groww multi-source engine")

pipeline_res = run_sip_pipeline(data["records"], llm_client=None)
print("Pipeline complete!")
print("\n=== Stages Summary ===")
for stage_name, stage_data in pipeline_res["stages"].items():
    print(f" - {stage_name}: {stage_data}")

hypotheses = pipeline_res["hypothesis_report"].get("hypotheses", [])
print(f"\n=== Hypotheses Generated ({len(hypotheses)}) ===")
for h in hypotheses[:3]:
    print(f"  * [{h.get('label', h.get('category'))}] Rank #{h.get('rank', 1)} (Score: {h.get('scores', {}).get('composite')})")
    print(f"    Problem: {h.get('problem_statement', '')[:100]}...")
    print(f"    Quotes count: {len(h.get('representative_quotes', []))}")


opps = get_opportunity_summary(pipeline_res)
print(f"\n=== Opportunities ({len(opps)}) ===")
for op in opps[:3]:
    print(f"  * {op['category']} -> {op['opportunity'][:90]}...")
