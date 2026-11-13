"""Call-budget-matched study, resumable response cache, isolated evaluator."""
import csv,hashlib,json,os,random,re,subprocess,sys,tempfile,time
from pathlib import Path
from catalog import TASKS,BUNDLES,prompt
BASE=Path(__file__).resolve().parent
FILES=('system.py','policy_runtime.py','catalog.py','evaluator.py','study.py','analysis.py')
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def save(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False));tmp.replace(path)
def evaluate(source,task,split='development',seeds=10):
 with tempfile.TemporaryDirectory(prefix='mas-v03-') as td:
  root=Path(td)
  for f in FILES:(root/f).write_bytes((BASE/f).read_bytes())
  try:
   p=subprocess.run([sys.executable,'-I',str(root/'evaluator.py')],input=json.dumps(dict(source=source,task=task,split=split,seeds=seeds)),capture_output=True,text=True,timeout=15,cwd=root,env={'PATH':os.defpath,'LANG':'C.UTF-8'})
   if p.returncode:raise ValueError('worker_exit_'+str(p.returncode))
   return json.loads(p.stdout)
  except (subprocess.TimeoutExpired,ValueError) as e:return dict(passed=False,runs=0,passed_runs=0,failed_runs=1,failures=[dict(error=str(e))])
def extract(text):
 text=text.strip();m=re.fullmatch(r'```(?:python|json)?\s*\n(.*?)\n```',text,re.S);return m.group(1) if m else text

def compact_feedback(report):
 items=[];seen=set()
 for f in report['failures']:
  label=f.get('scenario',f.get('error'))
  if label not in seen:seen.add(label);items.append(f)
  if len(items)==3:break
 return json.dumps(items,ensure_ascii=False)[:14000]
def rank(record):
 d=record['dev'];return (bool(d['passed']),d.get('passed_runs',0)/max(1,d.get('runs',0)))

