"""Single-stage trail running: ordered checkpoints, cutoffs and time penalties."""
from copy import deepcopy
from .race import Race,INDEX,TIME
from ..values import fields,fail
CONFIG=dict(recall=False,conduct_warnings=False,time_quantum_us=1,route_configurable=True,false_start_disqualifies=False)
BASE=Race(CONFIG)
def validate(d):
 BASE.validate(d)
 if len(d['cutoffs_us'])!=len(d['route']):fail('Each checkpoint requires an explicit cutoff or null',code='INVALID_STATE')
 for r in d['runners']:
  if r['status'] in ('ready','dns') and r['penalty_us']:fail('Time penalties require a started runner',code='INVALID_STATE')
  n=r['checkpoints_completed']
  if n and d['cutoffs_us'][n-1] is not None and r['last_checkpoint_time']>d['cutoffs_us'][n-1] and r['status'] in ('running','finished'):fail('A missed checkpoint cutoff excludes a runner from classification',code='INVALID_STATE')
def apply(state,action):
 p=action['params'];k=action['type'];d=deepcopy(state['data'])
 if k=='configure_route':
  fields(p,dict(controls=dict(type='array',items=dict(type='string',minLength=1,maxLength=64),minItems=1,maxItems=128),time_limit_us=TIME,cutoffs_us=dict(type='array',minItems=1,maxItems=128,items=TIME)),'/params')
  if len(p['cutoffs_us'])!=len(p['controls']):fail('Supply one nullable cutoff per checkpoint')
  d=BASE.apply(state,dict(action,params={key:p[key] for key in ('controls','time_limit_us')}));d['cutoffs_us']=p['cutoffs_us'][:];return d
 if k=='assess_penalty':
  fields(p,dict(participant=INDEX,time_us=dict(type='integer',minimum=1,maximum=1000000000000)),'/params');r=d['runners'][p['participant']]
  if d['phase'] not in ('racing','review') or r['status'] not in ('running','finished'):fail('Assess a time penalty only against an active or provisionally finished runner')
  r['penalty_us']+=p['time_us'];return d
 if k=='correct_penalty':
  fields(p,dict(participant=INDEX,penalty_us=dict(type='integer',minimum=0,maximum=1000000000000)),'/params')
  if d['phase']!='review' or d['runners'][p['participant']]['status'] in ('dns','ready'):fail('Penalty correction requires official result review and a started runner')
  d['runners'][p['participant']]['penalty_us']=p['penalty_us'];return d
 d=BASE.apply(state,action)
 if k=='visit_control':
  r=d['runners'][p['participant']];limit=d['cutoffs_us'][r['checkpoints_completed']-1]
  if limit is not None and p['time_us']>limit:r['status']='ot';BASE.settle(d)
 return d
def legal(state):
 result=BASE.legal(state);d=state['data']
 for a in result['action_types']:
  if a['type']=='configure_route':a['params_schema']['cutoffs_us']=dict(type='array',minItems=1,maxItems=128,items=TIME)
 for k,schema in ([('assess_penalty',dict(participant=INDEX,time_us=dict(type='integer',minimum=1,maximum=1000000000000)))] if d['phase'] in ('racing','review') else [])+([('correct_penalty',dict(participant=INDEX,penalty_us=dict(type='integer',minimum=0,maximum=1000000000000)))] if d['phase']=='review' else []):result['action_types'].append(dict(type=k,params_schema=schema,preconditions=['Started runner and result phase must permit the penalty decision.'],external_observations=['Official event-specific time penalty or review correction.']))
 result['constraints']['cutoffs_us']=d['cutoffs_us'];return result
def outcome(state,pack):
 adjusted=deepcopy(state)
 for r in adjusted['data']['runners']:
  if r['status']=='finished':r['time_us']+=r['penalty_us']
 result=BASE.outcome(adjusted,pack)
 for entry in result['placements']:
  i=next(i for i,p in enumerate(state['players']) if p['id']==entry['player_id']);r=state['data']['runners'][i]
  entry['elapsed_us']=r['time_us'];entry['penalty_us']=r['penalty_us']
 return result
