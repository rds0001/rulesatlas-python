"""Twelve-single-fence Table-A-style round against the clock."""
from copy import deepcopy
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
RESULT={'type': 'object', 'properties': {'status': {'type': 'enum', 'values': ['finished', 'eliminated', 'dns', 'dq']}, 'completed': {'type': 'integer', 'minimum': 0, 'maximum': 12}, 'refusals': {'type': 'integer', 'minimum': 0, 'maximum': 2}, 'obstacle_faults': {'type': 'integer', 'minimum': 0, 'maximum': 52}, 'elapsed_ms': {'type': 'integer', 'minimum': 0, 'maximum': 320001}, 'correction_ms': {'type': 'integer', 'minimum': 0, 'maximum': 6000}}, 'required': ['status', 'completed', 'refusals', 'obstacle_faults', 'elapsed_ms', 'correction_ms']}
def current(d):return next((i for i,r in enumerate(d['riders']) if r['status'] in ('pending','active')),None)
def settle(d):
 d['phase']='ready' if current(d) is not None else 'review';d['bell_remaining_ms']=45000;d['start_crossed']=False
def effective(r):return r['elapsed_ms']+r['correction_ms']
def expire(d,r):
 if effective(r)>160000:r['status']='eliminated';settle(d);return True
 return False
