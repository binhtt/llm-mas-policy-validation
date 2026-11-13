"""Independent trusted interpreter and integration scenarios."""
import copy,json,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from system import TradingMAS as BaseMAS
from policy_runtime import policy
from catalog import TASKS,BUNDLES

class MAS(BaseMAS):
 def __init__(self,fn,task):
  self.functions=fn if isinstance(fn,dict) else {task:fn};self.task=task;self.commands=[];self.drop_remaining=0;super().__init__()
 def decide(self,event,order,key):
  commands=self.functions[key](copy.deepcopy(event),copy.deepcopy(order))
  if not isinstance(commands,list) or len(commands)>3:raise ValueError('expected list with at most three commands')
  self.commands.append({'policy':key,'event':event,'order':order,'commands':copy.deepcopy(commands)})
  return commands
 def market(self,kind,d):
  if 'freshness' not in self.functions:return super().market(kind,d)
  cmds=self.decide({'kind':kind,**d},{},'freshness')
  if cmds not in ([],[{'type':'forward'}]):raise ValueError('invalid forward command')
  if cmds:self.send('analysis','quote',**d)
 def risk(self,kind,d):
  if 'reservation' not in self.functions:return super().risk(kind,d)
  oid=d['oid'];o=self.orders[oid]
  reserved=sum(v['price']*(v['qty']-v['filled']) for v in self.orders.values() if v['status']=='approved')
  cmds=self.decide({'kind':kind,'cash':self.cash,'reserved':reserved},{'price':o['price'],'qty':o['qty']},'reservation')
  if cmds not in ([],[{'type':'approve'}]):raise ValueError('invalid approve command')
  if cmds:
   self.approvals[oid]=(o['price'],o['qty']);o['status']='approved';self.send('execution','submit',oid=oid)
  else:o['status']='rejected'
 def execution(self,kind,d):
  if kind=='cancel':self.orders[d['oid']]['status']='cancelled';return
  oid=d['oid'];o=self.orders[oid]
  if 'retry' in self.functions:
   view={k:o[k] for k in ('price','qty','status')};view.update(order_id=oid,approved=self.approvals.get(oid)==(o['price'],o['qty']))
   cmds=self.decide({'kind':kind},view,'retry')
  else:
   # Fixed execution agent already supports idempotent retry for non-retry tasks.
   cmds=[] if self.approvals.get(oid)!=(o['price'],o['qty']) or o['status'] in ('filled','cancelled') else [{'type':'submit','client_order_id':oid,'price':o['price'],'qty':o['qty']}]
  for c in cmds:
   if not isinstance(c,dict) or set(c)!={'type','client_order_id','price','qty'} or c['type']!='submit' or not isinstance(c['client_order_id'],str) or len(c['client_order_id'])>100 or type(c['price'])!=int or type(c['qty'])!=int or min(c['price'],c['qty'])<=0:raise ValueError('invalid submission schema')
   if self.approvals.get(oid)!=(c['price'],c['qty']):self.error('approval_binding')
   if o['status'] in ('cancelled','filled'):self.error('submission_after_terminal')
   if self.drop_remaining:self.drop_remaining-=1;continue
   eid=c['client_order_id'];old=self.exchange_orders.get(eid)
   if old and (old['oid'],old['price'],old['qty'])!=(oid,c['price'],c['qty']):self.error('id_collision')
   if not old:self.exchange_orders[eid]={'oid':oid,'price':c['price'],'qty':c['qty'],'filled':0,'age':o['age']}
 def reconciliation(self,kind,d):
  key=next((k for k in ('partial','dedup','late_fill') if k in self.functions),None)
  if key is None:return super().reconciliation(kind,d)
  o=self.orders[d['oid']];event={'kind':kind,'qty':d['qty'],'price':d['price'],'seen':d['fid'] in self.seen_fills}
  cmds=self.decide(event,{k:o[k] for k in ('qty','filled','status')},key);self.seen_fills.add(d['fid'])
  for c in cmds:
   if not isinstance(c,dict) or set(c)!={'type','qty'} or c['type']!='apply_fill' or type(c['qty'])!=int or not 0<c['qty']<=100:raise ValueError('invalid fill command')
   self.cash-=c['qty']*d['price'];self.position+=c['qty'];o['filled']+=c['qty']
   if o['filled']>=o['qty']:o['status']='filled'

DEV={
'retry':['normal','retry_lost','retry_ack','cancel_timeout','unapproved'],
'freshness':['normal','stale','fresh_boundary','partial','qty_limit'],
'reservation':['normal','pending_cash','budget_equal','qty_limit','duplicate'],
'partial':['normal','partial','duplicate','late','budget_equal'],
'dedup':['normal','duplicate','partial','late','qty_limit'],
'late_fill':['normal','late','partial','duplicate','budget_equal']}
for bundle,parts in BUNDLES.items():
 DEV[bundle]=list(dict.fromkeys(n for part in parts for n in DEV[part]))
