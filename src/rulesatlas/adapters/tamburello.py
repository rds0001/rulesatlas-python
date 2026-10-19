"""Indoor Tamburello: thirteen games, fixed game servers and a deciding-game toss."""
from copy import deepcopy
from ..values import fields,fail
TEAM=dict(type='integer',minimum=0,maximum=1)
PLAYER=dict(type='integer',minimum=0,maximum=4)
def active(d,t):return [i for i,s in enumerate(d['players'][t]) if s=='active']
def serving(d):
 if d['game_first_server'] is None:return None
 return (d['game_first_server']+sum(d['points']))%2 if d['games']==[12,12] else d['game_first_server']
def point(d,t):
 d['points'][t]+=1;d['service_ms']=0;d['phase']='ready'
 if d['points'][t]==4:
  d['games'][t]+=1
  if d['games'][t]==13:d.update(phase='finished',winner=t,reason='thirteen_games')
  else:d['phase']='game_break'
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if len(active(d,t))>3:bad('At most three players may be active')
  if d['servers'][t] is not None and d['players'][t][d['servers'][t]]!='active':bad('Nominated server must remain active')
 if d['phase']=='toss' and (sum(d['games']) not in (0,24) or any(d['points']) or d['game_first_server'] is not None):bad('Service toss belongs before the first or deciding game')
 if d['phase'] in ('ready','service','rally','game_break') and (d['game_first_server'] is None or d['first_server'] is None):bad('Active game requires its starting-service decision')
 if d['phase'] in ('service','rally'):
  t=serving(d)
  if d['servers'][t] is None or any(len(active(d,j))<2 for j in (0,1)):bad('Authorized play requires two active players per team and a nominated server')
 if (d['phase']=='service')!=(d['service_ms']>0):bad('Service clock only runs after authorization and before the hit')
 if d['phase']=='game_break' and (max(d['points'])!=4 or d['points'][0]==d['points'][1] or max(d['games'])>=13):bad('Game break follows a completed nonfinal game')
 if d['phase'] in ('ready','service','rally') and max(d['points'])>=4:bad('Four points end the game')
 if d['phase']=='finished':
  if d['winner'] is None or d['reason'] is None:bad('Finished match needs a winner')
  if d['reason']=='thirteen_games' and (d['games'][d['winner']]!=13 or d['games'][1-d['winner']]>=13 or d['points'][d['winner']]!=4):bad('Normal result requires thirteen games')
 elif d['winner'] is not None or d['reason'] is not None or max(d['games'])>=13:bad('Only a finished match declares a result')
def schemas(d):
 phase=d['phase'];s={}
 if phase=='finished':return s
 if phase=='toss':s['choose_service']=dict(team=TEAM)
 if phase=='game_break':s['next_game']={}
 if phase=='ready':s.update(nominate_server=dict(team=TEAM,player=PLAYER),authorize_service={})
 if phase=='service':s.update(serve=dict(player=PLAYER),service_fault={},elapse_service=dict(milliseconds=dict(type='integer',minimum=1,maximum=10000)))
 if phase=='rally':s['award_rally']=dict(winner=TEAM)
 if phase in ('service','rally'):s['replay_point']={}
 if phase in ('toss','ready','service','game_break'):
  s.update(substitute=dict(team=TEAM,outgoing=PLAYER,incoming=PLAYER),enter=dict(team=TEAM,player=PLAYER),withdraw_player=dict(team=TEAM,player=PLAYER),exclude_player=dict(team=TEAM,player=PLAYER),timeout=dict(team=TEAM))
 if phase in ('ready','service','rally'):s['penalty_point']=dict(team=TEAM)
 s.update(concede=dict(team=TEAM),declare_incomplete=dict(team=TEAM))
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params');t=p.get('team')
 if k=='choose_service':
  d['game_first_server']=t;d['phase']='ready'
  if sum(d['games'])==0:d['first_server']=t
 elif k=='next_game':
  d.update(points=[0,0],servers=[None,None],service_ms=0,phase='toss' if d['games']==[12,12] else 'ready',game_first_server=None if d['games']==[12,12] else (d['first_server']+sum(d['games']))%2)
 elif k=='nominate_server':
  if t!=serving(d) or d['players'][t][p['player']]!='active' or d['servers'][t] is not None:fail('Nominate an active server once for the entitled team in this game')
  d['servers'][t]=p['player']
 elif k=='authorize_service':
  if d['servers'][serving(d)] is None or any(len(active(d,j))<2 for j in (0,1)):fail('Both teams need two active players and the serving team needs its server')
  d['phase']='service';d['service_ms']=10000
 elif k=='serve':
  if p['player']!=d['servers'][serving(d)]:fail('Only the nominated game server may serve')
  d['phase']='rally';d['service_ms']=0
 elif k=='service_fault':point(d,1-serving(d))
 elif k=='elapse_service':
  if p['milliseconds']>d['service_ms']:fail('Service clock cannot pass its deadline')
  d['service_ms']-=p['milliseconds']
  if d['service_ms']==0:point(d,1-serving(d))
 elif k=='award_rally':point(d,p['winner'])
 elif k=='replay_point':d['phase']='ready';d['service_ms']=0
 elif k in ('substitute','enter'):
  if k=='substitute':
   old=p['outgoing']
   if d['players'][t][old]!='active' or d['servers'][t]==old and d['phase']!='game_break':fail('The game server may not be ordinarily replaced before the game ends')
   d['players'][t][old]='bench'
   if d['servers'][t]==old:d['servers'][t]=None
  new=p['incoming'] if k=='substitute' else p['player']
  if d['players'][t][new]!='bench' or len(active(d,t))>=3 or k=='substitute' and new==old:fail('Replacement requires an eligible reserve and an available place')
  d['players'][t][new]='active'
 elif k in ('withdraw_player','exclude_player'):
  i=p['player']
  if d['players'][t][i] in ('withdrawn','dq'):fail('Player is already unavailable')
  d['players'][t][i]='withdrawn' if k=='withdraw_player' else 'dq'
  if d['servers'][t]==i:d['servers'][t]=None
  if d['phase']=='service' and (d['servers'][serving(d)] is None or len(active(d,t))<2):d['phase']='ready';d['service_ms']=0
 elif k=='timeout':
  if d['timeouts'][t]>=2:fail('Two team timeouts are available for the match')
  d['timeouts'][t]+=1
  if d['phase']=='service':d['phase']='ready';d['service_ms']=0
 elif k=='penalty_point':point(d,1-t)
 elif k in ('concede','declare_incomplete'):d.update(phase='finished',winner=1-t,reason='concession' if k=='concede' else 'incomplete_team',service_ms=0)
 return d
def legal(state):
 d=state['data'];t=serving(d)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Game, service entitlement, roster and interruption rights must permit the event.'],external_observations=['Official rally, fault, exclusion and stoppage decisions.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],serving_team=t,server=None if t is None else d['servers'][t],point_labels=['0','15','30','45','game'],service_ms=d['service_ms'],change_ends=d['phase']=='game_break' and sum(d['games'])%3==0),completeness=False,reason='official_indoor_tamburello_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner'];league=None
 if done and d['reason']=='thirteen_games':league=[0,0];league[w]=3 if d['games'][1-w]<=10 else 2;league[1-w]=0 if d['games'][1-w]<=10 else 1
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[dict(player_id=state['players'][t]['id'],place=1 if t==w else 2,games=d['games'][t],championship_points=league[t] if league else None) for t in (0,1)] if done else [],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
