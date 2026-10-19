"""Sixty-shot integer air-pistol qualification, including countback."""
from copy import deepcopy
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
SHOT=dict(score=dict(type='integer',minimum=0,maximum=10),inner_ten=dict(type='boolean'))
def key(r):
 scores=[x['score'] for x in r['shots']]
 return (sum(scores)-r['penalty_points'],sum(x['inner_ten'] for x in r['shots']),*[sum(scores[i:i+10]) for i in range(50,-1,-10)],*[v for shot in reversed(r['shots']) for v in (shot['score'],int(shot['inner_ten']))])
def close(d):
 for r in d['shooters']:
  if not r['disqualified']:r['shots'] += [dict(score=0,inner_ten=False) for _ in range(60-len(r['shots']))]
 d['phase']='review'
def validate(d):
 for r in d['shooters']:
  if any(s['inner_ten'] and s['score']!=10 for s in r['shots']):fail('Only a ten may be an inner ten',code='INVALID_STATE')
  if d['phase'] in ('preparation','sighting') and r['shots']:fail('Competition shots exist before match start',code='INVALID_STATE')
  if d['phase'] in ('review','finished') and not r['disqualified'] and len(r['shots'])!=60:fail('Resolve every required competition shot',code='INVALID_STATE')
 if d['phase'] in ('preparation','sighting') and d['remaining_seconds']!=4500:fail('Match clock cannot run before match start',code='INVALID_STATE')
 if d['phase']=='match' and (d['remaining_seconds']==0 or all(r['disqualified'] or len(r['shots'])==60 for r in d['shooters'])):fail('Completed match must enter review',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase']
 if k in ('begin_sighting','start_match','confirm_results'):
  fields(p,{},'/params');expected={'begin_sighting':'preparation','start_match':'sighting','confirm_results':'review'}[k]
  if phase!=expected:fail('Phase does not permit this command')
  d['phase']={'begin_sighting':'sighting','start_match':'match','confirm_results':'finished'}[k]
  if k=='start_match' and all(r['disqualified'] for r in d['shooters']):close(d)
 elif k=='elapse':
  fields(p,dict(seconds=dict(type='integer',minimum=1,maximum=4500)),'/params')
  if phase!='match' or p['seconds']>d['remaining_seconds']:fail('Elapsed time must fit the active match clock')
  d['remaining_seconds']-=p['seconds']
  if d['remaining_seconds']==0:close(d)
 elif k in ('record_shot','correct_shot'):
  schema=dict(participant=INDEX,**SHOT)
  if k=='correct_shot':schema['shot']=dict(type='integer',minimum=0,maximum=59)
  fields(p,schema,'/params');r=d['shooters'][p['participant']]
  if p['inner_ten'] and p['score']!=10:fail('Only a ten may be an inner ten')
  shot={x:p[x] for x in SHOT}
  if k=='record_shot':
   if phase!='match' or r['disqualified'] or len(r['shots'])==60:fail('No further competition shot is available')
   r['shots'].append(shot)
   if all(x['disqualified'] or len(x['shots'])==60 for x in d['shooters']):close(d)
  else:
   if phase!='review' or r['disqualified'] or p['shot']>=len(r['shots']):fail('Correct an eligible recorded shot during review')
   r['shots'][p['shot']]=shot
 elif k in ('assess_penalty','correct_penalty','disqualify'):
  schema=dict(participant=INDEX)
  if k!='disqualify':schema['points']=dict(type='integer',minimum=0 if k=='correct_penalty' else 1,maximum=600)
  fields(p,schema,'/params');r=d['shooters'][p['participant']]
  if r['disqualified']:fail('Participant is already disqualified')
  if k=='disqualify':r['disqualified']=True
  elif k=='assess_penalty':
   if phase not in ('sighting','match','review') or r['penalty_points']+p['points']>600:fail('Penalty is not permitted in this phase or exceeds the bound')
   r['penalty_points']+=p['points']
  else:
   if phase!='review':fail('Penalty correction requires result review')
   r['penalty_points']=p['points']
  if phase=='match' and all(x['disqualified'] or len(x['shots'])==60 for x in d['shooters']):close(d)
 else:fail('Unknown precision-shooting action')
 return d
def legal(state):
 d=state['data'];phase=d['phase'];specs={}
 if phase=='preparation':specs['begin_sighting']={}
 if phase=='sighting':specs['start_match']={}
 if phase=='match':specs.update(record_shot=dict(participant=INDEX,**SHOT),elapse=dict(seconds=dict(type='integer',minimum=1,maximum=4500)))
 if phase=='review':specs.update(correct_shot=dict(participant=INDEX,**SHOT,shot=dict(type='integer',minimum=0,maximum=59)),correct_penalty=dict(participant=INDEX,points=dict(type='integer',minimum=0,maximum=600)),confirm_results={})
 if phase in ('sighting','match','review'):specs['assess_penalty']=dict(participant=INDEX,points=dict(type='integer',minimum=1,maximum=600))
 if phase!='finished':specs['disqualify']=dict(participant=INDEX)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Phase, remaining shots, timing and eligibility must permit the event.'],external_observations=['Official shot score, inner-ten decision, elapsed range time or assessed penalty.']) for k,v in specs.items()],constraints=dict(phase=phase,remaining_seconds=d['remaining_seconds'],shots_remaining=[0 if r['disqualified'] else 60-len(r['shots']) for r in d['shooters']]),completeness=False,reason='official_precision_shooting_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';eligible=[i for i,r in enumerate(d['shooters']) if not r['disqualified']] if done else [];eligible.sort(key=lambda i:key(d['shooters'][i]),reverse=True)
 winners=[state['players'][i]['id'] for i in eligible if key(d['shooters'][i])==key(d['shooters'][eligible[0]])] if eligible else []
 placements=[dict(player_id=state['players'][i]['id'],place=1+sum(key(d['shooters'][j])>key(d['shooters'][i]) for j in eligible),score=key(d['shooters'][i])[0],inner_tens=key(d['shooters'][i])[1]) for i in eligible]
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if eligible else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=placements,reason='qualification_confirmed' if done else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official result confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
