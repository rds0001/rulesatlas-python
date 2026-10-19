"""IKF 2.1.0 men's league match, completed-raid rule protocol."""
from copy import deepcopy
from ..values import fields,fail
from .handball import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
T=I(0,1);P=I(0,11);B=dict(type='boolean')
def active(d,t):return [i for i in d['slots'][t] if d['status'][t][i]=='active']
def presence(d,t):return sum(d['status'][t][i]!='out' for i in d['slots'][t])
def revive(d,t,n):
 for _ in range(min(n,len(d['out_queue'][t]))):
  i=d['out_queue'][t].pop(0);d['status'][t][i]='suspended' if d['suspension_ms'][t][i] else 'active'
def put_out(d,t,i):
 if d['status'][t][i]!='active':fail('Only an active player can be declared out')
 d['status'][t][i]='out';d['out_queue'][t].append(i)
def tick(d,ms):
 d['clock_ms']=max(0,d['clock_ms']-ms)
 for t in (0,1):
  for i in range(12):
   if d['status'][t][i]=='suspended':
    d['suspension_ms'][t][i]=max(0,d['suspension_ms'][t][i]-ms)
    if not d['suspension_ms'][t][i]:d['status'][t][i]='active' if i in d['slots'][t] else 'bench'
def all_out(d,t):
 d['score'][1-t]+=2;revive(d,t,len(d['out_queue'][t]));d.update(phase='reentry',reentry_team=t,reentry_ms=0)
