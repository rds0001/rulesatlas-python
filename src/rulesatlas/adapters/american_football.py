"""IFAF 2023 completed-down and official-enforcement protocol; no physical model."""
from copy import deepcopy
from ..values import fields,fail
from .flag_football import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
E=lambda *x:dict(type='enum',values=list(x))
T=I(0,1);P=I(0,49);B=dict(type='boolean');SP=dict(type='number',minimum=0,maximum=100)
def finish(d,w,r):d.update(phase='finished',winner=w,reason=r,clock_running=False,break_ms=0)
def series(d,t,s):d.update(phase='ready',offense=t,spot=s,line_to_gain=min(100,s+10),down=1)
def kick(d,t,s=35):d.update(phase='kickoff',offense=t,spot=s,clock_running=False)
def settle(d):
 if d['quarter']<5 and not d['clock_ms'] and d['phase'] in ('ready','kickoff') and not d['extension']:
  d.update(resume_phase=d['phase'],phase='period_end',clock_running=False)
def end_series(d):
 if d['ot_series']==0:
  d['ot_series']=1;series(d,1-d['ot_first'],75)
 else:
  if d['score'][0]!=d['score'][1]:finish(d,int(d['score'][1]>d['score'][0]),'overtime');return
  old=d['ot_round'];d.update(ot_round=old+1,ot_series=0,timeouts=[0,0],phase='ot_choice')
  if old in (2,4):d.update(phase='interval',resume_phase='ot_choice',break_ms=120000)
  return
 if d['ot_round']>=3:d.update(phase='try_ready',spot=97)
def after_score(d,t):
 if d['quarter']==5:end_series(d)
 else:kick(d,t)
 settle(d)
def touchdown(d,t):
 d['score'][t]+=6
 if d['quarter']==5 and t!=d['offense']:finish(d,t,'overtime');return
 d.update(offense=t,phase='try_ready',spot=97,clock_running=False)
 deciding=(d['quarter']==4 and d['clock_ms']==0) or (d['quarter']==5 and d['ot_series']==1)
 if deciding and abs(d['score'][0]-d['score'][1])>2:after_score(d,t)
def elapse(d,n):
 if n>d['clock_ms'] or d['quarter']==5 and n:fail('Elapsed time exceeds the timed period')
 d['clock_ms']-=n
 d['clock_running']=False
 d['sit_out']=[[False]*50 for _ in (0,1)]
