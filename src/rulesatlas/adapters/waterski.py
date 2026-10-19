"""Slalom pass progression with official repeat bounds and skipped-pass credit."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b,**kw:dict(type='integer',minimum=a,maximum=b,**kw)
Q=dict(type='integer',enum=[q for q in range(25) if q%4!=3])
RULING=dict(quarters=Q,complete=dict(type='boolean'),reride=dict(type='enum',values=['none','optional','mandatory']),protected=Q,cap=Q,continue_allowed=dict(type='boolean'))
STAGE=dict(type='object',properties=dict(speed_kmh=I(25,58),rope_cm=I(800,1825)),required=['speed_kmh','rope_cm'])
SCHEMAS=dict(configure=dict(stages=dict(type='array',minItems=1,maxItems=32,items=STAGE),order=dict(type='array',minItems=8,maxItems=8,items=I(0,7))),start_pass=dict(stage=I(0,31)),judge_pass=RULING,correct_ruling=RULING,accept_pass={},take_reride={},continue_at_risk=dict(stage=I(0,31)),stop_run={},withdraw=dict(participant=I(0,7)),disqualify=dict(participant=I(0,7)),zero_performance=dict(participant=I(0,7)),confirm_result={})
def current(d):return next((i for i in d['order'] if d['skiers'][i]['status'] in ('pending','skiing')),None)
def clear(d):d.update(selected=None,protected=0,cap=24,ruling=None)
def settle(d):clear(d);d['phase']='review' if current(d) is None else 'ready'
def rule_valid(r):return r['protected']<=r['quarters']<=r['cap'] and (not r['complete'] or r['quarters']==24) and (not r['continue_allowed'] or r['complete'] and r['reride']!='none') and (r['reride']!='none' or r['protected']==0 and r['cap']==24)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['phase']=='setup':
  if d['stages'] or d['order'] or any(r['status']!='pending' or r['next_stage'] or r['score_quarters'] for r in d['skiers']):bad('Initial slalom event must be empty')
 else:
  if not d['stages'] or sorted(d['order'])!=list(range(8)):bad('Configure progression and the complete start order')
  if d['stages'][0]['rope_cm']!=1825 or any(x['rope_cm']!=1825 for x in d['stages'] if x['speed_kmh']<d['stages'][-1]['speed_kmh']):bad('Rope shortening starts only at the configured maximum speed')
  for a,b in zip(d['stages'],d['stages'][1:]):
   if b['speed_kmh']<a['speed_kmh'] or b['rope_cm']>a['rope_cm'] or b==a or b['speed_kmh']!=a['speed_kmh'] and b['speed_kmh']-a['speed_kmh']!=3:bad('Successive passes must be strictly harder')
 for r in d['skiers']:
  if r['score_quarters']%4==3:bad('Three-quarter buoy scores are not permitted')
  if r['next_stage']>len(d['stages']) or r['score_quarters']>24*len(d['stages']):bad('Score exceeds configured progression')
  if r['status'] in ('pending','dns') and (r['next_stage'] or r['score_quarters']):bad('Unstarted skier already has a score')
  if r['status']=='skiing' and r['next_stage']>=len(d['stages']):bad('Completed progression must finish the run')
  if r['status']=='skiing' and not 24*r['next_stage']<=r['score_quarters']<=24*(r['next_stage']+1):bad('Active score and next credited stage disagree')
 if d['protected']>d['cap']:bad('Conflicting reride score bounds')
 if d['selected'] is None:
  if d['phase'] in ('pass','pass_review') or d['protected'] or d['cap']!=24:bad('Pass context is missing')
 else:
  i=current(d)
  if i is None or d['phase'] not in ('ready','pass','pass_review') or not d['skiers'][i]['next_stage']<=d['selected']<len(d['stages']):bad('Selected pass is outside the remaining progression')
 if (d['phase']=='pass_review')!=(d['ruling'] is not None):bad('Pending ruling requires pass review')
 if d['ruling'] is not None and not rule_valid(d['ruling']):bad('Inconsistent pass ruling')
 if d['phase']!='setup' and (d['phase'] in ('review','finished'))!=(current(d) is None):bad('Resolve every skier before result review')
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase'];i=current(d)
 if k not in SCHEMAS:fail('Unknown slalom action')
 fields(p,SCHEMAS[k],'/params')
 if k=='configure':
  if phase!='setup' or sorted(p['order'])!=list(range(8)):fail('Configure each entrant once before skiing')
  d.update(stages=deepcopy(p['stages']),order=p['order'][:],phase='ready');validate(d)
 elif k=='start_pass':
  if phase!='ready' or not d['skiers'][i]['next_stage']<=p['stage']<len(d['stages']) or d['selected'] is not None and p['stage']!=d['selected']:fail('Start the next selected or authorized repeat pass')
  d['selected']=p['stage'];d['skiers'][i]['status']='skiing';d['phase']='pass'
 elif k in ('judge_pass','correct_ruling'):
  if phase!=('pass' if k=='judge_pass' else 'pass_review') or not rule_valid(p):fail('Supply a consistent official pass ruling in the proper phase')
  r=deepcopy(p);r['quarters']=max(d['protected'],min(d['cap'],r['quarters']))
  r['complete']=r['complete'] and r['quarters']==24
  r['protected']=max(d['protected'],r['protected']);r['cap']=min(d['cap'],r['cap'])
  if r['protected']>r['cap']:fail('Reride rulings conflict with existing protection')
  if r['reride']=='none':r.update(protected=0,cap=24,continue_allowed=False)
  if not r['complete']:r['continue_allowed']=False
  d['ruling']=r;d['phase']='pass_review'
 elif k=='accept_pass':
  if phase!='pass_review' or d['ruling']['reride']=='mandatory':fail('A mandatory reride cannot be accepted')
  r=d['skiers'][i];v=d['ruling'];r['score_quarters']=max(r['score_quarters'],24*(d['selected']+1) if v['complete'] else 24*r['next_stage']+v['quarters'])
  if v['complete']:r['next_stage']=d['selected']+1
  if not v['complete'] or r['next_stage']==len(d['stages']):r['status']='finished'
  settle(d)
 elif k=='take_reride':
  if phase!='pass_review' or d['ruling']['reride']=='none':fail('No repeat has been authorized')
  d.update(protected=d['ruling']['protected'],cap=d['ruling']['cap'],ruling=None,phase='ready')
 elif k=='continue_at_risk':
  if phase!='pass_review' or not d['ruling']['continue_allowed'] or not d['selected']<p['stage']<len(d['stages']):fail('No harder at-risk pass is authorized')
  r=d['skiers'][i];r['score_quarters']=max(r['score_quarters'],24*r['next_stage']+d['ruling']['protected']);clear(d);d.update(selected=p['stage'],phase='ready')
 elif k=='stop_run':
  if phase!='ready' or d['skiers'][i]['status']!='skiing':fail('Stop only between attempts after skiing has begun')
  r=d['skiers'][i];r['score_quarters']=max(r['score_quarters'],24*r['next_stage']+d['protected']);r['status']='finished';settle(d)
 elif k in ('withdraw','disqualify','zero_performance'):
  j=p['participant'];r=d['skiers'][j]
  if phase=='setup' or r['status']=='dq':fail('Entrant cannot receive this ruling now')
  if k=='withdraw':
   if r['status']!='pending':fail('Withdrawal before skiing is DNS; use stop_run after starting')
   r['status']='dns'
  elif k=='disqualify':r['status']='dq'
  else:r.update(status='finished',score_quarters=0,next_stage=0)
  if j==i:settle(d)
 elif k=='confirm_result':
  if phase!='review':fail('Resolve all runs before confirming results')
  d['phase']='finished'
 return d
def legal(state):
 d=state['data'];names={'setup':['configure'],'ready':['start_pass','stop_run'],'pass':['judge_pass'],'pass_review':['correct_ruling','accept_pass','take_reride','continue_at_risk'],'review':['confirm_result']}.get(d['phase'],[])
 if d['phase'] not in ('setup','finished'):names+=['withdraw','disqualify','zero_performance']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Pass selection, completion, repeat entitlement and protected score bounds must permit the event.'],external_observations=['Official buoy score, continuation eligibility and reride decision.']) for k in names],constraints=dict(phase=d['phase'],current_participant=current(d),selected_stage=d['selected'],protected_quarters=d['protected'],maximum_quarters=d['cap']),completeness=False,reason='official_slalom_pass_rulings')
def outcome(state,pack):
 d=state['data'];t=d['phase']=='finished';ranked=sorted([(-r['score_quarters'],i) for i,r in enumerate(d['skiers']) if r['status']=='finished']) if t else [];winners=[state['players'][i]['id'] for s,i in ranked if s==ranked[0][0]] if ranked else []
 return dict(status='terminal' if t else 'awaiting_adjudication' if d['phase'] in ('pass_review','review') else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if t else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other<s for other,_ in ranked),score_quarters=-s) for s,i in ranked],reason='slalom_confirmed' if t else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if t else None)
