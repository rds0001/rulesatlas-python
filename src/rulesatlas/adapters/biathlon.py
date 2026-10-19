"""Four-bout individual biathlon with one-minute missed-target penalties."""
from copy import deepcopy
from . import cross_country as xc
from ..values import fields,fail
CONTROLS=['prone_1','standing_1','prone_2','standing_2']
INDEX=dict(type='integer',minimum=0,maximum=7)
def validate(d):
 xc.validate(d)
 if d['route']!=CONTROLS or d['cutoffs_us']!=[None]*4 or d['time_limit_us'] is not None:fail('The individual event uses four fixed ordered shooting controls',code='INVALID_STATE')
 for r in d['runners']:
  if r['warnings']:fail('This format records official penalties or exclusions, not reprimand escalation',code='INVALID_STATE')
  n=r['checkpoints_completed']
  if any(shots and j>=n or j<n-1 and len(shots)!=5 for j,shots in enumerate(r['shooting'])):fail('Shooting bouts must follow the ordered range visits',code='INVALID_STATE')
  if r['status']=='finished' and any(len(s)!=5 for s in r['shooting']):fail('Finish requires twenty resolved shots',code='INVALID_STATE')
def apply(state,action):
 k=action['type'];p=action['params'];d=deepcopy(state['data'])
 if k in ('configure_route','written_reprimand','correct_reprimands'):fail('This event has a fixed range sequence and official penalty decisions')
 if k in ('record_shot','correct_shot'):
  schema=dict(participant=INDEX,hit=dict(type='boolean'))
  if k=='correct_shot':schema.update(bout=dict(type='integer',minimum=0,maximum=3),shot=dict(type='integer',minimum=0,maximum=4))
  fields(p,schema,'/params');r=d['runners'][p['participant']]
  if k=='record_shot':
   n=r['checkpoints_completed']
   if d['phase']!='racing' or r['status']!='running' or not r['started'] or n==0 or len(r['shooting'][n-1])==5:fail('Record a shot only during the current incomplete shooting bout')
   r['shooting'][n-1].append(p['hit'])
  else:
   if d['phase']!='review' or r['status']!='finished' or p['shot']>=len(r['shooting'][p['bout']]):fail('Correct a recorded shot for a classified finisher during review')
   r['shooting'][p['bout']][p['shot']]=p['hit']
  return d
 if k in ('visit_control','record_finish'):
  schema=next(a['params_schema'] for a in xc.legal(state)['action_types'] if a['type']==k) if any(a['type']==k for a in xc.legal(state)['action_types']) else None
  if schema is None:fail('The course event is unavailable now')
  fields(p,schema,'/params');r=d['runners'][p['participant']];n=r['checkpoints_completed']
  if n and len(r['shooting'][n-1])!=5:fail('Resolve all five targets before leaving the shooting bout')
  if k=='record_finish' and any(len(s)!=5 for s in r['shooting']):fail('Complete all four shooting bouts before finishing')
 return xc.apply(state,action)
def legal(state):
 result=xc.legal(state);d=state['data'];result['action_types']=[a for a in result['action_types'] if a['type'] not in ('configure_route','written_reprimand','correct_reprimands')]
 specs={}
 if d['phase']=='racing':specs['record_shot']=dict(participant=INDEX,hit=dict(type='boolean'))
 if d['phase']=='review':specs['correct_shot']=dict(participant=INDEX,hit=dict(type='boolean'),bout=dict(type='integer',minimum=0,maximum=3),shot=dict(type='integer',minimum=0,maximum=4))
 for k,v in specs.items():result['action_types'].append(dict(type=k,params_schema=v,preconditions=['Current shooting bout, shot count and result phase must permit the event.'],external_observations=['Official hit or missed-target ruling.']))
 result['constraints'].update(shooting_order=['prone','standing','prone','standing'],miss_penalty_us=60000000,shots_recorded=[[len(s) for s in r['shooting']] for r in d['runners']]);return result
def outcome(state,pack):
 adjusted=deepcopy(state)
 for r in adjusted['data']['runners']:r['penalty_us']+=60000000*sum(not hit for s in r['shooting'] for hit in s)
 result=xc.outcome(adjusted,pack)
 for entry in result['placements']:
  i=next(i for i,p in enumerate(state['players']) if p['id']==entry['player_id']);r=state['data']['runners'][i]
  entry['missed_targets']=sum(not hit for s in r['shooting'] for hit in s);entry['other_penalty_us']=r['penalty_us']
 return result
