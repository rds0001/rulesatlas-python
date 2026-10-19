"""Two-lift, three-attempt weightlifting with ascending bar order."""
from copy import deepcopy
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
WEIGHT=dict(type='integer',minimum=20,maximum=500)
def best(attempts):return max((a['weight_kg'] for a in attempts if a['passed']),default=0)
def candidates(d):return [i for i in range(8) if d['declared'][i] is not None]
def next_lifter(d):return min(candidates(d),key=lambda i:(d['declared'][i],len(d['attempts'][d['lift']][i]),d['lots'].index(i)),default=None)
def minimum(d,i):
 a=d['attempts'][d['lift']][i]
 return max(d['bar_kg'],a[-1]['weight_kg']+int(a[-1]['passed']) if a else 20)
def settle(d):
 if not candidates(d):d['phase']='review'
def validate(d):
 serials=[]
 for lift,group in enumerate(d['attempts']):
  for attempts in group:
   last=19
   for a in attempts:
    if a['weight_kg']<last:fail('Attempt weight falls below the required next load',code='INVALID_STATE')
    last=a['weight_kg']+int(a['passed']);serials.append(a['sequence'])
   if lift>d['lift'] and attempts:fail('Future lift already contains attempts',code='INVALID_STATE')
 if sorted(serials)!=list(range(1,len(serials)+1)):fail('Attempt sequence must be unique and contiguous',code='INVALID_STATE')
 if sorted(d['lots'])!=list(range(8)):fail('Lot order must be a permutation',code='INVALID_STATE')
 if d['phase']=='setup':
  if d['bar_kg']!=20 or any(d['attempts'][d['lift']]) or any(x is not None for x in d['declared']) or any(d['changes']) or any(d['withdrawn']):fail('Lift setup must precede declarations',code='INVALID_STATE')
 else:
  for i,a in enumerate(d['attempts'][d['lift']]):
   if d['disqualified'][i] and not d['withdrawn'][i]:fail('Disqualified entrants cannot continue',code='INVALID_STATE')
   if (d['declared'][i] is None)!=(len(a)==3 or d['withdrawn'][i]):fail('Remaining attempts require a declared weight',code='INVALID_STATE')
   if d['declared'][i] is not None and d['declared'][i]<minimum(d,i):fail('Declared weight is below the current minimum',code='INVALID_STATE')
  if (d['phase'] in ('ready','called'))!=bool(candidates(d)):fail('Phase and available attempts disagree',code='INVALID_STATE')
 if d['phase']=='finished' and d['lift']!=1:fail('Both lifts must be completed',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase'];lift=d['lift']
 if k=='declare_openers':
  fields(p,dict(weights_kg=dict(type='array',minItems=8,maxItems=8,items=WEIGHT)),'/params')
  if phase!='setup':fail('Opening declarations are already recorded')
  d['declared']=[None if d['disqualified'][i] else w for i,w in enumerate(p['weights_kg'])];d['withdrawn']=d['disqualified'][:];d['phase']='ready';settle(d)
 elif k=='change_declaration':
  fields(p,dict(participant=INDEX,weight_kg=WEIGHT),'/params');i=p['participant']
  if phase not in ('ready','called') or d['declared'][i] is None or d['changes'][i]>=2 or p['weight_kg']<minimum(d,i) or p['weight_kg']==d['declared'][i]:fail('At most two valid declaration changes are allowed per attempt')
  if phase=='called' and i!=next_lifter(d):fail('During a call, only the called lifter can change the declaration')
  d['declared'][i]=p['weight_kg'];d['changes'][i]+=1
  if phase=='called':d['phase']='ready'
 elif k=='call_next':
  fields(p,{},'/params')
  if phase!='ready':fail('No lifter can be called now')
  d['bar_kg']=d['declared'][next_lifter(d)];d['phase']='called'
 elif k in ('judge_attempt','time_expired'):
  fields(p,dict(votes=dict(type='array',minItems=3,maxItems=3,items=dict(type='boolean'))) if k=='judge_attempt' else {},'/params')
  if phase!='called':fail('Call the lifter before judging the attempt')
  i=next_lifter(d);passed=k=='judge_attempt' and sum(p['votes'])>=2
  seq=1+sum(len(a) for group in d['attempts'] for a in group)
  d['attempts'][lift][i].append(dict(weight_kg=d['declared'][i],passed=passed,sequence=seq))
  d['declared'][i]=None if len(d['attempts'][lift][i])==3 else d['declared'][i]+int(passed)
  d['changes'][i]=0;d['phase']='ready';settle(d)
 elif k=='withdraw_remaining':
  fields(p,dict(participant=INDEX),'/params');i=p['participant']
  if phase not in ('ready','called') or d['declared'][i] is None:fail('No remaining attempts can be withdrawn')
  if phase=='called' and i!=next_lifter(d):fail('Resolve the current called attempt first')
  d['declared'][i]=None;d['withdrawn'][i]=True;d['phase']='ready';settle(d)
 elif k=='disqualify':
  fields(p,dict(participant=INDEX),'/params');i=p['participant']
  if phase not in ('ready','review') or d['disqualified'][i]:fail('Official exclusion requires a ready platform or result review')
  d['disqualified'][i]=True;d['withdrawn'][i]=True;d['declared'][i]=None
  if phase=='ready':settle(d)
 elif k=='confirm_lift':
  fields(p,{},'/params')
  if phase!='review':fail('Resolve every remaining attempt before confirmation')
  if lift==1:d['phase']='finished'
  else:d.update(lift=1,phase='setup',bar_kg=20,declared=[None]*8,changes=[0]*8,withdrawn=[False]*8)
 else:fail('Unknown weightlifting action')
 return d
def legal(state):
 d=state['data'];phase=d['phase'];specs={}
 if phase=='setup':specs['declare_openers']=dict(weights_kg=dict(type='array',minItems=8,maxItems=8,items=WEIGHT))
 if phase in ('ready','called'):specs.update(change_declaration=dict(participant=INDEX,weight_kg=WEIGHT),withdraw_remaining=dict(participant=INDEX))
 if phase=='ready':specs['call_next']={}
 if phase=='called':specs.update(judge_attempt=dict(votes=dict(type='array',minItems=3,maxItems=3,items=dict(type='boolean'))),time_expired={})
 if phase in ('ready','review'):specs['disqualify']=dict(participant=INDEX)
 if phase=='review':specs['confirm_lift']={}
 i=next_lifter(d);previous=max((a['sequence'],j) for group in d['attempts'] for j,attempts in enumerate(group) for a in attempts)[1] if any(a for group in d['attempts'] for a in group) else None
 seconds=120 if i is not None and previous==i and d['attempts'][d['lift']][i] else 60
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Lift phase, ascending load order, remaining attempts and declaration limits must permit the event.'],external_observations=['Official declaration received within its deadline, three referee votes or official expiration of the attempt clock.']) for k,v in specs.items()],constraints=dict(phase=phase,lift=d['lift'],next_participant=i,ordinary_attempt_seconds=seconds),completeness=False,reason='official_weightlifting_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';ranked=[]
 if done:
  for i in range(8):
   a,b=[best(g[i]) for g in d['attempts']]
   if a and b and not d['disqualified'][i]:
    achieved=min(x['sequence'] for x in d['attempts'][1][i] if x['passed'] and x['weight_kg']==b)
    ranked.append((-a-b,achieved,i))
  ranked.sort()
 winners=[state['players'][ranked[0][2]]['id']] if ranked else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=j+1,total_kg=-t) for j,(t,_,i) in enumerate(ranked)],reason='total_confirmed' if done else 'lift_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official lift confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
