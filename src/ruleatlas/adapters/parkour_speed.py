"""Parkour speed course with mandatory gates and authorized attempt restarts."""
from copy import deepcopy
from . import trail_running
from ..values import fields,fail
validate=trail_running.validate
outcome=trail_running.outcome
INDEX=dict(type='integer',minimum=0,maximum=7)
def apply(state,action):
 if action['type']!='restart_attempt':return trail_running.apply(state,action)
 fields(action['params'],dict(participant=INDEX),'/params');d=deepcopy(state['data']);r=d['runners'][action['params']['participant']]
 if d['phase']!='racing' or r['status']!='running':fail('Only an unresolved active attempt can be officially restarted')
 r.update(checkpoints_completed=0,last_checkpoint_time=None);return d
def legal(state):
 result=trail_running.legal(state)
 if state['data']['phase']=='racing':result['action_types'].append(dict(type='restart_attempt',params_schema=dict(participant=INDEX),preconditions=['The attempt is active and has no official finish or exclusion.'],external_observations=['Official authorization to void and restart an interrupted attempt.']))
 return result
