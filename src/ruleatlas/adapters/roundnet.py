"""Doubles roundnet: service cycles, second serves and rally scoring."""
from copy import deepcopy
from ..values import fields,fail
TEAM=dict(type='integer',minimum=0,maximum=1)
SCHEMAS=dict(set_service_order=dict(order=dict(type='array',minItems=4,maxItems=4,items=dict(type='integer',minimum=0,maximum=3))),start_game={},serve=dict(result=dict(type='string',enum=['fault','ace','in_play','let'])),rally_result=dict(winner=TEAM),concede=dict(team=TEAM))
def winning_score(d):
 return next((i for i in (0,1) if d['scores'][i]>=21 and d['scores'][i]-d['scores'][1-i]>=2),None)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if sorted(d['service_order'])!=list(range(4)) or any(d['service_order'][i]//2==d['service_order'][(i+1)%4]//2 for i in range(4)):bad('Service order must alternate teams and include every player once')
 if d['phase']=='ready' and (d['scores']!=[0,0] or d['service_index']!=0 or d['faults']):bad('A new game starts with empty scoring and the first server')
 winner=winning_score(d)
 if d['phase']=='finished':
  if winner is None and d['conceded_by'] is None:bad('A finished game requires a two-point winning margin or concession')
  if d['faults']:bad('No unresolved serve remains after the game')
 else:
  if winner is not None or d['conceded_by'] is not None:bad('A decided game must be finished')
 if winner is not None and d['scores'][winner]>21 and d['scores'][winner]-d['scores'][1-winner]!=2:bad('Extended games end at the first two-point margin')
def point(d,team):
 serving=d['service_order'][d['service_index']]//2
 d['scores'][team]+=1;d['faults']=0
 if team!=serving:d['service_index']=(d['service_index']+1)%4
 d['phase']='finished' if winning_score(d) is not None else 'serve'
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in SCHEMAS:fail('Unknown roundnet event')
 fields(p,SCHEMAS[k],'/params')
 if d['phase']=='finished':fail('The game is finished')
 if k=='set_service_order':
  if d['phase']!='ready':fail('Declare the complete service order before play')
  d['service_order']=p['order'][:]
 elif k=='start_game':
  if d['phase']!='ready':fail('The game has already started')
  d['phase']='serve'
 elif k=='serve':
  if d['phase']!='serve':fail('A serve is not due')
  serving=d['service_order'][d['service_index']]//2
  if p['result']=='fault':
   if d['faults']==1:point(d,1-serving)
   else:d['faults']=1
  elif p['result']=='ace':point(d,serving)
  elif p['result']=='in_play':d['phase']='rally'
 elif k=='rally_result':
  if d['phase']!='rally':fail('A valid serve must begin the rally')
  point(d,p['winner'])
 elif k=='concede':
  d['conceded_by']=p['team'];d['phase']='finished';d['faults']=0
 return d
def legal(state):
 d=state['data'];names={'ready':['set_service_order','start_game','concede'],'serve':['serve','concede'],'rally':['rally_result','concede'],'finished':[]}[d['phase']]
 server=d['service_order'][d['service_index']]
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Game phase and the declared service cycle must permit the event.'],external_observations=['Official serve result, rally winner or concession.']) for k in names],constraints=dict(server=server,serving_team=server//2,receiving_team=1-server//2,serve_attempt=d['faults']+1,target=21,win_by=2),completeness=False,reason='official_roundnet_rally_judgments')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=(1-d['conceded_by'] if d['conceded_by'] is not None else winning_score(d)) if done else None
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[p['id'] for i,p in enumerate(state['players']) if i//2==w] if done else [],losers=[p['id'] for i,p in enumerate(state['players']) if i//2!=w] if done else [],placements=[],reason='concession' if d['conceded_by'] is not None else 'game_won' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
