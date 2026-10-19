"""Decathlon progression and exact integer-point classification from official marks."""
from copy import deepcopy
from math import floor
from ..values import fields,fail
EVENTS=['100m','long_jump','shot_put','high_jump','400m','110m_hurdles','discus','pole_vault','javelin','1500m']
COEFFICIENTS=[(25.4347,18,1.81),(0.14354,220,1.4),(51.39,1.5,1.05),(0.8465,75,1.42),(1.53775,82,1.81),(5.74352,28.5,1.92),(12.91,4,1.1),(0.2797,100,1.35),(10.14,7,1.08),(0.03768,480,1.85)]
TRACK=(0,4,5,9);THROWS=(2,6,8)
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
RESULT=dict(status=dict(type='string',enum=['ok','nm','dnf','dq','dns','absent']),mark=dict(I(1,60000),nullable=True))
SCHEMAS=dict(start_event={},submit_result=dict(player=I(0,7),**RESULT),amend_result=dict(player=I(0,7),**RESULT),withdraw=dict(player=I(0,7)),disqualify=dict(player=I(0,7)),confirm_event={})
def points(index,r):
 if r is None or r['status']!='ok':return 0
 a,b,c=COEFFICIENTS[index];m=r['mark']/100 if index in TRACK+THROWS else r['mark'];x=b-m if index in TRACK else m-b
 return floor(a*max(0,x)**c)
def eligible(d,i,current=True):return not d['withdrawn'][i] and not d['disqualified'][i] and all(row[i]['status'] not in ('dns','absent') for row in d['results']) and (not current or not d['current'] or d['current'][i] is None or d['current'][i]['status'] not in ('dns','absent'))
def totals(d):return [sum(points(j,row[i]) for j,row in enumerate(d['results']))+(points(d['event_index'],d['current'][i]) if d['current'] else 0) for i in range(8)]
def check_result(index,r,bad):
 if (r['status']=='ok')!=(r['mark'] is not None):bad('Only a valid performance carries a mark')
 if r['status']=='nm' and index in TRACK or r['status']=='dnf' and index not in TRACK:bad('No-mark and did-not-finish statuses must match the event type')
 if r['mark'] is not None and index not in TRACK and r['mark']>20000:bad('Field marks use centimetres within the declared input bound')
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');n=len(d['results']);phase=d['phase']
 for j,row in enumerate(d['results']):
  for r in row:check_result(j,r,bad)
 if phase=='finished':
  if d['current'] or n!=d['event_index']+1 or n<10 and any(eligible(d,i) for i in range(8)):bad('Final classification requires ten events or no remaining eligible athletes')
 else:
  if n!=d['event_index']:bad('Completed event count must match the next event index')
  if phase=='ready' and d['current'] or phase in ('event','review') and len(d['current'])!=8:bad('Current result slots must match the event phase')
 if d['current']:
  for r in d['current']:
   if r is not None:check_result(d['event_index'],r,bad)
  if (phase=='review')!=all(r is not None for r in d['current']):bad('Review begins when every event result is resolved')
 for i in range(8):
  absent=False
  for row in d['results']:
   if absent and row[i]['status']!='absent':bad('An athlete who failed to start cannot return in a subsequent event')
   if row[i]['status'] in ('dns','absent'):absent=True

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase']
 if k not in SCHEMAS:fail('Unknown decathlon event')
 fields(p,SCHEMAS[k],'/params')
 if phase=='finished':fail('Competition is finished')
 if k=='start_event':
  if phase!='ready':fail('Current event must be confirmed before another starts')
  d['current']=[None if eligible(d,i) else dict(status='absent',mark=None) for i in range(8)];d['phase']='event' if any(r is None for r in d['current']) else 'review'
 elif k in ('submit_result','amend_result'):
  i=p['player'];r=dict(status=p['status'],mark=p['mark'])
  if phase!=('event' if k=='submit_result' else 'review') or not eligible(d,i,current=False) or k=='submit_result' and d['current'][i] is not None or p['status']=='absent':fail('Submit an eligible athlete once, or amend the current event during review')
  check_result(d['event_index'],r,fail);d['current'][i]=r
  if all(x is not None for x in d['current']):d['phase']='review'
 elif k in ('withdraw','disqualify'):
  i=p['player'];field='withdrawn' if k=='withdraw' else 'disqualified'
  if d[field][i]:fail('Athlete already has this overall status')
  d[field][i]=True
  if d['current'] and d['current'][i] is None:d['current'][i]=dict(status='dns',mark=None)
  if d['current'] and all(x is not None for x in d['current']):d['phase']='review'
 elif k=='confirm_event':
  if phase!='review':fail('Resolve all current results before confirming the event')
  d['results'].append(d['current']);d['current']=[]
  if d['event_index']==9 or not any(eligible(d,i) for i in range(8)):d['phase']='finished'
  else:d['event_index']+=1;d['phase']='ready'
 return d

def legal(state):
 d=state['data'];phase=d['phase'];names=dict(ready=['start_event'],event=['submit_result'],review=['amend_result','confirm_event'],finished=[])[phase]
 if phase!='finished':names+=['withdraw','disqualify']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Event order, participation eligibility and result-review phase must permit the event.'],external_observations=['Official completed event marks or statuses; race and field-attempt judgments are supplied externally.']) for k in names],constraints=dict(phase=phase,event=EVENTS[d['event_index']],event_number=d['event_index']+1,mark_unit='centiseconds' if d['event_index'] in TRACK else 'centimetres',eligible=[i for i in range(8) if eligible(d,i)],totals=totals(d)),completeness=False,reason='official_decathlon_event_results')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';scores=totals(d);ids=[i for i in range(8) if eligible(d,i)];best=max((scores[i] for i in ids),default=None);w=[i for i in ids if scores[i]==best]
 return dict(status='terminal' if done else 'ongoing',result_kind=('no_contest' if not ids else 'draw' if len(w)>1 else 'win') if done else 'none',winners=[state['players'][i]['id'] for i in w] if done else [],losers=[state['players'][i]['id'] for i in ids if i not in w] if done else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(scores[j]>scores[i] for j in ids),points=scores[i]) for i in sorted(ids,key=lambda i:(-scores[i],i))] if done else [],reason='highest_total' if done and ids else 'no_classified_athletes' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
