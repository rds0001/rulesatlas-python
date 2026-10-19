"""Six-player, no-bench volleyball: rotations, sanctions, sets and timeouts."""
from copy import deepcopy
from ..values import fields,fail
TEAM=dict(type='integer',minimum=0,maximum=1)
def set_winner(s,index):
 target=15 if index==4 else 25
 return (0 if s[0]>s[1] else 1) if max(s)>=target and abs(s[0]-s[1])>=2 else None
def wins(d):return [sum(set_winner(s,i)==p for i,s in enumerate(d['sets'])) for p in (0,1)]
def ready(d):
 if all(d['configured']) and d['serving_team'] is not None:d['phase']='ready'
 return d
def new_set(d):
 d.update(phase='setup',points=[0,0],configured=[False,False],lineups=[list(range(6)),list(range(6))],timeouts=[0,0],expelled=[False]*12)
 d['set_first_server']=None if len(d['sets'])==4 else 1-d['set_first_server'];d['serving_team']=d['set_first_server'];return d
def finish_set(d,w):
 d['sets'].append(d['points'][:])
 if wins(d)[w]==3:d.update(phase='finished',winner=w,reason='three_sets');return d
 return new_set(d)
def point(d,w):
 if d['serving_team']!=w:
  d['lineups'][w]=d['lineups'][w][1:]+d['lineups'][w][:1];d['serving_team']=w
 d['points'][w]+=1;d['phase']='ready';winner=set_winner(d['points'],len(d['sets']))
 if winner is not None:return finish_set(d,winner)
 return d
def incomplete(d,team,permanent):
 w=1-team
 while True:
  target=15 if len(d['sets'])==4 else 25;d['points'][w]=max(target,d['points'][team]+2);d['sets'].append(d['points'][:])
  if wins(d)[w]==3:d.update(phase='finished',winner=w,reason='incomplete_team');return d
  new_set(d)
  if not permanent:return d
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if any(sorted(line)!=list(range(6)) for line in d['lineups']):bad('Each six-player lineup is a permutation of the team roster')
 if any(set_winner(s,i) is None for i,s in enumerate(d['sets'])):bad('Every completed set needs its target and a two-point margin')
 counts=wins(d)
 if any(v>3 for v in counts) or any(sum(set_winner(s,j)==p for j,s in enumerate(d['sets'][:i]))>=3 for i in range(len(d['sets'])) for p in (0,1)):bad('No additional set may follow a match-winning third set')
 if d['phase']=='finished':
  if d['winner'] is None or counts[d['winner']]!=3 or d['reason'] is None or d['points']!=d['sets'][-1]:bad('Terminal result requires three won sets and the final score')
 else:
  if max(counts)>=3 or d['winner'] is not None or d['reason'] is not None or any(v==3 for v in d['sanctions']) or any(d['expelled']):bad('A six-player team cannot continue a set with an unavailable member')
  if set_winner(d['points'],len(d['sets'])) is not None:bad('A completed set must transition immediately')
 if d['phase'] in ('ready','rally') and (not all(d['configured']) or d['serving_team'] is None):bad('A rally requires both lineups and a serving team')
 if d['phase']=='setup' and (any(d['points']) or any(d['timeouts']) or all(d['configured']) and d['serving_team'] is not None):bad('Set setup precedes scoring and completes once both lineups and service are known')
 if d['serving_team'] is not None and d['set_first_server'] is None:bad('Serving team requires a set starting-server decision')
 if any(e and s<2 for e,s in zip(d['expelled'],d['sanctions'])):bad('Set expulsion requires a corresponding misconduct sanction')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type']
 if k=='set_lineup':
  fields(p,dict(team=TEAM,players=dict(type='array',minItems=6,maxItems=6,items=dict(type='integer',minimum=0,maximum=5))),'/params');t=p['team']
  if d['phase']!='setup' or d['configured'][t] or sorted(p['players'])!=list(range(6)):fail('Submit each team lineup once before the set')
  d['lineups'][t]=p['players'][:];d['configured'][t]=True;return ready(d)
 if k=='choose_server':
  fields(p,dict(team=TEAM),'/params')
  if d['phase']!='setup' or d['set_first_server'] is not None:fail('Choose service from the external toss only before the first or fifth set')
  d['set_first_server']=d['serving_team']=p['team'];return ready(d)
 if k=='start_rally':
  fields(p,dict(server=dict(type='integer',minimum=0,maximum=11)),'/params')
  if d['phase']!='ready' or p['server']!=6*d['serving_team']+d['lineups'][d['serving_team']][0]:fail('Only the correct player in service position one may start the rally')
  d['phase']='rally';return d
 if k=='award_rally':
  fields(p,dict(winner=TEAM),'/params')
  if d['phase']!='rally':fail('An adjudicated rally result requires a started rally')
  return point(d,p['winner'])
 if k=='replay_rally':
  fields(p,{},'/params')
  if d['phase']!='rally':fail('Only an unresolved rally may be replayed')
  d['phase']='ready';return d
 if k=='timeout':
  fields(p,dict(team=TEAM),'/params');t=p['team']
  if d['phase']!='ready' or d['timeouts'][t]>=2:fail('Each team may take two timeouts per set between rallies')
  d['timeouts'][t]+=1;return d
 if k in ('delay','improper_request','conduct_warning','misconduct'):
  if d['phase'] not in ('ready','rally'):fail('Resolve official sanctions in an active configured set')
  if k=='misconduct':
   fields(p,dict(player=dict(type='integer',minimum=0,maximum=11),kind=dict(type='string',enum=['rude','offensive','aggression'])),'/params');who=p['player'];t=who//6
   level=max(d['sanctions'][who]+1,dict(rude=1,offensive=2,aggression=3)[p['kind']]);d['sanctions'][who]=min(3,level)
   if level>=2:d['expelled'][who]=True;return incomplete(d,t,level>=3)
   return point(d,1-t)
  fields(p,dict(team=TEAM),'/params');t=p['team']
  if k=='conduct_warning':
   if d['conduct_warned'][t]:fail('The team has already received its formal conduct warning')
   d['conduct_warned'][t]=True;return d
  if k=='improper_request' and not d['improper_requested'][t]:d['improper_requested'][t]=True;return d
  d['delays'][t]+=1
  if d['delays'][t]>=2:return point(d,1-t)
  return d
 if k=='concede':
  fields(p,dict(team=TEAM),'/params')
  if d['phase'] not in ('ready','rally'):fail('Concede after the set has been configured')
  return incomplete(d,p['team'],True)
 fail('Unknown action')
