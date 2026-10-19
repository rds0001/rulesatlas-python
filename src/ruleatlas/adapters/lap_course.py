"""Individual timed courses with explicit ordered controls on every lap."""
from copy import deepcopy
from .course_race import CourseRace
from .race import TIME
from ..values import fields,fail
class LapCourse(CourseRace):
 def __init__(self,config):super().__init__(config)
 def route(self,d):return [f'lap_{lap}/{gate}' for lap in range(1,d['lap_count']+1) for gate in d['control_names']]
 def layout_schema(self):return dict(controls=dict(type='array',minItems=1,maxItems=12,items=dict(type='string',minLength=1,maxLength=40)),laps=dict(type='integer',minimum=1,maximum=self.c['maximum_laps']),time_limit_us=TIME)
 def validate(self,d):
  super().validate(d)
  if d['lap_count']>self.c['maximum_laps'] or len(set(d['control_names']))!=len(d['control_names']) or any('/' in x for x in d['control_names']):fail('Invalid lap-course configuration',code='INVALID_STATE')
  if bool(d['lap_count'])!=bool(d['control_names']) or d['route']!=self.route(d):fail('Every configured lap requires the same ordered controls',code='INVALID_STATE')
  if any(x is not None for x in d['cutoffs_us']):fail('This time-trial format uses an overall cutoff only',code='INVALID_STATE')
 def apply(self,state,action):
  k=action['type'];p=action['params']
  if k=='configure_track':
   fields(p,self.layout_schema(),'/params');d=deepcopy(state['data'])
   if d['phase']!='ready' or d['route_locked']:fail('Configure the complete track before opening the event')
   d['control_names']=p['controls'][:];d['lap_count']=p['laps'];d['route']=self.route(d);d['cutoffs_us']=[None]*len(d['route']);d['time_limit_us']=p['time_limit_us'];return d
  if k=='configure_route':fail('Configure the lap track through configure_track')
  return super().apply(state,action)
 def legal(self,state):
  result=super().legal(state);d=state['data'];result['action_types']=[a for a in result['action_types'] if a['type']!='configure_route']
  if d['phase']=='ready' and not d['route_locked']:result['action_types'].append(dict(type='configure_track',params_schema=self.layout_schema(),preconditions=['The event has not opened and the course is not locked.'],external_observations=['Complete ordered control list, lap count and optional overall elapsed limit.']))
  n=len(d['control_names']);result['constraints'].update(lap_count=d['lap_count'],next_control=[d['route'][r['checkpoints_completed']] if r['status']=='running' and r['started'] and r['checkpoints_completed']<len(d['route']) else None for r in d['runners']],completed_laps=[r['checkpoints_completed']//n if n else 0 for r in d['runners']]);return result
