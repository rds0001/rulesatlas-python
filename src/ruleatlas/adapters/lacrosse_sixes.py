"""Sixes 2021 official match events and non-releasable penalty clocks."""
from copy import deepcopy
from ..values import fields,fail
from .pelota import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
E=lambda *x:dict(type='enum',values=list(x))
T=I(0,1);P=I(0,11);B=dict(type='boolean');NT=dict(T,nullable=True)
FOUL=dict(team=T,player=dict(P,nullable=True),server=P,kind=E('minor','major','expulsion'),timed=B)
FOUL_SPEC=dict(type='object',properties=FOUL,required=list(FOUL))
def active(d,t):return [i for i,x in enumerate(d['status'][t]) if x=='active']
def capacity(d,t):return 6-sum(x>0 for x in d['penalty_ms'][t])
def finish(d,w,r):d.update(phase='finished',winner=w,reason=r,clock_running=False,break_ms=0)
def assign_restart(d,t):
 d['restart_team']=t
 if d['period']>=5 or d['period']==4 and d['clock_ms']<=120000:d['clock_running']=False
 if d['phase'] not in ('period_review','abandoned'):d['phase']='restart'
def alternating(d):
 t=d['alternate'];d['alternate']=1-t;return t
def penalty(d,p):
 t=p['team'];i=p['player'];server=p['server'];kind=p['kind'];n=30000 if kind=='minor' and p['timed'] else 0 if kind=='minor' else 60000 if kind=='major' else 120000
 if i is not None and d['status'][t][i]=='excluded':fail('Excluded player cannot receive another participation penalty')
 if kind=='minor' and not n:return
 delegated=i is None or i==d['goalkeeper'][t] or kind=='expulsion'
 if delegated:
  home=d['in_home'][t]
  available=home is not None and d['status'][t][home] in ('active','bench') and (kind!='expulsion' or home!=i)
  if available and server!=home:fail('The designated in-home must serve the delegated penalty when available')
  if server==d['goalkeeper'][t] or d['status'][t][server] not in ('active','bench') or kind=='expulsion' and server==i:fail('Delegated penalty needs an eligible non-goalkeeper server')
 elif server!=i:fail('A field player serves their own minor or major penalty')
 if kind=='major' and i is not None:
  d['major_fouls'][t][i]+=1
  if d['major_fouls'][t][i]==3:d['status'][t][i]='excluded'
 if kind=='expulsion' and i is not None:
  n+=d['penalty_ms'][t][i];d['penalty_ms'][t][i]=0;d['penalty_started'][t][i]=False;d['status'][t][i]='excluded'
 if d['status'][t][server]!='excluded':d['status'][t][server]='penalty'
 d['penalty_ms'][t][server]+=n
 if i is not None and d['status'][t][i]=='excluded':
  if d['captain'][t]==i:d['captain'][t]=None
  if d['goalkeeper'][t]==i:d['goalkeeper'][t]=None
  if d['in_home'][t]==i:d['in_home'][t]=None
 if capacity(d,t)<1:d.update(phase='abandoned',clock_running=False)
def flush(d,goal_team=None):
 pending=d['delayed'];d['delayed']=[];retained=False
 for p in pending:
  if goal_team is not None and p['team']!=goal_team and p['kind']=='minor':continue
  penalty(d,p)
  if goal_team is not None and p['team']!=goal_team:retained=True
 return retained
