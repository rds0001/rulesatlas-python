"""Adjudicated Kubb turns with ten identifiable kubbs and a protected king."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
SCHEMAS=dict(choose_first_team=dict(team=I(0,1)),throw_kubb=dict(kubb=I(0,9),valid=dict(type='boolean'),king=dict(type='boolean')),place_penalty_kubb=dict(kubb=I(0,9)),throw_baton=dict(knocked=dict(type='array',minItems=0,maxItems=10,items=I(0,9)),king=dict(type='boolean'),from_baseline=dict(type='boolean')),end_turn={},concede={})
def settle_insertion(d):
 if any(x['status']=='down' for x in d['kubbs']):d['phase']='insert'
 else:d['phase']='batons'
def advance(d):
 d['team']=1-d['team'];d['batons_left']=6;d['failed_insertion']=0;d['inserting']=None;settle_insertion(d)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['phase']=='setup':
  if d['team'] is not None or d['winner'] is not None or d['reason'] is not None or d['batons_left']!=6 or d['inserting'] is not None or d['failed_insertion'] or any(x['status']!='base' or x['half']!=i//5 for i,x in enumerate(d['kubbs'])):bad('Invalid initial Kubb position')
  return
 if d['team'] is None:bad('An active game needs a team')
 if (d['phase']=='finished')!=(d['winner'] is not None and d['reason'] is not None):bad('Terminal result mismatch')
 if d['phase']!='finished' and (d['winner'] is not None or d['reason'] is not None):bad('Premature winner')
 for i,x in enumerate(d['kubbs']):
  if x['status']=='base' and x['half']!=i//5:bad('A base kubb cannot switch baseline')
 if d['phase'] in ('insert','penalty_placement'):
  if d['batons_left']!=6 or not any(x['status']=='down' for x in d['kubbs']):bad('Insertion requires returned kubbs before batons')
  if any(x['status']=='down' and x['half']!=d['team'] for x in d['kubbs']):bad('Insert the kubbs knocked down on your half')
  if d['inserting'] is not None and d['kubbs'][d['inserting']]['status']!='down':bad('Insertion target must still be down')
  if (d['phase']=='penalty_placement')!=(d['failed_insertion']==2):bad('Penalty placement follows two failed attempts')
  if (d['inserting'] is None)!=(d['failed_insertion']==0):bad('Attempt counter needs its selected kubb')
 elif d['inserting'] is not None or d['failed_insertion']:bad('Insertion counters exist outside insertion')
 if d['phase']=='batons' and d['batons_left']==0:bad('Exhausted batons must change the turn')
 if d['phase']=='finished' and d['reason']=='king' and (d['winner']!=d['team'] or any(x['half']!=d['team'] and x['status'] in ('base','field') for x in d['kubbs'])):bad('Winning king requires a cleared opposing half')
 if d['phase']=='finished' and d['reason'] in ('premature_king','illegal_king','concede') and d['winner']==d['team']:bad('The offending team cannot win')
def available(d):
 if d['phase']=='setup':return ['choose_first_team']
 if d['phase']=='insert':return ['throw_kubb','concede']
 if d['phase']=='penalty_placement':return ['place_penalty_kubb','concede']
 if d['phase']=='batons':return ['throw_baton','end_turn','concede']
 return []
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in available(d):fail('Action is not permitted in this phase')
 fields(p,SCHEMAS[k],'/params')
 if k=='choose_first_team':d['team']=p['team'];d['phase']='batons'
 elif k in ('throw_kubb','place_penalty_kubb'):
  j=p['kubb'];x=d['kubbs'][j]
  if x['status']!='down' or d['inserting'] is not None and d['inserting']!=j:fail('Complete the selected returned kubb first')
  if k=='throw_kubb' and p['king']:
   d.update(phase='finished',winner=1-d['team'],reason='premature_king',inserting=None,failed_insertion=0);return d
  if k=='throw_kubb' and not p['valid']:
   d['inserting']=j;d['failed_insertion']+=1
   if d['failed_insertion']==2:d['phase']='penalty_placement'
  else:
   x.update(status='field',half=1-d['team']);d['inserting']=None;d['failed_insertion']=0;settle_insertion(d)
 elif k=='throw_baton':
  if not p['from_baseline'] and not p['king'] and not any(x['half']==d['team'] and x['status']=='field' for x in d['kubbs']):fail('An advanced throwing line requires a standing field kubb on your half')
  ids=p['knocked']
  if len(set(ids))!=len(ids):fail('A kubb can be knocked at most once by a baton')
  for j in ids:
   x=d['kubbs'][j]
   if x['half']==d['team'] or x['status'] not in ('base','field'):fail('Only standing opposing kubbs are scoring targets')
   if x['status']=='base' and any(y['half']!=d['team'] and y['status']=='field' for y in d['kubbs']):continue
   x['status']='down'
  d['batons_left']-=1
  if p['king']:
   premature=any(x['half']!=d['team'] and x['status'] in ('base','field') for x in d['kubbs'])
   d['reason']='premature_king' if premature else 'illegal_king' if not p['from_baseline'] else 'king';d['winner']=1-d['team'] if d['reason']!='king' else d['team'];d['phase']='finished'
  elif d['batons_left']==0:advance(d)
 elif k=='end_turn':advance(d)
 elif k=='concede':d.update(phase='finished',winner=1-d['team'],reason='concede',inserting=None,failed_insertion=0)
 return d
def legal(state):
 d=state['data'];team=d['team'];fields_left=[] if team is None else [i for i,x in enumerate(d['kubbs']) if x['half']!=team and x['status']=='field'];bases=[] if team is None else [i for i,x in enumerate(d['kubbs']) if x['half']!=team and x['status']=='base']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Throw order, insertion attempts, field-kubb priority and king protection apply.'],external_observations=['Legal throw and placement rulings; ordered physical knockdowns.']) for k in available(d)],constraints=dict(phase=d['phase'],team=team,batons_left=d['batons_left'],field_targets=fields_left,base_targets=bases if not fields_left else [],king_available=team is not None and not fields_left and not bases,advanced_line_available=team is not None and any(x['half']==team and x['status']=='field' for x in d['kubbs']),penalty_placer=None if d['phase']!='penalty_placement' else 1-team),completeness=False,reason='official_kubb_throw_results')
def outcome(state,pack):
 d=state['data'];t=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if t else 'ongoing',result_kind='forfeit' if t and d['reason']=='concede' else 'win' if t else 'none',winners=[state['players'][w]['id']] if t else [],losers=[state['players'][1-w]['id']] if t else [],placements=[],reason=d['reason'] if t else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if t else None)
