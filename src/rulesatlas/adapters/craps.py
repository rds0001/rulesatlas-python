"""One Pass/Don't Pass contract with point play and exact 3-4-5x odds."""
from copy import deepcopy
from ..values import fields,fail
POINTS=[4,5,6,8,9,10]
def odds_ratio(d):
 p=d['point'];num,den=(2,1) if p in (4,10) else (3,2) if p in (5,9) else (6,5)
 return (num,den) if d['side']=='pass' else (den,num)
def max_odds(d):return min(1000-d['stake'],d['stake']*(6 if d['side']=='dont_pass' else 3 if d['point'] in (4,10) else 4 if d['point'] in (5,9) else 5))
def result(d):
 if d['reason']=='withdrawn_dont_pass':return 0
 total=sum(d['dice'])
 if d['point'] is None:
  won=total in (7,11) if d['side']=='pass' else total in (2,3)
  if d['side']=='dont_pass' and total==12:return 0
 else:won=(total==d['point']) if d['side']=='pass' else total==7
 if not won:return -d['stake']-d['odds']
 return d['stake']+(d['odds']*odds_ratio(d)[0]//odds_ratio(d)[1] if d['point'] is not None else 0)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['phase']=='betting':
  if d['point'] is not None or d['dice'] is not None or d['odds'] or d['reason'] is not None or (d['side'] is None)!=(d['stake']==0):bad('Initial betting cannot contain a point, odds or rolled result')
  return
 if d['side'] is None or d['stake']==0:bad('A closed contract requires a line bet')
 if d['point'] is None:
  if d['odds'] or d['phase']=='point_betting':bad('Free odds require an established point')
 else:
  if d['dice'] is None or d['odds']>max_odds(d) or d['odds']%odds_ratio(d)[1]:bad('Point contracts require a prior roll and exactly payable odds within the limit')
 if d['phase']=='settled':
  if d['reason']=='withdrawn_dont_pass':
   if d['side']!='dont_pass' or d['point'] is None:bad('Only an established Dont Pass contract may be withdrawn')
  elif d['reason']=='come_out':
   if d['point'] is not None or d['dice'] is None or sum(d['dice']) not in (2,3,7,11,12):bad('Come-out settlement requires a natural or craps number')
  elif d['reason']=='point_resolved':
   if d['point'] is None or d['dice'] is None or sum(d['dice']) not in (7,d['point']):bad('Resolve a point only on that point or seven')
  else:bad('Unknown settlement reason')
 elif d['reason'] is not None or (d['point'] is None and d['dice'] is not None):bad('Ongoing come-out contract cannot already contain a result')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type']
 if k=='bet':
  fields(p,dict(side=dict(type='string',enum=['pass','dont_pass']),stake=dict(type='integer',minimum=1,maximum=1000)),'/params')
  if d['phase']!='betting':fail('Select or replace the line bet before the first roll')
  d.update(side=p['side'],stake=p['stake']);return d
 if k=='cancel':
  fields(p,{},'/params')
  if d['phase']!='betting' or not d['stake']:fail('Cancel only an unrolled line bet')
  d.update(side=None,stake=0);return d
 if k=='close_roll':
  fields(p,{},'/params')
  if d['phase'] not in ('betting','point_betting') or not d['stake']:fail('Place a line bet and close the betting window before rolling')
  d['phase']='await_roll';return d
 if k=='set_odds':
  fields(p,dict(stake=dict(type='integer',minimum=0,maximum=1000)),'/params');n=p['stake']
  if d['phase']!='point_betting' or n>max_odds(d) or n%odds_ratio(d)[1]:fail('Change or remove odds only between point rolls, within 3-4-5x limits and exact chip increments')
  d['odds']=n;return d
 if k=='withdraw_dont_pass':
  fields(p,{},'/params')
  if d['phase']!='point_betting' or d['side']!='dont_pass':fail('Only Dont Pass may withdraw its established line contract between rolls')
  d.update(phase='settled',reason='withdrawn_dont_pass');return d
 if k!='roll':fail('Unknown action')
 fields(p,dict(dice=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=1,maximum=6))),'/params')
 if d['phase']!='await_roll':fail('Close betting before submitting the actual two-dice result')
 d['dice']=p['dice'][:];n=sum(d['dice'])
 if d['point'] is None:
  if n in POINTS:d.update(point=n,phase='point_betting')
  else:d.update(phase='settled',reason='come_out')
 elif n in (7,d['point']):d.update(phase='settled',reason='point_resolved')
 else:d['phase']='point_betting'
 return d
def legal(state):
 d=state['data'];schemas={}
 if d['phase']=='betting':
  schemas['bet']=dict(side=dict(type='string',enum=['pass','dont_pass']),stake=dict(type='integer',minimum=1,maximum=1000))
  if d['stake']:schemas.update(cancel={},close_roll={})
 elif d['phase']=='point_betting':
  schemas.update(set_odds=dict(stake=dict(type='integer',minimum=0,maximum=max_odds(d))),close_roll={})
  if d['side']=='dont_pass':schemas['withdraw_dont_pass']={}
 else:schemas['roll']=dict(dice=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=1,maximum=6)))
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Contract phase, chip budget and exact odds increments must permit the action.'],external_observations=['Player betting decision or actual two-dice result.']) for k,s in schemas.items()],constraints=dict(point=d['point'],line_stake=d['stake'],odds_stake=d['odds'],odds_increment=odds_ratio(d)[1] if d['point'] is not None else None,maximum_odds=max_odds(d) if d['point'] is not None else 0),completeness=False,reason='guarded_contract_and_external_dice')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='settled';net=result(d) if done else 0
 return dict(status='terminal' if done else 'ongoing',result_kind=('win' if net>0 else 'draw' if net==0 else 'other') if done else 'none',winners=[state['players'][0]['id']] if done and net>0 else [],losers=[state['players'][0]['id']] if done and net<0 else [],placements=[dict(player_id=state['players'][0]['id'],place=1,balance=1000+net,net=net)] if done else [],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
