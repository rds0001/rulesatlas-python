"""Floorball league match: official events, penalty queues and eligibility."""
from copy import deepcopy
from ..values import fields, fail
from .handball import outcome
T=dict(type='integer',minimum=0,maximum=1)
P=dict(type='integer',minimum=0,maximum=19)
NP=dict(P,nullable=True)
B=dict(type='boolean')
def enum(*x):return dict(type='enum',values=list(x))
def active(d,t):return [i for i,s in enumerate(d['status'][t]) if s=='active']
def measured(d):
 result=[];seen=[set(),set()]
 for j,r in enumerate(d['penalties']):
  t=r['team'];i=r['offender']
  if len(seen[t])<2 and i not in seen[t]:seen[t].add(i);result.append(j)
 return result
def capacity(d,t):return 6-sum(d['penalties'][j]['team']==t for j in measured(d))
def blocked(d,t,i):return any(r['team']==t and (i==r['server'] or i==r['offender'] and (not d['goalkeepers'][t][i] or d['status'][t][i]=='penalty')) for r in d['penalties']) or d['personal_ms'][t][i]>0 or d['held'][t][i]
def release(d,stopped):
 for t in (0,1):
  for i in range(20):
   if stopped or capacity(d,t)>4 and not d['goalkeepers'][t][i] and not d['personal_wait'][t][i]:d['held'][t][i]=False
   if stopped:d['personal_wait'][t][i]=False
   if d['status'][t][i]=='penalty' and not blocked(d,t,i):d['status'][t][i]='bench'
