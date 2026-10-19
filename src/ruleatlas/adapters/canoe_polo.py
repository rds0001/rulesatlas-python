"""ICF 2023 canoe polo official match events, no advertising timeouts."""
from copy import deepcopy
from ..values import fields,fail
from .handball import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
T=I(0,1);P=I(0,7);NT=dict(T,nullable=True);NP=dict(P,nullable=True);B=dict(type='boolean')
KINDS=['free_throw','free_shot','sideline','goal_line','corner','centre','referee_ball']
def active(d,t):return [i for i,s in enumerate(d['status'][t]) if s=='active']
def capacity(d,t):return 5-sum(d['ejected'][t])-sum(r['team']==t for r in d['penalties'])-sum(s=='waiting' for s in d['status'][t])
def release(d,j):
 r=d['penalties'].pop(j)
 if d['status'][r['team']][r['player']]=='suspended':d['status'][r['team']][r['player']]='bench'
def tick(d,ms):
 d['clock_ms']=max(0,d['clock_ms']-ms)
 for j in range(len(d['penalties'])-1,-1,-1):
  d['penalties'][j]['remaining_ms']-=ms
  if d['penalties'][j]['remaining_ms']<=0:release(d,j)
def reduced(d):
 if any(len(active(d,t))<3 or capacity(d,t)<3 or sum(s in ('active','bench','waiting') for s in d['status'][t])<3 for t in (0,1)):
  d.update(phase='abandoned',clock_running=False,pending=None,restart=None,staff_pending=None)
def sanction(d,t,i,level,ejection):
 if d['status'][t][i]=='excluded':fail('Player is already excluded')
 if not ejection and level<=d['cards'][t][i]:fail('Sanction level must advance green, yellow, red')
 d['penalties']=[r for r in d['penalties'] if not(r['team']==t and r['player']==i)]
 d['cards'][t][i]=3 if ejection else level
 if ejection:d['ejected'][t][i]=True
 else:d['penalties'].append(dict(team=t,player=i,remaining_ms=120000))
 d['status'][t][i]='excluded' if ejection or level==3 else 'suspended'
 d['clock_running']=False
 if d['phase'] in ('live','review'):d['phase']='restart';d['restart']=dict(kind='free_shot',team=1-t)
 reduced(d)
def goal(d,t):
 d['score'][t]+=1
 rr=[j for j,r in enumerate(d['penalties']) if r['team']==1-t]
 if rr:release(d,rr[0])
 d.update(clock_running=False,phase='restart',restart=dict(kind='centre',team=1-t),pending=None)
 if d['period']>2:d.update(phase='finished',winner=t,reason='sudden_goal',restart=None)
