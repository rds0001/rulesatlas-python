"""CMAS 2025 underwater hockey: official events and match-clock consequences."""
from copy import deepcopy
from ..values import fields,fail
from .handball import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
E=lambda *x:dict(type='enum',values=list(x))
A=lambda s,a,b:dict(type='array',minItems=a,maxItems=b,items=s)
T=I(0,1);P=I(0,9);NT=dict(T,nullable=True)
def capacity(d,t):return max(0,6-sum(d['dismissed'][t])-sum(ms>0 or pending>0 or ready for ms,pending,ready in zip(d['penalties'][t],d['pending_ms'][t],d['release_ready'][t])))
def eligible(d,t,p):return not(d['dismissed'][t][p] or d['penalties'][t][p] or d['pending_ms'][t][p] or d['release_ready'][t][p] or d['restricted'][t][p])
def stop_clock(d):return d['period']==5 or (d['period'] in (2,4) and d['remaining_ms']<=120000)
def restart(d,kind='equal',team=None,force_stop=False):
 d.update(phase='restart',restart_kind=kind,restart_team=team,restart_wait_ms=0,contact_ms=0,goal_review=False)
 if force_stop or (kind!='goal' and stop_clock(d)):d['clock_running']=False

def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason,clock_running=False,shot_team=None)
def scored(d,t):
 d['scores'][t]+=1
 if d['period']==5:finish(d,t,'sudden_death_goal')
 else:restart(d,'goal');d['clock_running']=True

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['period']>2 and not d['knockout']:bad('Overtime requires knockout rules')
 if d['period'] in (3,4) and d['remaining_ms']>300000:bad('Overtime halves last five minutes')
 if d['period']==5 and d['remaining_ms']!=0:bad('Sudden death has no countdown limit')
 for t in (0,1):
  if len(set(d['active'][t]))!=len(d['active'][t]):bad('Active player ids must be distinct')
  if any(not eligible(d,t,p) for p in d['active'][t]):bad('Only eligible players may be active')
  if d['phase'] in ('live','await_contact') and len(d['active'][t])>capacity(d,t):bad('Active lineup exceeds the available team places')
  for p in range(10):
   ms=d['penalties'][t][p];ready=d['release_ready'][t][p];pending=d['pending_ms'][t][p]
   if (ready and (ms or pending)) or (d['return_blocked'][t][p] and not ready):bad('Penalty timer, release and start flags disagree')
   if d['dismissed'][t][p] and (ms or ready or pending):bad('Dismissal replaces the player timed exclusion')
   if len(set(d['cautions'][t][p]))!=len(d['cautions'][t][p]):bad('Individual caution categories must be distinct')
  if len(set(d['team_cautions'][t]))!=len(d['team_cautions'][t]):bad('Team caution categories must be distinct')
 if (d['phase']=='penalty_shot')!=(d['shot_team'] is not None):bad('Penalty-shot phase requires an attacking team')
 if d['restart_kind']=='advantage' and d['restart_team'] is None:bad('Advantage restart requires an entitled team')
 if d['restart_kind']!='advantage' and d['restart_team'] is not None:bad('Neutral restart has no entitled team')
 if d['phase'] in ('interval','team_timeout','penalty_shot','horn','abandoned','finished') and d['clock_running']:bad('This phase stops the game clock')
 if d['phase'] in ('live','await_contact') and not d['clock_running']:bad('Active play requires a running match clock')
 if d['phase']=='restart' and stop_clock(d) and d['restart_kind']!='goal' and d['clock_running']:bad('Late ordinary stoppage must stop the clock')
 if d['phase']=='horn' and (d['remaining_ms']!=0 or d['period']==5):bad('Horn requires an expired timed period')
 if d['phase']=='team_timeout' and (d['period']>2 or d['pause_ms']<=0):bad('Team timeout requires remaining regulation timeout time')
 if d['phase']=='interval' and (d['period']==5 or d['pause_ms']<=0):bad('Interval requires time before the next period')
 if d['phase']=='finished':
  if d['reason']=='regulation' and d['winner']!=(None if d['scores'][0]==d['scores'][1] else int(d['scores'][1]>d['scores'][0])):bad('Result must agree with the final goals')
 elif d['winner'] is not None:bad('Only a finished match can have a winner')

