"""FINA 2019-2021 regulation league water polo: clocks and official events."""
from copy import deepcopy
from ..values import fields,fail
from .handball import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
E=lambda *x:dict(type='enum',values=list(x))
T=I(0,1);P=I(0,12);NT=dict(T,nullable=True);NP=dict(P,nullable=True)
B=dict(type='boolean')
def reduction(d,t,p):return next((r for r in d['exclusions'] if r['team']==t and r['player']==p),None)
def capacity(d,t):return 7-sum(r['team']==t for r in d['exclusions'])
def eligible(d,t,p):return d['status'][t][p]=='eligible'
def mark_release(d,team=None,goal=False,changed=False):
 for r in d['exclusions']:
  if r['kind']=='ordinary' and (goal or r['team']==team or(changed and r['paired'])):r['ready']=True

def entitlement(d,t,reset=True):
 changed=d['attack'] is not None and d['attack']!=t
 d['attack']=t
 if reset:d['shot_ms']=30000
 mark_release(d,t,changed=changed)
def restart(d,kind,t,direct=False):d.update(phase='restart',restart=kind,attack=t,direct_allowed=direct,second_touch=False)
def scored(d,t):
 d['score'][t]+=1;mark_release(d,goal=True);d['shot_ms']=30000;restart(d,'centre',1-t)
def add_exclusion(d,t,p,kind='ordinary',dismiss=False,paired=False):
 if d['status'][t][p]=='dismissed':fail('Player is already permanently excluded')
 d['fouls'][t][p]+=1
 d['status'][t][p]='dismissed' if dismiss or d['fouls'][t][p]>=3 else 'excluded'
 d['exclusions']=[r for r in d['exclusions'] if (r['team'],r['player'])!=(t,p)]
 d['exclusions'].append(dict(team=t,player=p,kind=kind,ms=240000 if kind=='brutality' else 20000,ready=False,cleared=False,paired=paired))
 if p in d['active'][t]:d['active'][t].remove(p)
 if d['keeper'][t]==p:d['keeper'][t]=None

def keeper_ok(d,t):
 ps=d['active'][t];k=d['keeper'][t]
 if k is not None and k not in ps:return False
 if len(ps)==7 and k is None:return False
 if k is not None and k not in (0,12) and any(eligible(d,t,p) for p in (0,12)):return False
 if any(p in ps and p!=k for p in (0,12)) and any(eligible(d,t,p) and p not in ps for p in range(1,12)):return False
 return True

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');seen=set()
 for r in d['exclusions']:
  key=(r['team'],r['player'])
  if key in seen or d['status'][r['team']][r['player']] not in ('excluded','dismissed'):bad('Each reduction requires one excluded player')
  seen.add(key)
  if r['kind']=='brutality' and d['status'][r['team']][r['player']]!='dismissed':bad('Brutality excludes the player permanently')
  if r['ms']==0 and not r['ready']:bad('Expired exclusions must be eligible for official release')
  if r['kind']=='brutality' and r['ms']>0 and r['ready']:bad('Brutality cannot be released before four playing minutes')
 for t in (0,1):
  if len(set(d['active'][t]))!=len(d['active'][t]) or any(not eligible(d,t,p) for p in d['active'][t]):bad('Active players must be distinct and eligible')
  if d['phase']=='live' and len(d['active'][t])>capacity(d,t):bad('Lineup exceeds available playing places')
  if not keeper_ok(d,t):bad('Goalkeeper designation and available field-player substitutes must be respected')
  for p,s in enumerate(d['status'][t]):
   if s=='excluded' and (t,p) not in seen:bad('Temporary exclusion requires its reduction')
   if d['fouls'][t][p]>=3 and s!='dismissed':bad('Three personal fouls exclude a player for the match')
 if d['phase']=='live' and (d['attack'] is None or not d['period_ms'] or not d['shot_ms']):bad('Live play requires an attack entitlement and both clocks')
 if d['phase']=='siren_review' and d['period_ms'] and d['shot_ms']:bad('Siren review requires an expired clock')
 if d['phase']=='period_review' and d['period_ms']:bad('Period review follows an expired period')
 if (d['phase']=='penalty')!=bool(d['penalty_queue']):bad('Penalty phase requires at least one awarded throw')
 if d['phase'] in ('interval','timeout') and not d['pause_ms']:bad('Break phase requires remaining time')
 if d['phase']=='finished' and d['reason']=='regulation':
  w=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0])
  if d['period']!=4 or d['period_ms'] or d['winner']!=w:bad('Regulation result must match four completed periods')
 elif d['phase']!='finished' and d['winner'] is not None:bad('Only a finished game has a winner')

