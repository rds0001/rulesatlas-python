"""Fleet board series: windsurf tie order and kite tangle sanctions."""
from copy import deepcopy
from . import sailing
from ..values import fields,fail
class BoardRacing:
 def __init__(self,kind):self.kind=kind
 def schemas(self):
  s=deepcopy(sailing.SCHEMAS)
  for k in ('submit_result','amend_result'):
   p=s[k]['results']['items']['properties'];p['status']['values']=sailing.ENTRY['properties']['status']['values']+['nsc']+(['dct'] if self.kind=='kite' else [])
   p['redress_denominator'].update(maximum=10,enum=[1,2,3,4,5,6,10])
  if self.kind=='kite':
   for k in ('tangle_penalty','cancel_current_tangle'):s[k]=dict(participant=dict(type='integer',minimum=0,maximum=7))
  return s
 def normalize(self,d,row):
  row=deepcopy(row)
  if self.kind=='kite':
   for i,r in enumerate(row):
    if d['current_tangles'][i]:r.update(status='dne' if d['tangle_counts'][i]>=2 or r['status']=='dne' else 'dct',order=None,redress_numerator=None,redress_denominator=None)
  return row
 def validate(self,d):
  sailing.validate(d)
  rows=d['races']+([d['pending']] if d['pending'] is not None else [])
  for row in rows:
   for r in row:
    if r['status']=='redress' and r['redress_numerator']>9*r['redress_denominator']:fail('Board-series redress lies between one and nine points',code='INVALID_STATE')
  if self.kind=='kite':
   if any(a<b for a,b in zip(d['tangle_counts'],d['current_tangles'])):fail('Current-race tangle counts cannot exceed event totals',code='INVALID_STATE')
   if d['phase'] in ('ready','finished') and any(d['current_tangles']):fail('No unresolved race tangle counts outside an active race',code='INVALID_STATE')
   if d['pending'] is not None:
    if d['pending']!=self.normalize(d,d['pending']):fail('Race result does not apply its tangle sanction',code='INVALID_STATE')
    if any(r['status']=='dct' and not d['current_tangles'][i] for i,r in enumerate(d['pending'])):fail('DCT requires a recorded tangle ruling',code='INVALID_STATE')
   for i in range(8):
    firsts=sum(row[i]['status']=='dct' for row in d['races'])
    if firsts>1 or firsts>d['tangle_counts'][i]:fail('Repeated tangle disqualification must be non-excludable',code='INVALID_STATE')
 def available(self,d):
  names={'ready':['start_race'],'racing':['abandon_race','submit_result'],'review':['abandon_race','amend_result','confirm_race']}.get(d['phase'],[])
  if self.kind=='kite' and d['phase'] in ('racing','review'):names+=['tangle_penalty','cancel_current_tangle']
  return names
 def apply(self,state,action):
  d=deepcopy(state['data']);k=action['type'];p=action['params']
  if k not in self.available(d):fail('Action is not permitted in this board-race phase')
  fields(p,self.schemas()[k],'/params')
  if k=='start_race':d['phase']='racing'
  elif k=='abandon_race':
   d.update(phase='ready',pending=None)
   if self.kind=='kite':d['current_tangles']=[0]*8
  elif k in ('submit_result','amend_result'):
   d['pending']=self.normalize(d,p['results']);d['phase']='review'
  elif k=='confirm_race':
   d['races'].append(d['pending']);d['pending']=None;d['phase']='finished' if len(d['races'])==5 else 'ready'
   if self.kind=='kite':d['current_tangles']=[0]*8
  elif k=='tangle_penalty':
   i=p['participant'];d['tangle_counts'][i]+=1;d['current_tangles'][i]+=1
   if d['pending'] is not None:d['pending']=self.normalize(d,d['pending'])
  elif k=='cancel_current_tangle':
   i=p['participant']
   if not d['current_tangles'][i]:fail('Only a tangle ruling from the unresolved race can be cancelled')
   d['current_tangles'][i]-=1;d['tangle_counts'][i]-=1;d.update(phase='racing',pending=None)
  return d
 def key(self,d,i):
  key,discard,scores=sailing.key(d,i)
  if self.kind=='windsurf':key=[key[0],scores[discard] if discard is not None else 0]+sorted(scores)+scores[::-1]
  return key,discard,scores
 def legal(self,state):
  d=state['data'];s=self.schemas();c=dict(phase=d['phase'],confirmed_races=len(d['races']),score_unit_denominator=60,provisional_points_units=sailing.points(d['pending']) if d['pending'] is not None else None)
  if self.kind=='kite':c['tangle_counts']=d['tangle_counts'][:]
  return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s[k],preconditions=['A started race and complete reviewed result are required before confirmation.'],external_observations=['Official finishing places, exclusion codes, redress and board-specific rulings.']) for k in self.available(d)],constraints=c,completeness=False,reason='official_board_series')
 def outcome(self,state,pack):
  d=state['data'];done=d['phase']=='finished';ranked=sorted((self.key(d,i)[0],i) for i in range(8)) if done else [];winners=[state['players'][i]['id'] for k,i in ranked if k==ranked[0][0]] if ranked else []
  return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind='ranking' if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if done else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other<k for other,_ in ranked),points_units=k[0],score_unit_denominator=60,discarded_race=self.key(d,i)[1]) for k,i in ranked],reason='series_confirmed' if done else 'race_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official race confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
