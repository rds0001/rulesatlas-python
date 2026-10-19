"""Singles real tennis with ordered chases and externally judged rests."""
from copy import deepcopy
from ..values import fields, fail
from .pelota import outcome
P=dict(type='integer',minimum=0,maximum=1)
K=dict(type='enum',values=['service','hazard'])
MARK=dict(type='string',minLength=1,maxLength=100)
def wins(d):return [sum(s[t]==6 for s in d['sets']) for t in (0,1)]
def change_due(d):return not d['playing_chases'] and bool(d['chases']) and (len(d['chases'])==2 or max(d['points'])>=3)
def settle(d):
 d['fault']=False;d['phase']='ready'
 if not d['chases']:d['playing_chases']=False
 if change_due(d):d['phase']='change_ends'
def point(d,t):
 d['points'][t]+=1
 if d['points'][t]>=4 and d['points'][t]-d['points'][1-t]>=2:
  d['points']=[0,0];d['games'][t]+=1;d['chases']=[];d['playing_chases']=False
  if d['games'][t]==6:
   d['sets'].append(d['games'][:]);d['games']=[0,0]
   if wins(d)[t]==2:
    d.update(phase='finished',winner=t,reason='two_sets',fault=False);return
 elif min(d['points'])>=3:
  m=min(d['points'])-3;d['points']=[v-m for v in d['points']]
 settle(d)
def consume(d):
 if d['playing_chases']:d['chases'].pop(0)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if max(d['points'])==4 and min(d['points'])!=3:bad('Advantage requires forty for the opponent')
 for j,s in enumerate(d['sets']):
  if max(s)!=6 or min(s)>=6:bad('A completed set ends at six games')
  if any(sum(x[t]==6 for x in d['sets'][:j])==2 for t in (0,1)):bad('No set follows match victory')
 if d['phase']=='choose_server':
  if d['server'] is not None or any(d['points']+d['games']) or d['sets'] or d['chases'] or d['fault']:bad('Initial service choice precedes all play')
 elif d['phase'] not in ('finished','abandoned') and d['server'] is None:bad('Play requires a service-side player')
 if d['playing_chases'] and not d['chases']:bad('Playing chases requires a pending chase')
 for c in d['chases']:
  if not c['mark'].strip():bad('Chase marker cannot be blank')
 if d['phase'] not in ('finished','abandoned'):
  if (d['phase']=='change_ends')!=change_due(d):bad('Required change of ends must occur before service')
  if max(wins(d))==2:bad('Two sets end the match')
 if d['phase'] in ('choose_server','change_ends','finished','abandoned') and d['fault']:bad('Fault only persists during the current rest')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason']=='no_contest')!=(d['winner'] is None):bad('Result must identify a winner or no contest')
  if d['reason']=='two_sets' and (wins(d)[d['winner']]!=2 or any(d['games']+d['points'])):bad('Normal victory requires two sets')
 elif d['winner'] is not None or d['reason'] is not None:bad('Only a finished match has a result')
def schemas(d):
 phase=d['phase'];s={}
 if phase=='finished':return s
 if phase=='abandoned':return dict(official_result=dict(winner=dict(P,nullable=True)))
 if phase=='choose_server':s['choose_server']=dict(player=P)
 if phase=='change_ends':s['change_ends']={}
 if phase=='ready':
  s['start_serve']=dict(player=P)
  if d['chases']:s['correct_chase']=dict(index=dict(type='integer',minimum=0,maximum=len(d['chases'])-1),kind=K,mark=MARK)
 if phase=='serve':s['service_decision']=dict(result=dict(type='enum',values=['good','fault','let']))
 if phase=='rally':
  s.update(award_rest=dict(winner=P),let={})
  if d['playing_chases']:s['chase_result']=dict(result=dict(type='enum',values=['better','worse','equal','opposite_end']))
  else:s['set_chase']=dict(kind=K,mark=MARK)
 s.update(concede=dict(player=P),disqualify=dict(player=P),abandon={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='choose_server':d.update(server=p['player'],phase='ready')
 elif k=='change_ends':d.update(server=1-d['server'],playing_chases=True,phase='ready')
 elif k=='correct_chase':
  if not p['mark'].strip():fail('Chase marker cannot be blank')
  d['chases'][p['index']]=dict(kind=p['kind'],mark=p['mark'])
 elif k=='start_serve':
  if p['player']!=d['server']:fail('Only the service-side player may serve')
  d['phase']='serve'
 elif k=='service_decision':
  if p['result']=='good':d['phase']='rally'
  elif p['result']=='let':d['phase']='ready'
  elif d['fault']:consume(d);point(d,1-d['server'])
  else:d.update(fault=True,phase='ready')
 elif k=='let':d['phase']='ready'
 elif k=='set_chase':
  if not p['mark'].strip():fail('Chase marker cannot be blank')
  d['chases'].append(dict(kind=p['kind'],mark=p['mark']));settle(d)
 elif k=='chase_result':
  attacker=d['server'] if d['chases'][0]['kind']=='hazard' else 1-d['server'];consume(d)
  if p['result']=='equal':settle(d)
  else:point(d,attacker if p['result']=='better' else 1-attacker)
 elif k=='award_rest':consume(d);point(d,p['winner'])
 elif k in ('concede','disqualify'):d.update(phase='finished',winner=1-p['player'],reason='concession' if k=='concede' else 'disqualification',fault=False)
 elif k=='abandon':d.update(phase='abandoned',fault=False)
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data'];attacker=None
 if d['playing_chases']:attacker=d['server'] if d['chases'][0]['kind']=='hazard' else 1-d['server']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Phase, service side and ordered chase rights must permit the event.'],external_observations=['Official service decisions, chase marks, chase comparisons and rest winners.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],server=d['server'],service_attempt=2 if d['fault'] else 1,chases=d['chases'],playing_chases=d['playing_chases'],attacker=attacker,points=d['points'],games=d['games'],sets_won=wins(d)),completeness=False,reason='official_real_tennis_events')
