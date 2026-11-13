"""Deterministic message-driven stock-trading MAS; integer money units."""
from dataclasses import dataclass, asdict
from collections import deque

@dataclass(frozen=True)
class Config:
    stale_check: bool = True
    risk_gate: bool = True
    bind_approval: bool = True
    reserve_cash: bool = True
    stable_retry_id: bool = True
    dedup_fills: bool = True
    partial_accounting: bool = True
    late_fill_accounting: bool = True

class TradingMAS:
    def __init__(self, config=Config(), cash=1000):
        self.config=config; self.initial_cash=cash; self.cash=cash; self.position=0
        self.queue=deque(); self.trace=[]; self.orders={}; self.approvals={}
        self.exchange_orders={}; self.seen_fills=set(); self.fills=[]; self.counter=0
        self.delivered={}; self.errors=[]
        self.agents={'market':self.market,'analysis':self.analysis,'portfolio':self.portfolio,
                     'risk':self.risk,'execution':self.execution,'reconciliation':self.reconciliation}
    def send(self, agent, kind, **data): self.queue.append((agent,kind,data))
    def run(self):
        steps=0
        while self.queue:
            agent,kind,data=self.queue.popleft(); steps+=1
            if steps>1000: raise RuntimeError('message budget exceeded')
            self.trace.append({'step':len(self.trace),'agent':agent,'kind':kind,'data':dict(data)})
            self.agents[agent](kind, data)
            self.check()
    def market(self, kind,d):
        if kind!='quote': raise ValueError(kind)
        if self.config.stale_check and d['age']>5: return
        self.send('analysis','quote',**d)
    def analysis(self,kind,d):
        if d['signal']=='buy': self.send('portfolio','propose',price=d['price'],qty=d['qty'],age=d['age'])
    def portfolio(self,kind,d):
        self.counter+=1; oid='o'+str(self.counter)
        self.orders[oid]={**d,'status':'proposed','filled':0}
        self.send('risk','assess',oid=oid)
    def risk(self,kind,d):
        oid=d['oid']; o=self.orders[oid]
        reserved=sum(v['price']*(v['qty']-v['filled']) for v in self.orders.values() if v['status']=='approved') if self.config.reserve_cash else 0
        if o['price']*o['qty']<=self.cash-reserved and o['qty']<=10:
            self.approvals[oid]=(o['price'],o['qty']); o['status']='approved'
            self.send('execution','submit',oid=oid)
        else: o['status']='rejected'
    def execution(self,kind,d):
        oid=d['oid']; o=self.orders[oid]
        if kind=='cancel': o['status']='cancelled'; return
        if self.config.risk_gate and oid not in self.approvals: return
        if self.config.bind_approval and oid in self.approvals and self.approvals[oid]!=(o['price'],o['qty']): return
        eid=oid
        if kind=='retry' and not self.config.stable_retry_id: eid=oid+'-retry'
        if eid not in self.exchange_orders:
            self.exchange_orders[eid]={'oid':oid,'price':o['price'],'qty':o['qty'],'filled':0,'age':o['age']}
    def reconciliation(self,kind,d):
        fid=d['fid']; oid=d['oid']; o=self.orders[oid]
        if self.config.dedup_fills and fid in self.seen_fills: return
        self.seen_fills.add(fid)
        if o['status']=='cancelled' and not self.config.late_fill_accounting: return
        qty=d['qty'] if self.config.partial_accounting else o['qty']
        self.cash-=qty*d['price']; self.position+=qty; o['filled']+=qty
        if o['filled']>=o['qty']: o['status']='filled'
    def quote(self,price=100,qty=2,age=0):
        self.send('market','quote',price=price,qty=qty,age=age,signal='buy')
    def fill(self,eid,qty,fid,duplicate=False):
        e=self.exchange_orders[eid]
        if qty<=0 or qty>e['qty']-e['filled']: raise ValueError('invalid exchange fill')
        e['filled']+=qty
        f={'fid':fid,'oid':e['oid'],'price':e['price'],'qty':qty}
        self.fills.append(f)
        self.send('reconciliation','fill',**f)
        if duplicate: self.send('reconciliation','fill',**f)
        self.run()
    def check(self):
        # Independent observer: approved submissions and committed cash exposure.
        for e in self.exchange_orders.values():
            if self.approvals.get(e['oid'])!=(e['price'],e['qty']): self.error('approval_binding')
            if e['age']>5: self.error('fresh_market_data')
        logical=[e['oid'] for e in self.exchange_orders.values()]
        if len(logical)!=len(set(logical)): self.error('idempotent_submission')
        exposure=sum(e['price']*e['qty'] for e in self.exchange_orders.values())
        if exposure>self.initial_cash: self.error('cash_exposure')
        if self.cash<0: self.error('nonnegative_cash')
    def error(self,name):
        if name not in self.errors: self.errors.append(name)
    def final_check(self):
        qty=sum(f['qty'] for f in self.fills); value=sum(f['qty']*f['price'] for f in self.fills)
        if self.position!=qty or self.cash!=self.initial_cash-value: self.error('ledger_conservation')
        self.check(); return self.errors
