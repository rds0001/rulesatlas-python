"""Six-player foam-style dodgeball set with ordered outs and catch revival."""
from copy import deepcopy
from ..values import fields,fail
TEAM=dict(type='integer',minimum=0,maximum=1);PLAYER=dict(type='integer',minimum=0,maximum=5)
EVENT=dict(type='object',properties=dict(kind=dict(type='string',enum=['hit','boundary','catch']),team=TEAM,player=PLAYER,thrower=dict(PLAYER,nullable=True)),required=['kind','team','player','thrower'])
SCHEMAS=dict(start_set={},resolve_exchange=dict(events=dict(type='array',minItems=1,maxItems=24,items=EVENT)),disqualify_player=dict(team=TEAM,player=PLAYER),confirm_result={},restart_drawn_set={},concede=dict(team=TEAM))
def active(d,t):return [i for i,s in enumerate(d['status'][t]) if s=='active']
def settle(d):
 if any(not active(d,t) for t in (0,1)):d['phase']='review'
def eliminate(d,t,i):
 if d['status'][t][i]=='active':d['status'][t][i]='out';d['out_order'][t].append(i)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if len(set(d['out_order'][t]))!=len(d['out_order'][t]) or set(d['out_order'][t])!={i for i,s in enumerate(d['status'][t]) if s=='out'}:bad('The re-entry queue must contain each temporarily eliminated player exactly once')
 empty=any(not active(d,t) for t in (0,1))
 if d['phase']=='ready' and (any(s!='active' for team in d['status'] for s in team) or d['conceded_by'] is not None):bad('A new set starts with six active players per team')
 if d['phase']=='playing' and empty:bad('A fully eliminated team requires result review')
 if d['phase']=='review' and not empty:bad('Result review requires a fully eliminated team')
 if d['phase']=='finished' and not empty and d['conceded_by'] is None:bad('A finished set requires elimination or concession')
 if d['phase']!='finished' and d['conceded_by'] is not None:bad('A conceded set is finished')
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in SCHEMAS:fail('Unknown dodgeball event')
 fields(p,SCHEMAS[k],'/params')
 if d['phase']=='finished':fail('The set is finished')
 if k=='start_set':
  if d['phase']!='ready':fail('The set has already started')
  d['phase']='playing'
 elif k=='resolve_exchange':
  if d['phase']!='playing':fail('An exchange requires an active set')
  for e in p['events']:
   t=e['team'];i=e['player'];kind=e['kind']
   if d['status'][t][i]!='active':fail('The affected player must be active at this adjudicated event')
   if kind in ('hit','boundary'):
    if e['thrower'] is not None:fail('An out event does not identify a catch thrower')
    eliminate(d,t,i)
   else:
    if e['thrower'] is None:fail('A catch identifies the opposing thrower')
    eliminate(d,1-t,e['thrower'])
    if d['out_order'][t]:
     revived=d['out_order'][t].pop(0);d['status'][t][revived]='active'
  settle(d)
 elif k=='disqualify_player':
  if d['phase'] not in ('playing','review'):fail('Player exclusion requires a started set')
  t=p['team'];i=p['player']
  if d['status'][t][i]=='dismissed':fail('Player is already dismissed')
  d['status'][t][i]='dismissed';d['out_order'][t]=[x for x in d['out_order'][t] if x!=i];settle(d)
 elif k=='confirm_result':
  if d['phase']!='review':fail('Resolve an elimination before confirming the result')
  d['phase']='finished'
 elif k=='restart_drawn_set':
  if d['phase']!='review' or active(d,0) or active(d,1):fail('Only simultaneous complete elimination can be replayed')
  for t in (0,1):
   d['status'][t]=['dismissed' if s=='dismissed' else 'active' for s in d['status'][t]];d['out_order'][t]=[]
  if any(not active(d,t) for t in (0,1)):fail('A dismissed entire team cannot replay')
  d['phase']='playing'
 elif k=='concede':d['conceded_by']=p['team'];d['phase']='finished'
 return d
def legal(state):
 d=state['data'];names={'ready':['start_set','concede'],'playing':['resolve_exchange','disqualify_player','concede'],'review':['confirm_result','disqualify_player','concede'],'finished':[]}[d['phase']]
 if d['phase']=='review' and not active(d,0) and not active(d,1):names+=['restart_drawn_set']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Player eligibility, re-entry order and set phase must permit the event.'],external_observations=['Official ordered valid hits, boundary outs, catches and exclusions for one resolved exchange.']) for k in names],constraints=dict(active=[active(d,t) for t in (0,1)],next_reentry=[q[0] if q else None for q in d['out_order']]),completeness=False,reason='official_dodgeball_exchange_rulings')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=None
 if done:
  if d['conceded_by'] is not None:w=1-d['conceded_by']
  elif bool(active(d,0))!=bool(active(d,1)):w=0 if active(d,0) else 1
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('draw' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason='concession' if d['conceded_by'] is not None else 'set_finished' if done else 'exchange_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official resolution of the complete exchange.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