def check_all_out(d):
 for t in (0,1):
  if not active(d,t) and not any(d['status'][t][i]=='suspended' for i in d['slots'][t]) and d['out_queue'][t]:all_out(d,t);return
 if any(all(d['status'][t][i]=='excluded' for i in d['slots'][t]) for t in (0,1)):d['phase']='abandoned'
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if len(set(d['slots'][t]))!=7:bad('Each team must retain seven distinct playing places')
  q=d['out_queue'][t]
  if len(set(q))!=len(q) or set(q)!={i for i in range(12) if d['status'][t][i]=='out'}:bad('Out queue must contain every out player exactly once')
  for i,s in enumerate(d['status'][t]):
   if s in ('active','out') and i not in d['slots'][t] or s in ('bench','retired') and i in d['slots'][t]:bad('Playing places and player status disagree')
   if s=='suspended' and not d['suspension_ms'][t][i] or d['suspension_ms'][t][i] and s not in ('suspended','out'):bad('Suspension clock must belong to a suspended or pending-revival player')
   if s=='out' and d['suspension_ms'][t][i] not in (0,120000):bad('Out-player suspension starts only at revival')
   if d['yellow'][t][i]==2 and s!='excluded':bad('Second yellow excludes the player for the rest of the match')
 if d['phase']=='pre' and (d['first_raider'] is not None or d['half']!=1 or d['clock_ms']!=1200000 or any(d['score']) or any(d['out_queue'])):bad('Pre-match state precedes toss and play')
 if d['phase'] not in ('pre','abandoned','finished') and (d['first_raider'] is None or d['next_team'] is None):bad('Started match requires raid entitlement')
 if d['phase']=='interval' and (d['half']!=1 or d['clock_ms']!=0):bad('Halftime follows completed first-half play')
 if (d['phase'] in ('interval','timeout'))!=(d['break_ms']>0):bad('Break duration and phase disagree')
 if (d['phase']=='reentry')!=(d['reentry_team'] is not None):bad('All-out reentry phase needs the returning team')
 if d['phase']=='finished':
  if d['reason']=='regulation':
   w=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0])
   if d['half']!=2 or d['clock_ms'] or d['winner']!=w:bad('Regulation result must match completed time and score')
  elif d['reason']=='concession':
   if d['winner'] is None:bad('Concession requires a winner')
  elif d['reason'] not in ('official_result','no_contest'):bad('Finished match requires a result reason')
 elif d['winner'] is not None or d['reason'] is not None:bad('Ongoing match cannot declare a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 if ph=='pre':s['start_match']=dict(first_team=T)
 if ph=='ready':
  if d['clock_ms']:
   f=dict(player=P,reason=dict(type='enum',values=['touch','self_out','foul']))
   s['raid']=dict(team=T,raider=P,duration_ms=I(1,30000),result=dict(type='enum',values=['returned','caught','self_out','cant','timeout']),baulk_valid=B,bonus=B,defenders_out=dict(type='array',minItems=0,maxItems=7,items=dict(type='object',properties=f,required=list(f))),technical_points=dict(type='array',minItems=2,maxItems=2,items=I(0,7)))
   s.update(elapse=dict(milliseconds=I(1,1200000)),timeout=dict(team=T),official_stop={})
  else:s['close_half']={}
  s['declare_remaining_out']=dict(team=T)
 if ph in ('ready','stopped'):
  pair=dict(outgoing=P,incoming=P)
  s.update(substitute=dict(team=T,pairs=dict(type='array',minItems=1,maxItems=7,items=dict(type='object',properties=pair,required=list(pair))),exception_authorized=B),sanction=dict(team=T,player=P,kind=dict(type='enum',values=['green','yellow','red'])),technical_point=dict(team=T))
 if ph=='stopped':s['resume']={}
 if ph in ('interval','timeout'):s['elapse_break']=dict(milliseconds=I(1,300000))
 if ph=='reentry':s.update(confirm_reentry={},elapse_reentry=dict(milliseconds=I(1,60000)))
 s.update(abandon={},concede=dict(team=T))
 return s

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];ss=schemas(d)
 if k not in ss:fail('Action is not permitted in this phase')
 fields(p,ss[k],'/params');t=p.get('team')
 if k=='start_match':
  if any(len(active(d,j))!=7 for j in (0,1)):fail('Both teams require seven active starters')
  d.update(phase='ready',first_raider=p['first_team'],next_team=p['first_team'])
 elif k=='raid':
  i=p['raider'];other=1-t;outs=p['defenders_out'];ids=[r['player'] for r in outs]
  if t!=d['next_team'] or i not in active(d,t) or not active(d,other):fail('Raid requires the entitled active raider and an active opposing team')
  tick(d,p['duration_ms'])
  if len(ids)!=len(set(ids)) or any(j not in active(d,other) for j in ids):fail('Out defenders must be distinct active opponents')
  if p['bonus'] and presence(d,other)<6:fail('Bonus requires at least six defenders including disciplinary absences')
  if p['bonus'] and not p['baulk_valid']:fail('A qualifying bonus crossing also crosses the baulk line')
  raider_out=p['result']!='returned'
  if raider_out and any(r['reason']=='touch' for r in outs):fail('Touched defenders are out only when the raider returns safely')
  if not p['baulk_valid'] and not any(r['reason']=='touch' for r in outs):raider_out=True
  if p['result']=='timeout' and p['duration_ms']!=30000:fail('Raid time expiry requires thirty seconds')
  productive=bool(ids or p['bonus'] or any(p['technical_points']) or raider_out)
  if not productive and d['empty_raids'][t]==2:raider_out=True;productive=True
  count_at_catch=presence(d,other)-len(ids)
  for j in ids:put_out(d,other,j)
  if raider_out:put_out(d,t,i)
  d['score'][t]+=len(ids)+int(p['bonus'])+p['technical_points'][t]
  d['score'][other]+=(2 if count_at_catch<=3 else 1) if raider_out else 0
  d['score'][other]+=p['technical_points'][other]
  revive(d,t,len(ids));revive(d,other,int(raider_out))
  d['empty_raids'][t]=0 if productive else d['empty_raids'][t]+1
  d['next_team']=other;check_all_out(d)
 elif k=='elapse':
  if p['milliseconds']>d['clock_ms']:fail('Between-raid clock cannot cross the half boundary')
  tick(d,p['milliseconds'])
 elif k=='declare_remaining_out':
  ids=active(d,t)
  if not 1<=len(ids)<=2 or any(d['status'][t][i]=='suspended' for i in d['slots'][t]):fail('Voluntary all-out requires one or two remaining active players and no suspended playing place')
  for i in ids:put_out(d,t,i)
  d['score'][1-t]+=len(ids);revive(d,1-t,len(ids));all_out(d,t)
 elif k=='substitute':
  pairs=p['pairs'];old=[r['outgoing'] for r in pairs];new=[r['incoming'] for r in pairs]
  if len(set(old))!=len(old) or len(set(new))!=len(new) or any(i not in active(d,t) for i in old) or any(d['status'][t][i]!='bench' for i in new):fail('Substitution batch requires distinct active outgoing and eligible reserve players')
  if d['substitutions'][t]>=5 and not p['exception_authorized']:fail('Five substitution occasions have been exhausted')
  if p['exception_authorized'] and d['substitutions'][t]<5:fail('Exceptional replacement is used only after the ordinary allowance is exhausted')
  for a,b in zip(old,new):
   d['slots'][t][d['slots'][t].index(a)]=b;d['status'][t][a]='retired' if p['exception_authorized'] else 'bench';d['status'][t][b]='active'
  if not p['exception_authorized']:d['substitutions'][t]+=1
 elif k=='sanction':
  i=p['player'];kind=p['kind'];status=d['status'][t][i]
  if status in ('excluded','retired'):fail('Player is no longer eligible for a new match sanction')
  if kind=='green' and (d['green'][t][i] or d['yellow'][t][i]):kind='yellow'
  if kind=='green':d['green'][t][i]=True
  else:
   if kind=='yellow':d['yellow'][t][i]+=1;d['score'][1-t]+=1
   if kind=='red' or d['yellow'][t][i]==2:
    d['status'][t][i]='excluded';d['suspension_ms'][t][i]=0
    if i in d['out_queue'][t]:d['out_queue'][t].remove(i)
   else:
    d['suspension_ms'][t][i]=120000
    if status!='out':d['status'][t][i]='suspended'
   check_all_out(d)
 elif k=='technical_point':d['score'][t]+=1
 elif k=='official_stop':d['phase']='stopped'
 elif k=='resume':d['phase']='ready'
 elif k=='timeout':
  if d['timeouts'][t]>=2:fail('Two team timeouts per half are available')
  d['timeouts'][t]+=1;d.update(phase='timeout',break_ms=30000)
 elif k=='elapse_break':
  if p['milliseconds']>d['break_ms']:fail('Elapsed time exceeds the remaining break')
  d['break_ms']-=p['milliseconds']
  if d['break_ms']==0:
   if d['phase']=='interval':d.update(half=2,clock_ms=1200000,next_team=1-d['first_raider'],empty_raids=[0,0],timeouts=[0,0])
   d['phase']='ready'
 elif k=='close_half':
  if d['half']==1:d.update(phase='interval',break_ms=300000)
  else:d.update(phase='finished',winner=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0]),reason='regulation')
 elif k=='confirm_reentry':d.update(phase='ready',reentry_team=None,reentry_ms=0)
 elif k=='elapse_reentry':
  ms=p['milliseconds']
  if d['reentry_ms']+ms>60000:fail('All-out return clock cannot exceed one minute')
  before=d['reentry_ms'];d['reentry_ms']+=ms;other=1-d['reentry_team']
  d['score'][other]+=d['reentry_ms']//15000-before//15000;tick(d,ms)
  if d['reentry_ms']==60000:d.update(phase='finished',winner=other,reason='concession',reentry_team=None)
 elif k=='abandon':d.update(phase='abandoned',break_ms=0,reentry_team=None)
 elif k=='concede':d.update(phase='finished',winner=1-t,reason='concession',break_ms=0,reentry_team=None)
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_contest' if p['winner'] is None else 'official_result')
 return d

def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Raid entitlement, eligibility, revival order, playing time and remaining allowances must permit the event.'],external_observations=['Completed raid result, ordered defender outs, bonus crossing, technical points and disciplinary decisions.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],half=d['half'],clock_ms=d['clock_ms'],score=d['score'],next_team=d['next_team'],active=[active(d,t) for t in (0,1)],out_queue=d['out_queue'],empty_raids=d['empty_raids'],suspension_ms=d['suspension_ms'],substitutions=d['substitutions'],timeouts=d['timeouts']),completeness=False,reason='official_completed_kabaddi_raids')
