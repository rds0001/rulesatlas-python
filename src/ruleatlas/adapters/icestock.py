"""Six-end team icestock with official proximity rulings and player eligibility."""
from copy import deepcopy
from ..values import fields,fail
TEAM=dict(type='integer',minimum=0,maximum=1);PLAYER=dict(type='integer',minimum=0,maximum=3)
STONE=dict(type='object',properties=dict(status=dict(type='string',enum=['unplayed','live','dead']),rank=dict(type='integer',minimum=1,maximum=8,nullable=True)),required=['status','rank'])
BOARD=dict(type='array',minItems=8,maxItems=8,items=STONE)
SCHEMAS=dict(start_match=dict(first_team=TEAM),deliver_stock=dict(team=TEAM,player=PLAYER,board=BOARD),set_available=dict(team=TEAM,player=PLAYER,available=dict(type='boolean')),disqualify_player=dict(team=TEAM,player=PLAYER),assess_penalty=dict(team=TEAM,points=dict(type='integer',minimum=1,maximum=100)),agree_end={},repeat_end={},measure_stocks=dict(board=BOARD),confirm_end={},confirm_match={},abandon_match={})
def empty():return [dict(status='unplayed',rank=None) for _ in range(8)]
def remaining(d,t):return [i for i in range(4) if d['available'][t][i] and d['board'][t*4+i]['status']=='unplayed']
def nearest(d,t):return min([s['rank'] for s in d['board'][t*4:t*4+4] if s['status']=='live'] or [9])
def next_team(d,last):
 a=nearest(d,0);b=nearest(d,1);team=last if a==b else 0 if a>b else 1
 return team if remaining(d,team) else 1-team if remaining(d,1-team) else None

def points(d):
 a=nearest(d,0);b=nearest(d,1);r=[0,0]
 if a!=b:
  t=0 if a<b else 1;r[t]=sum(s['status']=='live' and s['rank']<nearest(d,1-t) for s in d['board'][t*4:t*4+4])
 return r

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['scores']!=[sum(r[t] for r in d['end_scores']) for t in (0,1)]:bad('Score totals must equal confirmed ends')
 if any(r[0] and r[1] for r in d['end_scores']):bad('Only one team scores positive stock points in an end')
 for s in d['board']:
  if (s['status']=='live')!=(s['rank'] is not None):bad('Only valid live stocks have proximity ranks')
 for t in (0,1):
  if any(a and dq for a,dq in zip(d['available'][t],d['dismissed'][t])):bad('Dismissed players cannot be available')
  if d['phase'] in ('playing','end_review','match_review') and sum(d['available'][t])<3:bad('An incomplete team requires competition adjudication')
 if d['phase']=='setup' and (d['end_scores'] or any(s['status']!='unplayed' for s in d['board']) or d['early_end']):bad('Unstarted match must have an empty board')
 if d['phase']=='playing':
  if d['turn'] is None or not remaining(d,d['turn']) or d['early_end']:bad('The next team needs an available unused delivery')
  if any(s['status']!='unplayed' for s in d['board']) and d['last_team'] is not None and d['turn']!=next_team(d,d['last_team']):bad('Turn contradicts the current best position')
 if d['phase']=='end_review' and not d['early_end'] and (remaining(d,0) or remaining(d,1)):bad('Unplayed stocks require mutual early-end agreement')
 if d['phase'] in ('match_review','finished') and len(d['end_scores'])!=6:bad('Six confirmed ends are required')
 if d['phase'] in ('playing','end_review') and len(d['end_scores'])>=6:bad('The six-end match is complete')
 if d['phase'] not in ('setup','playing') and d['turn'] is not None:bad('No delivery is due outside active play')

def settle(d,last):
 d['last_team']=last;d['turn']=next_team(d,last)
 if d['turn'] is None:d['phase']='end_review'
