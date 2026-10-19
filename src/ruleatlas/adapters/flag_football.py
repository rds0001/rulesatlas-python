"""Five-a-side flag football: completed downs and official penalty enforcement."""
from copy import deepcopy
from ..values import fields,fail
from .pelota import outcome as base_outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
E=lambda *x:dict(type='enum',values=list(x))
T=I(0,1);P=I(0,14);B=dict(type='boolean');SPOT=dict(type='number',minimum=0,maximum=50)
def active(d,t):return [i for i,x in enumerate(d['status'][t]) if x=='active']
def finish(d,w,r):d.update(phase='finished',winner=w,reason=r,clock_running=False,break_ms=0)
def new_series(d,t,spot=5):d.update(offense=t,spot=spot,down=1,middle_gained=spot>25,phase='ready',try_value=0)
def end_ot_series(d):
 if d['ot_series']==0:
  d['ot_series']=1;new_series(d,1-d['ot_first'],25)
 else:
  if d['score'][0]!=d['score'][1]:finish(d,int(d['score'][1]>d['score'][0]),'overtime');return
  d['ot_round']+=1;d['ot_series']=0;new_series(d,d['ot_first'],45)
 if d['ot_round']>=2:d.update(phase='try_ready',try_value=1,spot=45)
 else:d['middle_gained']=True
 d['clock_running']=False

def settle(d):
 if d['half']<=2 and d['clock_ms']==0 and d['phase']=='ready' and not d['extension']:d['phase']='period_end';d['clock_running']=False
 if d['half']<=2 and d['clock_ms']<=120000 and not d['notified']:
  d['notified']=True;d['mercy_clock']=abs(d['score'][0]-d['score'][1])>=30;d['clock_running']=False

def elapse(d,n):
 if n>d['clock_ms'] or d['half']==3 and n:fail('Elapsed time exceeds the timed period')
 d['clock_ms']-=n

def down_end(d):
 if d['down']==4:
  if d['half']==3:end_ot_series(d)
  else:new_series(d,1-d['offense'])
 else:d['down']+=1

