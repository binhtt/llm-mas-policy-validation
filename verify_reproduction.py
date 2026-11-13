"""Compare behavioral evidence to archived results, excluding timings."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FIELDS=('task','variant','split','passed','runs','failed_runs','sha256')
def load(directory):
 with (directory/'evaluation.csv').open(newline='') as f:return sorted(tuple(r[k] for k in FIELDS) for r in csv.DictReader(f))
def main():
 expected=ROOT/'results'/'reported';actual=ROOT/'results'/'reproduced'
 if load(expected)!=load(actual):raise SystemExit('FAIL: behavioral records differ')
 e=json.loads((expected/'summary.json').read_text());a=json.loads((actual/'summary.json').read_text())
 for key in ('candidate_artifacts','candidate_final_passed','candidate_scenario_runs','baseline_and_candidate_scenario_runs','candidate_failed_scenario_runs','api_calls','independent_llm_trials','observed_repair_attempts'):
  if e[key]!=a[key]:raise SystemExit('FAIL: '+key)
 print('PASS: all 36 behavioral records and summary counts reproduce.')
if __name__=='__main__':main()
