"""Single-round K90 ski jumping with a fixed gate and uncompensated wind."""
from copy import deepcopy
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
class SkiJump:
 def __init__(self,c):self.c=c
 def schema(self):
  return dict(distance_half_m=dict(type='integer',minimum=0,maximum=260),style_half_points=dict(type='array',minItems=5,maxItems=5,items=dict(type='integer',minimum=0,maximum=40)),penalty_tenths=dict(type='integer',minimum=0,maximum=3000))
 def current(self,d):return next((i for i in d['order'] if d['entrants'][i]['status'] in ('pending','active','awaiting_marks')),None)
 def settle(self,d):
  i=self.current(d);d['phase']='review' if i is None else 'ready'
 def validate(self,d):
  bad=lambda m:fail(m,code='INVALID_STATE')
  if d['phase']=='setup':
   if d['order'] or any(r['status']!='pending' or r['marks'] is not None for r in d['entrants']):bad('Unstarted final must be empty')
   return
  if sorted(d['order'])!=list(range(8)):bad('Start order must be a permutation of entrants')
  for r in d['entrants']:
   if r['status']=='scored' and r['marks'] is None or r['status'] not in ('scored','dq') and r['marks'] is not None:bad('Marks and entrant status disagree')
   if r['marks'] is not None:fields(r['marks'],self.schema(),'/marks')
  i=self.current(d)
  expected='review' if i is None else {'pending':'ready','active':'jump','awaiting_marks':'judging'}[d['entrants'][i]['status']]
  if d['phase']!='finished' and d['phase']!=expected or d['phase']=='finished' and i is not None:bad('Phase does not match the next jump')
  if sum(r['status'] in ('active','awaiting_marks') for r in d['entrants'])>1:bad('Only one jump may be active or awaiting marks')
  if i is not None and any(r['status'] in ('active','awaiting_marks') for j,r in enumerate(d['entrants']) if j!=i):bad('Jump violates the start order')
 def available(self,d):
  phase=d['phase'];s={}
  if phase=='setup':return dict(set_start_order=dict(order=dict(type='array',minItems=8,maxItems=8,items=INDEX)))
  if phase=='ready':s.update(start_jump=dict(participant=INDEX),withdraw=dict(participant=INDEX))
  if phase=='jump':s.update(complete_jump={},authorized_restart={},abandon_jump={})
  if phase=='judging':s['record_marks']=self.schema()
  if phase=='review':s.update(correct_marks=dict(participant=INDEX,**self.schema()),confirm_result={})
  if phase!='finished':s['disqualify']=dict(participant=INDEX)
  return s
 def apply(self,state,action):
  d=deepcopy(state['data']);k=action['type'];p=action['params'];schemas=self.available(d)
  if k not in schemas:fail('Action is not permitted in this phase')
  fields(p,schemas[k],'/params');i=self.current(d)
  if k=='set_start_order':
   if sorted(p['order'])!=list(range(8)):fail('Each entrant must appear once')
   d['order']=p['order'][:];d['phase']='ready'
  elif k=='start_jump':
   if p['participant']!=i:fail('Start the next scheduled entrant')
   d['entrants'][i]['status']='active';d['phase']='jump'
  elif k=='complete_jump':d['entrants'][i]['status']='awaiting_marks';d['phase']='judging'
  elif k=='authorized_restart':d['entrants'][i]['status']='pending';d['phase']='ready'
  elif k=='abandon_jump':d['entrants'][i]['status']='dnf';self.settle(d)
  elif k in ('record_marks','correct_marks'):
   j=i if k=='record_marks' else p['participant'];r=d['entrants'][j]
   if k=='correct_marks' and r['status'] not in ('scored','dq') or k=='correct_marks' and r['marks'] is None:fail('Correct an existing judged jump only')
   r['marks']={name:deepcopy(p[name]) for name in self.schema()}
   if k=='record_marks':r['status']='scored';self.settle(d)
  elif k in ('withdraw','disqualify'):
   j=p['participant'];r=d['entrants'][j]
   if r['status']=='dq' or k=='withdraw' and r['status']!='pending':fail('Entrant cannot receive this status now')
   r['status']='dns' if k=='withdraw' else 'dq'
   if i==j or d['phase'] in ('ready','review'):self.settle(d)
  elif k=='confirm_result':d['phase']='finished'
  return d
 def components(self,m):
  return [max(0,600+10*(m['distance_half_m']-180)+5*sum(sorted(m['style_half_points'])[1:-1])-m['penalty_tenths'])]
 def legal(self,state):
  d=state['data']
  return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Start order, jump completion and review phase must permit the event.'],external_observations=['Official half-metre distance, five half-point style marks and neutral deductions.']) for k,v in self.available(d).items()],constraints=dict(phase=d['phase'],current_participant=self.current(d),score_unit_denominator=10),completeness=False,reason='official_ski_jump_judgments')
 def outcome(self,state,pack):
  d=state['data'];done=d['phase']=='finished';ranked=sorted([(self.components(r['marks']),i) for i,r in enumerate(d['entrants']) if r['status']=='scored'],key=lambda x:tuple(-v for v in x[0])+(x[1],)) if done else []
  winners=[state['players'][i]['id'] for key,i in ranked if key==ranked[0][0]] if ranked else []
  return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other>key for other,_ in ranked),score_units=key[0],score_unit_denominator=10) for key,i in ranked],reason='scores_confirmed' if done else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official result confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)

_ENGINE=SkiJump({})
validate=_ENGINE.validate
apply=_ENGINE.apply
legal=_ENGINE.legal
outcome=_ENGINE.outcome