def tick(d,ms):
 if d['phase'] in ('interval','timeout'):
  if ms>d['pause_ms']:fail('Advance only to the end of this break')
  d['pause_ms']-=ms
  if not d['pause_ms']:
   if d['phase']=='interval':d['period']+=1;d.update(phase='start',period_ms=480000,attack=None,shot_ms=30000,restart='sprint',second_touch=False,direct_allowed=False)
   else:restart(d,'corner' if d['timeout_corner'] else 'timeout',d['attack'],d['timeout_corner'])
  return
 if ms>min(d['period_ms'],d['shot_ms']):fail('Advance only to the next game or attack-clock signal')
 d['period_ms']-=ms;d['shot_ms']-=ms
 for r in d['exclusions']:
  r['ms']=max(0,r['ms']-ms)
  if not r['ms']:r['ready']=True
 if not d['period_ms'] or not d['shot_ms']:d['phase']='siren_review'

def schemas(d):
 ph=d['phase'];out={}
 if ph=='finished':return out
 if ph=='abandoned':return dict(official_result=dict(winner=NT))
 out['abandon']={}
 out['reentry_restriction']=dict(team=T,player=P,restricted=B)
 if ph not in ('penalty',):out['lineup']=dict(team=T,players=dict(type='array',minItems=0,maxItems=7,items=P),keeper=NP)
 if ph=='pre':out['start_match']={}
 if ph=='start':out['sprint_winner']=dict(team=T)
 if ph in ('live','timeout','interval'):out['advance']=dict(ms=I(1,480000))
 if ph=='live':out.update(turnover={},second_touch={},goal=dict(team=T,own_goal=B),shot_result=dict(result=E('goal','attack_rebound','defence_rebound','corner','goal_throw')),ordinary_foul=dict(team=T,outside_six=B),official_restart=dict(team=NT,kind=E('neutral','goal_throw','corner','sideline','delay'),outside_six=B))
 if ph=='restart':out['take_restart']=dict(team=T)
 if ph in ('live','restart'):out['timeout_request']=dict(team=T)
 if ph in ('live','restart','interval','timeout','period_review','penalty'):
  out.update(personal_foul=dict(team=T,player=P,kind=E('exclusion','penalty','misconduct','brutality','immediate_dismissal','penalty_dismissal','illegal_entry','excluded_interference','penalty_interference')),staff_card=dict(team=T,staff=I(0,2),card=E('yellow','red')),team_caution=dict(team=T))
 if ph in ('live','restart'):
  out['simultaneous_exclusions']=dict(players=dict(type='array',minItems=2,maxItems=2,items=P),brutality=B)
 if ph not in ('pre','finished','abandoned'):
  out.update(clear_reentry=dict(team=T,player=P),release_exclusion=dict(team=T,player=P))
 if ph=='penalty':out['bench_for_reduction']=dict(team=T,player=P)
 if ph=='penalty':out.update(take_penalty=dict(player=P,elapsed_ms=I(0,480000),result=E('goal','attack_rebound','defence_rebound','goal_throw','attacker_violation','retake')),replace_for_penalty=dict(team=T,outgoing=NP,incoming=P,keeper=NP),decline_penalty={})
 if ph=='siren_review':out['penalty_at_signal']=dict(team=T,player=P)
 if ph=='siren_review':out['resolve_siren']=dict(result=E('no_goal','goal','penalty'),released_before_signal=B,attacker_touch_after_signal=B,offender=NP)
 if ph=='period_review':out['end_period']={}
 return out

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];a=action['params'];ph=d['phase'];ss=schemas(d)
 if k not in ss:fail('Action is not permitted in this phase')
 fields(a,ss[k],'/params')
 if k=='penalty_at_signal':k='personal_foul';a=dict(a,kind='penalty')
 if k=='advance':tick(d,a['ms'])
 elif k=='lineup':
  t=a['team'];ps=a['players']
  if len(set(ps))!=len(ps) or len(ps)>capacity(d,t) or any(not eligible(d,t,p) for p in ps):fail('Lineup needs distinct eligible players within available places')
  d['active'][t]=ps;d['keeper'][t]=a['keeper']
  if not keeper_ok(d,t):fail('Goalkeeper and substitute roles are not satisfied')
 elif k=='reentry_restriction':
  t,p=a['team'],a['player']
  if d['status'][t][p] not in ('eligible','restricted') or (not a['restricted'] and ph=='live'):fail('Official reentry clearance requires a stoppage and no disciplinary exclusion')
  d['status'][t][p]='restricted' if a['restricted'] else 'eligible'
  if a['restricted']:
   if p in d['active'][t]:d['active'][t].remove(p)
   if d['keeper'][t]==p:d['keeper'][t]=None
 elif k=='start_match':d['phase']='start'
 elif k=='sprint_winner':d.update(phase='live',attack=a['team'],shot_ms=30000,second_touch=False,direct_allowed=False)
 elif k=='take_restart':
  if d['attack'] is not None and a['team']!=d['attack']:fail('Restart belongs to the entitled team')
  d.update(attack=a['team'],phase='live',second_touch=False)
 elif k=='second_touch':d['second_touch']=True
 elif k=='turnover':entitlement(d,1-d['attack']);d.update(direct_allowed=True,second_touch=True)
 elif k=='goal':
  if not a['own_goal'] and not(d['direct_allowed'] or d['second_touch']):fail('This restart needs another eligible player touch before scoring')
  if a['team']!=d['attack'] and not a['own_goal']:fail('The goal must be credited to the attack team unless an own goal is recorded')
  scored(d,a['team'])
 elif k=='shot_result':
  t=d['attack'];result=a['result']
  if result=='goal':
   if not(d['direct_allowed'] or d['second_touch']):fail('Direct scoring is not permitted from this restart')
   scored(d,t)
  elif result=='attack_rebound':d['shot_ms']=20000
  elif result=='defence_rebound':entitlement(d,1-t);d.update(direct_allowed=True,second_touch=True)
  elif result=='corner':d['shot_ms']=20000;restart(d,'corner',t,True)
  else:entitlement(d,1-t);restart(d,'goal_throw',1-t,True)
 elif k=='ordinary_foul':
  t=1-a['team'];same=d['attack']==t;entitlement(d,t,not same);restart(d,'free',t,a['outside_six'])
 elif k=='official_restart':
  t=a['team'];kind=a['kind']
  if (kind=='neutral')!=(t is None):fail('Only neutral throws have no entitled team')
  if t is not None:
   same=d['attack']==t;entitlement(d,t,not same or kind=='goal_throw')
  if kind=='corner':d['shot_ms']=20000
  elif kind=='neutral':d['shot_ms']=30000
  restart(d,kind,t,kind in ('corner','goal_throw'))
 elif k=='timeout_request':
  t=a['team']
  if t!=d['attack']:d.update(phase='penalty',penalty_queue=[1-t],penalty_resume=None)
  elif d['timeouts'][t]>=2:entitlement(d,1-t);restart(d,'timeout',1-t)
  else:d['timeouts'][t]+=1;d.update(phase='timeout',pause_ms=60000,timeout_corner=d['restart']=='corner' and ph=='restart')
 elif k=='personal_foul':
  t,p=a['team'],a['player'];kind=a['kind'];other=1-t;interval=ph in ('interval','timeout','period_review') or(ph=='restart' and d['restart']=='centre')
  if d['status'][t][p]=='dismissed':fail('Player is already permanently excluded')
  if kind=='immediate_dismissal':
   d['fouls'][t][p]+=1
   d['status'][t][p]='dismissed';d['exclusions']=[r for r in d['exclusions'] if (r['team'],r['player'])!=(t,p)]
   if p in d['active'][t]:d['active'][t].remove(p)
   if d['keeper'][t]==p:d['keeper'][t]=None
  elif kind=='misconduct' and interval:
   d['fouls'][t][p]+=1;d['status'][t][p]='dismissed';d['exclusions']=[r for r in d['exclusions'] if (r['team'],r['player'])!=(t,p)]
   if p in d['active'][t]:d['active'][t].remove(p)
   if d['keeper'][t]==p:d['keeper'][t]=None
  elif kind=='penalty':
   d['fouls'][t][p]+=1
   if d['fouls'][t][p]>=3:
    d['status'][t][p]='dismissed';d['exclusions']=[r for r in d['exclusions'] if (r['team'],r['player'])!=(t,p)];d['forced_replacements'][t]+=1
    if p in d['active'][t]:d['active'][t].remove(p)
    if d['keeper'][t]==p:d['keeper'][t]=None
   d.update(phase='penalty',penalty_queue=[other],penalty_resume=None)
  elif kind=='excluded_interference':
   if reduction(d,t,p) is None:fail('Excluded-player interference requires an existing exclusion')
   d['fouls'][t][p]+=1
   if d['fouls'][t][p]>=3:d['status'][t][p]='dismissed'
   d.update(phase='penalty',penalty_queue=[other],penalty_resume=None)
  else:
   brut=kind=='brutality';add_exclusion(d,t,p,'brutality' if brut else 'ordinary',kind in ('misconduct','brutality','penalty_dismissal','penalty_interference'))
   penalty=kind in ('penalty_dismissal','penalty_interference') or(kind=='illegal_entry' and t!=d['attack']) or(brut and ph=='live')
   if penalty:d.update(phase='penalty',penalty_queue=[other],penalty_resume=None)
   elif not interval and ph!='penalty' and not(brut and ph!='live'):
    same=d['attack']==other;entitlement(d,other,not same)
    if same:d['shot_ms']=max(20000,d['shot_ms'])
    restart(d,'free',other)
 elif k=='simultaneous_exclusions':
  old=d['attack'];brut=a['brutality']
  for t,p in enumerate(a['players']):add_exclusion(d,t,p,'brutality' if brut else 'ordinary',brut,not brut)
  if brut and ph=='live':
   if old is None:fail('Simultaneous live brutalities require the existing attack entitlement')
   d.update(phase='penalty',penalty_queue=[old,1-old],penalty_resume=old)
  elif old is None:d['shot_ms']=30000;restart(d,'neutral',None)
  else:restart(d,'free',old)
 elif k=='clear_reentry':
  r=reduction(d,a['team'],a['player'])
  if r is None:fail('Player has no exclusion to clear')
  r['cleared']=True
 elif k=='release_exclusion':
  t,p=a['team'],a['player'];r=reduction(d,t,p);interval=ph in ('interval','timeout','period_review') or(ph=='restart' and d['restart']=='centre')
  if r is None or not r['ready'] or not(r['cleared'] or interval):fail('Exclusion release requires its rule trigger and reentry clearance')
  d['exclusions'].remove(r)
  if d['status'][t][p]=='excluded':d['status'][t][p]='eligible'
 elif k=='bench_for_reduction':
  t,p=a['team'],a['player']
  if len(d['active'][t])<=capacity(d,t) or p not in d['active'][t]:fail('Only an excess active player can be removed for this reduction')
  d['active'][t].remove(p)
  if d['keeper'][t]==p:d['keeper'][t]=None
 elif k=='replace_for_penalty':
  t=a['team'];out=a['outgoing'];inc=a['incoming']
  if inc in d['active'][t] or not eligible(d,t,inc):fail('Replacement must be an eligible bench player')
  if out is None:
   if not d['forced_replacements'][t]:fail('No immediate third-foul replacement is pending')
   d['forced_replacements'][t]-=1
  else:
   if d['keeper'][t] is not None or inc not in (0,12) or out not in d['active'][t]:fail('Only the required replacement goalkeeper may be brought in during a pending penalty')
   d['active'][t].remove(out)
  d['active'][t].append(inc);d['keeper'][t]=a['keeper']
  if len(d['active'][t])>capacity(d,t) or not keeper_ok(d,t):fail('Penalty replacement violates capacity or goalkeeper roles')
 elif k=='decline_penalty':
  if d['period']!=4 or not 0<d['period_ms']<=60000 or len(d['penalty_queue'])!=1 or d['penalty_resume'] is not None:fail('A single penalty can be exchanged for a free throw only in the final minute')
  t=d['penalty_queue'][0];d['penalty_queue']=[];d['forced_replacements']=[0,0];entitlement(d,t);restart(d,'timeout',t)
 elif k=='take_penalty':
  t=d['penalty_queue'][0];p=a['player'];result=a['result']
  if any(len(d['active'][q])>capacity(d,q) for q in (0,1)):fail('Correct the reduced lineups before the penalty throw')
  if p not in d['active'][t]:fail('Penalty taker must be an eligible active player')
  ms=a['elapsed_ms']
  if ms>d['period_ms']:fail('Penalty elapsed time cannot exceed the remaining period')
  d['period_ms']-=ms
  for r in d['exclusions']:
   r['ms']=max(0,r['ms']-ms)
   if not r['ms']:r['ready']=True
  if result=='retake':return d
  if result=='goal':d['score'][t]+=1;mark_release(d,goal=True)
  d['penalty_queue'].pop(0);d['forced_replacements']=[0,0]
  if not d['penalty_queue']:
   if not d['period_ms']:d['phase']='period_review'
   elif d['penalty_resume'] is not None:
    t=d['penalty_resume'];d['penalty_resume']=None;entitlement(d,t);restart(d,'timeout',t)
   elif result=='goal':entitlement(d,1-t);restart(d,'centre',1-t)
   elif result=='attack_rebound':entitlement(d,t,False);d.update(phase='live',shot_ms=20000,direct_allowed=True,second_touch=True)
   elif result=='defence_rebound':entitlement(d,1-t);d.update(phase='live',direct_allowed=True,second_touch=True)
   else:entitlement(d,1-t);restart(d,'free' if result=='attacker_violation' else 'goal_throw',1-t,result!='attacker_violation')
 elif k=='resolve_siren':
  result=a['result'];t=d['attack'];ended=d['period_ms']==0
  if result!='no_goal' and (not a['released_before_signal'] or a['attacker_touch_after_signal'] or not(d['direct_allowed'] or d['second_touch'])):fail('Late scoring decision requires a legally released shot before the signal without subsequent attacking contact')
  if result=='goal':scored(d,t)
  elif result=='penalty':
   p=a['offender']
   if p is None or not eligible(d,1-t,p):fail('Late penalty requires an eligible defending offender')
   d['fouls'][1-t][p]+=1
   if d['fouls'][1-t][p]>=3:
    d['status'][1-t][p]='dismissed';d['forced_replacements'][1-t]+=1
    if p in d['active'][1-t]:d['active'][1-t].remove(p)
    if d['keeper'][1-t]==p:d['keeper'][1-t]=None
   d.update(phase='penalty',penalty_queue=[t],penalty_resume=None)
  elif not ended:entitlement(d,1-t);restart(d,'free',1-t)
  if ended and result!='penalty':d['phase']='period_review'
 elif k=='end_period':
  if d['period']==4:d.update(phase='finished',winner=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0]),reason='regulation')
  else:d.update(phase='interval',pause_ms=180000 if d['period']==2 else 120000)
 elif k=='staff_card':
  t,p=a['team'],a['staff']
  if d['staff_red'][t][p]:fail('Staff member is already dismissed')
  if a['card']=='yellow':
   if p!=0:fail('The head coach receives the preliminary staff caution')
   if d['staff_yellow'][t][p]:fail('A cautioned staff member requires a red card for further misconduct')
   d['staff_yellow'][t][p]=True
  else:d['staff_red'][t][p]=True
 elif k=='team_caution':d['team_warned'][a['team']]=True
 elif k=='abandon':d.update(phase='abandoned',penalty_queue=[])
 elif k=='official_result':d.update(phase='finished',winner=a['winner'],reason='no_contest' if a['winner'] is None else 'official')
 return d

def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Clock, restart, personal fouls, exclusion release and player roles must permit this official event.'],external_observations=['Official restart, shot result, sanction classification and reentry clearance.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],restart=d['restart'],period=d['period'],period_ms=d['period_ms'],shot_ms=d['shot_ms'],attack=d['attack'],score=d['score'],capacity=[capacity(d,t) for t in (0,1)],fouls=d['fouls'],exclusions=d['exclusions'],timeouts=d['timeouts'],direct_allowed=d['direct_allowed'],second_touch=d['second_touch'],penalty_queue=d['penalty_queue']),completeness=False,reason='official_regulation_league_events_without_ball_motion')