def restart(d):
 d['board']=empty();d['early_end']=False;d['last_team']=None;d['turn']=(d['first_team']+len(d['end_scores']))%2;d['phase']='playing'

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in SCHEMAS:fail('Unknown icestock event')
 fields(p,SCHEMAS[k],'/params')
 if d['phase'] in ('finished','abandoned'):fail('Match is not open')
 if k=='start_match':
  if d['phase']!='setup' or any(sum(a)<3 for a in d['available']):fail('Each team needs at least three eligible players')
  d['first_team']=p['first_team'];restart(d)
 elif k=='deliver_stock':
  t=p['team'];i=t*4+p['player']
  if d['phase']!='playing' or t!=d['turn'] or p['player'] not in remaining(d,t):fail('Wrong team or already used or unavailable player')
  new=deepcopy(p['board'])
  for j,(before,after) in enumerate(zip(d['board'],new)):
   if j==i:
    if after['status']=='unplayed':fail('A delivery must resolve live or dead')
   elif before['status'] in ('unplayed','dead') and after!=before:fail('Unused or removed stocks cannot be introduced by another delivery')
   elif before['status']=='live' and after['status']=='unplayed':fail('A played stock cannot become unplayed')
  d['board']=new;settle(d,t)
 elif k in ('set_available','disqualify_player'):
  t=p['team'];i=p['player']
  if k=='set_available':
   if d['dismissed'][t][i] and p['available']:fail('A dismissed player cannot return')
   d['available'][t][i]=p['available']
  else:d['dismissed'][t][i]=True;d['available'][t][i]=False
  if d['phase']!='setup' and sum(d['available'][t])<3:d['phase']='abandoned';d['turn']=None
  elif d['phase']=='playing':settle(d,d['last_team'] if d['last_team'] is not None else d['turn'])
 elif k=='assess_penalty':d['penalties'][p['team']]+=p['points']
 elif k=='agree_end':
  if d['phase']!='playing':fail('Only an active end can be ended early by agreement')
  d['early_end']=True;d['turn']=None;d['phase']='end_review'
 elif k=='repeat_end':
  if d['phase'] not in ('playing','end_review'):fail('Only the unresolved end may be repeated')
  restart(d)
 elif k=='measure_stocks':
  if d['phase']!='end_review':fail('Measurement correction requires end review')
  if any(a['status']!=b['status'] for a,b in zip(d['board'],p['board'])):fail('Measurement changes proximity, not stock inventory')
  d['board']=deepcopy(p['board'])
 elif k=='confirm_end':
  if d['phase']!='end_review':fail('Resolve the end before confirming its score')
  r=points(d);d['end_scores'].append(r);d['scores']=[d['scores'][t]+r[t] for t in (0,1)]
  if len(d['end_scores'])==6:d['phase']='match_review';d['turn']=None
  else:restart(d)
 elif k=='confirm_match':
  if d['phase']!='match_review':fail('Six confirmed ends are required')
  d['phase']='finished'
 elif k=='abandon_match':d['phase']='abandoned';d['turn']=None
 return d

def legal(state):
 d=state['data'];names={'setup':['start_match'],'playing':['deliver_stock','agree_end','repeat_end'],'end_review':['measure_stocks','confirm_end','repeat_end'],'match_review':['confirm_match'],'finished':[],'abandoned':[]}[d['phase']]
 if d['phase'] not in ('finished','abandoned'):names+=['set_available','disqualify_player','assess_penalty','abandon_match']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Team eligibility, available deliveries and end phase must permit the event.'],external_observations=['Official final stock proximities, penalty, availability or agreed-end ruling.']) for k in names],constraints=dict(phase=d['phase'],next_team=d['turn'],available_players=remaining(d,d['turn']) if d['turn'] is not None else [],provisional_end_score=points(d) if d['phase']=='end_review' else None),completeness=False,reason='official_icestock_rulings')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';scores=[d['scores'][t]-d['penalties'][t] for t in (0,1)];w=None if scores[0]==scores[1] else 0 if scores[0]>scores[1] else 1
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase'] in ('end_review','match_review','abandoned') else 'ongoing',result_kind=('draw' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason='match_finished' if done else 'competition_decision_required' if d['phase']=='abandoned' else 'ongoing',evidence_required=['Official competition decision.'] if d['phase']=='abandoned' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
