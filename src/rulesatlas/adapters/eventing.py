"""Three-phase eventing from finalized component score sheets, using integer tenths."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
P=I(0,7)
DRESS=dict(percentage_bp=dict(I(0,10000),nullable=True),collective_half_points=I(0,10000),errors=I(0,3))
XC=dict(completed=I(0,40),refusals=dict(type='array',minItems=1,maxItems=40,items=I(0,3)),frangibles=I(0,40),missed_flags=I(0,40),dangerous_riding=I(0,2),time_ms=I(1,7200001))
JUMP=dict(completed=I(0,20),knockdowns=I(0,20),refusals=I(0,2),time_ms=I(1,1200001))
SCHEMAS=dict(configure=dict(xc_fences=I(1,40),jump_efforts=I(1,20),xc_optimum_ms=I(1,3600000),jump_allowed_ms=I(1,600000)),record_dressage=dict(player=P,**DRESS),record_cross_country=dict(player=P,**XC),record_jumping=dict(player=P,**JUMP),withdraw=dict(player=P),eliminate=dict(player=P),disqualify=dict(player=P),next_phase={},confirm={})
def dress_penalty(r):return (10000-r['dressage']['percentage_bp']+5)//10
def xc_penalty(d,r):
 x=r['xc'];obstacles=sum(200 if n==1 else 600 if n>=2 else 0 for n in x['refusals'])+110*x['frangibles']+150*x['missed_flags']+250*x['dangerous_riding']
 return obstacles+4*max(0,(x['time_ms']-d['xc_optimum_ms']+999)//1000)
def jump_penalty(d,r):
 x=r['jump'];return 40*(x['knockdowns']+x['refusals'])+4*max(0,(x['time_ms']-d['jump_allowed_ms']+999)//1000)
def xc_eliminated(d,x):return x['completed']!=d['xc_fences'] or sum(x['refusals'])>=3 or x['time_ms']>2*d['xc_optimum_ms']
def jump_eliminated(d,x):return x['completed']!=d['jump_efforts'] or x['refusals']>=2 or x['time_ms']>2*d['jump_allowed_ms']
def key(d,r):
 xc=xc_penalty(d,r);jump=jump_penalty(d,r)
 return (dress_penalty(r)+xc+jump,xc,abs(r['xc']['time_ms']-d['xc_optimum_ms']),jump,r['jump']['time_ms'],-r['dressage']['collective_half_points'])
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');phase=d['phase']
 for r in d['entrants']:
  dress=r['dressage'];xc=r['xc'];jump=r['jump']
  if dress is not None and (dress['errors']==3)!=(dress['percentage_bp'] is None):bad('Third dressage error eliminates rather than producing a scored percentage')
  if xc is not None:
   if dress is None or len(xc['refusals'])!=d['xc_fences'] or xc['completed']>d['xc_fences'] or xc['frangibles']>d['xc_fences'] or xc['missed_flags']>d['xc_fences']:bad('Cross-country record requires dressage and the configured course')
  if jump is not None and (xc is None or jump['completed']>d['jump_efforts'] or jump['knockdowns']>jump['completed']):bad('Jumping record requires cross country and valid completed efforts')
  if phase=='dressage' and (xc is not None or jump is not None) or phase=='cross_country' and jump is not None:bad('Later phase records cannot precede their competition phase')
  if r['status']=='eligible':
   if dress is not None and dress['errors']>=3 or xc is not None and xc_eliminated(d,xc) or jump is not None and jump_eliminated(d,jump):bad('An eliminating component result prevents continuation')
   if phase!='dressage' and dress is None or phase in ('jumping','review','finished') and xc is None or phase in ('review','finished') and jump is None:bad('Eligible entrant must complete every preceding phase')
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase']
 if k not in SCHEMAS:fail('Unknown eventing decision')
 fields(p,SCHEMAS[k],'/params')
 if phase=='finished':fail('Competition is finished')
 if k=='configure':
  if phase!='dressage' or any(r['dressage'] is not None for r in d['entrants']):fail('Course settings are fixed once component scoring starts')
  d.update(p)
 elif k in ('record_dressage','record_cross_country','record_jumping'):
  expected={'record_dressage':'dressage','record_cross_country':'cross_country','record_jumping':'jumping'}[k];field={'record_dressage':'dressage','record_cross_country':'xc','record_jumping':'jump'}[k];r=d['entrants'][p['player']]
  if phase!=expected or r['status']!='eligible' or r[field] is not None:fail('Record each eligible combination once in the active phase')
  x={k:v for k,v in p.items() if k!='player'}
  if k=='record_dressage':
   if (x['errors']==3)!=(x['percentage_bp'] is None):fail('Third dressage error must be recorded as elimination without a percentage')
   out=x['errors']==3
  elif k=='record_cross_country':
   if len(x['refusals'])!=d['xc_fences'] or x['completed']>d['xc_fences'] or x['frangibles']>d['xc_fences'] or x['missed_flags']>d['xc_fences']:fail('Cross-country summary must match the configured fences')
   out=xc_eliminated(d,x)
  else:
   if x['completed']>d['jump_efforts'] or x['knockdowns']>x['completed']:fail('Jumping summary exceeds the completed efforts')
   out=jump_eliminated(d,x)
  r[field]=x
  if out:r['status']='eliminated'
 elif k in ('withdraw','eliminate','disqualify'):
  r=d['entrants'][p['player']]
  if r['status']!='eligible':fail('Combination is already excluded')
  r['status']={'withdraw':'withdrawn','eliminate':'eliminated','disqualify':'dq'}[k]
 elif k=='next_phase':
  if phase not in ('dressage','cross_country','jumping'):fail('No component phase can advance')
  field={'dressage':'dressage','cross_country':'xc','jumping':'jump'}[phase]
  if any(r['status']=='eligible' and r[field] is None for r in d['entrants']):fail('Resolve every eligible combination before advancing')
  d['phase']='review' if not any(r['status']=='eligible' for r in d['entrants']) else {'dressage':'cross_country','cross_country':'jumping','jumping':'review'}[phase]
 elif k=='confirm':
  if phase!='review':fail('All three phases must reach review before confirmation')
  d['phase']='finished'
 return d
def legal(state):
 d=state['data'];phase=d['phase'];names=dict(dressage=['record_dressage','next_phase'],cross_country=['record_cross_country','next_phase'],jumping=['record_jumping','next_phase'],review=['confirm'],finished=[])[phase]
 if phase=='dressage' and all(r['dressage'] is None for r in d['entrants']):names=['configure']+names
 if phase!='finished':names+=['withdraw','eliminate','disqualify']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Combination eligibility, component order, score-sheet consistency and elimination limits must permit the event.'],external_observations=['Final dressage percentage after deductions; official course faults, corrected times and exclusion decisions.']) for k in names],constraints=dict(phase=phase,eligible=[i for i,r in enumerate(d['entrants']) if r['status']=='eligible'],xc_optimum_ms=d['xc_optimum_ms'],xc_time_limit_ms=2*d['xc_optimum_ms'],jump_allowed_ms=d['jump_allowed_ms'],jump_time_limit_ms=2*d['jump_allowed_ms']),completeness=False,reason='official_eventing_component_results')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';ids=[i for i,r in enumerate(d['entrants']) if r['status']=='eligible'] if done else [];ids.sort(key=lambda i:(key(d,d['entrants'][i]),i));best=key(d,d['entrants'][ids[0]]) if ids else None;w=[i for i in ids if key(d,d['entrants'][i])==best]
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ids else 'no_contest') if done else 'none',winners=[state['players'][i]['id'] for i in w],losers=[state['players'][i]['id'] for i in ids if i not in w],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(key(d,d['entrants'][j])<key(d,d['entrants'][i]) for j in ids),penalty_tenths=key(d,d['entrants'][i])[0]) for i in ids],reason='three_phase_classification' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
