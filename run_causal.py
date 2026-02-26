"""Clean runner for causal inference — no Unicode to stdout."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
# Force UTF-8 stdout to handle box-drawing characters
sys.stdout.reconfigure(encoding="utf-8")

from causal_inference import run_causal_inference

result = run_causal_inference()

print("\n=== CAUSAL EFFECTS SUMMARY ===")
for k, v in result["causal_effects"].items():
    print(f"  {k:<28s} {v['causal_effect']:+.4f}  [{v['method']}]")

print("\n=== INTERVENTIONS SUMMARY ===")
for k, v in result["interventions"].items():
    print(f"  {k:<30s} {v['original_sell_prob']:.0%} -> {v['new_sell_prob']:.0%}  "
          f"({v['recommendation'][:60]})")

print("\nDONE")

