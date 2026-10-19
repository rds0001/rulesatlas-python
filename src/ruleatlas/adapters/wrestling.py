"""Non-video adult freestyle wrestling with activity timing and score criteria."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
A=lambda x,n:dict(type='array',minItems=n,maxItems=n,items=x)
ACTIVITY=dict(type='object',properties=dict(player=I(0,1),remaining_ms=I(0,30000)),required=['player','remaining_ms'],nullable=True)
RECORD=dict(holds=A(A(I(0,1000),4),2),penalty_points=A(I(0,10000),2),cautions=A(I(0,3),2),last_point=dict(I(0,1),nullable=True),activity=ACTIVITY,remaining_ms=I(0,180000))
AWARD=dict(type='object',properties=dict(player=I(0,1),value=dict(type='integer',enum=[1,2,4,5])),required=['player','value'])
SCHEMAS=dict(start={},pause={},resume={},begin_second_period={},elapse=dict(milliseconds=I(1,180000)),score_action=dict(awards=dict(type='array',minItems=1,maxItems=16,items=AWARD),fall_winner=dict(I(0,1),nullable=True)),passivity_warning=dict(player=I(0,1)),start_activity=dict(player=I(0,1)),resolve_activity={},caution=dict(player=I(0,1),opponent_points=I(1,2)),fall=dict(winner=I(0,1)),correct_record=RECORD,disqualify=dict(loser=I(0,1)),forfeit=dict(loser=I(0,1)),both_disqualified={},confirm={})
VALUES=[1,2,4,5]
def scores(d):return [sum(n*v for n,v in zip(row,VALUES))+d['penalty_points'][i] for i,row in enumerate(d['holds'])]
def tie_winner(d):
 s=scores(d)
 if s[0]!=s[1]:return 0 if s[0]>s[1] else 1
 keys=[]
 for i,row in enumerate(d['holds']):
  maximum=max([v for n,v in zip(row,VALUES) if n] or [1]);count=row[VALUES.index(maximum)] if maximum>1 else s[i]
  keys.append((maximum,count,-d['cautions'][i]))
 if keys[0]!=keys[1]:return 0 if keys[0]>keys[1] else 1
 return d['last_point']
def finish(d,w,reason):d.update(phase='review',winner=w,reason=reason,activity=None)
def settle(d):
 d['winner']=None;d['reason']=None;s=scores(d)
 if max(d['cautions'])==3:finish(d,1-d['cautions'].index(3),'three_cautions')
 elif abs(s[0]-s[1])>=10:finish(d,0 if s[0]>s[1] else 1,'technical_superiority')
 elif d['activity'] is not None and d['activity']['remaining_ms']==0:d['phase']='paused'
 elif d['remaining_ms']==0:
  if d['period']==1:d['phase']='interval'
  else:
   w=tie_winner(d)
   if w is None:d['phase']='decision'
   else:finish(d,w,'points')
 else:d['phase']='paused'
def add(d,i,value,technical):
 if technical:d['holds'][i][VALUES.index(value)]+=1
 else:d['penalty_points'][i]+=value
 d['last_point']=i
 if d['activity'] is not None and d['activity']['player']==i:d['activity']=None

def mandatory_activity(d):return d['period']==1 and d['remaining_ms']<=60000 and scores(d)==[0,0] and d['activity'] is None

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');s=scores(d);terminal=d['phase'] in ('review','finished')
 if (sum(s)==0)!=(d['last_point'] is None) or d['last_point'] is not None and s[d['last_point']]==0:bad('Last-point identity must agree with the score record')
 if terminal!=(d['reason'] is not None):bad('Result phase and reason disagree')
 if d['phase']=='ready' and (d['period']!=1 or d['remaining_ms']!=180000 or sum(s) or any(d['cautions']) or any(d['warned']) or d['activity'] is not None):bad('Unstarted contest must have an empty record')
 if d['phase']=='interval' and (d['period']!=1 or d['remaining_ms'] or d['activity'] is not None):bad('Interval requires an expired first period')
 if d['phase'] in ('active','paused') and d['remaining_ms']==0 and d['activity'] is None:bad('Expired period requires resolution')
 if d['phase']=='active' and (mandatory_activity(d) or d['activity'] is not None and d['activity']['remaining_ms']==0):bad('Resolve the mandatory activity decision before resuming')
 if d['activity'] is not None:
  if d['phase'] not in ('active','paused') or d['activity']['remaining_ms']>d['remaining_ms'] or not d['warned'][d['activity']['player']]:bad('Activity clock must fit the remaining live period')
 if not terminal:
  if d['winner'] is not None or max(d['cautions'])==3 or abs(s[0]-s[1])>=10:bad('A winning result must enter review')
  if d['phase']=='decision' and (d['period']!=2 or d['remaining_ms'] or tie_winner(d) is not None):bad('Only unresolved expired records require adjudication')
 elif d['reason']=='both_disqualified':
  if d['winner'] is not None:bad('Double disqualification has no winner')
 else:
  w=d['winner']
  if w is None:bad('A decisive result requires a winner')
  if d['reason']=='technical_superiority' and s[w]-s[1-w]<10:bad('Technical superiority requires a ten-point margin')
  if d['reason']=='three_cautions' and d['cautions'][1-w]!=3:bad('Three cautions must belong to the losing wrestler')
  if d['reason']=='points' and (d['period']!=2 or d['remaining_ms'] or tie_winner(d)!=w):bad('Points winner must satisfy final score criteria')

def available(d):
 phase=d['phase'];names={'ready':['start'],'active':['pause','elapse','score_action','passivity_warning','start_activity','caution','fall'],'paused':['resume','score_action','passivity_warning','start_activity','caution','fall','correct_record'],'interval':['begin_second_period','correct_record'],'decision':['correct_record'],'review':['confirm'],'finished':[]}[phase]
 if phase=='paused' and d['activity'] is not None and d['activity']['remaining_ms']==0:names+=['resolve_activity']
 if phase=='review' and d['reason'] in ('technical_superiority','points','three_cautions'):names+=['correct_record']
 if phase!='finished':names+=['disqualify','forfeit','both_disqualified']
 return names

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in available(d):fail('Event is not permitted in this wrestling phase')
 fields(p,SCHEMAS[k],'/params')
 if k in ('start','resume'):
  if not d['remaining_ms'] or mandatory_activity(d) or d['activity'] is not None and d['activity']['remaining_ms']==0:fail('Resolve the period or activity decision before resuming')
  d['phase']='active'
 elif k=='pause':d['phase']='paused'
 elif k=='begin_second_period':d.update(period=2,remaining_ms=180000,phase='paused')
 elif k=='elapse':
  limit=d['remaining_ms']
  if d['activity'] is not None:limit=min(limit,d['activity']['remaining_ms'])
  if d['period']==1 and scores(d)==[0,0] and d['activity'] is None and d['remaining_ms']>60000:limit=min(limit,d['remaining_ms']-60000)
  if p['milliseconds']>limit:fail('Time cannot cross a period or mandatory activity boundary')
  d['remaining_ms']-=p['milliseconds']
  if d['activity'] is not None:d['activity']['remaining_ms']-=p['milliseconds']
  if d['remaining_ms']==0 or mandatory_activity(d) or d['activity'] is not None and d['activity']['remaining_ms']==0:settle(d)
 elif k=='score_action':
  for award in p['awards']:add(d,award['player'],award['value'],True)
  if p['fall_winner'] is not None:finish(d,p['fall_winner'],'fall')
  else:settle(d)
 elif k=='passivity_warning':
  if not d['remaining_ms'] or d['warned'][p['player']]:fail('The initial passivity warning is recorded once')
  d['warned'][p['player']]=True;d['phase']='paused'
 elif k=='start_activity':
  i=p['player']
  if d['remaining_ms']<30000 or d['activity'] is not None or not(d['warned'][i] or mandatory_activity(d)):fail('An activity period requires a prior warning or the scoreless first-period rule and thirty seconds')
  d['warned'][i]=True;d['activity']=dict(player=i,remaining_ms=30000);d['phase']='paused'
 elif k=='resolve_activity':
  i=d['activity']['player'];d['activity']=None;add(d,1-i,1,False);settle(d)
 elif k=='caution':
  i=p['player'];d['cautions'][i]+=1;add(d,1-i,p['opponent_points'],False);settle(d)
 elif k=='fall':finish(d,p['winner'],'fall')
 elif k=='correct_record':d.update(deepcopy(p));settle(d)
 elif k in ('disqualify','forfeit'):finish(d,1-p['loser'],k)
 elif k=='both_disqualified':finish(d,None,k)
 elif k=='confirm':d['phase']='finished'
 return d

def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Official completed-action awards, cautions, period and activity clocks must permit the event.'],external_observations=['Referee judgments, completed action sequences and elapsed active milliseconds.']) for k in available(d)],constraints=dict(phase=d['phase'],period=d['period'],remaining_ms=d['remaining_ms'],scores=scores(d),activity=d['activity'],mandatory_activity=mandatory_activity(d),video_challenges=False),completeness=False,reason='official_freestyle_rulings')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase'] in ('review','decision') else 'ongoing',result_kind=('no_contest' if w is None else 'forfeit' if d['reason']=='forfeit' else 'disqualification' if d['reason'] in ('disqualify','three_cautions') else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason=d['reason'] if done else 'official_decision_required' if d['phase']=='decision' else 'ongoing',evidence_required=['Official scoring-record correction.'] if d['phase']=='decision' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
