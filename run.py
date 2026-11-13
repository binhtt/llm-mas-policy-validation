"""Reexecute frozen interactive-assistant artifacts; no generation or API calls."""
import argparse,csv,hashlib,json,sys,time,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'tool_source'
sys.path.insert(0,str(SOURCE if SOURCE.exists() else ROOT.parent/'mas_study_v04'))
from catalog import TASKS,BUNDLES
from study import evaluate

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',default='results/reproduced');args=parser.parse_args()
 out=Path(args.out);out=out if out.is_absolute() else ROOT/out
 if out.resolve()==(ROOT/'results'/'reported').resolve():raise ValueError('Reported evidence is immutable; choose a different output directory.')
 out.mkdir(parents=True,exist_ok=True);rows=[];scenario_rows=[];frozen=json.loads((ROOT/'frozen_candidates_sha256.json').read_text())
 for task in TASKS:
  name=task+('.json' if task in BUNDLES else '.py');path=ROOT/'candidates'/name
  assert hashlib.sha256(path.read_bytes()).hexdigest()==frozen[name],'Candidate changed after freeze: '+name
  for variant,src in [('pre_evolution_baseline',TASKS[task]['baseline']),('interactive_candidate',path.read_text())]:
   for split in ('development','final'):
    started=time.perf_counter();report=evaluate(src,task,split,20);elapsed=time.perf_counter()-started
    (out/f'{task}.{variant}.{split}.json').write_text(json.dumps(report,indent=2))
    rows.append(dict(task=task,variant=variant,split=split,passed=report['passed'],runs=report.get('runs',0),failed_runs=report.get('failed_runs',0),seconds=elapsed,sha256=hashlib.sha256(src.encode()).hexdigest()))
    for f in report.get('failures',[]):
     for violation in f.get('violations',['invalid_candidate']):scenario_rows.append(dict(task=task,variant=variant,split=split,scenario=f.get('scenario','parse'),seed=f.get('seed',''),violation=violation))
    print(task,variant,split,'PASS' if report['passed'] else 'FAIL','runs',report.get('runs'),flush=True)
 for name,data in [('evaluation.csv',rows),('failures.csv',scenario_rows)]:
  with (out/name).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=data[0].keys());w.writeheader();w.writerows(data)
 candidates=[r for r in rows if r['variant']=='interactive_candidate'];final=[r for r in candidates if r['split']=='final'];baselines=[r for r in rows if r['variant']=='pre_evolution_baseline' and r['split']=='final']
 summary=dict(study_type='developer_assisted_interactive_feasibility_run',candidate_artifacts=len(final),authored_policies=6,derived_bundles=3,candidate_final_passed=sum(r['passed'] for r in final),pre_evolution_baseline_final_passed=sum(r['passed'] for r in baselines),candidate_scenario_runs=sum(r['runs'] for r in candidates),baseline_and_candidate_scenario_runs=sum(r['runs'] for r in rows),candidate_failed_scenario_runs=sum(r['failed_runs'] for r in candidates),api_calls=0,independent_llm_trials=0,observed_repair_attempts=0,python=platform.python_version(),evaluation_seconds=sum(r['seconds'] for r in rows),interpretation='Feasibility evidence for these frozen artifacts only; evaluator-aware assistant authored the six policies and reused them in three bundles. Not independent LLM efficacy evidence.')
 (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