def penalty_distance(d,t,base,yards):
 distance=base if t==d['offense'] else 50-base
 shift=min(yards,distance/2)
 d['spot']=base-shift if t==d['offense'] else base+shift

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if len(active(d,t))>5:bad('At most five players may be active')
  for i in range(15):
   if d['unsporting'][t][i]==2 and d['status'][t][i]!='excluded':bad('Second unsportsmanlike act requires exclusion')
   if d['sit_out'][t][i] and d['status'][t][i]=='active':bad('A player ordered to miss a down cannot be active')
 if d['half']==3 and (d['clock_ms']!=0 or d['ot_round']<1 or d['ot_first'] is None or d['clock_running']):bad('Overtime is untimed and requires a recorded toss')
 if d['phase'] in ('ready','try_ready') and not 0<d['spot']<50:bad('Next snap must be inside the field of play')
 if d['phase']=='try_ready' and d['try_value'] not in (1,2):bad('A try needs a fixed point value')
 if d['phase']=='try_choice' and d['try_value']!=0:bad('Try choice cannot already have a declared value')
 if d['phase']=='period_end' and (d['clock_ms']!=0 or d['extension']):bad('Period end requires expiry and no outstanding extension')
 if (d['phase'] in ('timeout','interval'))!=(d['break_ms']>0):bad('Break clock must agree with phase')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason'] in ('draw','no_contest'))!=(d['winner'] is None):bad('Result must identify winner, draw or no contest')
  if d['reason'] in ('regulation','overtime') and d['score'][d['winner']]<=d['score'][1-d['winner']]:bad('Winner must lead the score')
  if d['reason']=='draw' and d['score'][0]!=d['score'][1]:bad('Draw requires equal scores')
 elif d['winner'] is not None or d['reason'] is not None:bad('Unfinished match cannot have a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 if ph=='pre_game':s['choose_start']=dict(team=T)
 if ph=='ready':s['play']=dict(result=E('advance','incomplete','interception','touchdown','defensive_touchdown','safety','touchback'),spot=SPOT,elapsed_ms=I(0,1200000),out_of_bounds=B,forward_pass=B)
 if ph in ('ready','try_choice','try_ready') and d['half']<=2:
  s['elapse_between']=dict(milliseconds=I(1,1200000));s['timeout']=dict(team=T)
 if ph=='try_choice':s['choose_try']=dict(points=I(1,2))
 if ph=='try_ready':s['try_result']=dict(result=E('success','miss','defensive_touchdown','offense_safety','defense_safety'),elapsed_ms=I(0,1200000))
 if ph in ('ready','try_ready','period_end'):s['penalty']=dict(team=T,base_spot=SPOT,yards=E(0,5,10),effect=E('repeat','loss','first','keep'),live=B)
 if ph in ('try_choice','interval','period_end'):s['carry_penalty']=dict(team=T,yards=E(5,10))
 if ph=='period_end':s['close_period']={}
 if ph in ('timeout','interval'):s['elapse_break']=dict(milliseconds=I(1,120000))
 if ph=='ot_toss':s['choose_overtime']=dict(first=T)
 if ph!='pre_game':
  s.update(set_lineup=dict(team=T,players=dict(type='array',minItems=4,maxItems=5,items=P)),sanction=dict(team=T,player=P,kind=E('unsporting','flagrant')),miss_next_down=dict(team=T,player=P),official_clock=dict(running=B))
 s.update(concede=dict(team=T),abandon={})
 return s
def apply_carry(d):
 for item in d['carry']:penalty_distance(d,item['team'],d['spot'],item['yards'])
 d['carry']=[]
 if d['spot']>25:d['middle_gained']=True

def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='choose_start':d['first_team']=p['team'];new_series(d,p['team'])
 elif k=='play':
  if any(len(active(d,t))<4 for t in (0,1)):fail('Each team needs at least four active eligible players')
  if d['half']<=2 and not d['clock_ms'] and not d['extension']:fail('Expired period requires an authorized untimed down')
  r=p['result'];old=d['offense'];oldspot=d['spot'];n=p['elapsed_ms']
  if oldspot>=45 and not p['forward_pass'] and r in ('advance','touchdown'):fail('A play from the no-running zone requires a forward pass beyond scrimmage')
  if r in ('touchdown','defensive_touchdown') and p['spot']!=50 or r in ('safety','touchback') and p['spot']!=0:fail('Scoring events must use the matching goal-line spot')
  if r=='incomplete' and p['spot']!=oldspot:fail('Incomplete pass retains the previous scrimmage spot')
  if r in ('advance','interception') and not 0<p['spot']<50:fail('Use a scoring or touchback event at the goal line')
  elapse(d,n);d['extension']=False;d['clock_running']=d['half']<=2 and d['clock_ms']>0
  d['sit_out']=[[False]*15 for _ in (0,1)]
  first=False
  if r in ('advance','incomplete'):
   d['spot']=p['spot']
   if not d['middle_gained'] and d['spot']>25:d['middle_gained']=True;d['down']=1;first=True
   else:
    previous=d['offense'];down_end(d);first=d['offense']!=previous
  elif r in ('interception','touchback'):
   if d['half']==3:end_ot_series(d)
   else:new_series(d,1-old,p['spot'] if r=='interception' else 5)
   first=True
  elif r in ('touchdown','defensive_touchdown'):
   w=old if r=='touchdown' else 1-old;d['score'][w]+=6
   if d['half']==3 and d['ot_series']==0 and w!=old:finish(d,w,'overtime')
   else:d.update(offense=w,phase='try_choice',try_value=0)
  elif r=='safety':
   d['score'][1-old]+=2
   if d['half']==3:
    if d['ot_series']==0:finish(d,1-old,'overtime')
    else:end_ot_series(d)
   else:new_series(d,1-old)
   first=True
  if d['clock_ms']<=120000 and not d['mercy_clock'] and (first or p['out_of_bounds'] or r!='advance'):d['clock_running']=False
  settle(d)
 elif k=='elapse_between':
  if not d['clock_running']:fail('The official game clock is stopped')
  elapse(d,p['milliseconds']);settle(d)
 elif k=='choose_try':
  d.update(try_value=p['points'],spot=45 if p['points']==1 else 40,phase='try_ready');apply_carry(d)
 elif k=='try_result':
  if any(len(active(d,t))<4 for t in (0,1)):fail('Each team needs four active players for a try')
  if p['elapsed_ms'] and not d['clock_running']:fail('Try elapsed time requires a running game clock')
  elapse(d,p['elapsed_ms']);r=p['result'];old=d['offense'];d['sit_out']=[[False]*15 for _ in (0,1)]
  if r=='success':d['score'][old]+=d['try_value']
  elif r=='defensive_touchdown':d['score'][1-old]+=2
  elif r=='offense_safety':d['score'][1-old]+=1
  elif r=='defense_safety':d['score'][old]+=1
  if d['half']==3:
   if d['ot_round']>=2 and d['ot_series']==0 and r in ('defensive_touchdown','offense_safety'):finish(d,1-old,'overtime')
   else:end_ot_series(d)
  else:new_series(d,1-old);apply_carry(d);settle(d)
 elif k=='penalty':
  t=p['team'];eff=p['effect'];live=p['live'];old=d['offense'];is_try=d['phase']=='try_ready'
  if eff=='first' and t==old or eff=='loss' and (t!=old or not live) or eff=='repeat' and not live or eff=='keep' and live:fail('Down effect must agree with offending side and live/dead classification')
  if not 0<p['base_spot']<50:fail('Goal-line foul awards require an official scoring decision')
  penalty_distance(d,t,p['base_spot'],p['yards'])
  if d['clock_ms']<=120000 and not d['mercy_clock']:d['clock_running']=False
  if not is_try:
   if eff=='first' or not d['middle_gained'] and d['spot']>25:d['down']=1;d['middle_gained']=d['middle_gained'] or d['spot']>25
   elif eff=='loss':down_end(d)
   if live and eff!='loss' and d['half']<=2 and d['clock_ms']==0:d['extension']=True;d['phase']='ready'
  elif eff=='loss':
   if d['half']==3:end_ot_series(d)
   else:new_series(d,1-old)
  settle(d)
 elif k=='carry_penalty':d['carry'].append(dict(team=p['team'],yards=p['yards']))
 elif k=='close_period':
  if d['half']==1:
   d.update(half=2,clock_ms=1200000,timeouts=[0,0],notified=False,mercy_clock=False,clock_running=False,break_ms=120000);new_series(d,1-d['first_team']);apply_carry(d);d['phase']='interval'
  elif d['score'][0]!=d['score'][1]:finish(d,int(d['score'][1]>d['score'][0]),'regulation')
  elif d['allow_draw']:finish(d,None,'draw')
  else:d.update(phase='interval',break_ms=120000,interval_overtime=True,clock_running=False)
 elif k=='choose_overtime':
  d.update(half=3,ot_first=p['first'],ot_round=1,ot_series=0);new_series(d,p['first'],25);d['middle_gained']=True;apply_carry(d)
 elif k=='timeout':
  t=p['team']
  if d['timeouts'][t]>=2:fail('No charged timeout remains in this half')
  d['timeouts'][t]+=1;d.update(resume_phase=d['phase'],phase='timeout',break_ms=60000,clock_running=False)
 elif k=='elapse_break':
  if p['milliseconds']>d['break_ms']:fail('Elapsed time exceeds the current break')
  d['break_ms']-=p['milliseconds']
  if d['break_ms']==0:
   d['phase']=d['resume_phase'] if d['phase']=='timeout' else 'ot_toss' if d['interval_overtime'] else 'ready'
   if d['phase']=='ready':apply_carry(d)
 elif k=='set_lineup':
  t=p['team'];line=p['players']
  if len(line)!=len(set(line)) or any(d['status'][t][i]=='excluded' or d['sit_out'][t][i] for i in line):fail('Lineup needs distinct eligible players')
  for i in range(15):
   if d['status'][t][i]!='excluded':d['status'][t][i]='active' if i in line else 'bench'
 elif k=='sanction':
  t=p['team'];i=p['player']
  if d['status'][t][i]=='excluded':fail('Player is already excluded')
  if p['kind']=='unsporting':d['unsporting'][t][i]+=1
  if p['kind']=='flagrant' or d['unsporting'][t][i]==2:d['status'][t][i]='excluded'
 elif k=='miss_next_down':
  t=p['team'];i=p['player']
  if d['status'][t][i]!='active':fail('Removal requires an active player')
  d['status'][t][i]='bench';d['sit_out'][t][i]=True;d['clock_running']=False
 elif k=='official_clock':
  if p['running'] and (d['half']==3 or not d['clock_ms'] or d['phase'] not in ('ready','try_choice','try_ready')):fail('Clock cannot run in this phase')
  d['clock_running']=p['running']
 elif k=='concede':finish(d,1-p['team'],'concession')
 elif k=='abandon':d.update(phase='abandoned',clock_running=False,break_ms=0)
 elif k=='official_result':finish(d,p['winner'],'no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data'];s=schemas(d)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Phase, down, official clock and eligible lineup must permit the event.'],external_observations=['Completed downs, official spots, penalty classifications, timing and sanctions.']) for k,v in s.items()],constraints=dict(phase=d['phase'],score=d['score'],half=d['half'],clock_ms=d['clock_ms'],offense=d['offense'],spot=d['spot'],down=d['down'],middle_gained=d['middle_gained'],try_value=d['try_value'],ot_round=d['ot_round'],ot_series=d['ot_series'],extension=d['extension']),completeness=False,reason='official_flag_football_downs')
def outcome(state,pack):
 o=base_outcome(state,pack)
 if state['data']['reason']=='draw':o['result_kind']='draw'
 return o
