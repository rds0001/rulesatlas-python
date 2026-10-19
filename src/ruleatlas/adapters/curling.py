"""Four-player team curling with abstract stone rulings and five-rock protection."""
from copy import deepcopy
from ..values import fields,fail
TEAM=dict(type='integer',minimum=0,maximum=1)
STONE=dict(type='object',properties=dict(status=dict(type='string',enum=['unplayed','dead','guard','other','house']),rank=dict(type='integer',minimum=1,maximum=16,nullable=True)),required=['status','rank'])
BOARD=dict(type='array',minItems=16,maxItems=16,items=STONE)
SCHEMAS=dict(start_match=dict(hammer=TEAM,ends=dict(type='integer',enum=[8,10])),deliver_stone=dict(board=BOARD),measure_stones=dict(board=BOARD),confirm_end={},concede=dict(team=TEAM))
def empty():return [dict(status='unplayed',rank=None) for _ in range(16)]
def next_stone(d):
 team=(1-d['hammer']) if d['delivered']%2==0 else d['hammer']
 return team,team*8+d['delivered']//2

def points(d):
 ranks=[[s['rank'] for s in d['board'][team*8:team*8+8] if s['status']=='house'] for team in (0,1)]
 nearest=[min(r) if r else 17 for r in ranks]
 if nearest[0]==nearest[1]:return [0,0]
 team=0 if nearest[0]<nearest[1] else 1;result=[0,0];result[team]=sum(r<nearest[1-team] for r in ranks[team]);return result

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['scores']!=[sum(r[t] for r in d['end_scores']) for t in (0,1)]:bad('Match totals must equal confirmed end scores')
 if any(r[0]>0 and r[1]>0 for r in d['end_scores']):bad('Only one team scores in an end')
 for s in d['board']:
  if (s['status']=='house')!=(s['rank'] is not None):bad('Only stones in the house have a scoring proximity rank')
 for team in (0,1):
  count=d['delivered']//2+int(d['delivered']%2==1 and team==1-d['hammer'])
  if any((s['status']!='unplayed')!=(i<count) for i,s in enumerate(d['board'][team*8:team*8+8])):bad('Stone inventory conflicts with alternating deliveries')
 if d['phase']=='setup' and (d['delivered'] or d['end_scores'] or d['conceded_by'] is not None):bad('The match has not started')
 if d['phase']=='delivering' and d['delivered']>=16:bad('The end requires score review')
 if d['phase']=='end_review' and d['delivered']!=16:bad('Complete all sixteen deliveries before end review')
 if d['phase']!='finished' and d['conceded_by'] is not None:bad('A conceded match is finished')
 if d['phase']=='finished' and d['conceded_by'] is None:
  if len(d['end_scores'])<d['scheduled_ends'] or d['scores'][0]==d['scores'][1] or d['delivered']!=16:bad('A completed match requires a confirmed decisive final end')
  if d['end_scores'][-1]!=points(d):bad('Final end score disagrees with the stones')
 if d['phase'] in ('delivering','end_review') and len(d['end_scores'])>=d['scheduled_ends'] and d['scores'][0]!=d['scores'][1]:bad('A decided match cannot continue to an extra end')

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in SCHEMAS:fail('Unknown curling event')
 fields(p,SCHEMAS[k],'/params')
 if d['phase']=='finished':fail('The match is finished')
 if k=='start_match':
  if d['phase']!='setup':fail('The match has already started')
  d['hammer']=p['hammer'];d['scheduled_ends']=p['ends'];d['phase']='delivering'
 elif k=='deliver_stone':
  if d['phase']!='delivering':fail('A delivery is not due')
  team,index=next_stone(d);new=deepcopy(p['board'])
  for i,(before,after) in enumerate(zip(d['board'],new)):
   if i==index:
    if after['status']=='unplayed':fail('The delivered stone must resolve on or off the playing area')
   elif before['status']=='unplayed' and after!=before:fail('Future stones cannot enter play')
   elif before['status']=='dead' and after!=before:fail('A removed stone cannot return during a delivery')
   elif before['status'] not in ('unplayed','dead') and after['status']=='unplayed':fail('A delivered stone cannot become unplayed')
  violation=d['delivered']<5 and any(i//8!=team and s['status']=='guard' and new[i]['status']=='dead' for i,s in enumerate(d['board']))
  if violation:new=deepcopy(d['board']);new[index]=dict(status='dead',rank=None)
  d['board']=new;d['delivered']+=1
  if d['delivered']==16:d['phase']='end_review'
 elif k=='measure_stones':
  if d['phase']!='end_review':fail('Measurements require completed-end review')
  for before,after in zip(d['board'],p['board']):
   if before['status'] in ('unplayed','dead') and after!=before or before['status'] not in ('unplayed','dead') and after['status'] in ('unplayed','dead'):fail('Measurements may change proximity and house membership, not stone inventory')
  d['board']=deepcopy(p['board'])
 elif k=='confirm_end':
  if d['phase']!='end_review':fail('Complete and review the end first')
  result=points(d);d['end_scores'].append(result);d['scores']=[d['scores'][i]+result[i] for i in (0,1)]
  if len(d['end_scores'])>=d['scheduled_ends'] and d['scores'][0]!=d['scores'][1]:d['phase']='finished'
  else:
   if result[0]>0:d['hammer']=1
   elif result[1]>0:d['hammer']=0
   d['delivered']=0;d['board']=empty();d['phase']='delivering'
 elif k=='concede':d['conceded_by']=p['team'];d['phase']='finished'
 return d

def legal(state):
 d=state['data'];names={'setup':['start_match','concede'],'delivering':['deliver_stone','concede'],'end_review':['measure_stones','confirm_end','concede'],'finished':[]}[d['phase']]
 team,index=next_stone(d) if d['phase']=='delivering' else (None,None)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Delivery order, stone inventory and end phase must permit the event.'],external_observations=['Official resulting stone statuses and proximity ranks after delivery or measurement.']) for k in names],constraints=dict(phase=d['phase'],end_number=len(d['end_scores'])+int(d['phase']!='finished' or d['conceded_by'] is not None),delivering_team=team,delivering_player=d['delivered']//4 if team is not None else None,stone_index=index,five_rock_protection=d['phase']=='delivering' and d['delivered']<5,provisional_end_score=points(d) if d['phase']=='end_review' else None),completeness=False,reason='official_curling_stone_rulings')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=(1-d['conceded_by'] if d['conceded_by'] is not None else 0 if d['scores'][0]>d['scores'][1] else 1) if done else None
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='end_review' else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[],reason='concession' if d['conceded_by'] is not None else 'match_finished' if done else 'end_review' if d['phase']=='end_review' else 'ongoing',evidence_required=['Official end-score agreement.'] if d['phase']=='end_review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