def tick(d,ms):
 if d['phase'] in ('interval','team_timeout'):
  if ms>d['pause_ms']:fail('Advance only to the end of this break')
  d['pause_ms']-=ms
  if d['pause_ms']==0:
   if d['phase']=='interval':
    d['period']+=1;d['remaining_ms']=900000 if d['period']==2 else 300000 if d['period'] in (3,4) else 0
    if d['period']==2:d['timeouts']=[0,0]
    restart(d,'start',force_stop=True)
   else:restart(d,d['restart_kind'],d['restart_team'],True)
  return
 if not d['clock_running']:fail('The game clock is stopped')
 if d['period']!=5 and ms>d['remaining_ms']:fail('Advance only to the period horn')
 if d['phase']=='restart':
  if d['restart_kind']=='goal' and d['restart_wait_ms']+ms>30000:fail('Goal restart must occur within thirty seconds')
  if d['restart_kind']!='goal' and d['period'] in (2,4) and d['remaining_ms']>120000 and d['remaining_ms']-ms<120000:fail('Stop the clock exactly at the final two-minute boundary')
 if d['phase']=='await_contact' and d['restart_kind']=='advantage' and d['contact_ms']+ms>5000:fail('Resolve the five-second advantage-puck deadline first')
 for t in (0,1):
  for p in range(10):
   if d['penalties'][t][p]:
    d['penalties'][t][p]=max(0,d['penalties'][t][p]-ms)
    if not d['penalties'][t][p] and not d['pending_ms'][t][p]:d['release_ready'][t][p]=True;d['return_blocked'][t][p]=d['phase']=='restart'
 if d['phase']=='restart':d['restart_wait_ms']+=ms
 if d['phase']=='await_contact':d['contact_ms']+=ms
 if d['period']!=5:d['remaining_ms']-=ms
 if d['period']!=5 and not d['remaining_ms']:d.update(phase='horn',clock_running=False,horn_review_open=True)
 elif d['phase']=='await_contact' and d['restart_kind']=='advantage' and d['contact_ms']==5000:restart(d,'equal')
 elif d['phase']=='restart' and d['restart_kind']!='goal' and stop_clock(d):d['clock_running']=False

