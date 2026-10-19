"""Six-person twenty-five-target trap round with official target judgments."""
from copy import deepcopy
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=5)
def next_shooter(d):return min((i for i,r in enumerate(d['shooters']) if not r['disqualified'] and len(r['targets'])<25),key=lambda i:(len(d['shooters'][i]['targets']),i),default=None)
def settle(d):
 d['phase']='review' if next_shooter(d) is None else 'ready';d['repeat_second_only']=False
def key(r):return (sum(r['targets'])-r['penalty_targets'],*reversed(r['targets']))
def validate(d):
 if d['repeat_second_only'] and d['phase'] not in ('ready','called'):fail('Restricted repeat requires an unresolved target',code='INVALID_STATE')
 if d['phase'] in ('review','finished') and any(not r['disqualified'] and len(r['targets'])!=25 for r in d['shooters']):fail('Every eligible shooter must resolve twenty-five targets',code='INVALID_STATE')
 if d['phase'] in ('ready','called') and next_shooter(d) is None:fail('Completed round must enter review',code='INVALID_STATE')
 if d['phase']=='preparation' and any(r['targets'] or r['malfunctions'] or r['delay_warning'] for r in d['shooters']):fail('Target history exists before the round',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase']
 if k in ('start_round','call_target','no_target','malfunction','time_violation','confirm_result'):
  fields(p,dict(after_first_miss=dict(type='boolean')) if k=='malfunction' else {},'/params')
  if k=='start_round':
   if phase!='preparation':fail('Round already started')
   settle(d)
  elif k=='confirm_result':
   if phase!='review':fail('Resolve all targets and review results first')
   d['phase']='finished'
  else:
   if phase!=('ready' if k in ('call_target','time_violation') else 'called'):fail('Target phase does not permit this event')
   i=next_shooter(d);r=d['shooters'][i]
   if k=='call_target':d['phase']='called'
   elif k=='no_target':d['phase']='ready'
   elif k=='malfunction':
    if r['malfunctions']<2:r['malfunctions']+=1;d['phase']='ready';d['repeat_second_only']=d['repeat_second_only'] or p['after_first_miss']
    else:r['targets'].append(False);settle(d)
   else:
    if not r['delay_warning']:r['delay_warning']=True
    else:r['targets'].append(False);settle(d)
 elif k=='record_target':
  fields(p,dict(hit=dict(type='boolean'),shots=dict(type='integer',minimum=1,maximum=2)),'/params')
  if phase!='called':fail('A valid target must be called first')
  d['shooters'][next_shooter(d)]['targets'].append(p['hit'] and (not d['repeat_second_only'] or p['shots']==2));settle(d)
 elif k in ('correct_target','assess_penalty','correct_penalty','disqualify'):
  schema=dict(participant=INDEX)
  if k=='correct_target':schema.update(target=dict(type='integer',minimum=0,maximum=24),hit=dict(type='boolean'))
  elif k!='disqualify':schema['targets']=dict(type='integer',minimum=0 if k=='correct_penalty' else 1,maximum=25)
  fields(p,schema,'/params');i=p['participant'];r=d['shooters'][i]
  if r['disqualified']:fail('Participant is already disqualified')
  if k=='disqualify':
   if phase=='called' and i!=next_shooter(d):fail('Resolve the active target before excluding another shooter')
   r['disqualified']=True
   if phase in ('ready','called'):settle(d)
  elif k=='correct_target':
   if phase!='review' or p['target']>=len(r['targets']):fail('Correct an existing target judgment during review')
   r['targets'][p['target']]=p['hit']
  elif k=='correct_penalty':
   if phase!='review':fail('Penalty correction requires review')
   r['penalty_targets']=p['targets']
  else:
   if phase not in ('ready','review') or r['penalty_targets']+p['targets']>25:fail('Penalty exceeds the round bound or is unavailable now')
   r['penalty_targets']+=p['targets']
 else:fail('Unknown trap action')
 return d
def legal(state):
 d=state['data'];phase=d['phase'];specs={}
 if phase=='preparation':specs['start_round']={}
 if phase=='ready':specs.update(call_target={},time_violation={})
 if phase=='called':specs.update(record_target=dict(hit=dict(type='boolean'),shots=dict(type='integer',minimum=1,maximum=2)),no_target={},malfunction=dict(after_first_miss=dict(type='boolean')))
 if phase=='review':specs.update(correct_target=dict(participant=INDEX,target=dict(type='integer',minimum=0,maximum=24),hit=dict(type='boolean')),correct_penalty=dict(participant=INDEX,targets=dict(type='integer',minimum=0,maximum=25)),confirm_result={})
 if phase in ('ready','review'):specs['assess_penalty']=dict(participant=INDEX,targets=dict(type='integer',minimum=1,maximum=25))
 if phase!='finished':specs['disqualify']=dict(participant=INDEX)
 i=next_shooter(d)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Target phase, next shooter, repetition allowance and review status must permit this event.'],external_observations=['Official hit/lost target, no-target decision, accepted malfunction, preparation-time violation or sanction.']) for k,v in specs.items()],constraints=dict(phase=phase,next_participant=i,repeat_second_only=d['repeat_second_only'],shooting_station=None if i is None else (i+len(d['shooters'][i]['targets']))%5+1,preparation_seconds=12),completeness=False,reason='official_trap_round_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';eligible=[i for i,r in enumerate(d['shooters']) if not r['disqualified']] if done else [];eligible.sort(key=lambda i:key(d['shooters'][i]),reverse=True)
 winners=[state['players'][i]['id'] for i in eligible if key(d['shooters'][i])==key(d['shooters'][eligible[0]])] if eligible else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if eligible else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(key(d['shooters'][j])>key(d['shooters'][i]) for j in eligible),score=key(d['shooters'][i])[0]) for i in eligible],reason='round_confirmed' if done else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official round confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
