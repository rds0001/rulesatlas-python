"""Configurable individual-start course races with official time penalties."""
from copy import deepcopy
from . import trail_running as trail
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
class CourseRace:
 def __init__(self,config):self.c=config
 def internal(self,state):
  s=deepcopy(state)
  for r in s['data']['runners']:r['warnings']=0
  return s
 def validate(self,d):
  trail.validate(self.internal(dict(data=d))['data'])
  for r in d['runners']:
   if not r['started'] and (r['checkpoints_completed'] or r['time_us'] is not None or r['penalty_us'] or r['status'] in ('finished','dnf','mp','ot')):fail('An unstarted entrant cannot have course observations',code='INVALID_STATE')
   if r['started'] and r['status'] in ('ready','dns'):fail('A started entrant cannot be ready or DNS',code='INVALID_STATE')
   if any(r[k] is not None and r[k]%self.c['quantum_us'] for k in ('time_us','penalty_us')):fail('Classification time precision mismatch',code='INVALID_STATE')
 def apply(self,state,action):
  d=deepcopy(state['data']);p=action['params'];k=action['type'];schemas={a['type']:a['params_schema'] for a in self.legal(state)['action_types']}
  if k not in schemas:fail('Event is unavailable in this phase')
  fields(p,schemas[k],'/params')
  if k=='start_participant':
   r=d['runners'][p['participant']]
   if d['phase']!='racing' or r['status']!='running' or r['started']:fail('Start an eligible entrant once after opening the event')
   r['started']=True;return d
  if k in ('visit_control','record_finish','assess_penalty','correct_penalty') and not d['runners'][p['participant']]['started']:fail('This observation requires an individual start')
  if k in ('record_finish','assess_penalty','correct_penalty','amend_result'):
   for key in ('time_us','penalty_us'):
    if p.get(key) is not None and p[key]%self.c['quantum_us']:fail('Classification time precision mismatch')
  a=deepcopy(action)
  if k=='amend_result':a['params']['warnings']=0
  result=trail.apply(self.internal(state),a)
  for r in result['runners']:r.pop('warnings')
  if k=='withdraw' and not d['runners'][p['participant']]['started']:result['runners'][p['participant']]['status']='dns'
  return result
 def legal(self,state):
  result=trail.legal(self.internal(state));d=state['data']
  for a in result['action_types']:
   if a['type']=='amend_result':a['params_schema'].pop('warnings')
  if d['phase']=='racing':result['action_types'].append(dict(type='start_participant',params_schema=dict(participant=INDEX),preconditions=['The entrant is eligible and has not started.'],external_observations=['Official individual start.']))
  result['constraints'].update(time_quantum_us=self.c['quantum_us'],started=[r['started'] for r in d['runners']]);return result
 def outcome(self,state,pack):return trail.outcome(self.internal(state),pack)
