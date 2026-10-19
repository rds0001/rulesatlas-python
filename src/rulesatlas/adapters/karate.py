"""Classic three-minute kumite, two warning categories and no senshu."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
A=lambda x,n:dict(type='array',minItems=n,maxItems=n,items=x)
SCHEMAS=dict(start={},pause={},resume={},elapse=dict(milliseconds=I(1,180000)),award_scores=dict(points=A(I(0,3),2)),warning=dict(player=I(0,1),category=I(1,2),level=I(1,4)),correct_record=dict(scores=A(I(0,1000000),2),remaining_ms=I(0,180000)),hantei=dict(votes=A(I(0,1),5)),disqualify=dict(loser=I(0,1)),forfeit=dict(loser=I(0,1)),both_disqualified={},confirm={})
def settle(d):
 d['winner']=None;d['reason']=None;a,b=d['scores']
 if abs(a-b)>=8 or d['remaining_ms']==0 and a!=b:d.update(phase='review',winner=0 if a>b else 1,reason='points')
 elif d['remaining_ms']==0:d['phase']='decision'
 else:d['phase']='paused'
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');terminal=d['phase'] in ('review','finished')
 if terminal!=(d['reason'] is not None):bad('Result phase and reason disagree')
 if d['phase']=='ready' and (d['scores']!=[0,0] or d['penalties']!=[[0,0],[0,0]] or d['remaining_ms']!=180000):bad('Unstarted bout must have empty records')
 if d['phase'] in ('active','paused') and (d['remaining_ms']==0 or abs(d['scores'][0]-d['scores'][1])>=8):bad('A decided period cannot remain active')
 if d['phase']=='decision' and (d['remaining_ms'] or d['scores'][0]!=d['scores'][1]):bad('Hantei requires tied scores at time expiry')
 if not terminal:
  if d['winner'] is not None or any(4 in row for row in d['penalties']):bad('A winning decision must enter review')
 elif d['reason']=='both_disqualified':
  if d['winner'] is not None:bad('Double disqualification has no winner')
 else:
  w=d['winner']
  if w is None:bad('A decisive result requires a winner')
  if d['reason']=='points' and (d['scores'][w]<=d['scores'][1-w] or not(abs(d['scores'][0]-d['scores'][1])>=8 or d['remaining_ms']==0)):bad('Point victory requires an eight-point margin or a lead at time expiry')
  if d['reason']=='hantei' and (d['remaining_ms'] or d['scores'][0]!=d['scores'][1]):bad('Hantei requires a tied expired bout')
  if d['reason']=='hansoku' and 4 not in d['penalties'][1-w]:bad('Hansoku requires a final warning-category sanction')
def available(d):
 phase=d['phase'];names={'ready':['start'],'active':['pause','elapse','award_scores','warning'],'paused':['resume','award_scores','warning','correct_record'],'decision':['hantei','warning','correct_record'],'review':['confirm'],'finished':[]}[phase]
 if phase=='review' and d['reason']=='points':names+=['correct_record']
 if phase!='finished':names+=['disqualify','forfeit','both_disqualified']
 return names
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in available(d):fail('Event is not permitted in this bout phase')
 fields(p,SCHEMAS[k],'/params')
 if k in ('start','resume'):d['phase']='active'
 elif k=='pause':d['phase']='paused'
 elif k=='elapse':
  if p['milliseconds']>d['remaining_ms']:fail('Elapsed time cannot cross the bout boundary')
  d['remaining_ms']-=p['milliseconds']
  if d['remaining_ms']==0:settle(d)
 elif k=='award_scores':
  if not any(p['points']):fail('At least one official score is required')
  d['scores']=[d['scores'][i]+p['points'][i] for i in (0,1)];settle(d)
 elif k=='warning':
  i=p['player'];c=p['category']-1
  if p['level']<=d['penalties'][i][c]:fail('A warning category must progress to a higher sanction')
  d['penalties'][i][c]=p['level']
  if p['level']==4:d.update(phase='review',winner=1-i,reason='hansoku')
  elif d['phase']=='active':d['phase']='paused'
 elif k=='correct_record':d.update(deepcopy(p));settle(d)
 elif k=='hantei':d.update(phase='review',winner=1 if sum(p['votes'])>=3 else 0,reason='hantei')
 elif k in ('disqualify','forfeit'):d.update(phase='review',winner=1-p['loser'],reason=k)
 elif k=='both_disqualified':d.update(phase='review',winner=None,reason=k)
 elif k=='confirm':d['phase']='finished'
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Official score, independent warning-category progression and clock phase must permit the event.'],external_observations=['Recognized one-, two- or three-point scores, official sanctions, elapsed active time or five decision votes.']) for k in available(d)],constraints=dict(phase=d['phase'],remaining_ms=d['remaining_ms'],winning_margin=8,first_score_advantage=False),completeness=False,reason='official_classic_kumite_rulings')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('no_contest' if w is None else 'forfeit' if d['reason']=='forfeit' else 'disqualification' if d['reason'] in ('hansoku','disqualify') else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