def schemas(d):
 ph=d['phase'];out={}
 if ph=='finished':return out
 if ph=='abandoned':return dict(official_result=dict(winner=NT))
 out.update(abandon={},lineup=dict(team=T,players=A(P,0,6)),restrict_player=dict(team=T,player=P,restricted=dict(type='boolean')))
 if ph in ('live','await_contact','restart','interval','team_timeout'):out['advance']=dict(ms=I(1,900000))
 if ph=='restart':out.update(whistle={},team_timeout=dict(team=T))
 if ph=='await_contact':out['complete_restart']=dict(team=T)
 if ph in ('live','await_contact'):out['official_stop']=dict(kind=E('equal','advantage'),team=NT,stop_time=dict(type='boolean'))
 if ph in ('live','restart','horn'):out.update(goal=dict(team=T),award_shot=dict(team=T))
 if ph in ('restart','horn','team_timeout','interval','penalty_shot'):
  out.update(sanction=dict(team=T,player=P,category=I(0,23),kind=E('caution','one_minute','two_minutes','five_minutes','dismissal'),team_caution=dict(type='boolean')),dismiss_staff=dict(team=T,staff=I(0,3)))
 if ph in ('live','await_contact','restart'):out['release_player']=dict(team=T,player=P)
 if ph=='penalty_shot':out['resolve_shot']=dict(attackers=A(P,2,2),defender=P,first_contact_ms=I(0,5001),result=E('goal','defended','attacker_foul','defender_foul','no_contact'))
 if ph=='horn':out['close_period']={}
 return out

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];a=action['params'];ss=schemas(d);ph=d['phase']
 if k not in ss:fail('Action is not permitted in this phase')
 fields(a,ss[k],'/params')
 if k=='advance':tick(d,a['ms'])
 elif k=='lineup':
  t=a['team'];ps=a['players']
  if len(set(ps))!=len(ps) or len(ps)>capacity(d,t) or any(not eligible(d,t,p) for p in ps):fail('Lineup requires distinct eligible players within the available team places')
  d['active'][t]=ps
 elif k=='restrict_player':
  t,p=a['team'],a['player'];d['restricted'][t][p]=a['restricted']
  if a['restricted'] and p in d['active'][t]:d['active'][t].remove(p)
 elif k=='whistle':
  if any(len(d['active'][t])>capacity(d,t) for t in (0,1)):fail('Remove excess players before the restart')
  if not d['started'] and any(len(ps)<4 for ps in d['active']):fail('Match start requires at least four players per team')
  d.update(phase='await_contact',clock_running=True,contact_ms=0,started=True,goal_review=False)
  for t in (0,1):
   for p in range(10):d['penalties'][t][p]+=d['pending_ms'][t][p];d['pending_ms'][t][p]=0
 elif k=='complete_restart':
  if d['restart_kind']=='advantage' and a['team']!=d['restart_team']:fail('The entitled team must take the advantage puck first')
  d.update(phase='live',contact_ms=0);d['return_blocked']=[[False]*10 for _ in (0,1)]
 elif k=='official_stop':
  if (a['kind']=='advantage')!=(a['team'] is not None):fail('Only an advantage restart identifies an entitled team')
  restart(d,a['kind'],a['team'],a['stop_time']);d['goal_review']=True
 elif k=='goal':
  if ph=='restart' and not d['goal_review']:fail('No unresolved official scoring review')
  if ph=='horn' and not d['horn_review_open']:fail('The horn scoring review is already resolved')
  scored(d,a['team'])
  if ph=='horn':d.update(phase='horn',clock_running=False,horn_review_open=False)
 elif k=='award_shot':
  if ph=='restart' and not d['goal_review']:fail('No unresolved official scoring review')
  if ph=='horn' and not d['horn_review_open']:fail('The horn scoring review is already resolved')
  d.update(phase='penalty_shot',clock_running=False,shot_team=a['team'],horn_review_open=False)
 elif k=='resolve_shot':
  t=d['shot_team'];ps=a['attackers'];q=a['defender'];result=a['result']
  if len(set(ps))!=2 or any(not eligible(d,t,p) for p in ps) or not eligible(d,1-t,q):fail('Penalty shot requires two distinct eligible attackers and one eligible defender')
  if (result=='no_contact')!=(a['first_contact_ms']>5000):fail('A failed five-second contact deadline is a defended penalty shot')
  if result in ('goal','defender_foul'):d['scores'][t]+=1
  d['shot_team']=None
  if d['period']==5 and result in ('goal','defender_foul'):finish(d,t,'sudden_death_goal')
  elif d['period']!=5 and not d['remaining_ms']:d.update(phase='horn',horn_review_open=False)
  else:restart(d,'start',force_stop=True)
 elif k=='team_timeout':
  t=a['team']
  if d['period']>2 or d['timeouts'][t]:fail('One timeout per team per regulation half; none in overtime')
  d['timeouts'][t]+=1;d.update(phase='team_timeout',clock_running=False,pause_ms=60000)
 elif k=='sanction':
  t,p,c=a['team'],a['player'],a['category'];kind=a['kind']
  if d['dismissed'][t][p]:fail('A dismissed player cannot receive another match sanction')
  d['infractions'][t][p][c]+=1
  if a['team_caution'] and c not in d['team_cautions'][t]:d['team_cautions'][t].append(c)
  if kind=='caution':
   if c not in d['cautions'][t][p]:d['cautions'][t][p].append(c)
  else:
   if kind=='dismissal':d['dismissed'][t][p]=True;d['penalties'][t][p]=0;d['pending_ms'][t][p]=0;d['release_ready'][t][p]=False;d['return_blocked'][t][p]=False
   else:
    d['pending_ms'][t][p]+={'one_minute':60000,'two_minutes':120000,'five_minutes':300000}[kind]
    d['release_ready'][t][p]=False;d['return_blocked'][t][p]=False
   if p in d['active'][t]:d['active'][t].remove(p)
 elif k=='dismiss_staff':
  t,p=a['team'],a['staff']
  if d['staff_dismissed'][t][p]:fail('Team official is already dismissed')
  d['staff_dismissed'][t][p]=True
 elif k=='release_player':
  t,p=a['team'],a['player']
  if not d['release_ready'][t][p] or d['return_blocked'][t][p] or d['restricted'][t][p]:fail('Return requires expired penalty, official release and any required restart contact')
  d['release_ready'][t][p]=False;d['active'][t].append(p)
  if len(d['active'][t])>capacity(d,t):fail('Return would exceed available team places')
 elif k=='close_period':
  period=d['period'];tied=d['scores'][0]==d['scores'][1]
  if period==2 and (not d['knockout'] or not tied):finish(d,None if tied else int(d['scores'][1]>d['scores'][0]),'regulation')
  elif period==4 and not tied:finish(d,int(d['scores'][1]>d['scores'][0]),'regulation')
  else:d.update(phase='interval',pause_ms=180000 if period in (1,2) else 60000)
 elif k=='abandon':d.update(phase='abandoned',clock_running=False,shot_team=None)
 elif k=='official_result':finish(d,a['winner'],'official' if a['winner'] is not None else 'no_contest')
 return d

def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Phase, official clock, player eligibility and restart entitlement must permit the event.'],external_observations=['Official scoring, infringements, sanction severity, completed substitution or restart contact.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],period=d['period'],remaining_ms=d['remaining_ms'],clock_running=d['clock_running'],scores=d['scores'],capacity=[capacity(d,t) for t in (0,1)],penalties=d['penalties'],release_ready=d['release_ready'],restart_kind=d['restart_kind'],restart_team=d['restart_team'],timeouts=d['timeouts'],shot_team=d['shot_team']),completeness=False,reason='official_match_events_without_puck_or_movement_simulation')
