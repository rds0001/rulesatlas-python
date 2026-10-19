"""Three-lift powerlifting with round order and half-kilogram integer units."""
from copy import deepcopy
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
WEIGHT=dict(type='integer',minimum=40,maximum=1000)
def best(attempts):return max((a['weight_halfkg'] for a in attempts if a['passed']),default=0)
def candidates(d):return [i for i in range(8) if d['declared'][i] is not None]
def next_lifter(d):return min(candidates(d),key=lambda i:(len(d['attempts'][d['lift']][i]),d['declared'][i],d['lots'].index(i)),default=None)
def minimum(d,i):
 a=d['attempts'][d['lift']][i]
 return a[-1]['weight_halfkg']+5*int(a[-1]['passed']) if a else 40
def settle(d):
 if not candidates(d):d['phase']='review'
def validate(d):
 serials=[]
 for lift,group in enumerate(d['attempts']):
  for attempts in group:
   last=40
   for a in attempts:
    if a['weight_halfkg']%5 or a['weight_halfkg']<last:fail('Attempt weight falls below the required next load',code='INVALID_STATE')
    last=a['weight_halfkg']+5*int(a['passed']);serials.append(a['sequence'])
   if lift>d['lift'] and attempts:fail('Future lift already contains attempts',code='INVALID_STATE')
 if sorted(serials)!=list(range(1,len(serials)+1)):fail('Attempt sequence must be unique and contiguous',code='INVALID_STATE')
 if sorted(d['lots'])!=list(range(8)):fail('Lot order must be a permutation',code='INVALID_STATE')
 if d['phase']!='setup' and any(w is None for w in d['bodyweight_g']):fail('Official weigh-in is required',code='INVALID_STATE')
 if d['phase']=='setup':
  if d['bar_halfkg']!=40 or any(d['attempts'][d['lift']]) or any(x is not None for x in d['declared']) or any(d['changes']) or any(d['withdrawn']):fail('Lift setup must precede declarations',code='INVALID_STATE')
 else:
  for i,a in enumerate(d['attempts'][d['lift']]):
   if d['disqualified'][i] and not d['withdrawn'][i]:fail('Disqualified entrants cannot continue',code='INVALID_STATE')
   if (d['declared'][i] is None)!=(len(a)==3 or d['withdrawn'][i]):fail('Remaining attempts require a declared weight',code='INVALID_STATE')
   if d['declared'][i] is not None and (d['declared'][i]%5 or d['declared'][i]<minimum(d,i)):fail('Declared weight is below the current minimum',code='INVALID_STATE')
  if (d['phase'] in ('ready','called'))!=bool(candidates(d)):fail('Phase and available attempts disagree',code='INVALID_STATE')
 if d['phase']=='finished' and d['lift']!=2:fail('All three lifts must be completed',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase'];lift=d['lift']
 if k=='record_weigh_in':
  fields(p,dict(bodyweight_g=dict(type='array',minItems=8,maxItems=8,items=dict(type='integer',minimum=20000,maximum=300000))),'/params')
  if phase!='setup' or lift!=0:fail('Record official bodyweights before the first lift')
  d['bodyweight_g']=p['bodyweight_g'][:]
 elif k=='declare_openers':
  fields(p,dict(weights_halfkg=dict(type='array',minItems=8,maxItems=8,items=WEIGHT)),'/params')
  if phase!='setup':fail('Opening declarations are already recorded')
  if any(w is None for w in d['bodyweight_g']) or any(w%5 for w in p['weights_halfkg']):fail('Weigh-in and 2.5-kilogram loading increments are required')
  d['declaration_fixed']=[True]*8
  d['declared']=[None if d['disqualified'][i] else w for i,w in enumerate(p['weights_halfkg'])];d['withdrawn']=d['disqualified'][:];d['phase']='ready';settle(d)
 elif k=='change_declaration':
  fields(p,dict(participant=INDEX,weight_halfkg=WEIGHT),'/params');i=p['participant']
  n=len(d['attempts'][lift][i]);limit=1 if n==0 else 2 if lift==2 and n==2 else 0
  if phase!='ready' or d['declared'][i] is None or (d['declaration_fixed'][i] and d['changes'][i]>=limit) or p['weight_halfkg']%5 or p['weight_halfkg']<minimum(d,i) or p['weight_halfkg']==d['declared'][i]:fail('Declaration timing, change limit or loading increment is invalid')
  d['declared'][i]=p['weight_halfkg']
  if d['declaration_fixed'][i]:d['changes'][i]+=1
  d['declaration_fixed'][i]=True
 elif k=='call_next':
  fields(p,{},'/params')
  if phase!='ready':fail('No lifter can be called now')
  d['declaration_fixed'][next_lifter(d)]=True;d['bar_halfkg']=d['declared'][next_lifter(d)];d['phase']='called'
 elif k in ('judge_attempt','time_expired'):
  fields(p,dict(votes=dict(type='array',minItems=3,maxItems=3,items=dict(type='boolean'))) if k=='judge_attempt' else {},'/params')
  if phase!='called':fail('Call the lifter before judging the attempt')
  i=next_lifter(d);passed=k=='judge_attempt' and sum(p['votes'])>=2
  seq=1+sum(len(a) for group in d['attempts'] for a in group)
  d['attempts'][lift][i].append(dict(weight_halfkg=d['declared'][i],passed=passed,sequence=seq))
  d['declared'][i]=None if len(d['attempts'][lift][i])==3 else d['declared'][i]+5*int(passed)
  d['declaration_fixed'][i]=False;d['changes'][i]=0;d['phase']='ready';settle(d)
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
  if lift==2:d['phase']='finished'
  else:d.update(lift=lift+1,phase='setup',bar_halfkg=40,declared=[None]*8,changes=[0]*8,withdrawn=[False]*8)
 else:fail('Unknown powerlifting action')
 return d
def legal(state):
 d=state['data'];phase=d['phase'];specs={}
 if phase=='setup' and d['lift']==0:specs['record_weigh_in']=dict(bodyweight_g=dict(type='array',minItems=8,maxItems=8,items=dict(type='integer',minimum=20000,maximum=300000)))
 if phase=='setup':specs['declare_openers']=dict(weights_halfkg=dict(type='array',minItems=8,maxItems=8,items=WEIGHT))
 if phase=='ready':specs.update(change_declaration=dict(participant=INDEX,weight_halfkg=WEIGHT),withdraw_remaining=dict(participant=INDEX))
 if phase=='ready':specs['call_next']={}
 if phase=='called':specs['withdraw_remaining']=dict(participant=INDEX)
 if phase=='called':specs.update(judge_attempt=dict(votes=dict(type='array',minItems=3,maxItems=3,items=dict(type='boolean'))),time_expired={})
 if phase in ('ready','review'):specs['disqualify']=dict(participant=INDEX)
 if phase=='review':specs['confirm_lift']={}
 i=next_lifter(d);seconds=60
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Lift phase, round and load order, remaining attempts and declaration limits must permit the event.'],external_observations=['Official declaration received within its deadline, three final referee votes or official expiration of the attempt clock.']) for k,v in specs.items()],constraints=dict(phase=phase,lift=d['lift'],next_participant=i,ordinary_attempt_seconds=seconds),completeness=False,reason='official_powerlifting_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';ranked=[]
 if done:
  for i in range(8):
   lifts=[best(g[i]) for g in d['attempts']]
   if all(lifts) and not d['disqualified'][i]:
    achieved=min(x['sequence'] for x in d['attempts'][2][i] if x['passed'] and x['weight_halfkg']==lifts[2])
    ranked.append((-sum(lifts),d['bodyweight_g'][i],achieved,i))
  ranked.sort()
 winners=[state['players'][ranked[0][3]]['id']] if ranked else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=j+1,total_halfkg=-t) for j,(t,_,__,i) in enumerate(ranked)],reason='total_confirmed' if done else 'lift_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official lift confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
