"""Descriptive, paired analysis; inference units are generated task/trial pairs."""
import csv,json,math
from collections import Counter
from pathlib import Path

def wilson(k,n):
 if not n:return [None,None]
 z=1.959963984540054;p=k/n;d=1+z*z/n
 center=(p+z*z/(2*n))/d;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
 return [max(0,center-half),min(1,center+half)]
def analyze(out):
 out=Path(out);rows=list(csv.DictReader((out/'trials.csv').open()))
 truth=lambda v:str(v).lower()=='true'
 summaries=[]
 for task in sorted({r['task'] for r in rows})+['ALL']:
  for arm in ('initial','resample','feedback'):
   group=[r for r in rows if r['arm']==arm and (task=='ALL' or r['task']==task)]
   n=len(group);k=sum(truth(r['final_passed']) for r in group)
   summaries.append(dict(task=task,arm=arm,passed=k,total=n,rate=k/n if n else None,wilson95=wilson(k,n)))
 paired={}
 for r in rows:paired.setdefault((r['task'],r['trial']),{})[r['arm']]=truth(r['final_passed'])
 wins=sum(x['feedback'] and not x['resample'] for x in paired.values());losses=sum(x['resample'] and not x['feedback'] for x in paired.values());discordant=wins+losses
 p=min(1.0,2*sum(math.comb(discordant,i) for i in range(min(wins,losses)+1))/2**discordant) if discordant else 1.0
 transitions=[]
 for arm in ('resample','feedback'):
  failed_initial=[x for x in paired.values() if not x['initial']]
  passed_initial=[x for x in paired.values() if x['initial']]
  recovered=sum(x[arm] for x in failed_initial)
  regressed=sum(not x[arm] for x in passed_initial)
  transitions.append(dict(arm=arm,recovered=recovered,initially_failed=len(failed_initial),
                          recovery_wilson95=wilson(recovered,len(failed_initial)),
                          regressed=regressed,initially_passed=len(passed_initial)))
 result=dict(initial_to_selected=transitions,by_task_and_arm=summaries,paired_feedback_vs_resample=dict(feedback_only=wins,resample_only=losses,discordant=discordant,exact_mcnemar_p=p),notes=['Wilson intervals and pooled exact test are exploratory; heterogeneous tasks and small samples limit inference.','Seeds/scenario executions are NOT independent LLM trials.','Do not claim general repair success from mock outputs or one task/trial.'])
 counts=Counter()
 for path in out.rglob('*.final.json'):
  task=path.parent.parent.name;arm=path.name.split('.')[0]
  for failure in json.loads(path.read_text()).get('failures',[]):
   for violation in failure.get('violations',['candidate_invalid']):
    counts[(task,arm,failure.get('scenario','parse_or_schema'),violation)]+=1
 with (out/'error_breakdown.csv').open('w',newline='') as f:
  writer=csv.writer(f);writer.writerow(['task','arm','scenario','violation','failed_scenario_runs'])
  for key,count in sorted(counts.items()):writer.writerow([*key,count])
 result['error_breakdown_file']='error_breakdown.csv'
 (out/'analysis.json').write_text(json.dumps(result,indent=2))
 mode=json.loads((out/'config.json').read_text())['mode']
 lines=['# MAS evolution study results','',f'Mode: **{mode}**. '+('MOCK ONLY — NOT LLM evidence.' if mode!='openai_api' else 'API responses and prompts are archived.'),'','| Task | Arm | Final passed | Rate |','|---|---|---:|---:|']
 for s in summaries:lines.append(f"| {s['task']} | {s['arm']} | {s['passed']}/{s['total']} | {s['rate']:.1%} |")
 lines+=['','| Arm | Recovered among initial failures | Regressed among initial passes |',
         '|---|---:|---:|']
 for t in transitions:
  lines.append(f"| {t['arm']} | {t['recovered']}/{t['initially_failed']} | {t['regressed']}/{t['initially_passed']} |")
 lines+=['','## Paired comparison',f'Feedback-only passes: {wins}; resampling-only passes: {losses}.',f'Exploratory exact McNemar p={p:.6g}.','',*result['notes'],'','Matched request budgets do not mean matched token costs. See trials.csv for arm usage. Error frequencies in error_breakdown.csv count scenario runs, not independent LLM samples.']
 (out/'REPORT.md').write_text('\n'.join(lines));return result
if __name__=='__main__':
 import sys
 print(json.dumps(analyze(sys.argv[1]),indent=2))
