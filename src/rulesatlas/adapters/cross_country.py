"""Interval-start freestyle race with individual starts and written reprimands."""
from copy import deepcopy
from . import trail_running as trail
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
def validate(d):
 base=deepcopy(d)
 for r in base['runners']:r['warnings']=0
 trail.validate(base)
 for r in d['runners']:
  if not r['started'] and (r['checkpoints_completed'] or r['time_us'] is not None or r['penalty_us'] or r['status'] in ('finished','dnf','mp','ot')):fail('An unstarted skier cannot have race observations',code='INVALID_STATE')
  if r['started'] and r['status'] in ('ready','dns'):fail('A started skier cannot be ready or DNS',code='INVALID_STATE')
  if r['warnings']==2 and r['status']!='dq':fail('Two written reprimands require disqualification',code='INVALID_STATE')
  if any(r[k] is not None and r[k]%100000 for k in ('time_us','penalty_us')):fail('Classification times require tenth-second precision',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type']
 if k in ('start_participant','written_reprimand','correct_reprimands'):
  schema=dict(participant=INDEX)
  if k=='correct_reprimands':schema['warnings']=dict(type='integer',minimum=0,maximum=2)
  fields(p,schema,'/params');r=d['runners'][p['participant']]
  if k=='start_participant':
   if d['phase']!='racing' or r['status']!='running' or r['started']:fail('Start an eligible skier once after opening the race')
   r['started']=True
  elif k=='written_reprimand':
   if d['phase'] not in ('ready','racing','review') or r['status'] in ('dns','dq'):fail('Written reprimand is unavailable')
   r['warnings']+=1
   if r['warnings']==2:r['status']='dq';r['time_us']=None
   trail.BASE.settle(d)
  else:
   if d['phase']!='review':fail('Correct written reprimands during review')
   r['warnings']=p['warnings']
   if r['warnings']==2:r['status']='dq';r['time_us']=None
  return d
 if k=='warn':fail('Use the written reprimand event')
 if k in ('visit_control','record_finish','assess_penalty','correct_penalty'):
  fields(p, next(a['params_schema'] for a in trail.legal(state)['action_types'] if a['type']==k),'/params') if any(a['type']==k for a in trail.legal(state)['action_types']) else fail('Event is unavailable in this phase')
  if not d['runners'][p['participant']]['started']:fail('This observation requires an individual start')
 if k=='amend_result':
  fields(p,dict(participant=INDEX,status=dict(type='enum',values=trail.BASE.result_statuses()),time_us=trail.TIME,warnings=dict(type='integer',minimum=0,maximum=2)),'/params')
  if p['warnings']!=d['runners'][p['participant']]['warnings']:fail('Correct reprimands explicitly before amending the result')
 if k in ('record_finish','assess_penalty','correct_penalty','amend_result'):
  for key in ('time_us','penalty_us'):
   if p.get(key) is not None and p[key]%100000:fail('Classification times require tenth-second precision')
 result=trail.apply(state,action)
 if k=='withdraw' and not d['runners'][p['participant']]['started']:result['runners'][p['participant']]['status']='dns'
 return result
def legal(state):
 result=trail.legal(state);d=state['data'];specs={}
 if d['phase']=='racing':specs['start_participant']=dict(participant=INDEX)
 if d['phase'] in ('ready','racing','review'):specs['written_reprimand']=dict(participant=INDEX)
 if d['phase']=='review':specs['correct_reprimands']=dict(participant=INDEX,warnings=dict(type='integer',minimum=0,maximum=2))
 for k,v in specs.items():result['action_types'].append(dict(type=k,params_schema=v,preconditions=['Individual start, eligibility and written reprimand count must permit the event.'],external_observations=['Official start or disciplinary ruling.']))
 result['constraints'].update(time_quantum_us=100000,started=[r['started'] for r in d['runners']],written_reprimands=[r['warnings'] for r in d['runners']]);return result
outcome=trail.outcome