def next_down(d):
 if d['spot']>=d['line_to_gain']:series(d,d['offense'],d['spot'])
 elif d['down']<4:d['down']+=1
 elif d['quarter']==5:end_series(d)
 else:series(d,1-d['offense'],100-d['spot'])
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if d['status'][t].count('active')>11:bad('At most eleven players may be active')
  for i in range(50):
   if d['unsporting'][t][i]==2 and d['status'][t][i]!='excluded':bad('Second unsportsmanlike act requires exclusion')
   if d['sit_out'][t][i] and d['status'][t][i]=='active':bad('Restricted player cannot be active')
 if d['quarter']==5 and (d['clock_ms'] or d['clock_running'] or not d['ot_round']):bad('Overtime requires an untimed extra period')
 if d['phase'] in ('ready','try_ready','kickoff') and not 0<d['spot']<100:bad('Restart spot must lie inside the field')
 if d['phase']=='ready' and d['line_to_gain']<=d['spot']:bad('An earned first down must establish a new line to gain')
 if d['phase']=='period_end' and (d['clock_ms'] or d['extension']):bad('Period end requires expiry without an extension')
 if (d['phase'] in ('timeout','interval'))!=(d['break_ms']>0):bad('Break clock must agree with phase')
 if d['clock_running'] and d['phase']!='ready':bad('Game clock may run between scrimmage downs only')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason'] in ('draw','no_contest'))!=(d['winner'] is None):bad('Result must identify a winner or draw')
  if d['reason'] in ('regulation','overtime') and d['score'][d['winner']]<=d['score'][1-d['winner']]:bad('Winner must lead')
  if d['reason']=='draw' and d['score'][0]!=d['score'][1]:bad('Draw requires equal scores')
 elif d['winner'] is not None or d['reason'] is not None:bad('Unfinished match cannot have a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 if ph=='pre_game':s['choose_start']=dict(kicking_team=T)
 if ph=='halftime_choice':s['choose_second_half']=dict(kicking_team=T)
 if ph=='ot_choice':s['choose_overtime']=dict(first=T)
 if ph=='ready':s['play']=dict(result=E('advance','incomplete','turnover','new_series','regained','touchdown','defensive_touchdown','safety','defensive_safety','touchback','field_goal','missed_field_goal'),spot=SP,elapsed_ms=I(0,720000))
 if ph=='kickoff':s['free_kick_result']=dict(result=E('return','recovery','touchback','return_touchdown','safety'),spot=SP,elapsed_ms=I(0,720000))
 if ph=='try_ready':
  s['try_result']=dict(result=E('kick','touchdown','miss','defensive_touchdown','safety','defensive_safety'))
  s['forego_try']={}
 if ph in ('ready','kickoff','try_ready','period_end'):
  s['penalty']=dict(team=T,base_spot=SP,yards=E(0,5,10,15),effect=E('repeat','loss','first','keep'),live=B,extend=B,elapsed_ms=I(0,720000))
  s['official_enforcement']=dict(team=T,spot=SP,down=I(1,4),line_to_gain=SP,restart=E('ready','kickoff','try_ready'),extend=B,elapsed_ms=I(0,720000))
 if ph in ('ready','try_ready','kickoff'):s['timeout']=dict(team=T)
 if ph=='ready' and d['quarter']<5:
  s['official_clock']=dict(running=B);s['elapse_between']=dict(milliseconds=I(1,720000));s['clock_runoff']=dict(team=T,avoid_with_timeout=B)
 if ph=='period_end':s['close_period']={}
 if ph in ('timeout','interval'):s['elapse_break']=dict(milliseconds=I(1,1200000))
 s.update(set_lineup=dict(team=T,players=dict(type='array',minItems=1,maxItems=11,items=P)),sanction=dict(team=T,player=P,kind=E('unsporting','disqualify')),miss_next_down=dict(team=T,player=P),concede=dict(team=T),abandon={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];ss=schemas(d)
 if k not in ss:fail('Action is not permitted in this phase')
 fields(p,ss[k],'/params');t=d['offense']
 if k in ('play','try_result','free_kick_result') and any(not d['status'][x].count('active') for x in (0,1)):fail('Both teams require eligible players')
 if k=='choose_start':kick(d,p['kicking_team'])
 elif k=='choose_second_half':kick(d,p['kicking_team'])
 elif k=='choose_overtime':
  d.update(ot_first=p['first'],ot_series=0);series(d,p['first'],75)
  if d['ot_round']>=3:d.update(phase='try_ready',spot=97)
 elif k=='play':
  if d['quarter']<5 and not d['clock_ms'] and not d['extension']:fail('Expired period needs an authorized untimed down')
  r=p['result'];s=p['spot'];oldspot=d['spot'];elapse(d,p['elapsed_ms']);d['extension']=False
  if r in ('advance','turnover','new_series','regained') and not 0<s<100:fail('Use a scoring or touchback event at a goal line')
  if r=='incomplete' and s!=oldspot:fail('Incomplete pass retains the scrimmage spot')
  if r in ('touchdown','defensive_touchdown','field_goal') and s!=100 or r in ('safety','defensive_safety','touchback') and s!=0:fail('Scoring event requires the matching goal-line spot')
  if r in ('advance','incomplete'):d['spot']=s;next_down(d)
  elif r in ('turnover','touchback','missed_field_goal'):
   if d['quarter']==5:end_series(d)
   else:series(d,1-t,20 if r=='touchback' else max(20,100-oldspot) if r=='missed_field_goal' else s)
  elif r=='new_series':series(d,t,s)
  elif r=='regained':
   if d['quarter']==5:end_series(d)
   else:series(d,t,s)
  elif r in ('touchdown','defensive_touchdown'):touchdown(d,t if r=='touchdown' else 1-t)
  elif r=='field_goal':d['score'][t]+=3;after_score(d,t)
  elif r in ('safety','defensive_safety'):
   w=1-t if r=='safety' else t;d['score'][w]+=2
   if d['quarter']==5:
    if w!=t:finish(d,w,'overtime')
    else:end_series(d)
   else:kick(d,1-w,20)
  settle(d)
 elif k=='free_kick_result':
  r=p['result'];s=p['spot'];elapse(d,p['elapsed_ms']);d['extension']=False
  if r in ('return','recovery') and not 0<s<100:fail('Returned or recovered kick needs an interior spot')
  if r=='return_touchdown' and s!=100 or r in ('touchback','safety') and s!=0:fail('Kick scoring event requires a goal-line spot')
  if r=='return_touchdown':touchdown(d,1-t)
  elif r=='safety':d['score'][t]+=2;kick(d,1-t,20)
  else:series(d,t if r=='recovery' else 1-t,20 if r=='touchback' else s)
  settle(d)
 elif k=='try_result':
  d['extension']=False
  r=p['result'];d['sit_out']=[[False]*50 for _ in (0,1)]
  if r=='kick' and not (d['quarter']==5 and d['ot_round']>=2):d['score'][t]+=1
  elif r=='touchdown':d['score'][t]+=2
  elif r=='defensive_touchdown':d['score'][1-t]+=2
  elif r=='safety':d['score'][1-t]+=1
  elif r=='defensive_safety':d['score'][t]+=1
  after_score(d,t)
 elif k=='forego_try':
  deciding=d['quarter']==4 and not d['clock_ms'] or d['quarter']==5 and d['ot_series']==1
  if not deciding or d['score'][t]-d['score'][1-t] not in (1,2):fail('Only a deciding try with a one- or two-point lead may be declined')
  after_score(d,t)
 elif k in ('penalty','official_enforcement'):
  ph=d['phase'];live=p.get('live',True)
  if p['elapsed_ms'] and (not live or ph in ('try_ready','period_end')):fail('No game time may elapse on this enforcement')
  if p['elapsed_ms']:elapse(d,p['elapsed_ms'])
  d['clock_running']=False
  if p['extend'] and (d['quarter']==5 or d['clock_ms'] or not live):fail('Extension requires an accepted live foul at timed-period expiry')
  if k=='official_enforcement':
   if not 0<p['spot']<100 or p['restart']=='ready' and p['line_to_gain']<=p['spot']:fail('Official enforcement must establish a valid restart')
   d.update(offense=p['team'],spot=p['spot'],down=p['down'],line_to_gain=p['line_to_gain'],phase=p['restart'],extension=p['extend'])
  else:
   eff=p['effect'];base=p['base_spot'];team=p['team']
   if not 0<base<100:fail('Goal-line enforcement requires an official scoring decision')
   if eff=='first' and team==t or eff=='loss' and (team!=t or not live) or eff=='repeat' and not live or eff=='keep' and live:fail('Down effect conflicts with the offending side or classification')
   if ph in ('kickoff','try_ready') and eff=='first':fail('Special restart does not award a scrimmage first down')
   shift=min(p['yards'],(base if team==t else 100-base)/2);d['spot']=base-shift if team==t else base+shift
   d['extension']=p['extend']
   if ph=='period_end':d['phase']=d['resume_phase']
   if ph=='try_ready' and eff=='loss':after_score(d,t)
   elif ph!='kickoff' and ph!='try_ready':
    if eff=='first' or d['spot']>=d['line_to_gain']:series(d,t,d['spot'])
    elif eff=='loss':next_down(d)
  settle(d)
 elif k=='official_clock':
  if p['running'] and not d['clock_ms']:fail('Expired clock cannot run')
  d['clock_running']=p['running']
 elif k=='elapse_between':
  if not d['clock_running']:fail('Official game clock is stopped')
  n=p['milliseconds']
  if n>d['clock_ms']:fail('Elapsed time exceeds the timed period')
  d['clock_ms']-=n;settle(d)
 elif k=='clock_runoff':
  if d['quarter'] not in (2,4) or d['clock_ms']>=60000:fail('Ten-second runoff is restricted to the final minute')
  if p['avoid_with_timeout']:
   if d['timeouts'][p['team']]>=3:fail('No timeout remains to avoid the runoff')
   d['timeouts'][p['team']]+=1
  else:d['clock_ms']=max(0,d['clock_ms']-10000)
  d['clock_running']=False;settle(d)
 elif k=='close_period':
  q=d['quarter']
  if q<4:
   d.update(quarter=q+1,clock_ms=720000,clock_running=False,phase='interval',break_ms=1200000 if q==2 else 60000)
   if q==2:d.update(timeouts=[0,0],resume_phase='halftime_choice')
  elif d['score'][0]!=d['score'][1]:finish(d,int(d['score'][1]>d['score'][0]),'regulation')
  elif d['allow_draw']:finish(d,None,'draw')
  else:d.update(quarter=5,ot_round=1,ot_series=0,timeouts=[0,0],phase='ot_choice',clock_running=False)
 elif k=='timeout':
  team=p['team'];cap=1 if d['quarter']==5 else 3
  if d['timeouts'][team]>=cap:fail('No charged timeout remains')
  d['timeouts'][team]+=1;d.update(resume_phase=d['phase'],phase='timeout',break_ms=60000,clock_running=False)
 elif k=='elapse_break':
  if p['milliseconds']>d['break_ms']:fail('Elapsed time exceeds this break')
  d['break_ms']-=p['milliseconds']
  if not d['break_ms']:d['phase']=d['resume_phase']
 elif k=='set_lineup':
  team=p['team'];line=p['players']
  if len(set(line))!=len(line) or any(d['status'][team][i]=='excluded' or d['sit_out'][team][i] for i in line):fail('Lineup requires distinct eligible players')
  d['status'][team]=[x if x=='excluded' else 'active' if i in line else 'bench' for i,x in enumerate(d['status'][team])]
 elif k=='sanction':
  team=p['team'];i=p['player']
  if d['status'][team][i]=='excluded':fail('Player is already excluded')
  if p['kind']=='unsporting':d['unsporting'][team][i]+=1
  if p['kind']=='disqualify' or d['unsporting'][team][i]==2:d['status'][team][i]='excluded'
 elif k=='miss_next_down':
  team=p['team'];i=p['player']
  if d['status'][team][i]!='active':fail('Restriction requires an active player')
  d['status'][team][i]='bench';d['sit_out'][team][i]=True;d['clock_running']=False
 elif k=='concede':finish(d,1-p['team'],'concession')
 elif k=='abandon':d.update(phase='abandoned',clock_running=False,break_ms=0)
 elif k=='official_result':finish(d,p['winner'],'no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Official completed event and current phase must agree.'],external_observations=['Final dead-ball result, legal scoring, official enforcement and clock rulings.']) for k,v in schemas(d).items()],constraints={k:d[k] for k in ('phase','quarter','clock_ms','score','offense','spot','line_to_gain','down','extension','ot_round','ot_series','timeouts')},completeness=False,reason='official_tackle_football_protocol')
