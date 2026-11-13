"""Deterministic validation only. No real OpenAI calls."""
import json,tempfile
from pathlib import Path
from catalog import TASKS,BUNDLES
from study import run,evaluate
from analysis import analyze

def main():
 validation=[]
 for task,t in TASKS.items():
  for split in ('development','final'):
   good=evaluate(t['reference'],task,split,20);bad=evaluate(t['baseline'],task,split,20)
   assert good['passed'],(task,split,good['failures'][:1])
   assert not bad['passed'],(task,split,'baseline should fail new requirement')
   reject=evaluate('def next_commands(event, order):\n    return []',task,split,2)
   assert not reject['passed']
   validation.append(dict(task=task,split=split,reference_passed=True,baseline_detected=True,reference_runs=good['runs'],baseline_runs=bad['runs']))
 for invalid in ('import os\n'+TASKS['retry']['reference'],'def next_commands(event, order):\n    while True: pass','def next_commands(event, order):\n    return open("x")','def next_commands(event, order):\n    return event.__class__','def next_commands(event, order):\n    order["approved"] = True\n    return []'):
  assert not evaluate(invalid,'retry')['passed']
 # A policy can pass development and still fail previously unseen interactions.
 overfit=TASKS['retry']['reference'].replace('order["order_id"]','"one-global-id"')
 assert evaluate(overfit,'retry','development')['passed']
 assert not evaluate(overfit,'retry','final')['passed']
 class Response:
  status='completed'
  def __init__(self,code):self.output_text=code
  def model_dump(self,mode):return dict(id='MOCK',model='MOCK',status='completed',usage=dict(input_tokens=0,output_tokens=0))
 class Fake:
  def __init__(self):self.responses=self;self.calls=0;self.fail_at=None
  def create(self,**kw):
   self.calls+=1
   if self.calls==self.fail_at:raise ConnectionError('mock interruption')
   text=kw['input'][0]['content'];task=text.split('Task ID: ')[1].split('\n')[0]
   assert 'FINAL_EXTRA' not in text and 'REFERENCE' not in text
   # Independent resamples deliberately retain the baseline; feedback gets oracle code.
   return Response(TASKS[task]['reference'] if len(kw['input'])>1 else TASKS[task]['baseline'])
 # Bundle schema and incomplete simultaneous updates must be rejected.
 for bundle,parts in BUNDLES.items():
  reject_bundle=json.dumps({part:'def next_commands(event, order):\n    return []' for part in parts})
  assert not evaluate(reject_bundle,bundle)['passed']
  malformed=json.dumps({parts[0]:TASKS[parts[0]]['reference']})
  assert not evaluate(malformed,bundle)['passed']
  for broken in parts:
   mixed={part:TASKS[part]['reference'] for part in parts};mixed[broken]=TASKS[broken]['baseline']
   assert not evaluate(json.dumps(mixed),bundle,'final',2)['passed'],(bundle,broken)
 root=Path('validation');root.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory() as td:
  fake=Fake();summary=run(fake,'MOCK',td,trials=2,budget=3,seeds=2,mode='mock')
  assert fake.calls==len(TASKS)*2*5==summary['expected_unique_requests']
  rows=analyze(td)['by_task_and_arm']
  assert all(r['passed']==r['total'] for r in rows if r['arm']=='feedback')
  assert all(r['passed']==0 for r in rows if r['arm'] in ('initial','resample'))
  second=run(fake,'MOCK',td,trials=2,budget=3,seeds=2,mode='mock')
  assert second['new_mock_requests']==0 and second['cached_requests']==len(TASKS)*2*5
  for name in ('analysis.json','REPORT.md','trials.csv','summary.json'):(root/('MOCK_'+name)).write_bytes((Path(td)/name).read_bytes())
 with tempfile.TemporaryDirectory() as td:
  fake=Fake();fake.fail_at=2
  try:run(fake,'MOCK',td,tasks=['retry'],budget=2,seeds=1,mode='mock')
  except RuntimeError:pass
  else:raise AssertionError('interruption not raised')
  fake.fail_at=None
  resumed=run(fake,'MOCK',td,tasks=['retry'],budget=2,seeds=1,mode='mock')
  assert resumed['cached_requests']==1 and resumed['new_mock_requests']==2
 (root/'oracle_validation.json').write_text(json.dumps(validation,indent=2))
 print('PASS: nine tasks including multi-agent bundles, reference/baseline/reject-all, invalid code, final-only fault, matched budgets, resume and interruption recovery. MOCK results are not LLM evidence.')
if __name__=='__main__':main()