def check_lineups(d):
 if any(not 3<=len(active(d,t))<=capacity(d,t) for t in (0,1)):fail('Restart requires three to five eligible players within reduced capacity')
 if d['staff_pending'] is not None:fail('Ejected team official must leave before restarting')
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');seen=set()
 for r in d['penalties']:
  key=(r['team'],r['player'])
  if key in seen or d['status'][r['team']][r['player']] not in ('suspended','excluded') or d['ejected'][r['team']][r['player']]:bad('Timed sanction needs one non-ejected suspended or excluded player')
  seen.add(key)
 for t in (0,1):
  for i,s in enumerate(d['status'][t]):
   if s=='suspended' and (t,i) not in seen:bad('Suspension requires its timer')
   if (d['cards'][t][i]==3)!=(s=='excluded'):bad('Red sanction level and exclusion disagree')
   if d['ejected'][t][i] and s!='excluded':bad('Ejection excludes the player permanently')
  if d['phase'] not in ('pre','abandoned','finished') and capacity(d,t)<3:bad('Fewer than three available places requires official adjudication')
 if d['period']>2 and (not d['knockout'] or d['clock_ms']>300000):bad('Overtime requires knockout mode and five-minute periods')
 if d['phase']=='interval' and d['clock_ms']:bad('Interval requires a completed period')
 if d['period']>2 and d['phase'] not in ('finished','abandoned') and d['score'][0]!=d['score'][1]:bad('Ongoing sudden-goal overtime must remain tied')
 if d['clock_running'] and (d['phase'] not in ('live','restart') or d['clock_ms']==0):bad('Running clock requires an active period')
 if d['phase']=='live' and (d['restart'] is not None or d['pending'] is not None or not d['clock_running']):bad('Live play requires running clock and no pending restart')
 if d['phase']=='live' and any(not 3<=len(active(d,t))<=capacity(d,t) for t in (0,1)):bad('Live lineup must fit reduced capacity')
 if d['phase']=='restart' and d['restart'] is None:bad('Restart phase requires its entitlement')
 if d['restart'] is not None and (d['restart']['kind']=='referee_ball')!=(d['restart']['team'] is None):bad('Only a neutral referees ball has no entitled team')
 if (d['phase']=='penalty')!=(d['pending'] is not None):bad('Penalty phase requires its pending team')
 if d['phase']=='review' and d['clock_ms']!=0:bad('Period review follows the horn')
 if (d['phase']=='interval')!=(d['break_ms']>0):bad('Interval needs its remaining break duration')
 if d['phase']=='pre' and (d['period']!=1 or d['clock_ms']!=600000 or any(d['score']) or d['penalties']):bad('Pre-match state precedes play and scoring')
 if d['phase']=='finished':
  if d['reason']=='regulation':
   w=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0])
   if d['period']!=2 or d['clock_ms'] or d['winner']!=w or w is None and d['knockout']:bad('Regulation result must match completed time, score and format')
  elif d['reason']=='sudden_goal':
   if d['period']<3 or d['winner'] is None or d['score'][d['winner']]!=d['score'][1-d['winner']]+1:bad('Sudden goal must break an overtime tie')
  elif d['reason']=='concession':
   if d['winner'] is None:bad('Concession requires a winner')
  elif d['reason'] not in ('official_result','no_contest'):bad('Finished match needs a result reason')
 elif d['winner'] is not None or d['reason'] is not None:bad('Ongoing match cannot declare a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=NT))
 if ph=='pre':s['start_match']={}
 if ph=='start':s['sprint_start']={}
 if ph in ('pre','start','live','restart','penalty','review','interval'):
  s['set_lineup']=dict(team=T,players=dict(type='array',minItems=3,maxItems=5,items=P))
 if d['clock_running']:s['elapse']=dict(milliseconds=I(1,600000))
 if ph=='live':s.update(goal=dict(team=T,player=NP),restricted_exit=dict(team=T,player=P))
 if ph in ('live','restart'):
  s['award_restart']=dict(kind=dict(type='enum',values=KINDS),team=NT,stop_clock=B)
 if ph in ('live','restart','review','penalty'):
  s.update(sanction=dict(team=T,player=P,level=I(1,3),ejection=B),staff_misconduct=dict(team=T,severe=B))
  if d['pending'] is None:s['award_penalty']=dict(team=T,offender=P,level=I(1,3),ejection=B)
 if not d['clock_running']:s['clear_exit']=dict(team=T,player=P)
 if d['staff_pending'] is not None:s['confirm_staff_departure']=dict(complied=B)
 if ph=='restart':
  if d['clock_ms']:s['take_restart']=dict(team=NT,player=NP,result=dict(type='enum',values=['play','direct_goal','direct_miss']),milliseconds=I(0,5000))
  else:s.update(close_period={},late_goal=dict(team=T,player=NP))
 if ph=='review':s.update(close_period={},late_goal=dict(team=T,player=NP))
 if ph=='penalty':s['take_penalty']=dict(shooter=P,goalkeeper=P,result=dict(type='enum',values=['goal','miss','retake','offensive_fault']),milliseconds=I(0,5000))
 if ph=='interval':s['elapse_break']=dict(milliseconds=I(1,180000))
 s.update(abandon={},concede=dict(team=T))
 return s

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];ss=schemas(d)
 if k not in ss:fail('Action is not permitted in this phase')
 fields(p,ss[k],'/params');t=p.get('team')
 if k=='start_match':
  if any(len(active(d,j))!=5 for j in (0,1)):fail('Five active players per team are required at match start')
  d['phase']='start'
 elif k=='sprint_start':check_lineups(d);d.update(phase='live',clock_running=True,late_used=False,restart=None)
 elif k=='set_lineup':
  ids=p['players']
  if len(ids)!=len(set(ids)) or len(ids)>capacity(d,t) or any(d['status'][t][i] not in ('active','bench') for i in ids):fail('Lineup requires distinct eligible players within capacity')
  for i in active(d,t):d['status'][t][i]='bench'
  for i in ids:d['status'][t][i]='active'
 elif k=='elapse':
  if p['milliseconds']>d['clock_ms']:fail('Clock cannot pass the period boundary')
  tick(d,p['milliseconds'])
  if not d['clock_ms']:d.update(phase='review',clock_running=False,restart=None)
 elif k in ('goal','late_goal'):
  if p['player'] is not None and p['player'] not in active(d,t):fail('Recorded scorer must be an eligible active player')
  if k=='late_goal':
   if d['late_used']:fail('Period-ending goal already recorded')
   d['late_used']=True
  goal(d,t)
 elif k=='restricted_exit':
  if p['player'] not in active(d,t):fail('Only an active player can leave under a restricted-entry ruling')
  d['status'][t][p['player']]='waiting';reduced(d)
 elif k=='clear_exit':
  if d['status'][t][p['player']]!='waiting':fail('Player has no pending restricted exit')
  d['status'][t][p['player']]='bench'
 elif k=='award_restart':
  if (p['kind']=='referee_ball')!=(t is None):fail('Only a referees ball has neutral entitlement')
  d.update(phase='restart',restart=dict(kind=p['kind'],team=t))
  if p['stop_clock']:d['clock_running']=False
 elif k=='take_restart':
  check_lineups(d);r=d['restart']
  if t!=r['team'] or t is None and p['player'] is not None or t is not None and p['player'] not in active(d,t):fail('Restart requires the entitled active thrower or a neutral referees ball')
  if p['result']!='play' and r['kind']!='free_shot':fail('Only a free shot permits a direct attempt at goal')
  if p['milliseconds']>d['clock_ms']:fail('An ordinary restart must be taken before the period ends')
  tick(d,p['milliseconds']);d.update(phase='live' if d['clock_ms'] else 'review',clock_running=d['clock_ms']>0,restart=None)
  if p['result']=='direct_goal':goal(d,t)
 elif k=='sanction':sanction(d,t,p['player'],p['level'],p['ejection'])
 elif k=='award_penalty':
  sanction(d,1-t,p['offender'],p['level'],p['ejection'])
  if d['phase']!='abandoned':d.update(phase='penalty',pending=t,restart=None,clock_running=False)
 elif k=='take_penalty':
  check_lineups(d);t=d['pending']
  if p['shooter'] not in active(d,t) or p['goalkeeper'] not in active(d,1-t):fail('Penalty shot requires an active shooter and defending goalkeeper')
  tick(d,p['milliseconds'])
  if p['result']=='retake':pass
  elif p['result']=='goal':goal(d,t)
  elif p['result']=='offensive_fault':d.update(phase='restart',pending=None,restart=dict(kind='free_throw',team=1-t),clock_running=False)
  else:d.update(phase='live' if d['clock_ms'] else 'review',pending=None,clock_running=d['clock_ms']>0)
 elif k=='staff_misconduct':
  if not p['severe'] and not d['staff_warning'][t]:d['staff_warning'][t]=True
  else:
   if d['staff_pending'] is not None:fail('Resolve the previous staff departure first')
   d['staff_warning'][t]=True;d['staff_pending']=t;d['clock_running']=False
   if d['phase']=='live':d.update(phase='restart',restart=dict(kind='free_throw',team=1-t))
 elif k=='confirm_staff_departure':
  d['staff_pending']=None
  if not p['complied']:d.update(phase='abandoned',pending=None,restart=None,clock_running=False)
 elif k=='close_period':
  if d['staff_pending'] is not None:fail('Resolve the official staff departure decision')
  if d['period']==2 and (d['score'][0]!=d['score'][1] or not d['knockout']):d.update(phase='finished',winner=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0]),reason='regulation',restart=None)
  else:d.update(phase='interval',break_ms=180000 if d['period']<=2 else 60000,restart=None)
 elif k=='elapse_break':
  if p['milliseconds']>d['break_ms']:fail('Elapsed time exceeds the interval')
  d['break_ms']-=p['milliseconds']
  if not d['break_ms']:d.update(period=d['period']+1,phase='start',clock_ms=600000 if d['period']==1 else 300000,late_used=False)
 elif k=='abandon':d.update(phase='abandoned',clock_running=False,break_ms=0,pending=None,restart=None,staff_pending=None)
 elif k=='concede':d.update(phase='finished',winner=1-t,reason='concession',clock_running=False,break_ms=0,pending=None,restart=None,staff_pending=None)
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_contest' if p['winner'] is None else 'official_result')
 return d

def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Restart entitlement, eligible lineup, sanction level and current clock phase must permit the event.'],external_observations=['Official goals, fouls, penalty-shot outcomes, restart decisions and elapsed playing time.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],period=d['period'],clock_ms=d['clock_ms'],clock_running=d['clock_running'],score=d['score'],capacity=[capacity(d,t) for t in (0,1)],penalties=d['penalties'],restart=d['restart'],pending=d['pending'],cards=d['cards']),completeness=False,reason='official_2023_canoe_polo_events')
