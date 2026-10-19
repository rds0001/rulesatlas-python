"""Shared official-order race classification, including dead heats and recalls."""
from copy import deepcopy
from .race import Race,INDEX,TIME
from ..values import fields,fail
class OrderedRace:
 def __init__(self,config):self.c=config;self.base=Race(config)
 def validate(self,d):
  self.base.validate(d)
  for r in d['runners']:
   if (r['status']=='finished')!=(r['official_order'] is not None):fail('Only finishers have an official finish-order value',code='INVALID_STATE')
 def apply(self,state,action):
  p=action['params'];k=action['type'];d=deepcopy(state['data']);index=dict(type='integer',minimum=0,maximum=len(d['runners'])-1)
  if k=='recall_start':
   fields(p,{},'/params')
   if d['phase']!='racing' or any(r['status']=='finished' for r in d['runners']):fail('An officially invalid start can be recalled only before any finisher')
   for r in d['runners']:
    if r['status']=='running':r['status']='ready'
    elif r['status']=='dnf':r['status']='dns'
   d['phase']='ready';self.base.settle(d);return d
  if k in ('record_finish','amend_result'):
   schema=dict(participant=index,time_us=dict(TIME,nullable=k=='amend_result'),official_order=dict(type='integer',minimum=1,maximum=len(d['runners']),nullable=k=='amend_result'))
   if k=='amend_result':schema.update(status=dict(type='enum',values=self.base.result_statuses()),warnings=dict(type='integer',minimum=0,maximum=2))
   fields(p,schema,'/params')
   if k=='amend_result' and (p['status']=='finished')!=(p['official_order'] is not None):fail('Only a finished amended result has an official finish-order value')
   params={key:value for key,value in p.items() if key!='official_order'};d=self.base.apply(state,dict(action,params=params));d['runners'][p['participant']]['official_order']=p['official_order'];return d
  d=self.base.apply(state,action)
  for r in d['runners']:
   if r['status']!='finished':r['official_order']=None
  return d
 def legal(self,state):
  result=self.base.legal(state);d=state['data']
  for a in result['action_types']:
   if a['type'] in ('record_finish','amend_result'):a['params_schema']['official_order']=dict(type='integer',minimum=1,maximum=len(d['runners']),nullable=a['type']=='amend_result')
  if d['phase']=='racing' and not any(r['status']=='finished' for r in d['runners']):result['action_types'].append(dict(type='recall_start',params_schema={},preconditions=['No contestant has already finished.'],external_observations=['Official decision that the collective start is invalid and must be repeated.']))
  result['constraints']['ranking_basis']='official_order';return result
 def outcome(self,state,pack):
  d=state['data'];done=d['phase']=='finished';finishers=sorted((r['official_order'],i) for i,r in enumerate(d['runners']) if r['status']=='finished') if done else []
  winners=[state['players'][i]['id'] for order,i in finishers if order==finishers[0][0]] if finishers else []
  placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other<order for other,_ in finishers),time_us=d['runners'][i]['time_us'],official_order=order) for order,i in finishers]
  return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if finishers else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=placements,reason='results_confirmed' if done else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official result confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
