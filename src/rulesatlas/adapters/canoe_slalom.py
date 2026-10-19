"""One-run canoe slalom final with twenty ordered gate judgments."""
from copy import deepcopy
from .race import Race,INDEX,TIME
from ..values import fields,fail
CONFIG=dict(recall=False,conduct_warnings=False,time_quantum_us=10000,false_start_disqualifies=False,controls=[f'gate_{i+1}' for i in range(20)])
BASE=Race(CONFIG)
GATE=dict(type='integer',minimum=0,maximum=19)
VERDICT=dict(passed_correctly=dict(type='boolean'),touched=dict(type='boolean'))
def penalty(g):return 50000000 if not g['passed_correctly'] else 2000000 if g['touched'] else 0
def validate(d):
 BASE.validate(d)
 if d['upstream'] and (len(d['upstream'])!=20 or sum(d['upstream'])!=6):fail('The declared twenty-gate course requires exactly six upstream gates',code='INVALID_STATE')
 if (d['phase']=='racing' or any(r['gates'] or r['status']=='finished' for r in d['runners'])) and not d['upstream']:fail('Configure the course before starting the final',code='INVALID_STATE')
 for r in d['runners']:
  if len(r['gates'])!=r['checkpoints_completed']:fail('Gate judgments must match the completed checkpoint prefix',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type']
 if k=='configure_course':
  fields(p,dict(upstream=dict(type='array',minItems=20,maxItems=20,items=dict(type='boolean'))),'/params')
  if d['phase']!='ready' or sum(p['upstream'])!=6:fail('Configure exactly six upstream gates before starting')
  d['upstream']=p['upstream'][:];return d
 if k=='start' and not d['upstream']:fail('Configure the course before starting')
 if k=='visit_control':fail('Record a gate judgment instead of an unclassified checkpoint visit')
 if k in ('record_gate','correct_gate'):
  schema=dict(participant=INDEX,gate=GATE,**VERDICT)
  if k=='record_gate':schema['time_us']=dict(TIME,nullable=False)
  fields(p,schema,'/params');r=d['runners'][p['participant']];g=p['gate'];verdict={key:p[key] for key in VERDICT}
  if k=='record_gate':
   if d['phase']!='racing' or r['status']!='running' or g!=len(r['gates']):fail('Judge each gate exactly once in course order for an active paddler')
   d=BASE.apply(state,dict(type='visit_control',params=dict(participant=p['participant'],control=f'gate_{g+1}',time_us=p['time_us'])));d['runners'][p['participant']]['gates'].append(verdict)
  else:
   if d['phase']!='review' or g>=len(r['gates']):fail('Correct an existing gate judgment only during official review')
   r['gates'][g]=verdict
  return d
 return BASE.apply(state,action)
def legal(state):
 d=state['data'];result=BASE.legal(state);result['action_types']=[a for a in result['action_types'] if a['type']!='visit_control' and not (a['type']=='start' and not d['upstream'])]
 specs={}
 if d['phase']=='ready':specs['configure_course']=dict(upstream=dict(type='array',minItems=20,maxItems=20,items=dict(type='boolean')))
 if d['phase']=='racing':specs['record_gate']=dict(participant=INDEX,gate=GATE,**VERDICT,time_us=dict(TIME,nullable=False))
 if d['phase']=='review':specs['correct_gate']=dict(participant=INDEX,gate=GATE,**VERDICT)
 for k,s in specs.items():result['action_types'].append(dict(type=k,params_schema=s,preconditions=['Course configuration, gate order and review phase must permit the decision.'],external_observations=['Official gate passage in the prescribed direction and pole contact; multiple contacts still give only two seconds.']))
 result['constraints']['upstream']=d['upstream'];return result
def outcome(state,pack):
 adjusted=deepcopy(state)
 for r in adjusted['data']['runners']:
  if r['status']=='finished':r['time_us']+=sum(penalty(g) for g in r['gates'])
 result=BASE.outcome(adjusted,pack)
 for entry in result['placements']:
  i=next(i for i,p in enumerate(state['players']) if p['id']==entry['player_id']);r=state['data']['runners'][i]
  entry['elapsed_us']=r['time_us'];entry['penalty_us']=sum(penalty(g) for g in r['gates'])
 return result