def legal(state):
 d=state['data'];schemas={}
 if d['phase']=='setup':
  if not all(d['configured']):schemas['set_lineup']=dict(team=TEAM,players=dict(type='array',minItems=6,maxItems=6,items=dict(type='integer',minimum=0,maximum=5)))
  if d['set_first_server'] is None:schemas['choose_server']=dict(team=TEAM)
 else:
  if d['phase']=='ready':schemas.update(start_rally=dict(server=dict(type='integer',minimum=0,maximum=11)),timeout=dict(team=TEAM))
  elif d['phase']=='rally':schemas.update(award_rally=dict(winner=TEAM),replay_rally={})
  for k in ('delay','improper_request','conduct_warning','concede'):schemas[k]=dict(team=TEAM)
  schemas['misconduct']=dict(player=dict(type='integer',minimum=0,maximum=11),kind=dict(type='string',enum=['rude','offensive','aggression']))
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Set phase, lineup, service order and remaining allowances must permit the event.'],external_observations=['Official rally, toss, timeout or sanction decision.']) for k,s in schemas.items()],constraints=dict(set_number=len(d['sets'])+1 if d['phase']!='finished' else len(d['sets']),target=15 if len(d['sets'])==4 else 25,serving_team=d['serving_team'],server=None if d['serving_team'] is None else 6*d['serving_team']+d['lineups'][d['serving_team']][0],timeouts_remaining=[2-x for x in d['timeouts']],change_ends=len(d['sets'])==4 and max(d['points'])>=8),completeness=False,reason='official_rallies_and_fixed_six_player_rosters')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner'];counts=wins(d)
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p==w else 2,sets=counts[p]) for p in (0,1)] if done else [],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
