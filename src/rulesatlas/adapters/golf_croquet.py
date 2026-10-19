"""Thirteen-point level singles, recorded at completed official stroke boundaries."""
from copy import deepcopy
from ..values import fields,fail
from .pelota import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
E=lambda *x:dict(type='enum',values=list(x))
A=lambda x,n,m=None:dict(type='array',minItems=n,maxItems=n if m is None else m,items=x)
T=I(0,1);BALL=I(0,3);B=dict(type='boolean')
def owner(d,b):return (b%2+d['blue_owner'])%2
def counts(d):return [sum(owner(d,b)==t for b in d['hoops'])+d['awarded'][t] for t in (0,1)]
def finish(d,w,r):d.update(phase='finished',winner=w,reason=r)
def advance(d):
 d['next_ball']=(d['next_ball']+1)%4
 while d['lost_strokes'][owner(d,d['next_ball'])]:
  t=owner(d,d['next_ball']);d['lost_strokes'][t]-=1;d['next_ball']=(d['next_ball']+1)%4
SNAP=('next_ball','hoops','offside','penalty_area','lost_strokes')
def snapshot(d):return {k:deepcopy(d[k]) for k in SNAP}
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for j in range(len(d['hoops'])):
  if max(sum(owner(d,b)==t for b in d['hoops'][:j]) for t in (0,1))>=7:bad('No further hoop follows the winning seventh point')
 if any(d['offside'][b] and d['penalty_area'][b]!='none' for b in range(4)):bad('A directed ball cannot also be offside')
 if d['phase']=='choose_colors' and (d['hoops'] or d['next_ball']!=0):bad('Color allocation precedes play')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason']=='no_contest')!=(d['winner'] is None):bad('A result must identify winner or no contest')
  if d['reason'] in ('seven_points','misconduct','disqualification') and (counts(d)[d['winner']]!=7 or counts(d)[1-d['winner']]>=7):bad('Winning score must be seven against fewer than seven')
 else:
  if d['winner'] is not None or d['reason'] is not None or max(counts(d))>=7:bad('Ongoing game cannot contain a winning result')
 if any(d['awarded']) and d['reason'] not in ('misconduct','disqualification'):bad('Awarded points require an official match award')
 if (d['last'] is None)!=(d['last_actor'] is None):bad('Last-stroke snapshot and actor must agree')
 if d['last'] is not None:
  old=d['last']
  if len(old['hoops'])>len(d['hoops']) or old['hoops']!=d['hoops'][:len(old['hoops'])]:bad('Last-stroke snapshot must precede the current score')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 if ph=='choose_colors':return dict(choose_colors=dict(blue_owner=T))
 if ph=='ready':
  s.update(stroke=dict(player=T,ball=BALL,hoops=A(BALL,0,13),offside=A(B,4),fault=B,remedy=E('none','replay','swap','leave','replace'),entered_court=B),declare_stroke=dict(player=T,ball=BALL),offside_decision=dict(player=T,ball=BALL,direction=E('waive','D','E')),penalty_continuation=dict(reason=E('impasse','wrong_hoop','overlapping_unlawful','previous_opponent_ball'),cancel_hoops=I(0,13)),overlap_penalty=dict(player=T),misconduct=dict(player=T,severity=E('ordinary','lose_stroke','award_game','annul_last')),disqualify=dict(player=T))
  if d['last'] is not None:s['replay_last']=dict(reason=E('outside_interference','incorrect_information','wrong_mallet'))
 if ph=='penalty_toss':s['penalty_toss']=dict(first_ball=BALL,area=E('D','E'))
 s.update(concede=dict(player=T),abandon={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='choose_colors':d.update(blue_owner=p['blue_owner'],phase='ready')
 elif k in ('stroke','declare_stroke'):
  who=p['player'];ball=p['ball'];expected=d['next_ball'];entitled=owner(d,expected)
  if who!=entitled:fail('A stroke by the non-entitled side must be annulled, not entered as a completed turn')
  if d['offside'][ball]:fail('Obtain the opponent offside decision before recording this stroke')
  if k=='declare_stroke':
   if ball!=expected:fail('Declare the ball next in color sequence')
   d['last']=snapshot(d);d['last_actor']=who
   for b in range(4):
    if owner(d,b)!=who:d['offside'][b]=False
   advance(d)
  else:
   remedy=p['remedy'];fault=p['fault'];wrong=ball!=expected
   allowed=('leave','replace') if fault else ('replay','swap') if wrong and owner(d,ball)==who else ('replay',) if wrong else ('none',)
   if remedy not in allowed:fail('The declared remedy does not match the fault or wrong-ball rule')
   if not p['hoops'] and any(p['offside']):fail('New offside declarations require a newly scored hoop')
   if remedy in ('replay','replace') and (p['hoops'] or any(p['offside'])):fail('Replacement cancels all points and new offside declarations')
   if fault and any(owner(d,b)==who for b in p['hoops']):fail('A fault can retain points only for the non-offending side')
   if not p['entered_court'] and p['hoops']:fail('A boundary stroke not entering court cannot score')
   before=snapshot(d)
   if remedy=='replay':return d
   d['last']=before;d['last_actor']=who
   for b in range(4):
    if owner(d,b)!=who:d['offside'][b]=False
   if remedy!='replace':
    if p['entered_court']:d['penalty_area'][ball]='none'
    for b in p['hoops']:
     if max(counts(d))>=7:fail('Scoring stops at the winning seventh point')
     d['hoops'].append(b)
    if p['hoops']:
     if any(p['offside'][b] and d['penalty_area'][b]!='none' for b in range(4)):fail('Directed balls are exempt from a new offside declaration')
     d['offside']=p['offside'][:]
    if remedy=='swap':
     for field in ('offside','penalty_area'):d[field][ball],d[field][expected]=d[field][expected],d[field][ball]
   advance(d)
   if max(counts(d))==7:finish(d,counts(d).index(7),'seven_points')
 elif k=='offside_decision':
  b=p['ball']
  if not d['offside'][b] or p['player']==owner(d,b):fail('Only the offside opponent can direct or waive this ball')
  d['offside'][b]=False
  if p['direction']!='waive':d['penalty_area'][b]=p['direction']
 elif k=='penalty_continuation':
  n=p['cancel_hoops']
  if n>len(d['hoops']) or p['reason'] in ('impasse','overlapping_unlawful') and n:fail('This continuation cannot cancel the specified points')
  if n:d['hoops']=d['hoops'][:-n]
  d.update(phase='penalty_toss',offside=[False]*4,last=None,last_actor=None)
 elif k=='penalty_toss':d.update(next_ball=p['first_ball'],penalty_area=[p['area']]*4,phase='ready')
 elif k in ('misconduct','overlap_penalty','disqualify'):
  t=p['player'];severity=p.get('severity','lose_stroke')
  if k=='misconduct':
   d['warnings'][t]+=1
   if severity=='ordinary':severity='award_game' if d['warnings'][t]>=3 else 'lose_stroke' if d['warnings'][t]==2 else 'warn'
  if k=='disqualify' or severity=='award_game':
   w=1-t;d['awarded'][w]=7-counts(d)[w];finish(d,w,'disqualification' if k=='disqualify' else 'misconduct')
  elif severity=='annul_last':
   if d['last'] is None or d['last_actor']!=t:fail('Annulment requires the offending side last stroke')
   d.update(deepcopy(d['last']));d.update(last=None,last_actor=None)
  elif severity=='lose_stroke':
   if owner(d,d['next_ball'])==t:advance(d)
   else:d['lost_strokes'][t]+=1
 elif k=='replay_last':
  d.update(deepcopy(d['last']));d.update(last=None,last_actor=None)
 elif k=='concede':finish(d,1-p['player'],'concession')
 elif k=='abandon':d['phase']='abandoned'
 elif k=='official_result':finish(d,p['winner'],'no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data'];s=schemas(d)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Correct side, color sequence and remedy must agree with the recorded state.'],external_observations=['Official hoop completions, offside findings, faults, interference and opponent remedy choices.']) for k,v in s.items()],constraints=dict(phase=d['phase'],score=counts(d),hoop_in_order=len(d['hoops'])+1,next_ball=d['next_ball'],next_player=owner(d,d['next_ball']),offside=d['offside'],penalty_area=d['penalty_area'],warnings=d['warnings'],lost_strokes=d['lost_strokes']),completeness=False,reason='official_golf_croquet_stroke_events')
