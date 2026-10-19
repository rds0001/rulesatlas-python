"""36-metre fronton hand-pelota singles: games, service judgments and rest rights."""
from copy import deepcopy
from ..values import fields,fail
PLAYER=dict(type='integer',minimum=0,maximum=1)
def target(d):return 5 if len(d['games'])==2 else 10
def game_winner(s):return int(s[1]>s[0])
def wins(d):return [sum(game_winner(s)==t for s in d['games']) for t in (0,1)]
def point(d,t):
 d['points'][t]+=1;d['server']=t;d['long_fault']=False;d['phase']='ready'
 if d['points'][t]==target(d):
  d['games'].append(d['points'][:])
  if wins(d)[t]==2:d.update(phase='finished',winner=t,reason='two_games')
  else:d['phase']='interval'
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for j,s in enumerate(d['games']):
  if max(s)!=(5 if j==2 else 10) or s[0]==s[1]:bad('Completed game must end at its exact target')
  if any(sum(game_winner(x)==t for x in d['games'][:j])>=2 for t in (0,1)):bad('No game follows a match-winning second game')
 if d['phase']=='choose_server':
  if d['server'] is not None or len(d['games']) not in (0,2) or any(d['points']) or any(d['timeouts']) or d['long_fault']:bad('Toss belongs before the first or deciding game')
 elif d['phase'] in ('ready','serve','rally','interval') and (d['server'] is None or d['first_server'] is None):bad('Active play requires a chosen server')
 if d['phase'] in ('ready','serve','rally') and max(d['points'])>=target(d):bad('Completed game must enter its interval or result')
 if d['phase']=='interval' and (not d['games'] or d['points']!=d['games'][-1] or max(wins(d))>=2):bad('Interval follows a completed nonfinal game')
 if d['phase'] in ('choose_server','interval','rally','finished','abandoned') and d['long_fault']:bad('Long-service fault is relevant only before a valid service')
 if d['phase']=='finished':
  if d['reason'] is None or d['reason']!='no_contest' and d['winner'] is None or d['reason']=='no_contest' and d['winner'] is not None:bad('Finished match needs a consistent result')
  if d['reason']=='two_games' and (wins(d)[d['winner']]!=2 or d['points']!=d['games'][-1]):bad('Normal victory requires two completed games')
 elif d['winner'] is not None or d['reason'] is not None:bad('Only terminal state can declare a result')
 if d['phase'] not in ('finished','abandoned') and max(wins(d))>=2:bad('Two games end the match')
def schemas(d):
 phase=d['phase'];s={}
 if phase=='finished':return s
 if phase=='abandoned':return dict(official_result=dict(winner=dict(PLAYER,nullable=True)))
 if phase=='choose_server':s['choose_server']=dict(player=PLAYER)
 if phase=='ready':s.update(start_serve=dict(player=PLAYER),timeout=dict(player=PLAYER))
 if phase=='serve':s['service_decision']=dict(result=dict(type='enum',values=['good','long','fault','replay']))
 if phase=='rally':s.update(award_rally=dict(winner=PLAYER),replay_rally={})
 if phase=='interval':s['next_game']={}
 if phase in ('ready','serve','rally'):s['penalty_point']=dict(player=PLAYER)
 s.update(concede=dict(player=PLAYER),disqualify=dict(player=PLAYER),abandon={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='choose_server':
  d['server']=p['player'];d['phase']='ready'
  if not d['games']:d['first_server']=p['player']
 elif k=='start_serve':
  if p['player']!=d['server']:fail('Only the entitled player may serve')
  d['phase']='serve'
 elif k=='service_decision':
  result=p['result']
  if result=='good':d['phase']='rally';d['long_fault']=False
  elif result=='fault' or result=='long' and d['long_fault']:point(d,1-d['server'])
  else:
   d['phase']='ready'
   if result=='long':d['long_fault']=True
 elif k=='award_rally':point(d,p['winner'])
 elif k=='replay_rally':d['phase']='ready';d['long_fault']=False
 elif k=='timeout':
  if d['timeouts'][p['player']]:fail('One timeout per player per game is available')
  d['timeouts'][p['player']]=True
 elif k=='next_game':
  d.update(points=[0,0],timeouts=[False,False],long_fault=False,phase='choose_server' if len(d['games'])==2 else 'ready',server=None if len(d['games'])==2 else 1-d['first_server'])
 elif k=='penalty_point':point(d,1-p['player'])
 elif k in ('concede','disqualify'):d.update(phase='finished',winner=1-p['player'],reason='concession' if k=='concede' else 'disqualification',long_fault=False)
 elif k=='abandon':d.update(phase='abandoned',long_fault=False)
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Game phase, service entitlement and remaining timeout must permit the event.'],external_observations=['Official service, rally, disciplinary and toss decisions.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],server=d['server'],service_attempt=2 if d['long_fault'] else 1,target=target(d),timeouts_remaining=[0 if x else 1 for x in d['timeouts']]),completeness=False,reason='official_fronton_hand_pelota_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='abandoned' else 'ongoing',result_kind=('no_contest' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if w is not None else [],losers=[state['players'][1-w]['id']] if w is not None else [],placements=[],reason=d['reason'] if done else 'official_result_required' if d['phase']=='abandoned' else 'ongoing',evidence_required=['Official result decision.'] if d['phase']=='abandoned' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