FINAL_EXTRA=['repeated_loss','partial_timeout','filled_timeout','two_orders','duplicate_timeouts','stale_boundary','pending_after_partial','late_duplicate','split_interleaving','joint_recovery']

def scenario(fn,task,name,seed,final=False):
 r=random.Random(seed+10000*final);s=MAS(fn,task);p=r.randint(35,85);q=r.randint(2,4);expected=1
 if name in ('stale','stale_boundary'):age=6 if name=='stale_boundary' else r.randint(7,20);expected=0
 else:age=5 if name=='fresh_boundary' else 0
 if name=='budget_equal':p=100;q=10
 if name=='qty_limit':p=20;q=11;expected=0
 if name in ('pending_cash','pending_after_partial'):p=r.randint(60,90);q=10
 if name=='joint_recovery':p=60;q=10;s.drop_remaining=1
 if name=='retry_lost':s.drop_remaining=1
 if name=='repeated_loss':s.drop_remaining=r.randint(2,4)
 s.quote(p,q,age);s.run()
 def timeout(oid='o1',n=1):
  for _ in range(n):s.send('execution','timeout',oid=oid);s.run()
 def fill(oid,qty,fid,dup=False):
  eid=next((eid for eid,e in s.exchange_orders.items() if e['oid']==oid),None)
  if eid is not None:s.fill(eid,qty,fid,duplicate=dup)
 if name=='joint_recovery':
  s.quote(p,q);s.run();timeout(n=2);fill('o1',1,'joint-p1',True);timeout()
  s.quote(p,q,age=9);s.run();s.send('execution','cancel',oid='o1');s.run();fill('o1',1,'joint-p2',True);expected=1
 elif name in ('retry_lost','retry_ack','repeated_loss','duplicate_timeouts'):timeout(n=6 if name=='repeated_loss' else 3)
 elif name in ('pending_cash','two_orders'):
  s.quote(p,q);s.run();expected=1 if name=='pending_cash' else 2
  if name=='two_orders':timeout('o1');timeout('o2')
 elif name=='pending_after_partial':
  fill('o1',1,'p1');s.quote(p,q);s.run();expected=1
 elif name in ('partial','partial_timeout'):
  fill('o1',1,'p1')
  if name=='partial_timeout':timeout()
 elif name=='duplicate':fill('o1',q,'f1',True)
 elif name in ('late','late_duplicate'):
  s.send('execution','cancel',oid='o1');s.run();fill('o1',1,'late',name=='late_duplicate')
 elif name=='cancel_timeout':
  s.send('execution','cancel',oid='o1');s.run();timeout()
 elif name=='filled_timeout':fill('o1',q,'f1');timeout()
 elif name=='unapproved':
  s.exchange_orders.clear();s.approvals.clear();s.orders['o1']['status']='approved';timeout();expected=0
 elif name=='split_interleaving':
  s.quote(p,q);s.run();expected=2
  actions=[('fill','o1'),('fill','o2'),('timeout','o1'),('timeout','o2')];r.shuffle(actions)
  for action,oid in actions:
   if action=='fill':fill(oid,1,'interleave-'+oid,True)
   else:timeout(oid)
 if len(s.exchange_orders)!=expected:s.error('functional_order_count')
 # Deliver remaining legitimate fills; observer reconstructs ledger from exchange fill records.
 for i,(eid,e) in enumerate(list(s.exchange_orders.items())):
  rem=e['qty']-e['filled']
  if rem:s.fill(eid,rem,'end-'+str(i),duplicate=final)
 s.final_check()
 return dict(scenario=name,seed=seed,violations=s.errors,trace=s.trace,policy_calls=s.commands)

def evaluate(source,task,split='development',seeds=10):
 try:
  if task in BUNDLES:
   sources=json.loads(source)
   if not isinstance(sources,dict) or set(sources)!=set(BUNDLES[task]) or any(not isinstance(s,str) for s in sources.values()):raise ValueError('bundle keys/source strings mismatch')
   fn={key:policy(value) for key,value in sources.items()}
  else:fn=policy(source)
 except Exception as e:return dict(passed=False,runs=0,passed_runs=0,failed_runs=1,failures=[dict(error=type(e).__name__+': '+str(e))])
 failures=[];runs=0
 for name in list(dict.fromkeys(DEV[task]+(FINAL_EXTRA if split=='final' else []))):
  for seed in range(seeds):
   runs+=1
   try:res=scenario(fn,task,name,seed,split=='final')
   except Exception as e:res=dict(scenario=name,seed=seed,violations=['runtime_error'],error=type(e).__name__+': '+str(e))
   if res['violations']:failures.append(res)
 return dict(passed=not failures,runs=runs,passed_runs=runs-len(failures),failed_runs=len(failures),failures=failures)
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_CPU,(8,8));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
 try:
  req=json.loads(sys.stdin.read());print(json.dumps(evaluate(req['source'],req['task'],req['split'],req['seeds'])))
 except Exception as e:print(json.dumps(dict(passed=False,runs=0,passed_runs=0,failed_runs=1,failures=[dict(error=type(e).__name__+': '+str(e))])))
