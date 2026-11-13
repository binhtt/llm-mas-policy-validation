"""Versioned tasks. References used only for local validation, never prompts."""
RETRY_BASE='''def next_commands(event, order):
    if event["kind"] == "submit" and order["approved"] and order["status"] == "approved":
        return [{"type": "submit", "client_order_id": order["order_id"], "price": order["price"], "qty": order["qty"]}]
    return []
'''
RETRY_OK=RETRY_BASE.replace('event["kind"] == "submit"','event["kind"] in ("submit", "timeout")')
MARKET_BASE='''def next_commands(event, order):
    return [{"type": "forward"}]
'''
MARKET_OK='''def next_commands(event, order):
    if event["age"] <= 5:
        return [{"type": "forward"}]
    return []
'''
RISK_BASE='''def next_commands(event, order):
    if order["price"] * order["qty"] <= event["cash"] and order["qty"] <= 10:
        return [{"type": "approve"}]
    return []
'''
RISK_OK=RISK_BASE.replace('event["cash"]','event["cash"] - event["reserved"]')
RECON_OK='''def next_commands(event, order):
    if not event["seen"]:
        return [{"type": "apply_fill", "qty": event["qty"]}]
    return []
'''
TASKS={
 'retry':dict(agent='execution',title='Idempotent timeout retry',baseline=RETRY_BASE,reference=RETRY_OK,requirement='Add timeout retry. Preserve one exchange order per business order even if the exchange accepted the request but its acknowledgement was lost. Never submit unapproved, cancelled or filled orders.',contract='event: kind="submit" or "timeout". order: order_id(str),price(int),qty(int),approved(bool),status(str). Return [] or [{"type":"submit","client_order_id":str,"price":int,"qty":int}]. Exchange deduplicates client_order_id. Preserve approved order contents.'),
 'freshness':dict(agent='market',title='Reject stale quotes',baseline=MARKET_BASE,reference=MARKET_OK,requirement='Forward quotes with age at most five ticks, reject older quotes, preserving ordinary fresh quote processing.',contract='event: kind="quote",age(nonnegative int),price(int),qty(int). order: {}. Return [] to reject or [{"type":"forward"}] to forward unchanged.'),
 'reservation':dict(agent='risk',title='Reserve cash across pending orders',baseline=RISK_BASE,reference=RISK_OK,requirement='Approve only if price*qty does not exceed current cash minus funds reserved for approved unfilled orders. Preserve the maximum quantity of ten. Equal available cash is allowed.',contract='event: kind="assess",cash(int),reserved(int). order: price(int),qty(positive int). Return [] to reject or [{"type":"approve"}]. Reservations are computed and applied by the trusted runtime.'),
 'partial':dict(agent='reconciliation',title='Account partial fills',baseline=RECON_OK.replace('event["qty"]','order["qty"]'),reference=RECON_OK,requirement='Support partial fills: apply only the quantity executed in this notification. Preserve execution-id deduplication and reconcile valid late notifications after cancellation.',contract='event: kind="fill",qty(positive int),price(int),seen(bool). order: qty(int total order size),filled(int already accounted),status(str). Return [] or [{"type":"apply_fill","qty":int}]. Runtime marks the notification seen after policy execution and applies price from the actual fill.'),
 'dedup':dict(agent='reconciliation',title='Deduplicate execution notifications',baseline='''def next_commands(event, order):
    return [{"type": "apply_fill", "qty": event["qty"]}]
''',reference=RECON_OK,requirement='Ignore execution notifications already processed, while continuing to process distinct fills, including partial fills and valid late notifications after cancellation.',contract='event: kind="fill",qty(positive int),price(int),seen(bool). order: qty(int total),filled(int already accounted),status(str). Return [] or [{"type":"apply_fill","qty":int}]. The trusted runtime maintains seen identifiers and applies notification price.'),
 'late_fill':dict(agent='reconciliation',title='Reconcile valid late fills',baseline=RECON_OK.replace('if not event["seen"]:', 'if not event["seen"] and order["status"] != "cancelled":'),reference=RECON_OK,requirement='Reconcile valid exchange fills delivered after a local cancel request, because the exchange may have executed before cancellation. Preserve deduplication and partial-fill accounting. This is not a complete exchange cancellation protocol.',contract='event: kind="fill",qty(positive int),price(int),seen(bool). order: qty(int total),filled(int already accounted),status(str). Return [] or [{"type":"apply_fill","qty":int}]. Trusted runtime updates its seen set after policy execution.')
}
COMMON='''You are evolving one agent in a stock-trading MAS simulator.
Architecture: Market Data -> Analysis -> Portfolio -> Risk -> Execution -> Reconciliation.
Other agents, exchange adapter, accounting observer and message runtime are fixed.
Output ONLY one function next_commands(event, order), no Markdown or explanation.
Use only if/elif/else, return, local-name assignments, literals, dictionaries/lists/tuples,
subscripts, comparisons, boolean operators, + - *, and event.get/order.get.
No imports, loops, comprehensions, decorators, annotations, other function calls,
recursion, I/O, globals or mutation of input dictionaries. This is a constrained
policy extension task, not arbitrary agent synthesis. Returning [] for everything
will fail functional tests. Requirements below override baseline limitations.
'''

BUNDLES={
 'bundle_market_retry':['freshness','retry'],
 'bundle_risk_retry':['reservation','retry'],
 'bundle_pipeline':['freshness','reservation','retry','partial'],
}
import json
for name,parts in BUNDLES.items():
 TASKS[name]=dict(agent='multiple',title='Coordinated update: '+', '.join(parts),parts=parts,
  baseline=json.dumps({part:TASKS[part]['baseline'] for part in parts},indent=2),
  reference=json.dumps({part:TASKS[part]['reference'] for part in parts},indent=2),
  requirement='Update all listed policies together, preserving requirements of every component.',contract='JSON object mapping each specified policy key to its complete function source string.')
def prompt(task):
 t=TASKS[task]
 if task in BUNDLES:
  common=COMMON.replace('Output ONLY one function next_commands(event, order), no Markdown or explanation.',
   'Output ONLY a JSON object with the required policy keys; each value is a complete Python source string defining next_commands(event, order). No Markdown or explanation.')
  sections=[]
  for part in t['parts']:
   c=TASKS[part];sections.append('Policy key: '+part+'; target agent: '+c['agent']+'\nRequirement: '+c['requirement']+'\nInterface: '+c['contract'])
  return common+'\nTask ID: '+task+'\nEdit all policies together. Required keys: '+', '.join(t['parts'])+'\n'+'\n'.join(sections)+'\nBASELINE BUNDLE:\n'+t['baseline']
 return COMMON+'\nTask ID: '+task+'\nTarget agent: '+t['agent']+'\nRequirement: '+t['requirement']+'\nInterface: '+t['contract']+'\nBASELINE:\n'+t['baseline']
