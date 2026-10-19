"""Gundersen-style combined classification from a jump and pursuit ski race."""
from copy import deepcopy
from . import ski_jumping as jump,cross_country as ski
from ..values import fail
BLOCKED={'written_reprimand','correct_reprimands'}
def offsets(j):
 scores=[jump._ENGINE.components(r['marks'])[0] if r['status']=='scored' else None for r in j['entrants']];best=max((s for s in scores if s is not None),default=0)
 return [None if s is None else (best-s)*400000 for s in scores]
def start_ski(j):
 gaps=offsets(j)
 return dict(phase='ready' if any(g is not None for g in gaps) else 'review',runners=[dict(status='ready' if g is not None else 'dns',time_us=None,warnings=0,checkpoints_completed=0,last_checkpoint_time=None,penalty_us=0,started=False) for g in gaps],route=[],route_locked=False,time_limit_us=None,cutoffs_us=[])
def validate(d):
 jump.validate(d['jump'])
 if d['stage']=='jumping':
  if d['jump']['phase']=='finished' or d['ski'] is not None:fail('Ski race starts only after the jump result is confirmed',code='INVALID_STATE')
 else:
  if d['jump']['phase']!='finished' or d['ski'] is None:fail('Confirmed jumping result is required',code='INVALID_STATE')
  ski.validate(d['ski'])
  for g,r in zip(offsets(d['jump']),d['ski']['runners']):
   if g is None and (r['status']!='dns' or r['started']):fail('Only classified jumpers may enter the ski race',code='INVALID_STATE')
   if r['warnings']:fail('Use official penalties or exclusion decisions',code='INVALID_STATE')
  if (d['stage']=='finished')!=(d['ski']['phase']=='finished'):fail('Combined phase and ski confirmation disagree',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];inner=deepcopy(state)
 if d['stage']=='jumping':
  if not k.startswith('jump_'):fail('Complete jumping before the ski race')
  inner['data']=d['jump'];d['jump']=jump.apply(inner,dict(action,type=k[5:]))
  if d['jump']['phase']=='finished':d.update(stage='skiing',ski=start_ski(d['jump']))
 else:
  if not k.startswith('ski_') or k[4:] in BLOCKED:fail('Use an available ski race event')
  p=action['params'];kind=k[4:]
  if 'participant' in p and type(p['participant']) is int and 0<=p['participant']<8 and offsets(d['jump'])[p['participant']] is None:fail('This entrant has no classified jump')
  inner['data']=d['ski'];d['ski']=ski.apply(inner,dict(action,type=kind))
  if d['ski']['phase']=='finished':d['stage']='finished'
 return d
def legal(state):
 d=state['data'];inner=deepcopy(state);is_jump=d['stage']=='jumping';inner['data']=d['jump'] if is_jump else d['ski'];result=(jump if is_jump else ski).legal(inner)
 result['action_types']=[a for a in result['action_types'] if is_jump or a['type'] not in BLOCKED]
 for a in result['action_types']:a['type']=('jump_' if is_jump else 'ski_')+a['type']
 result['constraints'].update(stage=d['stage'],start_deficits_us=[] if is_jump else offsets(d['jump']));return result
def outcome(state,pack):
 d=state['data'];inner=deepcopy(state)
 if d['stage']=='jumping':
  inner['data']=d['jump'];return jump.outcome(inner,pack)
 inner['data']=deepcopy(d['ski']);gaps=offsets(d['jump'])
 for g,r in zip(gaps,inner['data']['runners']):
  if g is not None:r['penalty_us']+=g
 result=ski.outcome(inner,pack)
 for entry in result['placements']:
  i=next(i for i,p in enumerate(state['players']) if p['id']==entry['player_id']);entry['start_deficit_us']=gaps[i];entry['penalty_us']=d['ski']['runners'][i]['penalty_us']
 return result
