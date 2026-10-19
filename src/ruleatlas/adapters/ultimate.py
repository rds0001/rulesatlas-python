"""Uncapped seven-a-side Ultimate to fifteen, with point-boundary eligibility."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
TEAM=I(0,1);SLOT=I(0,27)
SCHEMAS=dict(set_lineup=dict(team=TEAM,roster_size=I(7,28),active=dict(type='array',minItems=7,maxItems=7,items=SLOT)),start_game=dict(first_receiving=TEAM),start_point={},resume_point={},begin_second_half={},goal=dict(team=TEAM,scorer=SLOT),substitute=dict(team=TEAM,out=dict(type='array',minItems=1,maxItems=7,items=SLOT),**{'in':dict(type='array',minItems=1,maxItems=7,items=SLOT)}),authorized_replacement=dict(team=TEAM,out=SLOT,**{'in':SLOT}),matching_replacement=dict(team=TEAM,out=SLOT,**{'in':SLOT}),timeout=dict(team=TEAM),end_timeout={},concede=dict(team=TEAM))
def active(t):return [i for i,s in enumerate(t['status']) if s=='active']
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in d['teams']:
  if len(t['blocked_this_point'])!=len(t['status']) or len(active(t))!=7:bad('Each team requires seven active players and matching eligibility vectors')
  if any(t['blocked_this_point'][i] for i in active(t)):bad('An officially replaced player cannot return during the same point')
 if d['phase']=='pre_game' and (d['scores']!=[0,0] or d['half']!=1 or any(t['timeouts_used'] for t in d['teams'])):bad('A new game starts with empty scoring and timeouts')
 if d['scores']==[15,15]:bad('The game ends when the first team reaches fifteen')
 if d['half']==1 and min(d['scores'])>=8:bad('Halftime begins when the first team reaches eight')
 if d['phase']=='halftime' and (d['half']!=1 or max(d['scores'])!=8):bad('Halftime begins at the first eight-point score')
 if d['phase'] not in ('halftime','finished') and d['half']==1 and max(d['scores'])>=8:bad('The first half cannot continue beyond eight points')
 if d['half']==2 and max(d['scores'])<8:bad('The second half requires a completed first half')
 if d['phase']=='finished':
  if d['conceded_by'] is None and max(d['scores'])!=15:bad('Victory requires fifteen points or concession')
  if d['timeout_team'] is not None:bad('No timeout remains after the game')
 elif max(d['scores'])>=15 or d['conceded_by'] is not None:bad('A decided game must finish')
 if d['timeout_team'] is not None and (d['phase'] not in ('point','between_points') or d['teams'][d['timeout_team']]['timeouts_used']==0):bad('Timeout must belong to an available playing phase and recorded allowance')
 if d['phase'] not in ('point','replacement_break') and any(t['matching_allowance'] or any(t['blocked_this_point']) for t in d['teams']):bad('Point-specific replacement rights expire at the point boundary')
 if d['phase']!='replacement_break' and any(t['matching_allowance'] for t in d['teams']):bad('Matching replacements require the current replacement stoppage')

def swap(t,out,inc):
 if out not in active(t) or inc>=len(t['status']) or t['status'][inc]!='bench' or t['blocked_this_point'][inc]:fail('Replacement requires an active outgoing player and an eligible substitute')
 t['status'][out]='bench';t['status'][inc]='active'
def clear_point(d):
 for t in d['teams']:t['blocked_this_point']=[False]*len(t['status']);t['matching_allowance']=0

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase']
 if k not in SCHEMAS:fail('Unknown Ultimate event')
 fields(p,SCHEMAS[k],'/params')
 if phase=='finished':fail('The game is finished')
 if d['timeout_team'] is not None and k not in ('end_timeout','concede'):fail('Complete the timeout before another event')
 if k=='set_lineup':
  if phase!='pre_game':fail('Set the roster before the game starts')
  n=p['roster_size'];players=p['active']
  if len(set(players))!=7 or max(players)>=n:fail('Starting lineup requires seven distinct roster players')
  d['teams'][p['team']].update(status=['active' if i in players else 'bench' for i in range(n)],blocked_this_point=[False]*n)
 elif k=='start_game':
  if phase!='pre_game':fail('The game has already started')
  d['first_receiving']=p['first_receiving'];d['next_receiver']=p['first_receiving'];d['phase']='between_points'
 elif k=='start_point':
  if phase!='between_points':fail('A new point is not due')
  d['phase']='point'
 elif k=='resume_point':
  if phase!='replacement_break':fail('No replacement stoppage is active')
  d['phase']='point'
  for t in d['teams']:t['matching_allowance']=0
 elif k=='begin_second_half':
  if phase!='halftime':fail('Halftime is not due')
  d['half']=2;d['phase']='between_points';d['next_receiver']=1-d['first_receiving']
  for t in d['teams']:t['timeouts_used']=0
 elif k=='goal':
  if phase!='point' or p['scorer'] not in active(d['teams'][p['team']]):fail('An active eligible receiver must score during a point')
  team=p['team'];d['scores'][team]+=1;d['next_receiver']=1-team;clear_point(d)
  d['phase']='finished' if d['scores'][team]==15 else 'halftime' if d['half']==1 and d['scores'][team]==8 else 'between_points'
 elif k=='substitute':
  if phase not in ('pre_game','between_points','halftime'):fail('Ordinary substitutions require a point boundary')
  if set(p['out']) & set(p['in']) or len(p['out'])!=len(p['in']) or len(set(p['out']))!=len(p['out']) or len(set(p['in']))!=len(p['in']):fail('Substitution vectors must pair distinct outgoing and incoming players')
  t=d['teams'][p['team']]
  for out,inc in zip(p['out'],p['in']):swap(t,out,inc)
 elif k in ('authorized_replacement','matching_replacement'):
  if phase not in ('point','replacement_break'):fail('Special replacements require an active point')
  t=d['teams'][p['team']]
  if k=='matching_replacement' and not t['matching_allowance']:fail('No matching replacement allowance is available')
  swap(t,p['out'],p['in'])
  if k=='authorized_replacement':t['blocked_this_point'][p['out']]=True;d['teams'][1-p['team']]['matching_allowance']+=1;d['phase']='replacement_break'
  else:t['matching_allowance']-=1
 elif k=='timeout':
  t=d['teams'][p['team']]
  if phase not in ('point','between_points') or t['timeouts_used']>=2:fail('Each team has two timeouts per half')
  t['timeouts_used']+=1;d['timeout_team']=p['team']
 elif k=='end_timeout':
  if d['timeout_team'] is None:fail('No timeout is active')
  d['timeout_team']=None
 elif k=='concede':d.update(phase='finished',conceded_by=p['team'],timeout_team=None);clear_point(d)
 return d

def legal(state):
 d=state['data'];phase=d['phase'];names={'pre_game':['set_lineup','substitute','start_game','concede'],'between_points':['start_point','substitute','timeout','concede'],'point':['goal','authorized_replacement','timeout','concede'],'replacement_break':['resume_point','authorized_replacement','matching_replacement','concede'],'halftime':['begin_second_half','substitute','concede'],'finished':[]}[phase]
 if d['timeout_team'] is not None:names=['end_timeout','concede']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Point phase, active-player eligibility, replacement rights and timeout allowance must permit the event.'],external_observations=['Official goal, completed timeout or authorized replacement; timeout entitlement is adjudicated externally.']) for k in names],constraints=dict(phase=phase,half=d['half'],receiving_team=d['next_receiver'],pulling_team=1-d['next_receiver'],active=[active(t) for t in d['teams']],timeouts_remaining=[2-t['timeouts_used'] for t in d['teams']],matching_replacements=[t['matching_allowance'] for t in d['teams']]),completeness=False,reason='official_ultimate_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=(1-d['conceded_by'] if d['conceded_by'] is not None else 0 if d['scores'][0]>d['scores'][1] else 1) if done else None
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[],reason='concession' if d['conceded_by'] is not None else 'fifteen_points' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
