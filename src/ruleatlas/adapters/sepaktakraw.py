"""ISTAF 2016 single-regu match, official rally and eligibility events."""
from copy import deepcopy
from ..values import fields,fail
from .pelota import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
T=I(0,1);P=I(0,4);NP=dict(P,nullable=True)
def wins(d):return [sum(s['winner']==t for s in d['sets']) for t in (0,1)]
def complete(s):return max(s)>=21 and (abs(s[0]-s[1])>=2 or max(s)==25)
def server(d):
 n=sum(d['points'])
 return (d['starter']+(n//3 if n<40 else 13+n-40))%2 if d['starter'] is not None else None
def eligible(d,t):return [i for i in range(5) if not d['red'][t][i] and d['available'][t][i]]
def ready(d):return all(None not in d['lineup'][t] and all(i in eligible(d,t) for i in d['lineup'][t]) for t in (0,1))
def finish_set(d,w,reason):
 d['sets'].append(dict(score=d['points'][:],winner=w,reason=reason));d.update(phase='interval',break_ms=120000)
 if wins(d)[w]==2:d.update(phase='finished',winner=w,reason='two_sets',break_ms=0)
def point(d,w):
 d['points'][w]+=1;d['phase']='ready'
 if complete(d['points']):finish_set(d,w,'points')
 elif len(d['sets'])==2 and not d['changed_ends'] and max(d['points'])==11:d['phase']='change_ends'
def replace(d,t,slot,i):
 if d['substitutions'][t]>=2 or i not in eligible(d,t) or i in d['lineup'][t]:fail('Replacement needs an eligible reserve and an unused set substitution')
 d['lineup'][t][slot]=i;d['substitutions'][t]+=1

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  ids=[i for i in d['lineup'][t] if i is not None]
  if len(ids)!=len(set(ids)) or any(i not in eligible(d,t) for i in ids):bad('Lineup must contain distinct eligible players')
  if any(d['yellow'][t][i]==2 and not d['red'][t][i] for i in range(5)):bad('Second match caution requires exclusion')
 for j,s in enumerate(d['sets']):
  if any(sum(x['winner']==t for x in d['sets'][:j])>=2 for t in (0,1)):bad('No set follows the second set victory')
  if s['reason']=='points':
   hi=max(s['score']);lo=min(s['score'])
   if not(hi==21 and lo<=19 or 22<=hi<=24 and lo==hi-2 or hi==25 and lo in (23,24)) or s['score'][s['winner']]!=hi:bad('Completed set must stop at its first winning score')
  elif complete(s['score']):bad('Forfeited set cannot already be decided by points')
 if d['phase']=='choose_service' and (d['starter'] is not None or d['sets'] or any(d['points'])):bad('Initial service choice precedes all play')
 if d['phase'] not in ('choose_service','abandoned','finished') and d['starter'] is None:bad('Started match needs initial set service entitlement')
 if d['phase'] in ('ready','rally','stopped','timeout','change_ends') and (complete(d['points']) or max(wins(d))==2):bad('Active set cannot already be decided')
 if len(d['sets'])==2 and d['phase'] in ('ready','rally','timeout') and max(d['points'])>=11 and not d['changed_ends']:bad('Complete the deciding-set end change before continuing')
 if d['phase']=='rally' and not ready(d):bad('Rally requires three eligible players per team')
 if d['phase']=='interval' and (not d['sets'] or d['points']!=d['sets'][-1]['score'] or max(wins(d))==2):bad('Interval follows a completed nonfinal set')
 if d['phase']=='change_ends' and (len(d['sets'])!=2 or max(d['points'])!=11 or d['changed_ends']):bad('Third-set end change occurs at eleven points')
 if (d['phase'] in ('timeout','interval'))!=(d['break_ms']>0):bad('Break clock and phase disagree')
 if d['phase']=='timeout' and d['break_ms']>60000:bad('Timeout lasts at most one minute')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason']=='no_contest')!=(d['winner'] is None):bad('Finished match needs its declared result')
  if d['reason']=='two_sets' and (wins(d)[d['winner']]!=2 or d['points']!=d['sets'][-1]['score']):bad('Match winner must have two completed sets')
 elif d['winner'] is not None or d['reason'] is not None or max(wins(d))==2:bad('Ongoing match cannot declare a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 if ph=='choose_service':s['choose_service']=dict(team=T)
 if ph=='ready':s.update(serve=dict(team=T,player=P),timeout=dict(team=T),service_delay=dict(team=T))
 if ph=='rally':s.update(fault=dict(team=T),replay={},stop={})
 if ph=='stopped':s['resume']={}
 if ph in ('ready','stopped','timeout','choose_service'):
  s.update(substitute=dict(team=T,slot=I(0,2),incoming=P),assign_roles=dict(team=T,players=dict(type='array',minItems=3,maxItems=3,items=P)))
 if ph in ('timeout','interval'):s['elapse_break']=dict(milliseconds=I(1,120000))
 if ph=='change_ends':s['change_ends']={}
 if ph in ('ready','rally','stopped','timeout','change_ends'):
  s.update(sanction=dict(team=T,player=P,kind=dict(type='enum',values=['yellow','red'])),unavailable=dict(team=T,player=P))
 if ph in ('interval','choose_service','ready','stopped'):s['restore_availability']=dict(team=T,player=P)
 s.update(abandon={},concede=dict(team=T))
 return s

def remove_player(d,t,i,red=False):
 if red:d['red'][t][i]=True
 else:d['available'][t][i]=False
 if i in d['lineup'][t]:
  slot=d['lineup'][t].index(i);d['lineup'][t][slot]=None
  reserves=[j for j in eligible(d,t) if j not in d['lineup'][t]]
  if d['substitutions'][t]>=2 or not reserves:finish_set(d,1-t,'insufficient_players')
  else:d.update(phase='stopped',break_ms=0)
 elif d['phase']=='rally':d['phase']='stopped'

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];ss=schemas(d)
 if k not in ss:fail('Action is not permitted in this phase')
 fields(p,ss[k],'/params');t=p.get('team')
 if k=='choose_service':
  if not ready(d):fail('Three eligible players per team are required')
  d.update(starter=t,phase='ready')
 elif k=='serve':
  if t!=server(d) or p['player']!=d['lineup'][t][0] or not ready(d):fail('Entitled Tekong and complete eligible lineups are required')
  d['phase']='rally'
 elif k=='fault':point(d,1-t)
 elif k=='replay':d['phase']='ready'
 elif k=='stop':d['phase']='stopped'
 elif k=='resume':
  if not ready(d):fail('Replace missing players before resuming')
  d['phase']='change_ends' if len(d['sets'])==2 and max(d['points'])==11 and not d['changed_ends'] else 'ready'
 elif k=='service_delay':
  if t!=server(d):fail('Service delay concerns the entitled serving regu')
  if d['delay_warned'][t]:point(d,1-t)
  else:d['delay_warned'][t]=True
 elif k=='substitute':replace(d,t,p['slot'],p['incoming'])
 elif k=='assign_roles':
  if sorted(p['players'])!=sorted(i for i in d['lineup'][t] if i is not None):fail('Role reassignment must preserve the three current players')
  d['lineup'][t]=p['players'][:]
 elif k=='timeout':
  if d['timeouts'][t]:fail('Only one timeout per team per set')
  d['timeouts'][t]=True;d.update(phase='timeout',break_ms=60000)
 elif k=='elapse_break':
  if p['milliseconds']>d['break_ms']:fail('Elapsed time exceeds the remaining break')
  d['break_ms']-=p['milliseconds']
  if d['break_ms']==0:
   if d['phase']=='interval':
    d.update(points=[0,0],starter=1-d['starter'],substitutions=[0,0],timeouts=[False,False],changed_ends=False)
   d['phase']='ready'
   short=[j for j in (0,1) if len(eligible(d,j))<3]
   if len(short)==2:d['phase']='abandoned'
   elif short:finish_set(d,1-short[0],'insufficient_players')
 elif k=='change_ends':d.update(phase='ready',changed_ends=True)
 elif k=='sanction':
  i=p['player']
  if d['red'][t][i]:fail('Player is already excluded')
  if p['kind']=='yellow':d['yellow'][t][i]+=1
  if p['kind']=='red' or d['yellow'][t][i]==2:remove_player(d,t,i,red=True)
  elif d['phase']=='rally':d['phase']='stopped'
 elif k=='unavailable':
  i=p['player']
  if d['red'][t][i] or not d['available'][t][i]:fail('Player is already unavailable')
  remove_player(d,t,i)
 elif k=='restore_availability':
  i=p['player']
  if d['red'][t][i] or d['available'][t][i]:fail('Only a non-excluded unavailable player can be restored')
  d['available'][t][i]=True
 elif k=='abandon':d.update(phase='abandoned',break_ms=0)
 elif k=='concede':d.update(phase='finished',winner=1-t,reason='concession',break_ms=0)
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_contest' if p['winner'] is None else 'official_result')
 return d

def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Service entitlement, phase, eligible lineup and remaining set allowances must permit the event.'],external_observations=['Official rally faults, delays, availability, sanctions and toss choice.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],points=d['points'],sets_won=wins(d),server=server(d),lineup=d['lineup'],substitutions=d['substitutions'],timeouts=d['timeouts'],break_ms=d['break_ms']),completeness=False,reason='official_2016_regu_events')