def faults(r):return r['obstacle_faults']+max(0,(effective(r)-80000+999)//1000)
def validate(d):
 active=[i for i,r in enumerate(d['riders']) if r['status']=='active']
 if (d['phase'] in ('bell','course','rebuild'))!=(len(active)==1):fail('Course phase and active rider disagree',code='INVALID_STATE')
 if active and active[0]!=current(d):fail('Active rider is out of start order',code='INVALID_STATE')
 if len(active)>1:fail('Only one rider may be on course',code='INVALID_STATE')
 if d['phase']=='ready' and current(d) is None:fail('Completed round must enter review',code='INVALID_STATE')
 if d['phase'] in ('review','finished') and current(d) is not None:fail('Resolve every entrant first',code='INVALID_STATE')
 if d['phase']=='bell' and (d['start_crossed'] or d['bell_remaining_ms']==0):fail('Bell countdown must precede start',code='INVALID_STATE')
 if d['phase']=='rebuild' and not d['start_crossed']:fail('Obstacle rebuilding requires a started course',code='INVALID_STATE')
 for r in d['riders']:
  if r['obstacle_faults']%4 or r['obstacle_faults']<4*min(1,r['refusals']) or r['correction_ms'] not in (0,6000):fail('Obstacle faults or time correction are inconsistent',code='INVALID_STATE')
  if r['correction_ms'] and not r['refusals']:fail('Time correction requires a refusal',code='INVALID_STATE')
  if r['refusals']==2 and r['status'] not in ('eliminated','dq'):fail('Second disobedience eliminates the entrant',code='INVALID_STATE')
  if r['status']=='finished' and (r['completed']!=12 or effective(r)==0 or effective(r)>160000):fail('Finish requires all fences within the time limit',code='INVALID_STATE')
  if r['status'] in ('pending','dns') and (r['completed'] or r['elapsed_ms'] or r['obstacle_faults'] or r['refusals'] or r['correction_ms']):fail('Course history exists for an unstarted rider',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase'];i=current(d);r=d['riders'][i] if i is not None else None
 if k in ('ring_bell','cross_start','resume_after_rebuild','finish','withdraw','confirm_result'):
  fields(p,{},'/params')
  if k=='ring_bell':
   if phase!='ready':fail('No entrant can be called now')
   r['status']='active';d['phase']='bell'
  elif k=='cross_start':
   if phase not in ('bell','course') or d['start_crossed']:fail('Start line cannot be crossed now')
   d['start_crossed']=True;d['phase']='course'
  elif k=='resume_after_rebuild':
   if phase!='rebuild':fail('No obstacle rebuild is pending')
   d['phase']='course'
  elif k=='finish':
   if phase!='course' or not d['start_crossed'] or r['completed']!=12 or effective(r)==0:fail('Finish requires a started and completed timed course')
   r['status']='finished';settle(d)
  elif k=='withdraw':
   if phase not in ('ready','bell','course','rebuild'):fail('No active entrant can withdraw')
   r['status']='dns' if phase=='ready' else 'eliminated';settle(d)
  else:
   if phase!='review':fail('Review every entrant before confirmation')
   d['phase']='finished'
 elif k=='amend_result':
  fields(p,dict(participant=INDEX,result=RESULT),'/params')
  if phase!='review':fail('Result amendments require official review')
  d['riders'][p['participant']]=deepcopy(p['result'])
 elif k=='elapse':
  fields(p,dict(milliseconds=dict(type='integer',minimum=1,maximum=160001)),'/params');ms=p['milliseconds']
  if phase=='bell':
   if ms>d['bell_remaining_ms']:fail('Advance to the countdown boundary before recording course time')
   d['bell_remaining_ms']-=ms
   if not d['bell_remaining_ms']:d['phase']='course'
  elif phase=='course':r['elapsed_ms']+=ms;expire(d,r)
  else:fail('Course timing is not running')
 elif k in ('jump_fence','refusal'):
  fields(p,dict(fence=dict(type='integer',minimum=0,maximum=11),**({'knocked':dict(type='boolean')} if k=='jump_fence' else {'destroyed':dict(type='boolean')})),'/params')
  if phase!='course' or not d['start_crossed'] or p['fence']!=r['completed']:fail('The next prescribed fence must be attempted after crossing the start')
  if k=='jump_fence':r['completed']+=1;r['obstacle_faults']+=4*int(p['knocked'])
  else:
   r['refusals']+=1
   if r['refusals']==2:r['status']='eliminated';settle(d)
   else:
    r['obstacle_faults']+=4
    if p['destroyed']:
     r['correction_ms']+=6000
     if not expire(d,r):d['phase']='rebuild'
 elif k in ('eliminate','disqualify'):
  schema=dict(reason=dict(type='enum',values=['wrong_course','fall','unauthorized_assistance','equipment','other_official']))
  if k=='disqualify':schema['participant']=INDEX
  fields(p,schema,'/params')
  if k=='eliminate':
   if phase not in ('bell','course','rebuild'):fail('No active entrant can be eliminated')
   r['status']='eliminated';settle(d)
  else:
   j=p['participant'];target=d['riders'][j]
   if target['status']=='dq':fail('Entrant is already disqualified')
   target['status']='dq'
   if j==i:settle(d)
 else:fail('Unknown show-jumping action')
 return d
def legal(state):
 d=state['data'];phase=d['phase'];specs={};i=current(d)
 if phase=='ready':specs['ring_bell']={}
 if phase in ('bell','course'):
  specs['elapse']=dict(milliseconds=dict(type='integer',minimum=1,maximum=160001))
  if not d['start_crossed']:specs['cross_start']={}
 if phase=='course' and d['start_crossed']:
  if d['riders'][i]['completed']<12:specs.update(jump_fence=dict(fence=dict(type='integer',minimum=0,maximum=11),knocked=dict(type='boolean')),refusal=dict(fence=dict(type='integer',minimum=0,maximum=11),destroyed=dict(type='boolean')))
  else:specs['finish']={}
 if phase=='rebuild':specs['resume_after_rebuild']={}
 if phase in ('ready','bell','course','rebuild'):specs['withdraw']={}
 reason=dict(type='enum',values=['wrong_course','fall','unauthorized_assistance','equipment','other_official'])
 if phase in ('bell','course','rebuild'):specs['eliminate']=dict(reason=reason)
 if phase=='review':specs.update(confirm_result={},amend_result=dict(participant=INDEX,result=RESULT))
 if phase!='finished':specs['disqualify']=dict(participant=INDEX,reason=reason)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Rider phase, start line, next fence and time limits must permit the event.'],external_observations=['Official fence judgment, valid start/finish crossing, running elapsed time, obstacle readiness or exclusion.']) for k,v in specs.items()],constraints=dict(phase=phase,current_participant=i,bell_remaining_ms=d['bell_remaining_ms'],allowed_time_ms=80000,time_limit_ms=160000),completeness=False,reason='official_show_jumping_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';eligible=[i for i,r in enumerate(d['riders']) if r['status']=='finished'] if done else [];key=lambda i:(faults(d['riders'][i]),effective(d['riders'][i]));eligible.sort(key=key)
 winners=[state['players'][i]['id'] for i in eligible if key(i)==key(eligible[0])] if eligible else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if eligible else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(key(j)<key(i) for j in eligible),faults=key(i)[0],time_ms=key(i)[1]) for i in eligible],reason='round_confirmed' if done else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official round confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
