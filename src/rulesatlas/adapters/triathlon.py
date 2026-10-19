"""Individual triathlon with ordered discipline and transition completion."""
from copy import deepcopy
from .course_race import CourseRace
from .race import TIME
from ..values import fields,fail
BASE=CourseRace(dict(quantum_us=1000))
ROUTE=['swim_exit','transition_one_exit','bike_exit','transition_two_exit','run_finish']
SEGMENTS=['swimming','transition_one','cycling','transition_two','running','awaiting_finish']
LIMITS=dict(time_limit_us=TIME,cutoffs_us=dict(type='array',minItems=5,maxItems=5,items=TIME))
def validate(d):
 BASE.validate(d)
 if d['route']!=ROUTE:fail('Triathlon requires swimming, first transition, cycling, second transition and running in order',code='INVALID_STATE')
def apply(state,action):
 if action['type']=='configure_limits':
  fields(action['params'],LIMITS,'/params');d=deepcopy(state['data'])
  if d['phase']!='ready' or d['route_locked']:fail('Set course limits before opening the event')
  d.update(deepcopy(action['params']));return d
 if action['type']=='configure_route':fail('The discipline sequence is fixed for this triathlon')
 return BASE.apply(state,action)
def legal(state):
 result=BASE.legal(state);d=state['data'];result['action_types']=[a for a in result['action_types'] if a['type']!='configure_route']
 if d['phase']=='ready' and not d['route_locked']:result['action_types'].append(dict(type='configure_limits',params_schema=LIMITS,preconditions=['Course limits are set before the event opens.'],external_observations=['Declared elapsed cutoffs and overall time limit.']))
 result['constraints']['segments']=[SEGMENTS[r['checkpoints_completed']] if r['status']=='running' and r['started'] else r['status'] if r['status']!='running' else 'awaiting_start' for r in d['runners']]
 return result
def outcome(state,pack):return BASE.outcome(state,pack)
