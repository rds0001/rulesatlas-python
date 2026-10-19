"""CMAS 2024 underwater rugby, regulation league official-event protocol."""
from copy import deepcopy
from ..values import fields, fail
from .handball import outcome
T=dict(type='integer',minimum=0,maximum=1)
P=dict(type='integer',minimum=0,maximum=14)
NT=dict(T,nullable=True)
B=dict(type='boolean')
def active(d,t):return [i for i,v in enumerate(d['players'][t]) if v=='active']
def capacity(d,t):return 6-sum(r['team']==t for r in d['penalties'])
def eligible(d,t,i):return d['players'][t][i] in ('active','bench')
def penalty(d,t,i,double=False,kind='time'):
 if not eligible(d,t,i):fail('Penalty server must be an eligible match player')
 d['players'][t][i]='penalty';d['restart_team']=1-t
 d['penalties'].append(dict(team=t,server=i,kind=kind,remaining_ms=300000 if kind=='expulsion' else 120000,segments=2 if double else 1,started=False))
 if double:d['final_warning'][t][i]=True

def release(d,index):
 r=d['penalties'][index]
 if r['segments']>1:r['segments']-=1;r['remaining_ms']=120000
 else:
  d['players'][r['team']][r['server']]='bench';d['penalties'].pop(index)
def goal(d,t):
 d['score'][t]+=1
 counts=[sum(r['team']==j and r['kind']=='time' for r in d['penalties']) for j in (0,1)]
 if counts[1-t]>counts[t]:release(d,next(i for i,r in enumerate(d['penalties']) if r['team']==1-t and r['kind']=='time'))
 d['restart_team']=1-t

def tick(d,ms):
 for i in range(len(d['penalties'])-1,-1,-1):
  r=d['penalties'][i]
  if not r['started']:continue
  left=ms
  while left>=r['remaining_ms']:
   left-=r['remaining_ms']
   if r['segments']==1:release(d,i);break
   release(d,i)
  else:r['remaining_ms']-=left

def flush(d):
 if d['delayed'] is not None:
  p=d['delayed'];d['delayed']=None
  if p['server'] is not None:penalty(d,p['team'],p['server'],p['double'])
  if p['throw']:d['pending']=dict(team=1-p['team'],attacker=None,defender=None,remaining_ms=45000)
  d['restart_team']=1-p['team']
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 seen=set()
 for r in d['penalties']:
  key=(r['team'],r['server'])
  if key in seen or d['players'][r['team']][r['server']]!='penalty':bad('Each penalty has one distinct suspended server')
  seen.add(key)
  duration=300000 if r['kind']=='expulsion' else 120000
  if r['remaining_ms']>duration or not r['started'] and r['remaining_ms']!=duration or r['kind']=='expulsion' and r['segments']!=1:bad('Penalty duration or consecutive segments are inconsistent')
 for t in (0,1):
  if capacity(d,t)<0:bad('More than six simultaneous team reductions')
  if sum(v=='reserve' for v in d['players'][t])>3:bad('At most three registered reserves')
  for i,v in enumerate(d['players'][t]):
   if (v=='penalty')!=((t,i) in seen):bad('Penalty status needs its serving record')
  for c in range(19):
   if sum(d['warnings'][t][i][c] for i in range(15))>=2 and not d['team_warnings'][t][c]:bad('Two player warnings of one category imply a team warning')
 if d['phase']=='live' and (d['clock_ms']==0 or d['pending'] is not None or any(not 0<len(active(d,t))<=capacity(d,t) for t in (0,1))):bad('Live play needs time and eligible reduced lineups')
 if d['phase']=='throw' and (d['pending'] is None or d['pending']['remaining_ms']==0):bad('A running throw needs its clock and participants')
 if d['pending'] is not None:
  p=d['pending']
  if d['phase'] not in ('stopped','throw','timeout'):bad('Pending penalty throw requires an interruption or throw phase')
  if (p['attacker'] is None)!=(p['defender'] is None):bad('Throw participants are nominated together')
  if p['attacker'] is not None and (not eligible(d,p['team'],p['attacker']) or not eligible(d,1-p['team'],p['defender'])):bad('Throw participants must be eligible')
  if d['phase']=='throw' and p['attacker'] is None:bad('Running throw needs nominated participants')
 if d['delayed'] is not None:
  p=d['delayed']
  if d['phase']!='live' or p['server'] is None and not p['throw'] or p['server'] is not None and not eligible(d,p['team'],p['server']):bad('Delayed decision requires live play and eligible server')
 if d['phase']=='pre' and (d['half']!=1 or d['clock_ms']!=900000 or any(d['score']) or d['penalties']):bad('Pre-match state precedes scoring and penalties')
 if d['phase']=='interval' and (d['half']!=1 or d['clock_ms']!=0):bad('Interval follows the first half')
 if d['phase'] in ('timeout','interval') and d['break_ms']==0:bad('Break phase needs remaining break time')
 if d['phase']=='finished':
  if d['reason']=='regulation':
   w=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0])
   if d['half']!=2 or d['clock_ms']!=0 or d['pending'] is not None or d['winner']!=w:bad('Regulation result must match completed time and score')
  elif d['reason']=='concession':
   if d['winner'] is None:bad('Concession needs a winner')
  elif d['reason'] not in ('official_result','no_contest'):bad('Finished match requires a result reason')
 elif d['winner'] is not None or d['reason'] is not None:bad('Unfinished match cannot declare a result')