def stop(d):
 d['phase']='stopped';release(d,True)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  a=active(d,t)
  if len(a)>6 or sum(d['goalkeepers'][t][i] for i in a)>1:bad('At most six active players and one goalkeeper are permitted')
  if d['phase']=='play' and (len(a)>capacity(d,t) or len(a)<4):bad('Live lineup must satisfy penalty capacity and minimum strength')
  for i in range(20):
   if blocked(d,t,i) and d['status'][t][i] not in ('penalty','excluded'):bad('Penalized players cannot be available')
   if d['status'][t][i]=='penalty' and not blocked(d,t,i):bad('Penalty status requires a clock or return restriction')
   if (d['majors'][t][i]>1 or d['personals'][t][i]>1) and d['status'][t][i]!='excluded':bad('Repeated major or personal misconduct excludes the player')
  if d['captain'][t] is not None and (d['goalkeepers'][t][d['captain'][t]] or d['status'][t][d['captain'][t]]=='excluded'):bad('Captain must be an eligible field player')
 for r in d['penalties']:
  if d['status'][r['team']][r['server']]!='penalty':bad('Penalty server must be unavailable')
 if d['phase']=='play' and (not d['clock_ms'] or d['pending_team'] is not None):bad('Play requires remaining time and no pending penalty shot')
 if d['phase']=='interval' and (d['period']==3 or d['clock_ms']!=0):bad('Interval must follow an unfinished regulation match')
 if d['phase']=='pre' and (d['period']!=1 or d['clock_ms']!=1200000 or any(d['score']) or d['penalties']):bad('Pre-game state must precede scoring and penalties')
 if d['pending_team'] is not None and d['phase'] not in ('stopped','timeout'):bad('Penalty shot requires a stopped match')
 if d['phase']=='finished':
  if d['reason']=='regulation':
   w=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0])
   if d['period']!=3 or d['clock_ms'] or d['winner']!=w:bad('Regulation outcome must match score and completed time')
  elif d['reason']=='concession':
   if d['winner'] is None:bad('Forfeit requires a winner')
  elif d['reason'] not in ('official_result','no_contest'):bad('Terminal state requires a result reason')
 elif d['winner'] is not None or d['reason'] is not None:bad('Only a finished match has a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 s.update(set_lineup=dict(team=T,players=dict(type='array',minItems=0,maxItems=6,items=P)),appoint_captain=dict(team=T,player=P),designate_goalkeeper=dict(team=T,player=P),withdraw=dict(team=T,player=P),abandon={},concede=dict(team=T))
 if ph=='pre':s['start_match']={}
 if ph=='interval':s['elapse_break']=dict(milliseconds=dict(type='integer',minimum=1,maximum=600000))
 if ph in ('play','stopped'):
  s['timeout']=dict(team=T)
  s['penalty']=dict(team=T,player=P,server=P,kind=enum('minor','major','personal','technical_match','match'))
  if d['pending_team'] is None:
   s['timeout']=dict(team=T)
   s['award_shot']=dict(team=T)
   if ph=='play':s.update(elapse=dict(milliseconds=dict(type='integer',minimum=1,maximum=1200000)),stop_play={},goal=dict(team=T,player=P,own_goal=B),signal_penalty=dict(team=T,player=P,server=P,kind=enum('minor','major','personal','technical_match','match'),goal_situation=B),signal_shot=dict(team=T))
   elif d['clock_ms']:s['restart']={}
   else:s['close_period']={}
  else:s['resolve_shot']=dict(player=P,scored=B)
 if ph=='timeout':s['elapse_break']=dict(milliseconds=dict(type='integer',minimum=1,maximum=30000))
 return s
def impose(d,p):
 t=p['team'];i=p['player'];server=p['server'];kind=p['kind']
 if d['status'][t][i]=='excluded':fail('Excluded player cannot incur another match reduction')
 if kind=='major':d['majors'][t][i]+=1
 if kind=='personal':d['personals'][t][i]+=1
 if d['majors'][t][i]>=2 or d['personals'][t][i]>=2:kind='match'
 delegated=kind in ('personal','technical_match','match') or d['personal_ms'][t][i]>0 or d['goalkeepers'][t][i] and kind=='minor' and not blocked(d,t,i)
 if delegated:
  if server==i or d['goalkeepers'][t][server] or d['status'][t][server] not in ('active','bench'):fail('This sanction needs a separate eligible field-player server')
 elif server!=i:fail('The offender must serve this penalty')
 if kind in ('technical_match','match'):
  d['status'][t][i]='excluded';d['personal_ms'][t][i]=0;d['personal_running'][t][i]=False;d['held'][t][i]=False;d['personal_wait'][t][i]=False
  if d['captain'][t]==i:d['captain'][t]=None
  for r in d['penalties']:
   if r['team']==t and r['offender']==i:r['server']=server
 elif not (d['goalkeepers'][t][i] and delegated and kind=='minor'):d['status'][t][i]='penalty'
 if kind=='personal':d['personal_ms'][t][i]=600000;d['personal_wait'][t][i]=True;d['personal_running'][t][i]=False
 d['status'][t][server]='penalty'
 for _ in range(2 if kind in ('major','technical_match','match') else 1):d['penalties'].append(dict(team=t,offender=i,server=server,ms=120000))
def flush(d,cancel_minor=False):
 pending=d['delayed'];d['delayed']=[]
 if cancel_minor:
  ix=next((i for i in reversed(range(len(pending))) if pending[i]['kind']=='minor'),None)
  if ix is not None:pending.pop(ix)
 for p in pending:impose(d,p)
def expire(d,indices):
 for j in indices:
  r=d['penalties'][j]
  for i in set((r['offender'],r['server'])):
   if d['status'][r['team']][i]=='penalty':d['held'][r['team']][i]=True
 d['penalties']=[r for j,r in enumerate(d['penalties']) if j not in indices]
 release(d,False)
def elapse(d,ms):
 while ms:
  indices=measured(d)
  for t in (0,1):
   for i in range(20):
    if not any(r['team']==t and r['offender']==i for r in d['penalties']):d['personal_running'][t][i]=d['personal_ms'][t][i]>0
    elif any(d['penalties'][j]['team']==t and d['penalties'][j]['offender']==i for j in indices):d['personal_running'][t][i]=False
  running=[(t,i) for t in (0,1) for i in range(20) if d['personal_ms'][t][i]>0 and d['personal_running'][t][i]]
  step=min([ms]+[d['penalties'][j]['ms'] for j in indices]+[d['personal_ms'][t][i] for t,i in running]);ms-=step
  for j in indices:d['penalties'][j]['ms']-=step
  for t,i in running:
   d['personal_ms'][t][i]-=step
   if not d['personal_ms'][t][i]:d['personal_running'][t][i]=False;d['held'][t][i]=True;d['personal_wait'][t][i]=True
  expire(d,[j for j in indices if d['penalties'][j]['ms']==0])
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params');t=p.get('team');i=p.get('player')
 if k=='start_match':
  if any(len(active(d,j))!=6 or sum(d['goalkeepers'][j][x] for x in active(d,j))!=1 or d['captain'][j] is None for j in (0,1)):fail('Start requires five field players, one goalkeeper and a captain per team')
  stop(d)
 elif k=='set_lineup':
  a=p['players']
  if len(set(a))!=len(a) or len(a)>capacity(d,t) or sum(d['goalkeepers'][t][x] for x in a)>1:fail('Lineup violates capacity, uniqueness or goalkeeper limit')
  if any(d['status'][t][x] not in ('active','bench') for x in a):fail('Unavailable player cannot enter')
  if d['phase']=='play' and len(a)<4:fail('At least four players are required during play')
  for x in range(20):
   if d['status'][t][x] in ('active','bench'):d['status'][t][x]='active' if x in a else 'bench'
 elif k=='appoint_captain':
  if d['goalkeepers'][t][i] or d['status'][t][i] not in ('active','bench'):fail('Captain must be an available field player')
  d['captain'][t]=i
 elif k=='designate_goalkeeper':
  if d['phase']=='play' or d['status'][t][i]!='bench' or d['captain'][t]==i:fail('A new goalkeeper must be an available bench player at an interruption')
  d['goalkeepers'][t][i]=True
 elif k=='withdraw':
  if d['status'][t][i] not in ('active','bench'):fail('Only available players can withdraw')
  d['status'][t][i]='excluded'
  if d['captain'][t]==i:d['captain'][t]=None
  if d['phase']=='play':stop(d)
 elif k=='restart':
  if d['delayed'] or d['delayed_shot'] is not None:fail('Resolve delayed decisions before restarting')
  if any(len(active(d,j))<4 or len(active(d,j))>capacity(d,j) or d['captain'][j] is None for j in (0,1)):fail('Restart requires legal lineups and captains')
  d['phase']='play'
 elif k=='elapse':
  ms=p['milliseconds']
  if ms>d['clock_ms']:fail('Time cannot cross the period boundary')
  elapse(d,ms);d['clock_ms']-=ms
  if not d['clock_ms']:
   flush(d);d['pending_team']=d['delayed_shot'];d['delayed_shot']=None;stop(d)
 elif k=='stop_play':
  flush(d);d['pending_team']=d['delayed_shot'];d['delayed_shot']=None;stop(d)
 elif k=='penalty':impose(d,p);stop(d)
 elif k=='signal_penalty':
  if d['delayed'] and (d['delayed'][0]['team']!=t or not p['goal_situation']):fail('Additional delayed penalties require the same offending team and a goal situation')
  probe=deepcopy(d);impose(probe,p)
  d['delayed'].append({x:p[x] for x in ('team','player','server','kind')})
 elif k=='signal_shot':
  if d['delayed_shot'] is not None:fail('A penalty shot is already delayed')
  d['delayed_shot']=t
 elif k=='goal':
  scorer=1-t if p['own_goal'] else t
  if d['status'][scorer][i]!='active':fail('Goal attribution requires an active player')
  delayed=bool(d['delayed']) or d['delayed_shot'] is not None
  disallowed=d['delayed'] and d['delayed'][0]['team']==t and not p['own_goal']
  if not disallowed:
   d['score'][t]+=1
   if not delayed and capacity(d,1-t)<capacity(d,t):
    js=[j for j in measured(d) if d['penalties'][j]['team']==1-t]
    if js:expire(d,[js[0]])
  flush(d,cancel_minor=bool(not disallowed and d['delayed'] and d['delayed'][0]['team']!=t))
  d['pending_team']=None if not disallowed and d['delayed_shot']==t else d['delayed_shot'];d['delayed_shot']=None;stop(d)
 elif k=='award_shot':
  flush(d);d['pending_team']=t;d['delayed_shot']=None;stop(d)
 elif k=='resolve_shot':
  t=d['pending_team']
  if d['status'][t][i] not in ('active','bench') or d['goalkeepers'][t][i]:fail('Penalty shooter must be an available field player')
  if p['scored']:d['score'][t]+=1
  d['pending_team']=None
 elif k=='timeout':
  if d['timeouts'][t]:fail('One timeout per team and match is available')
  if d['phase']=='play':fail('Record the official interruption before taking the timeout')
  d['timeouts'][t]=True;d['phase']='timeout';d['break_ms']=30000
 elif k=='elapse_break':
  ms=p['milliseconds']
  if ms>d['break_ms']:fail('Time cannot cross the break boundary')
  d['break_ms']-=ms
  if not d['break_ms']:
   if d['phase']=='interval':d['period']+=1;d['clock_ms']=1200000
   stop(d)
 elif k=='close_period':
  if d['delayed'] or d['delayed_shot'] is not None:fail('Outstanding official decisions must be resolved')
  if d['period']<3:d['phase']='interval';d['break_ms']=600000
  else:d.update(phase='finished',reason='regulation',winner=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0]))
 elif k=='abandon':d['phase']='abandoned';d['pending_team']=None
 elif k=='concede':d.update(phase='finished',winner=1-t,reason='concession',pending_team=None,score=[5 if j==1-t else 0 for j in (0,1)])
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Phase, eligible players, penalty queue and remaining time must permit the event.'],external_observations=['Official goals, infringements, interruptions and penalty-shot results.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],period=d['period'],clock_ms=d['clock_ms'],score=d['score'],capacity=[capacity(d,t) for t in (0,1)],penalties=d['penalties'],personal_ms=d['personal_ms'],pending_team=d['pending_team']),completeness=False,reason='official_floorball_events')
