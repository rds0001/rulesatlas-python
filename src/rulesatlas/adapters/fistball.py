"""2019 fistball, first to three sets, with point-counted player suspensions."""
from copy import deepcopy
from ..values import fields,fail
from .pelota import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
T=I(0,1);P=I(0,9)
def active(d,t):return [i for i,s in enumerate(d['status'][t]) if s=='active']
def capacity(d,t):return 5-sum(d['lost_place'][t])-sum(v>0 for v in d['suspensions'][t])
def complete(s):return max(s)>=11 and (abs(s[0]-s[1])>=2 or max(s)==15)
def wins(d):return [sum(s[t]>s[1-t] for s in d['sets']) for t in (0,1)]
def point(d,w):
 d['points'][w]+=1;d.update(server=1-w,phase='ready',has_rally=True)
 for t in (0,1):
  for i,n in enumerate(d['suspensions'][t]):
   if n:
    d['suspensions'][t][i]-=1
    if n==1:d['status'][t][i]='bench'
 if complete(d['points']):
  d['sets'].append(d['points'][:]);d['phase']='interval'
  if wins(d)[w]==3:d.update(phase='finished',winner=w,reason='three_sets')
 elif len(d['sets'])==4 and not d['decider_changed'] and max(d['points'])==6:d['phase']='change_ends'
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if len(active(d,t))>capacity(d,t):bad('Lineup exceeds available places after exclusions')
  for i,st in enumerate(d['status'][t]):
   if (st=='suspended')!=(d['suspensions'][t][i]>0):bad('Suspension status and remaining points must agree')
   if d['lost_place'][t][i] and st!='excluded':bad('Only excluded on-court players remove a permanent place')
  captain=d['captains'][t]
  if captain is not None and d['status'][t][captain] not in ('active','bench'):bad('Captain must remain eligible')
  if d['phase'] not in ('finished','abandoned') and capacity(d,t)<4:bad('Two simultaneous missing places require abandonment')
 for j,s in enumerate(d['sets']):
  hi=max(s);lo=min(s)
  if not(hi==11 and lo<=9 or 12<=hi<=14 and lo==hi-2 or hi==15 and lo in (13,14)):bad('Completed set must stop at its first winning score')
  if any(sum(x[t]>x[1-t] for x in d['sets'][:j])>=3 for t in (0,1)):bad('No set follows the third set victory')
 if d['phase']=='choose_server' and (d['server'] is not None or len(d['sets']) not in (0,4) or any(d['points'])):bad('Toss is available only before first or deciding set')
 if d['phase']=='interval' and (not d['sets'] or d['points']!=d['sets'][-1] or max(wins(d))==3):bad('Interval follows a completed nonfinal set')
 if d['phase'] in ('ready','rally','stopped','timeout','change_ends'):
  if d['server'] is None or complete(d['points']):bad('Active set requires a server and unfinished score')
  if any(len(active(d,t))<4 for t in (0,1)):bad('Play requires at least four active players')
 if d['phase']=='rally' and any(c is None for c in d['captains']):bad('Each team needs an appointed captain')
 if d['phase']=='change_ends' and (len(d['sets'])!=4 or max(d['points'])!=6 or d['decider_changed']):bad('Deciding-set end change occurs at the first six points')
 if (d['phase']=='timeout')!=(d['timeout_ms']>0):bad('Timeout clock must agree with phase')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason']=='no_contest')!=(d['winner'] is None):bad('Result must identify a winner or no contest')
  if d['reason']=='three_sets' and (wins(d)[d['winner']]!=3 or d['points']!=d['sets'][-1]):bad('Normal victory requires three completed sets')
 elif d['winner'] is not None or d['reason'] is not None or max(wins(d))==3:bad('An ongoing match cannot have a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 if ph=='choose_server':s['choose_server']=dict(team=T)
 if ph=='ready':s.update(serve=dict(team=T,player=P),timeout=dict(team=T))
 if ph=='rally':s.update(fault=dict(team=T),replay={})
 if ph in ('ready','rally'):s['stop']={}
 if ph=='stopped':s['resume']={}
 if ph=='timeout':s['elapse_timeout']=dict(milliseconds=I(1,30000))
 if ph=='interval':s['next_set']={}
 if ph=='change_ends':s['change_ends']={}
 if ph!='rally':s.update(substitute=dict(team=T,out=P,**{'in':P}),enter=dict(team=T,player=P),appoint_captain=dict(team=T,player=P))
 s['sanction']=dict(team=T,player=P,kind=dict(type='enum',values=['caution','suspension','expulsion']))
 if ph in ('ready','rally','stopped'):s.update(delay=dict(team=T),substitution_fault=dict(team=T))
 s.update(concede=dict(team=T),abandon={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params');t=p.get('team')
 if k=='choose_server':
  d.update(server=t,set_starter=t,phase='ready')
 elif k=='serve':
  if t!=d['server'] or p['player'] not in active(d,t) or any(c is None for c in d['captains']):fail('Service requires an active entitled player and appointed captains')
  d['phase']='rally'
 elif k=='fault':point(d,1-t)
 elif k=='replay':d.update(phase='ready',has_rally=True)
 elif k=='stop':d['phase']='stopped'
 elif k=='resume':d['phase']='ready'
 elif k=='timeout':
  if not d['has_rally'] or d['timeouts'][t]:fail('One timeout per team and set is available after a rally')
  d['timeouts'][t]=True;d.update(phase='timeout',timeout_ms=30000)
 elif k=='elapse_timeout':
  if p['milliseconds']>d['timeout_ms']:fail('Elapsed time exceeds the timeout')
  d['timeout_ms']-=p['milliseconds']
  if not d['timeout_ms']:d['phase']='ready'
 elif k=='next_set':
  deciding=len(d['sets'])==4;d.update(points=[0,0],server=None if deciding else 1-d['set_starter'],set_starter=None if deciding else 1-d['set_starter'],phase='choose_server' if deciding else 'ready',timeouts=[False,False],has_rally=False,decider_changed=False)
 elif k=='change_ends':d.update(server=1-d['server'],decider_changed=True,phase='ready')
 elif k=='substitute':
  if p['out'] not in active(d,t) or d['status'][t][p['in']]!='bench':fail('Substitution requires an active outgoing and eligible incoming player')
  d['status'][t][p['out']]='bench';d['status'][t][p['in']]='active'
 elif k=='enter':
  if d['status'][t][p['player']]!='bench' or len(active(d,t))>=capacity(d,t):fail('No eligible completion place is available')
  d['status'][t][p['player']]='active'
 elif k=='appoint_captain':
  if d['status'][t][p['player']] not in ('active','bench'):fail('Captain must be eligible')
  d['captains'][t]=p['player']
 elif k=='sanction':
  i=p['player'];kind=p['kind'];st=d['status'][t][i]
  if st=='excluded':fail('Excluded player cannot receive another match sanction')
  if kind=='caution':
   if d['cautions'][t][i]:fail('A player cannot receive a duplicate caution')
   d['cautions'][t][i]=True
  elif kind=='suspension':
   if st!='active':fail('Point-counted suspension requires an on-court player')
   d['status'][t][i]='suspended';d['suspensions'][t][i]=10
  else:
   d['lost_place'][t][i]=st in ('active','suspended');d['status'][t][i]='excluded';d['suspensions'][t][i]=0
  if kind!='caution' and d['captains'][t]==i:d['captains'][t]=None
  if capacity(d,t)<4 or len(active(d,t))<4:d.update(phase='abandoned',timeout_ms=0)
  elif d['phase']=='rally':d['phase']='stopped'
 elif k in ('delay','substitution_fault'):
  if k=='delay' and not d['delay_warned'][t]:d['delay_warned'][t]=True
  else:point(d,1-t)
 elif k=='concede':d.update(phase='finished',winner=1-t,reason='concession',timeout_ms=0)
 elif k=='abandon':d.update(phase='abandoned',timeout_ms=0)
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Set, service, timeout and player eligibility must permit the event.'],external_observations=['Official rally faults, sanctions, referee stoppages and toss results.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],server=d['server'],points=d['points'],sets_won=wins(d),active=[active(d,t) for t in (0,1)],capacity=[capacity(d,t) for t in (0,1)],captains=d['captains'],suspensions=d['suspensions'],timeout_ms=d['timeout_ms']),completeness=False,reason='official_2019_fistball_events')
