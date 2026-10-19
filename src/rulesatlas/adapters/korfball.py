"""Korfball match protocol: official events, no ball or movement model."""
from copy import deepcopy
from ..values import fields,fail
from .pelota import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
T=I(0,1);P=I(0,13);B=dict(type='boolean')
E=lambda *x:dict(type='enum',values=list(x))
def active(d,t):return [i for i,z in enumerate(d['zones'][t]) if z>=0]
def attack(d,t,i):return d['zones'][t][i]==d['attack_zone']
def playable(d):
 for z in (0,1):
  a=[[sum(d['zones'][t][i]==(z if t==0 else 1-z) and d['gender'][t][i]==g for i in range(14)) for g in (0,1)] for t in (0,1)]
  if any(sum(x)<3 or max(x)>2 for x in a) or sum(min(a[0][g],a[1][g]) for g in (0,1))<3:return False
 return True
def finish(d,w,r):d.update(phase='finished',winner=w,reason=r,break_ms=0)
def score(d,t):
 d['score'][t]+=1
 if sum(d['score'])%2==0:d['attack_zone']=1-d['attack_zone']
 d.update(restart_team=1-t,restart_kind='throw_off',taker=None,free_faults=0)
 if d['period']==5:finish(d,t,'golden_goal')
 elif d['clock_ms']>0:d['phase']='stopped'
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['attack_zone']!=(sum(d['score'])//2)%2:bad('Attacking groups switch after every two goals')
 for t in (0,1):
  if d['gender'][t].count(0)!=7:bad('Registered roster requires seven players of each gender')
  for i in range(14):
   if d['zones'][t][i]>=0 and (d['cards'][t][i]==2 or d['cooldown_ms'][t][i]>0 or d['withdrawn'][t][i]):bad('Unavailable player cannot occupy a zone')
   if d['cooldown_ms'][t][i]>0 and d['cards'][t][i]!=1:bad('Temporary bench restriction requires a yellow card')
  for z in (0,1):
   if any(sum(d['missing'][t][z*4+g*2:z*4+g*2+2])+sum(d['zones'][t][i]==z and d['gender'][t][i]==g for i in range(14))!=2 for g in (0,1)):bad('Recorded vacancies must match missing group places')
   if any(sum(d['zones'][t][i]==z and d['gender'][t][i]==g for i in range(14))>2 for g in (0,1)):bad('Each group permits two players of each gender')
  c=d['captains'][t]
  if c is not None and (d['cards'][t][c]==2 or d['withdrawn'][t][c]):bad('Captain must remain eligible for the match')
 if d['phase']=='play' and (not playable(d) or None in d['captains']):bad('Live play requires valid matched groups and captains')
 if d['clock_ms']>(600000 if d['period']==5 else 750000):bad('Clock exceeds the declared period')
 if d['phase'] in ('play','stopped','timeout') and d['clock_ms']==0 and d['restart_kind']!='penalty':bad('Expired period must enter review')
 if d['phase']=='review' and d['clock_ms']!=0:bad('Period review requires an expired clock')
 if (d['phase'] in ('timeout','interval'))!=(d['break_ms']>0):bad('Break clock must agree with phase')
 if d['phase'] in ('shoot_setup','shootout') and (d['period']!=5 or d['clock_ms']!=0 or d['score'][0]!=d['score'][1]):bad('Shoot-out follows tied golden goal')
 if d['phase']=='shootout':
  if d['shoot_first'] is None or any(not x or len(x)!=len(set(x)) for x in d['shoot_order']):bad('Shoot-out requires fixed unique orders')
  n=d['shoot_taken'];f=d['shoot_first']
  if n[f] not in (n[1-f],n[1-f]+1) or any(d['shoot_score'][t]>n[t] for t in (0,1)):bad('Shoot-out attempts and goals are inconsistent')
  if n[0]==n[1] and d['shoot_score'][0]!=d['shoot_score'][1]:bad('Decisive equal-length pair must end the shoot-out')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason']=='no_contest')!=(d['winner'] is None):bad('Result needs winner or no-contest')
  if d['reason'] in ('regulation','golden_goal') and d['score'][d['winner']]<=d['score'][1-d['winner']]:bad('Winner must lead the match score')
 else:
  if d['winner'] is not None or d['reason'] is not None:bad('Unfinished match cannot have a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 if ph in ('stopped','review'):
  s['award_restart']=dict(team=T,kind=E('restart','free_pass','penalty','out_ball'),player=dict(P,nullable=True))
  if d['restart_kind']=='penalty':s['penalty']=dict(team=T,player=P,result=E('goal','miss','retake','attacker_fault'))
 if ph=='stopped':
  if d['restart_kind']!='penalty':s['restart']=dict(team=T,player=P,milliseconds=I(0,4000))
  if d['restart_kind']=='free_pass':s['free_pass_fault']=dict(team=T)
  s['timeout']=dict(team=T)
 if ph=='play':s.update(elapse=dict(milliseconds=I(1,750000)),goal=dict(team=T,player=P),stop={},shot_clock_violation=dict(team=T))
 if ph=='review':s.update(late_goal=dict(team=T,player=P),close_period=dict(next_throw_off=T))
 if ph in ('timeout','interval'):s['elapse_break']=dict(milliseconds=I(1,600000))
 if ph=='shoot_setup':s['set_shootout']=dict(first=T,orders=dict(type='array',minItems=2,maxItems=2,items=dict(type='array',minItems=1,maxItems=8,items=P)))
 if ph=='shootout':s['shoot_penalty']=dict(team=T,player=P,scored=B)
 if ph not in ('play','shootout','shoot_setup'):
  s.update(substitute=dict(team=T,out=P,**{'in':P}),replace_missing=dict(team=T,slot=I(0,7),player=P),appoint_captain=dict(team=T,player=P))
 if ph not in ('shootout','shoot_setup'):
  s.update(card=dict(team=T,player=P,color=E('yellow','red')),withdraw=dict(team=T,player=P),coach_card=dict(team=T,color=E('yellow','red')))
 s.update(abandon={},concede=dict(team=T))
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d);t=p.get('team');i=p.get('player')
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='restart':
  if t!=d['restart_team'] or i not in active(d,t) or d['restart_kind'] in ('throw_off','free_pass') and not attack(d,t,i) or not playable(d) or None in d['captains']:fail('Restart requires entitled player, valid groups and captains')
  n=p['milliseconds']
  if n>d['clock_ms']:fail('Restart duration exceeds remaining period')
  d['clock_ms']-=n;d['phase']='play' if d['clock_ms'] else 'review';d['timeout_used_stop']=False;d['return_blocked']=[[False]*14 for _ in (0,1)]
  for a in (0,1):d['cooldown_ms'][a]=[max(0,x-n) for x in d['cooldown_ms'][a]];d['coach_ms'][a]=max(0,d['coach_ms'][a]-n)
 elif k=='elapse':
  n=p['milliseconds']
  if n>d['clock_ms']:fail('Elapsed time exceeds remaining period')
  d['clock_ms']-=n
  for a in (0,1):d['cooldown_ms'][a]=[max(0,x-n) for x in d['cooldown_ms'][a]];d['coach_ms'][a]=max(0,d['coach_ms'][a]-n)
  if d['clock_ms']==0:d.update(phase='review',late_used=False,restart_kind='none',taker=None)
 elif k in ('goal','late_goal'):
  if not attack(d,t,i) or k=='late_goal' and d['late_used']:fail('Goal requires an active attacker and an unresolved pre-buzzer shot')
  if k=='late_goal':d['late_used']=True
  score(d,t)
 elif k=='stop':d.update(phase='stopped',restart_kind='restart',taker=None)
 elif k=='shot_clock_violation':d.update(phase='stopped',restart_team=1-t,restart_kind='restart',taker=None,free_faults=0)
 elif k=='award_restart':
  if p['kind'] in ('penalty','free_pass') and (i is None or not attack(d,t,i)):fail('Penalty needs the officially designated active attacker')
  if d['phase']=='review' and p['kind']!='penalty':fail('Only an outstanding penalty extends an expired period')
  d.update(restart_team=t,restart_kind=p['kind'],taker=i if p['kind'] in ('penalty','free_pass') else None,free_faults=0)
 elif k=='free_pass_fault':
  if t==d['restart_team']:d.update(restart_team=1-t,restart_kind='restart',free_faults=0)
  else:
   d['free_faults']+=1
   if d['free_faults']==2:d.update(restart_kind='penalty')
 elif k=='penalty':
  if t!=d['restart_team'] or not attack(d,t,i) or d['taker'] is not None and i!=d['taker']:fail('Use the entitled penalty taker')
  r=p['result']
  if r=='goal':score(d,t)
  elif r!='retake':d.update(restart_kind='restart',restart_team=1-t if r=='attacker_fault' else t,taker=None,phase='review' if not d['clock_ms'] else 'stopped')
 elif k=='close_period':
  if d['restart_kind']=='penalty':fail('Resolve the outstanding penalty first')
  q=d['period']
  if q==4 and d['score'][0]!=d['score'][1]:finish(d,int(d['score'][1]>d['score'][0]),'regulation')
  elif q==5:d['phase']='shoot_setup'
  else:d.update(period=q+1,clock_ms=600000 if q==4 else 750000,phase='interval',break_ms=600000 if q==2 else 60000,restart_team=1 if q==2 else p['next_throw_off'],restart_kind='throw_off',taker=None,late_used=False,timeout_used_stop=False)
 elif k=='timeout':
  if d['timeouts'][t]>=2 or d['timeout_used_stop'] or d['coach_ms'][t]>0:fail('Timeout allowance, restart or coaching restriction prevents this timeout')
  d['timeouts'][t]+=1;d.update(phase='timeout',break_ms=60000,timeout_used_stop=True)
 elif k=='elapse_break':
  if p['milliseconds']>d['break_ms']:fail('Elapsed time exceeds break')
  d['break_ms']-=p['milliseconds']
  if not d['break_ms']:d['phase']='stopped'
 elif k=='substitute':
  o=p['out'];j=p['in']
  if o not in active(d,t) or d['zones'][t][j]>=0 or d['cards'][t][j]==2 or d['withdrawn'][t][j] or d['cooldown_ms'][t][j] or d['return_blocked'][t][j] or d['gender'][t][o]!=d['gender'][t][j] or d['substitutions'][t]>=8 or any(d['missing'][t]) or d['coach_ms'][t]>0:fail('Substitution is not permitted for this roster or allowance')
  d['zones'][t][j]=d['zones'][t][o];d['zones'][t][o]=-1;d['return_blocked'][t][o]=True;d['substitutions'][t]+=1
  if d['taker']==o and d['restart_team']==t:d['taker']=None
 elif k=='replace_missing':
  slot=p['slot'];z=slot//4;g=(slot%4)//2
  if not d['missing'][t][slot] or d['zones'][t][i]>=0 or d['gender'][t][i]!=g or d['cards'][t][i]==2 or d['withdrawn'][t][i] or d['cooldown_ms'][t][i] or d['return_blocked'][t][i]:fail('Replacement must fill a recorded vacancy with an eligible matching player')
  d['missing'][t][slot]=False;d['zones'][t][i]=z
 elif k=='appoint_captain':
  if d['captains'][t] is not None or i not in active(d,t):fail('A replacement captain must be an active player after permanent departure')
  d['captains'][t]=i
 elif k in ('card','withdraw'):
  if d['cards'][t][i]==2 or d['withdrawn'][t][i]:fail('Player is already permanently unavailable')
  if k=='withdraw':d['withdrawn'][t][i]=True
  else:d['cards'][t][i]=2 if p['color']=='red' else d['cards'][t][i]+1;d['cooldown_ms'][t][i]=240000 if d['cards'][t][i]==1 else 0
  z=d['zones'][t][i]
  if z>=0:
   g=d['gender'][t][i];slot=z*4+g*2
   if d['missing'][t][slot]:slot+=1
   d['missing'][t][slot]=True;d['zones'][t][i]=-1;d['substitutions'][t]+=1
   if d['restart_team']==t and d['taker']==i:d['taker']=None
  if (k=='withdraw' or d['cards'][t][i]==2) and d['captains'][t]==i:d['captains'][t]=None
  if d['phase']=='play':d.update(phase='stopped',restart_kind='restart')
 elif k=='coach_card':
  if d['coach_cards'][t]==2:fail('Coaching staff is already excluded')
  d['coach_cards'][t]=2 if p['color']=='red' else d['coach_cards'][t]+1;d['coach_ms'][t]=240000
  if d['phase']=='play':d.update(phase='stopped',restart_kind='restart')
 elif k=='set_shootout':
  for a in (0,1):
   if sorted(p['orders'][a])!=sorted(active(d,a)):fail('Shoot-out order must contain every on-court player exactly once')
  d.update(shoot_first=p['first'],shoot_order=p['orders'],phase='shootout')
 elif k=='shoot_penalty':
  f=d['shoot_first'];n=d['shoot_taken'];turn=f if n[f]==n[1-f] else 1-f
  if t!=turn or i!=d['shoot_order'][t][n[t]%len(d['shoot_order'][t])]:fail('Follow alternating teams and the registered player sequence')
  n[t]+=1;d['shoot_score'][t]+=int(p['scored'])
  if n[0]==n[1] and d['shoot_score'][0]!=d['shoot_score'][1]:finish(d,int(d['shoot_score'][1]>d['shoot_score'][0]),'shootout')
 elif k=='abandon':d.update(phase='abandoned',break_ms=0)
 elif k=='concede':finish(d,1-t,'concession')
 elif k=='official_result':finish(d,p['winner'],'no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data'];s=schemas(d)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Phase, roster eligibility and event-specific allowances must permit the event.'],external_observations=['Official goals, restart decisions, shot-clock violations and sanctions.']) for k,v in s.items()],constraints=dict(phase=d['phase'],score=d['score'],period=d['period'],clock_ms=d['clock_ms'],attack_zone=d['attack_zone'],restart_team=d['restart_team'],restart_kind=d['restart_kind'],substitutions=d['substitutions'],cooldown_ms=d['cooldown_ms'],playable=playable(d),shoot_score=d['shoot_score']),completeness=False,reason='official_korfball_match_events')
