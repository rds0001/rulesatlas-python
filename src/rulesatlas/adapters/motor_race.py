"""Declared motorcycle sprint and timed-plus-two-laps motocross classification."""
from copy import deepcopy
from .circuit_race import CircuitRace,SCHEMAS
from ..values import fields,fail
class MotorRace(CircuitRace):
 def __init__(self,kind):super().__init__(kind);self.percent=75;self.timed=kind=='motocross'
 def classified(self,d):
  if d['end_mode'] is None:return []
  lead=max((len(r['laps']) for r in d['runners'] if r['status'] not in ('dns','dq')),default=0)
  if lead==0:return []
  minimum=max(1,lead*75//100)
  return [i for i,r in enumerate(d['runners']) if r['status'] not in ('ready','running','dns','dq') and len(r['laps'])>=minimum and (d['end_mode']=='early' or r['status']=='finished' and r['laps'][-1]<=d['checkered_ms']+300000)]
 def validate(self,d):
  projected=deepcopy(d)
  if self.timed:
   if d['target_laps'] is None:projected['target_laps']=200
   elif d['target_laps']<3:fail('Timed motocross needs a triggering leader lap followed by two laps',code='INVALID_STATE')
   if d['phase']=='ready' and d['target_laps'] is not None:fail('Timed race distance is established only when the leading racer crosses after time',code='INVALID_STATE')
   if d['end_mode']=='normal' and d['target_laps'] is None:fail('Normal timed finish requires the two-lap target',code='INVALID_STATE')
  super().validate(projected)
 def apply(self,state,action):
  if self.timed and action['type']=='configure':
   fields(action['params'],dict(duration_ms=dict(type='integer',minimum=300000,maximum=3600000)),'/params')
   if state['data']['phase']!='ready':fail('Race duration is fixed after the start')
   d=deepcopy(state['data']);d['duration_ms']=action['params']['duration_ms'];return d
  projected=deepcopy(state)
  if self.timed and action['type']=='cross_line':
   fields(action['params'],SCHEMAS['cross_line'],'/params');d=projected['data'];p=action['params'];n=len(d['runners'][p['player']]['laps'])+1
   if d['target_laps'] is None and p['elapsed_ms']>=d['duration_ms'] and n>max((len(r['laps']) for i,r in enumerate(d['runners']) if i!=p['player'] and r['status']=='running'),default=0):
    if n+2>200:fail('Timed sprint exceeds the declared two-hundred-lap bound')
    d['target_laps']=n+2
  return super().apply(projected,action)
 def legal(self,state):
  result=super().legal(state)
  if self.timed:
   for event in result['action_types']:
    if event['type']=='configure':event['params_schema']=dict(duration_ms=dict(type='integer',minimum=300000,maximum=3600000))
   result['constraints'].update(duration_ms=state['data']['duration_ms'],additional_laps=2)
  result['constraints'].update(finish_window_ms=300000,normal_finish_required=True)
  return result