def goal(d,t):
 d['score'][t]+=1;retained=flush(d,t);d['clock_running']=False
 if d['period']>=5:finish(d,t,'sudden_victory')
 elif d['phase']!='abandoned':assign_restart(d,t if retained else 1-t)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if len(active(d,t))>6 or d['phase']=='play' and len(active(d,t))>max(0,capacity(d,t)):bad('Lineup exceeds capacity after time-serving penalties')
  for i in range(12):
   st=d['status'][t][i];n=d['penalty_ms'][t][i]
   if n>0 and st not in ('penalty','excluded') or st=='penalty' and n==0:bad('Penalty clocks and player status must agree')
   if not n and d['penalty_started'][t][i]:bad('An inactive penalty clock cannot be marked started')
   if d['major_fouls'][t][i]==3 and st!='excluded':bad('Three major fouls remove the player for the game')
  g=d['goalkeeper'][t];h=d['in_home'][t];c=d['captain'][t]
  if g is not None and d['status'][t][g]!='active':bad('Designated goalkeeper must be active')
  for role in (h,c):
   if role is not None and (role==g or d['status'][t][role]=='excluded'):bad('In-home and captain must be eligible non-goalkeepers')
  if d['phase']=='play' and (g is None or c is None or h is None):bad('Live play requires goalkeeper, captain and in-home')
 if d['clock_ms']>(480000 if d['period']<=4 else 240000):bad('Clock exceeds the current period')
 if d['phase']=='period_review' and d['clock_ms']!=0:bad('Period review requires an expired clock')
 if d['phase']=='play' and d['clock_ms']==0:bad('Play cannot continue after period expiry')
 if (d['phase'] in ('interval','timeout'))!=(d['break_ms']>0):bad('Break clock must agree with phase')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason']=='no_contest')!=(d['winner'] is None):bad('Result needs a winner or no contest')
  if d['reason'] in ('regulation','sudden_victory','forfeit') and d['score'][d['winner']]<=d['score'][1-d['winner']]:bad('Winner must lead the score')
 elif d['winner'] is not None or d['reason'] is not None:bad('Unfinished game cannot have a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=NT))
 if ph in ('pre_game','ot_toss'):s['choose_alternate']=dict(team=T)
 if ph=='draw':s.update(draw=dict(winner=T),redraw={})
 if ph in ('restart','stopped'):s['restart']=dict(team=T)
 if ph=='play':s.update(goal=dict(team=T,player=P),stop=dict(team=NT,official_timeout=B),signal_foul=FOUL,minor_turnover=dict(team=T),shot_clock_violation=dict(team=T))
 if ph=='period_review':s.update(late_goal=dict(team=T,player=P),close_period=dict(retain_team=NT))
 if ph not in ('pre_game','ot_toss','interval','timeout','period_review'):s['elapse']=dict(milliseconds=I(1,480000))
 if ph in ('play','restart','stopped','draw','pre_game','interval'):s['timeout']=dict(team=T,authorized=B)
 if ph in ('interval','timeout'):s['elapse_break']=dict(milliseconds=I(1,300000))
 if d['delayed']:s['resolve_delayed']=dict(team=NT)
 if ph not in ('timeout','interval'):
  s['assess_fouls']=dict(fouls=dict(type='array',minItems=1,maxItems=12,items=FOUL_SPEC),prior_team=NT,coincidental=B)
 s.update(set_lineup=dict(team=T,players=dict(type='array',minItems=1,maxItems=6,items=P)),appoint=dict(team=T,role=E('goalkeeper','captain','in_home'),player=P),withdraw=dict(team=T,player=P),concede=dict(team=T),abandon={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='choose_alternate':
  if d['period']==1 and any(len(active(d,t))!=6 for t in (0,1)):fail('Six active players per team are required to start')
  d['alternate']=p['team'];d['phase']='draw' if d['restart_team'] is None else 'restart'
 elif k in ('draw','restart'):
  if any(len(active(d,t))>capacity(d,t) for t in (0,1)):fail('Reduce the lineup to its available penalty capacity before restarting')
  if any(d[role][t] is None for role in ('goalkeeper','captain','in_home') for t in (0,1)):fail('Required team roles must be appointed')
  if k=='restart' and d['restart_team'] is not None and p['team']!=d['restart_team']:fail('Only the entitled team can restart')
  d['penalty_started']=[[x>0 for x in row] for row in d['penalty_ms']]
  d.update(phase='play',clock_running=True,restart_team=None,timeout_since_restart=False,redraws=0)
 elif k=='redraw':
  d['redraws']+=1
  if d['redraws']==2:assign_restart(d,alternating(d));d['redraws']=0
 elif k=='elapse':
  n=p['milliseconds']
  if not d['clock_running'] or n>d['clock_ms']:fail('Elapsed time requires a running clock and cannot exceed the period')
  d['clock_ms']-=n
  for t in (0,1):
   for i in range(12):
    if d['penalty_started'][t][i]:d['penalty_ms'][t][i]=max(0,d['penalty_ms'][t][i]-n)
    if not d['penalty_ms'][t][i]:d['penalty_started'][t][i]=False
    if not d['penalty_ms'][t][i] and d['status'][t][i]=='penalty':d['status'][t][i]='bench'
  if not d['clock_ms']:d.update(phase='period_review',clock_running=False,late_used=False)
 elif k in ('goal','late_goal'):
  if p['player'] not in active(d,p['team']) or k=='late_goal' and d['late_used']:fail('Goal needs an active player and an unresolved pre-buzzer shot')
  if k=='late_goal':d['late_used']=True
  goal(d,p['team'])
 elif k=='stop':
  flush(d);assign_restart(d,p['team'])
  if p['official_timeout'] or d['period']>=5 or d['period']==4 and d['clock_ms']<=120000:d['clock_running']=False
 elif k in ('minor_turnover','shot_clock_violation'):
  flush(d);assign_restart(d,1-p['team'])
  if d['period']>=5 or d['period']==4 and d['clock_ms']<=120000:d['clock_running']=False
 elif k=='signal_foul':
  if p['kind']=='minor' and not p['timed']:fail('A delayed defensive minor must be a time-serving foul')
  if any(x['team']!=p['team'] for x in d['delayed']):fail('An opposing foul ends the delayed situation; resolve the batch officially')
  d['delayed'].append(p)
 elif k=='resolve_delayed':flush(d);assign_restart(d,p['team'])
 elif k=='assess_fouls':
  fs=p['fouls'];totals=[0,0]
  cancelled=p['coincidental'] and not d['delayed'] and all(x['kind']=='minor' for x in fs) and len({x['team'] for x in fs})==2
  if d['delayed']:fail('Resolve the delayed penalty batch before another assessment')
  if not cancelled:
   for x in fs:
    penalty(d,x);totals[x['team']]+=30000 if x['kind']=='minor' and x['timed'] else 0 if x['kind']=='minor' else 60000 if x['kind']=='major' else 120000
  if d['phase']!='abandoned':
   if totals[0]!=totals[1]:team=int(totals[0]>totals[1])
   elif len({x['team'] for x in fs})==1:team=1-fs[0]['team']
   else:team=p['prior_team'] if p['prior_team'] is not None else alternating(d)
   assign_restart(d,team)
  if d['period']>=5 or d['period']==4 and d['clock_ms']<=120000:d['clock_running']=False
 elif k=='close_period':
  if d['delayed']:fail('Resolve delayed fouls before closing the period')
  if d['period']==4 and d['score'][0]!=d['score'][1]:finish(d,int(d['score'][1]>d['score'][0]),'regulation')
  else:
   retained=p['retain_team'] if capacity(d,0)!=capacity(d,1) else None
   d.update(phase='interval',break_ms=300000 if d['period']==2 else 120000,restart_team=retained,clock_running=False)
 elif k=='timeout':
  t=p['team'];limit=1 if d['period']>=5 else 2
  if not p['authorized'] or d['timeout_since_restart'] or d['timeouts'][t]>=limit:fail('Timeout needs official entitlement, remaining allowance and resumed play')
  d['timeouts'][t]+=1;d.update(resume_phase=d['phase'],resume_clock=d['clock_running'],resume_break_ms=d['break_ms'],phase='timeout',break_ms=30000,clock_running=False,timeout_since_restart=True)
 elif k=='elapse_break':
  if p['milliseconds']>d['break_ms']:fail('Elapsed time exceeds the break')
  d['break_ms']-=p['milliseconds']
  if not d['break_ms']:
   if d['phase']=='timeout':d['phase']=d['resume_phase'];d['clock_running']=d['resume_clock'];d['break_ms']=d['resume_break_ms']
   else:
    d['period']+=1;d['clock_ms']=480000 if d['period']<=4 else 240000
    if d['period']==3 or d['period']>=5:d['timeouts']=[0,0]
    d['timeout_since_restart']=False;d['late_used']=False;d['redraws']=0
    d['phase']='ot_toss' if d['period']==5 else 'restart' if d['restart_team'] is not None else 'draw'
 elif k=='set_lineup':
  t=p['team'];line=p['players']
  if len(line)!=len(set(line)) or len(line)>capacity(d,t) or any(d['status'][t][i] not in ('active','bench') for i in line):fail('Lineup must respect eligibility and unexpired penalty places')
  g=d['goalkeeper'][t]
  if g is not None and g not in line:fail('Keep the designated goalkeeper active until a new goalkeeper is appointed')
  for i in range(12):
   if d['status'][t][i] in ('active','bench'):d['status'][t][i]='active' if i in line else 'bench'
 elif k=='appoint':
  t=p['team'];i=p['player'];role=p['role']
  if d['status'][t][i] not in ('active','bench'):fail('Role needs an eligible player')
  if role=='goalkeeper':
   if i not in active(d,t) or i in (d['captain'][t],d['in_home'][t]):fail('Goalkeeper must be active and cannot hold captain or in-home role')
  elif i==d['goalkeeper'][t]:fail('Goalkeeper cannot be captain or in-home')
  d[role][t]=i
 elif k=='withdraw':
  t=p['team'];i=p['player']
  if d['status'][t][i] not in ('active','bench'):fail('Only an eligible player may withdraw')
  d['status'][t][i]='excluded'
  for role in ('goalkeeper','captain','in_home'):
   if d[role][t]==i:d[role][t]=None
  if d['phase']=='play':d['phase']='stopped';d['clock_running']=False
 elif k=='concede':d['score']=[0,0];d['score'][1-p['team']]=1;finish(d,1-p['team'],'forfeit')
 elif k=='abandon':d.update(phase='abandoned',clock_running=False,break_ms=0)
 elif k=='official_result':finish(d,p['winner'],'no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data'];s=schemas(d)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Period, clock, eligible lineup and penalty capacity must permit the event.'],external_observations=['Official goals, foul classifications, penalty servers, restart and timeout entitlement.']) for k,v in s.items()],constraints=dict(phase=d['phase'],period=d['period'],clock_ms=d['clock_ms'],score=d['score'],capacity=[capacity(d,t) for t in (0,1)],penalty_ms=d['penalty_ms'],major_fouls=d['major_fouls'],restart_team=d['restart_team'],timeouts=d['timeouts'],alternate=d['alternate']),completeness=False,reason='official_lacrosse_sixes_events')
