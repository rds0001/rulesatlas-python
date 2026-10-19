"""HPA 2022 outdoor polo, official match protocol without movement modelling."""
from copy import deepcopy
from ..values import fields,fail
from .handball import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
E=lambda *x:dict(type='enum',values=list(x))
A=lambda x,n:dict(type='array',minItems=n,maxItems=n,items=x)
T=I(0,1);P=I(0,7);NT=dict(T,nullable=True)
HITS=('p2','p3','p4','p5a','p5b','p6')
def totals(d):
 s=[2*x for x in d['goals']]
 if d['handicap']:
  diff=d['rating_peak'][0]-d['rating_peak'][1];numerator=abs(diff)*d['chukkas'];half=2*(numerator//6)+(numerator%6!=0)
  s[1 if diff>0 else 0]+=half
 return s
def available(d,t,p):return not(d['red'][t][p] or d['sinbin_ms'][t][p] or d['restricted'][t][p])
def finish(d,w,reason):d.update(phase='finished',clock_running=False,winner=w,reason=reason)
def golden(d):return d['chukka']>d['chukkas'] or(d['chukka']==d['chukkas'] and d['tail'])
def score(d,t):
 d['goals'][t]+=1;d['ends_reversed']=not d['ends_reversed'];d.update(restart='throw_in',restart_team=None,restart_delay_ms=0)
 if golden(d):finish(d,t,'golden_goal')
 elif d['tail']:d.update(phase='horn',clock_running=False)
 else:d.update(phase='restart',clock_running=True)
def pause(d,restart,team=None,whistle=True):
 d.update(phase='restart',restart=restart,restart_team=team,restart_delay_ms=0)
 if whistle:d['clock_running']=False
 if d['tail'] and d['chukka']<d['chukkas']:d.update(phase='horn',clock_running=False)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['tail'] and d['remaining_ms']>30000:bad('Second-bell tail is at most thirty seconds')
 if d['chukka']>d['chukkas'] and not d['knockout']:bad('Extra chukkas require a result-required match')
 for t in (0,1):
  if len(set(d['slots'][t]))!=4:bad('Four distinct players must occupy the team slots')
  if len(set(d['active'][t]))!=len(d['active'][t]) or any(p not in d['slots'][t] or not available(d,t,p) for p in d['active'][t]):bad('Active players must occupy eligible team slots')
  if d['rating_peak'][t]<sum(d['handicaps'][t][p] for p in d['slots'][t]):bad('Recorded handicap peak cannot be below the current team total')
  for p in range(8):
   if d['permanent_gap'][t][p] and not d['red'][t][p]:bad('A permanent unreplaceable gap requires a red flag')
  if len(set(d['played'][t]))!=len(d['played'][t]) or any(p not in d['played'][t] for p in d['slots'][t]):bad('Current slots must be included in player participation')
 if (d['restart'] in HITS+('hit_in','sideline','dropped_ball'))!=(d['restart_team'] is not None):bad('Restart entitlement must match the restart type')
 if d['phase'] in ('horn','interval','abandoned','finished') and d['clock_running']:bad('This phase stops the clock')
 if d['phase']=='live' and not d['clock_running']:bad('Live play requires a running clock')
 if d['phase']=='interval' and not d['pause_ms']:bad('Interval needs remaining break time')
 if d['phase']=='finished':
  s=totals(d)
  if d['reason']=='regulation' and d['winner']!=(None if s[0]==s[1] else int(s[1]>s[0])):bad('Result must agree with goals including handicap')
 elif d['winner'] is not None:bad('Only a finished match has a winner')

def advance(d,ms):
 if d['phase']=='interval':
  if ms>d['pause_ms']:fail('Advance only to the end of the interval')
  d['pause_ms']-=ms
  if not d['pause_ms']:
   d['chukka']+=1;d.update(phase='restart',remaining_ms=420000,tail=False,at_start=True,clock_running=False)
  return
 if not d['clock_running']:fail('The match clock is stopped')
 if ms>d['remaining_ms']:fail('Advance only to the next bell')
 d['remaining_ms']-=ms;d['at_start']=False
 for t in (0,1):d['sinbin_ms'][t]=[max(0,n-ms) for n in d['sinbin_ms'][t]]
 if d['phase']=='restart':d['restart_delay_ms']+=ms
 if d['remaining_ms']==0:
  if d['tail'] or (d['chukka']<d['chukkas'] and d['phase']=='restart') or (d['chukka']==d['chukkas'] and totals(d)[0]!=totals(d)[1]):
   if d['phase']=='live':d.update(restart='throw_in',restart_team=None)
   d.update(phase='horn',clock_running=False)
  else:d.update(tail=True,remaining_ms=30000)

def schemas(d):
 ph=d['phase'];out={}
 if ph=='finished':return out
 if ph=='abandoned':return dict(resume_match={},official_result=dict(winner=NT))
 out.update(abandon={},lineup=dict(team=T,players=dict(type='array',minItems=0,maxItems=4,items=P)),restrict_player=dict(team=T,player=P,restricted=dict(type='boolean')),substitute=dict(team=T,slots=A(P,4),approved=dict(type='boolean')),flag=dict(team=T,player=P,kind=E('yellow','double_yellow','red','red_unpermitted_exit')),correct_score=dict(goals=A(I(0,999),2)))
 if ph in ('live','restart','interval'):out['advance']=dict(ms=I(1,420000))
 if ph=='live':out.update(goal=dict(team=T),official_stop=dict(restart=E('throw_in','hit_in','sideline','dropped_ball'),team=NT,whistle=dict(type='boolean')),award_penalty=dict(team=T,penalty=E('p1',*HITS)))
 if ph in ('restart','horn'):out['award_penalty']=dict(team=T,penalty=E('p1',*HITS))
 if ph=='restart':
  if d['restart'] in HITS:out['penalty_attempt']=dict(player=P,wait_ms=I(0,20001),result=E('goal','backline','in_play','defender_violation','defender_prevents_goal','attacker_violation','both_violate'))
  else:out['restart_play']=dict(team=NT,wait_ms=I(0,25001))
 if ph=='live' and d['restricted_half_shot'] is not None:out['defender_played']={}
 if ph=='horn':out['close_chukka']={}
 return out

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];a=action['params'];ph=d['phase'];ss=schemas(d)
 if k not in ss:fail('Action is not permitted in this phase')
 fields(a,ss[k],'/params')
 if k=='advance':advance(d,a['ms'])
 elif k=='lineup':
  t=a['team'];ps=a['players']
  if len(set(ps))!=len(ps) or any(p not in d['slots'][t] or not available(d,t,p) for p in ps):fail('Lineup requires distinct eligible players in the four team slots')
  d['active'][t]=ps
 elif k=='restrict_player':
  t,p=a['team'],a['player'];d['restricted'][t][p]=a['restricted']
  if a['restricted'] and p in d['active'][t]:d['active'][t].remove(p)
 elif k=='substitute':
  t=a['team'];new=a['slots'];old=d['slots'][t]
  if not a['approved'] or len(set(new))!=4:fail('A substitute requires explicit tournament approval and distinct slots')
  if any(p not in old and (not available(d,t,p) or (p in d['played'][t] and not d['at_start'])) for p in new):fail('Returning substituted players may rejoin only at a chukka start; all entrants must be eligible')
  for before,after in zip(old,new):
   if before!=after and (d['sinbin_ms'][t][before] or d['permanent_gap'][t][before]):fail('A sin-binned or permanently unreplaceable player cannot be substituted')
  d['slots'][t]=new;d['active'][t]=[p for p in new if available(d,t,p)];d['played'][t]+= [p for p in new if p not in d['played'][t]]
  d['rating_peak'][t]=max(d['rating_peak'][t],sum(d['handicaps'][t][p] for p in new))
 elif k=='flag':
  t,p=a['team'],a['player'];kind=a['kind']
  if d['red'][t][p]:fail('Player is already dismissed')
  if kind.startswith('red'):
   d['red'][t][p]=True;d['yellow'][t][p]+=2;d['sinbin_ms'][t][p]=120000 if kind=='red' else 0;d['permanent_gap'][t][p]=kind=='red_unpermitted_exit'
  else:
   d['yellow'][t][p]+=1 if kind=='yellow' else 2
   if d['yellow'][t][p]>=2:d['sinbin_ms'][t][p]+=120000
  if not available(d,t,p) and p in d['active'][t]:d['active'][t].remove(p)
 elif k=='goal':score(d,a['team']);d['restricted_half_shot']=None
 elif k=='official_stop':
  if (a['restart']!='throw_in')!=(a['team'] is not None):fail('Only a neutral throw-in has no entitled team')
  pause(d,a['restart'],a['team'],a['whistle']);d['restricted_half_shot']=None
 elif k=='award_penalty':
  t=a['team'];pen=a['penalty'];d['restricted_half_shot']=None;d['moved_up_yards']=0
  if pen=='p1':
   score(d,t)
   if d['phase']!='finished':
    d.update(restart='p5b',restart_team=t,clock_running=False)
    if ph=='horn' and d['chukka']<d['chukkas']:d['phase']='horn'
    elif d['chukka']>=d['chukkas'] and d['remaining_ms']<5000:d.update(remaining_ms=5000,phase='restart')
  else:
   normal_tail=d['tail'] and d['chukka']<d['chukkas']
   pause(d,pen,t,True)
   if normal_tail or(ph=='horn' and d['chukka']<d['chukkas']):d['phase']='horn'
   elif d['chukka']>=d['chukkas'] and d['remaining_ms']<5000:d.update(remaining_ms=5000,phase='restart')
 elif k=='restart_play':
  if a['team']!=d['restart_team']:fail('Restart must respect team entitlement')
  limit=10000 if d['restart']=='hit_in' else 5000 if d['restart'] in ('sideline','dropped_ball') else 25000
  if a['wait_ms']>limit:
   if d['restart']=='hit_in':pause(d,'throw_in',None,True)
   elif d['restart']=='throw_in':fail('A delayed throw-in requires the official penalty decision')
   else:pause(d,'p5a',1-d['restart_team'],True)
  else:d.update(phase='live',clock_running=True,at_start=False,restart_delay_ms=0)
 elif k=='penalty_attempt':
  t=d['restart_team'];p=a['player'];kind=d['restart'];result=a['result']
  if p not in d['active'][t]:fail('Penalty taker must be an eligible active player')
  if a['wait_ms']>20000:result='attacker_violation'
  if result=='attacker_violation':pause(d,'p5a',1-t,True);d['moved_up_yards']=0
  elif result in ('defender_violation','both_violate'):
   if result=='defender_violation' and kind in ('p5a','p5b'):d['moved_up_yards']+=30
   d['clock_running']=False
  elif result in ('goal','defender_prevents_goal'):score(d,t)
  elif result=='backline':pause(d,'hit_in',1-t,False);d['clock_running']=True
  elif kind=='p2':pause(d,'p5a',1-t,True)
  else:d.update(phase='live',clock_running=True,restricted_half_shot=t if kind in ('p3','p4','p6') else None)
  d['at_start']=False
 elif k=='defender_played':d['restricted_half_shot']=None
 elif k=='correct_score':d['goals']=a['goals']
 elif k=='close_chukka':
  s=totals(d);different=s[0]!=s[1]
  if d['chukka']>=d['chukkas'] and (different or not d['knockout']):finish(d,None if not different else int(s[1]>s[0]),'regulation')
  else:
   if d['chukka']==(d['chukkas']+1)//2 and not sum(d['goals']):d['ends_reversed']=not d['ends_reversed']
   if d['chukka']>d['chukkas']:d['ends_reversed']=not d['ends_reversed']
   d.update(phase='interval',pause_ms=300000 if d['chukka']==(d['chukkas']+1)//2 or d['chukka']>=d['chukkas'] else 180000)
 elif k=='abandon':d['saved_phase']=d['phase'];d['saved_running']=d['clock_running'];d.update(phase='abandoned',clock_running=False)
 elif k=='resume_match':d.update(phase=d['saved_phase'],clock_running=d['saved_running'])
 elif k=='official_result':finish(d,a['winner'],'official' if a['winner'] is not None else 'no_contest')
 return d

def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Chukka, clock, restart entitlement, player eligibility and official substitution approval must permit the event.'],external_observations=['Official goals, fouls, flags, restart outcomes and tournament eligibility approval.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],chukka=d['chukka'],remaining_ms=d['remaining_ms'],tail=d['tail'],score_half_goals=totals(d),restart=d['restart'],restart_team=d['restart_team'],sinbin_ms=d['sinbin_ms'],rating_peak=d['rating_peak'],restricted_half_shot=d['restricted_half_shot'],moved_up_yards=d['moved_up_yards']),completeness=False,reason='official_outdoor_polo_events_without_trajectory_or_horse_simulation')