def schemas(d):
 phase=d['phase'];s={}
 if phase=='finished':return s
 if phase=='abandoned':return dict(official_result=dict(winner=NT))
 if phase=='pre':s['start_match']={}
 if phase in ('pre','live','stopped','interval'):
  s['set_lineup']=dict(team=T,players=dict(type='array',minItems=0,maxItems=6,items=P))
 if phase=='live':
  s.update(goal=dict(team=T,player=P),stop=dict(restart_team=NT),signal_delayed=dict(team=T,server=dict(P,nullable=True),double=B,throw=B))
 if phase in ('live','throw'):s['elapse']=dict(milliseconds=dict(type='integer',minimum=1,maximum=900000))
 if phase in ('live','stopped'):
  s.update(time_penalty=dict(team=T,server=P,double=B),expel=dict(team=T,player=P,server=P,repeated=B),warn=dict(team=T,player=P,category=dict(type='integer',minimum=0,maximum=18)),team_warning=dict(team=T,category=dict(type='integer',minimum=0,maximum=18)),final_warning=dict(team=T,player=P))
  s['additional_penalty']=dict(team=T,server=P)
  s['expel_serving']=dict(team=T,player=P,server=P,retain_time_penalty=B,replacement_server=dict(P,nullable=True))
  if d['pending'] is None:s['award_throw']=dict(team=T)
 if phase=='stopped':
  s.update(reserve_substitution=dict(team=T,outgoing=P,incoming=P,authorized=B),timeout=dict(team=T))
  if d['pending'] is not None:s['start_throw']=dict(attacker=P,defender=P)
  elif d['clock_ms']>0:s['restart']=dict(team=NT)
  else:s.update(close_half={},late_goal=dict(team=T,player=P))
 if phase=='throw':s['resolve_throw']=dict(result=dict(type='enum',values=['goal','save','attacker_foul','defender_foul','defender_surface_foul']))
 if phase in ('interval','timeout'):s['elapse_break']=dict(milliseconds=dict(type='integer',minimum=1,maximum=300000))
 s.update(abandon={},concede=dict(team=T))
 return s

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];ss=schemas(d)
 if k not in ss:fail('Action is not permitted in this phase')
 fields(p,ss[k],'/params');t=p.get('team')
 if k=='start_match':
  if any(len(active(d,j))!=6 for j in (0,1)):fail('Each team must start with six eligible players')
  d['phase']='stopped'
 elif k=='set_lineup':
  ids=p['players']
  if len(ids)!=len(set(ids)) or len(ids)>capacity(d,t) or any(not eligible(d,t,i) for i in ids):fail('Lineup exceeds capacity or includes an ineligible player')
  for i in active(d,t):d['players'][t][i]='bench'
  for i in ids:d['players'][t][i]='active'
  if d['phase']=='live' and not ids:fail('A team without active players requires an official stoppage')
 elif k=='restart':
  if p['team']!=d['restart_team']:fail('Restart entitlement must match the official decision')
  if any(not 0<len(active(d,j))<=capacity(d,j) for j in (0,1)):fail('Correct the reduced lineup before restarting')
  d['phase']='live';d['restart_team']=None;d['late_used']=False
  for r in d['penalties']:r['started']=True
 elif k=='stop':flush(d);d['phase']='stopped';d['restart_team']=p['restart_team']
 elif k=='signal_delayed':
  if d['delayed'] is not None or p['server'] is None and not p['throw'] or p['server'] is None and p['double']:fail('One pending time-penalty or penalty-throw decision is required')
  if p['server'] is not None and not eligible(d,t,p['server']):fail('Delayed server must be eligible')
  d['delayed']=deepcopy(p)
 elif k in ('goal','late_goal'):
  if d['players'][t][p['player']]!='active':fail('The scorer must be active')
  if k=='late_goal':
   if d['late_used']:fail('The period-ending goal has already been recorded')
   d['late_used']=True
  if d['delayed'] is not None:
   if d['delayed']['team']==t:fail('Stop and resolve the delayed decision before an offending-team goal')
   d['delayed']=None
  goal(d,t);d['phase']='stopped'
 elif k=='elapse':
  ms=p['milliseconds'];throw=d['phase']=='throw'
  if ms>(d['pending']['remaining_ms'] if throw else d['clock_ms']):fail('Clock event exceeds the current playing segment')
  d['clock_ms']=max(0,d['clock_ms']-ms);tick(d,ms)
  if throw:
   d['pending']['remaining_ms']-=ms
   if d['pending']['remaining_ms']==0:d['pending']=None;d['phase']='stopped';d['restart_team']=None
  elif d['clock_ms']==0:flush(d);d['phase']='stopped'
 elif k in ('time_penalty','expel','warn','team_warning','final_warning'):
  if d['pending'] is not None and d['pending']['attacker'] is not None:fail('Complete the nominated throw before an unrelated disciplinary decision')
  flush(d);d['phase']='stopped'
  if k=='time_penalty':penalty(d,t,p['server'],p['double'])
  elif k=='expel':
   i=p['player'];server=p['server']
   if d['players'][t][i]=='excluded' or i==server or p['repeated'] and not d['final_warning'][t][i]:fail('Repeat expulsion needs a final warning and a different eligible server')
   old=[r for r in d['penalties'] if r['team']==t and r['server']==i]
   if old:fail('Resolve the serving player penalty before a separate expulsion decision')
   d['players'][t][i]='excluded';penalty(d,t,server,kind='expulsion')
  elif k=='final_warning':
   if not eligible(d,t,p['player']):fail('Final warning requires an eligible player')
   d['final_warning'][t][p['player']]=True
  elif k=='team_warning':d['team_warnings'][t][p['category']]=True
  else:
   i=p['player'];c=p['category']
   if not eligible(d,t,i):fail('Warning requires an eligible player')
   if d['team_warnings'][t][c] or d['warnings'][t][i][c]:penalty(d,t,i)
   else:
    d['warnings'][t][i][c]=True
    if sum(d['warnings'][t][j][c] for j in range(15))>=2:d['team_warnings'][t][c]=True
 elif k=='additional_penalty':
  rr=[r for r in d['penalties'] if r['team']==t and r['server']==p['server']]
  if len(rr)!=1 or rr[0]['kind']!='time' or rr[0]['started'] or rr[0]['segments']!=1:fail('Additional misconduct extends one unstarted time penalty to two segments')
  rr[0]['segments']=2;d['final_warning'][t][p['server']]=True;d['phase']='stopped'
 elif k=='expel_serving':
  i=p['player'];rr=[r for r in d['penalties'] if r['team']==t and r['server']==i]
  if len(rr)!=1 or rr[0]['kind']!='time' or p['server']==i:fail('Nominate a serving time-penalty player and a different expulsion server')
  j=p['replacement_server']
  if p['retain_time_penalty']:
   if j is None or j==p['server'] or not eligible(d,t,j):fail('Retained time penalty requires a separate eligible replacement server')
   rr[0]['server']=j;d['players'][t][j]='penalty'
  else:
   if j is not None:fail('A superseded time penalty needs no replacement server')
   d['penalties'].remove(rr[0])
  d['players'][t][i]='excluded';penalty(d,t,p['server'],kind='expulsion');d['phase']='stopped';flush(d)
 elif k=='award_throw':
  flush(d)
  if d['pending'] is not None:fail('The delayed decision already awarded a penalty throw')
  d['pending']=dict(team=t,attacker=None,defender=None,remaining_ms=45000);d['phase']='stopped'
 elif k=='start_throw':
  q=d['pending'];t=q['team']
  if not eligible(d,t,p['attacker']) or not eligible(d,1-t,p['defender']):fail('Throw participants must be eligible match players')
  q.update(p);q['remaining_ms']=45000;d['phase']='throw'
 elif k=='resolve_throw':
  q=d['pending'];t=q['team'];result=p['result']
  d['phase']='stopped'
  if result in ('defender_foul','defender_surface_foul'):
   penalty(d,1-t,q['defender'],result=='defender_surface_foul');q.update(attacker=None,defender=None,remaining_ms=45000)
  else:
   d['pending']=None;d['restart_team']=None
   if result=='goal':goal(d,t)
 elif k=='reserve_substitution':
  a=p['outgoing'];b=p['incoming']
  if not p['authorized'] or d['reserve_changes'][t]>=3 or not eligible(d,t,a) or d['players'][t][b]!='reserve':fail('Reserve substitution needs authorization, an eligible pair and a remaining allowance')
  if d['pending'] is not None and d['pending']['attacker'] is not None:fail('Do not change nominated throw participants')
  d['players'][t][b]=d['players'][t][a];d['players'][t][a]='reserve';d['reserve_changes'][t]+=1
 elif k=='timeout':
  if d['timeouts'][t] or d['clock_ms']==0:fail('One timeout per team and half is available during an existing interruption')
  d['timeouts'][t]=True;d['phase']='timeout';d['break_ms']=60000
 elif k=='elapse_break':
  if p['milliseconds']>d['break_ms']:fail('Break elapsed time exceeds its remaining duration')
  d['break_ms']-=p['milliseconds']
  if d['break_ms']==0:
   if d['phase']=='interval':d.update(half=2,clock_ms=900000,timeouts=[False,False],late_used=False,restart_team=None)
   d['phase']='stopped'
 elif k=='close_half':
  if d['half']==1:d.update(phase='interval',break_ms=300000)
  else:d.update(phase='finished',winner=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0]),reason='regulation')
 elif k=='abandon':d.update(phase='abandoned',pending=None,delayed=None)
 elif k=='concede':d.update(phase='finished',winner=1-t,reason='concession',pending=None,delayed=None)
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_contest' if p['winner'] is None else 'official_result')
 return d

def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Eligible participants, reduced capacity, phase and remaining allowances must permit the event.'],external_observations=['Official goals, infringements, restart decisions and elapsed effective time.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],half=d['half'],clock_ms=d['clock_ms'],score=d['score'],capacity=[capacity(d,t) for t in (0,1)],penalties=d['penalties'],pending=d['pending'],restart_team=d['restart_team'],reserve_changes=d['reserve_changes'],timeouts=d['timeouts']),completeness=False,reason='official_underwater_rugby_events')