def run(client,model,out,tasks=None,trials=1,budget=2,seeds=10,max_output_tokens=3000,mode='openai_api'):
 tasks=list(tasks or TASKS)
 if trials<1 or budget<1 or budget>4 or seeds<1 or any(t not in TASKS for t in tasks) or len(tasks)!=len(set(tasks)):raise ValueError('invalid settings')
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 config=dict(version='0.4',model=model,tasks=tasks,trials=trials,budget=budget,seeds=seeds,max_output_tokens=max_output_tokens,mode=mode,source_hashes={f:sha((BASE/f).read_text()) for f in FILES},selection='highest development pass fraction; earliest wins ties',candidate_formats='Single tasks: Python; bundle tasks: JSON mapping policy keys to Python source',arms='shared initial, independent resampling, feedback repair; fixed call budgets')
 if (out/'config.json').exists():
  if json.loads((out/'config.json').read_text())!=config:raise ValueError('Resume settings/source differ from original; use a new output directory.')
 else:save(out/'config.json',config)
 total_calls=len(tasks)*trials*(2*budget-1);calls=0;cached=0;rows=[]
 def generate(messages,stem):
  nonlocal calls,cached
  request=dict(model=model,input=messages,store=False,max_output_tokens=max_output_tokens);fingerprint=sha(json.dumps(request,sort_keys=True))
  response_file=stem.with_suffix('.response.json');meta_file=stem.with_suffix('.meta.json')
  if response_file.exists():
   meta=json.loads(meta_file.read_text())
   if meta['request_sha256']!=fingerprint:raise ValueError('Cached request mismatch; use a new run directory.')
   dump=json.loads(response_file.read_text());elapsed=meta['seconds'];cached+=1
  else:
   save(stem.with_suffix('.request.json'),request);start=time.perf_counter()
   try:r=client.responses.create(**request)
   except Exception as e:
    save(stem.with_suffix('.error.json'),{'type':type(e).__name__,'message':'API failed; no implicit retry. Resume with unchanged settings to reuse completed calls.'})
    raise RuntimeError('API error: '+type(e).__name__+'. Partial artifacts retained; keys are not logged.') from None
   calls+=1;elapsed=time.perf_counter()-start;dump=r.model_dump(mode='json')
   # SDK output_text is a convenience property, not necessarily in model_dump.
   dump['_extracted_output_text']=r.output_text or ''
   save(meta_file,dict(request_sha256=fingerprint,seconds=elapsed))
   save(response_file,dump)
  src=extract(dump.get('_extracted_output_text','')) if dump.get('status','completed')=='completed' else ''
  stem.with_suffix('.bundle.json' if task in BUNDLES else '.py').write_text(src)
  usage=dump.get('usage') or {}
  return dict(source=src,response_id=dump.get('id'),returned_model=dump.get('model'),input_tokens=usage.get('input_tokens',0) or 0,output_tokens=usage.get('output_tokens',0) or 0,seconds=elapsed,source_sha256=sha(src))
 for task in tasks:
  for trial in range(trials):
   folder=out/task/f'trial_{trial:03d}';folder.mkdir(parents=True,exist_ok=True)
   initial_messages=[dict(role='user',content=prompt(task))]
   first=generate(initial_messages,folder/'initial')
   first['dev']=evaluate(first['source'],task,'development',seeds);save(folder/'initial.dev.json',first['dev'])
   arms={'initial':[first],'resample':[first],'feedback':[first]}
   order=['resample','feedback'];random.Random(trial+sum(map(ord,task))).shuffle(order)
   save(folder/'arm_order.json',order)
   for arm in order:
    history=list(initial_messages)
    for iteration in range(1,budget):
     if arm=='feedback':
      previous=arms[arm][-1]
      report=previous['dev']
      advice='Development tests passed. Review for other integration errors while preserving known behavior.' if report['passed'] else 'Development failures:\n'+compact_feedback(report)
      history += [dict(role='assistant',content=previous['source'] or '[No complete function returned]'),dict(role='user',content=advice+'\nReturn only the complete output in the task required format (function or JSON bundle).')]
      messages=history
     else:messages=initial_messages
     rec=generate(messages,folder/f'{arm}_{iteration:02d}');rec['dev']=evaluate(rec['source'],task,'development',seeds);arms[arm].append(rec)
     save(folder/f'{arm}_{iteration:02d}.dev.json',rec['dev'])
     print(task,'trial',trial+1,arm,'candidate',iteration+1,'dev=',rec['dev']['passed'],flush=True)
   # Lock selections using development only, before ANY final evaluation.
   selected={arm:max(range(len(records)),key=lambda i:rank(records[i])) for arm,records in arms.items()}
   save(folder/'selection.json',selected)
   for arm,records in arms.items():
    idx=selected[arm];rec=records[idx];final=evaluate(rec['source'],task,'final',seeds);save(folder/f'{arm}.final.json',final)
    rows.append(dict(task=task,trial=trial,arm=arm,selected_index=idx,development_passed=rec['dev']['passed'],final_passed=final['passed'],final_runs=final.get('runs',0),final_failed_runs=final.get('failed_runs',0),candidate_count=len(records),input_tokens=sum(r['input_tokens'] for r in records),output_tokens=sum(r['output_tokens'] for r in records),seconds=sum(r['seconds'] for r in records)))
    save(folder/f'{arm}.candidates.json',[{k:v for k,v in r.items() if k not in ('source','dev')} for r in records])
   with (out/'trials.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 summary=dict(mode=mode,expected_unique_requests=total_calls,completed_unique_requests=calls+cached,new_api_requests=calls if mode=='openai_api' else 0,new_mock_requests=calls if mode!='openai_api' else 0,cached_requests=cached,task_trial_pairs=len(tasks)*trials,arm_results=len(rows),source_hashes=config['source_hashes'],limitations=['Six single-policy tasks plus three simultaneous multi-policy bundles; not arbitrary agent synthesis.','Matched calls/output caps; feedback prompts may use more input tokens.','Deterministic FIFO simulator; selected final scenarios and numeric inputs vary.','Final suites excluded from prompts but visible to notebook owner.','One simulator/domain; no exhaustive verification or profitability claims.'])
 raw=[json.loads(p.read_text()) for p in out.rglob('*.response.json')]
 summary['unique_request_input_tokens']=sum((r.get('usage') or {}).get('input_tokens',0) or 0 for r in raw)
 summary['unique_request_output_tokens']=sum((r.get('usage') or {}).get('output_tokens',0) or 0 for r in raw)
 summary['unique_response_files']=len(raw)
 save(out/'summary.json',summary);return summary
