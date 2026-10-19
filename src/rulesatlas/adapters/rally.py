"""Three-stage single-leg rally with explicit road-control penalties."""
from copy import deepcopy
from .timed_heats import TimedHeats,INDEX
from ..values import fields,fail
BASE=TimedHeats(dict(heats=3,quantum_us=100000))
def road_penalty(d,i):return sum((v*10 if v>=0 else -v*60) for row in d['checkins'] if (v:=row[i]) is not None)
def overdue(d,i,h):
 values=[row[i] for row in d['checkins'][:h+1]]
 return values[-1] is not None and (values[-1]>15 or sum(max(0,v) for v in values if v is not None)>30)
def validate(d):
 BASE.validate(d)
 for h,row in enumerate(d['checkins']):
  for i,v in enumerate(row):
   r=d['results'][h][i]
   if h>d['heat'] and v is not None:fail('Future road control already recorded',code='INVALID_STATE')
   if v is not None and r['status']=='not_eligible':fail('Ineligible stage cannot have a road control',code='INVALID_STATE')
   if r['status']=='finished' and v is None:fail('Stage finish requires its road-control check-in',code='INVALID_STATE')
   if overdue(d,i,h) and r['status']!='dq':fail('Maximum lateness requires exclusion',code='INVALID_STATE')
 if d['phase']=='active' and d['checkins'][d['heat']][BASE.next(d)] is None:fail('A stage cannot start without check-in',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];h=d['heat'];i=BASE.next(d)
 if k in ('check_in','correct_check_in'):
  schema=dict(delta_minutes=dict(type='integer',minimum=-60,maximum=60))
  if k=='correct_check_in':schema['participant']=INDEX
  fields(p,schema,'/params')
  if k=='check_in':
   if d['phase']!='run' or d['checkins'][h][i] is not None:fail('Check in once before the next stage start')
  else:
   i=p['participant']
   if d['phase']!='review' or d['checkins'][h][i] is None:fail('Correct an existing current-stage control during review')
  d['checkins'][h][i]=p['delta_minutes']
  if overdue(d,i,h):
   d['results'][h][i]=dict(status='dq',time_us=None)
   if d['phase']=='run':d['phase']='run' if BASE.next(d) is not None else 'review'
  return d
 if k in ('assess_penalty','correct_penalty'):
  fields(p,dict(participant=INDEX,seconds=dict(type='integer',minimum=1 if k=='assess_penalty' else 0,maximum=100000)),'/params');i=p['participant']
  if k=='correct_penalty' and d['phase']!='review':fail('Correct other penalties only during review')
  d['other_penalty_seconds'][i]=d['other_penalty_seconds'][i]+p['seconds'] if k=='assess_penalty' else p['seconds']
  if d['other_penalty_seconds'][i]>100000:fail('Other penalties exceed the supported bound')
  return d
 if k=='start_next' and d['phase']=='run' and d['checkins'][h][i] is None:fail('Check in before starting the stage')
 return BASE.apply(state,action)
def legal(state):
 result=BASE.legal(state);d=state['data'];schemas={}
 if d['phase']=='run':schemas['check_in']=dict(delta_minutes=dict(type='integer',minimum=-60,maximum=60))
 if d['phase']=='review':schemas.update(correct_check_in=dict(participant=INDEX,delta_minutes=dict(type='integer',minimum=-60,maximum=60)),correct_penalty=dict(participant=INDEX,seconds=dict(type='integer',minimum=0,maximum=100000)))
 if d['phase']!='finished':schemas['assess_penalty']=dict(participant=INDEX,seconds=dict(type='integer',minimum=1,maximum=100000))
 for k,v in schemas.items():result['action_types'].append(dict(type=k,params_schema=v,preconditions=['Current control, stage eligibility and review phase must permit the event.'],external_observations=['Official signed whole-minute control deviation or additional time sanction.']))
 result['constraints'].update(road_penalty_seconds=[road_penalty(d,i) for i in range(8)],maximum_single_lateness_minutes=15,maximum_total_lateness_minutes=30);return result
def key(d,i):
 times=[row[i]['time_us'] for row in d['results']]
 return [sum(times)+1000000*(road_penalty(d,i)+d['other_penalty_seconds'][i])]+times
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';ranked=sorted([(key(d,i),i) for i in range(8) if all(row[i]['status']=='finished' for row in d['results'])]) if done else []
 winners=[state['players'][i]['id'] for k,i in ranked if k==ranked[0][0]] if ranked else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other<k for other,_ in ranked),total_time_us=k[0],road_penalty_seconds=road_penalty(d,i),other_penalty_seconds=d['other_penalty_seconds'][i]) for k,i in ranked],reason='rally_confirmed' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
