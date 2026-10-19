"""Fixed twenty-obstacle agility course with faults and hundredth-second timing."""
from copy import deepcopy
from ..values import fields,fail
COURSE=['jump','jump','tunnel','jump','dogwalk','jump','weave','tunnel','jump','aframe','jump','jump','tunnel','seesaw','jump','tunnel','jump','jump','tunnel','jump']
INDEX=dict(type='integer',minimum=0,maximum=7)
PROPS=dict(status=dict(type='enum',values=['finished','eliminated','dns','dq']),completed=dict(type='integer',minimum=0,maximum=20),refusals=dict(type='integer',minimum=0,maximum=3),faults=dict(type='integer',minimum=0,maximum=310),elapsed_ms=dict(type='integer',minimum=0,maximum=240010))
RESULT=dict(type='object',properties=PROPS,required=list(PROPS))
def current(d):return next((i for i,r in enumerate(d['dogs']) if r['status'] in ('pending','active')),None)
def settle(d):d['phase']='ready' if current(d) is not None else 'review'
def score(r):return r['faults']*100+max(0,(r['elapsed_ms']-60000)//10)
def validate(d):
 active=[i for i,r in enumerate(d['dogs']) if r['status']=='active']
 if (d['phase']=='course')!=(len(active)==1) or len(active)>1:fail('Course phase requires exactly one active dog',code='INVALID_STATE')
 if active and active[0]!=current(d):fail('Active dog is out of start order',code='INVALID_STATE')
 if d['phase']=='ready' and current(d) is None:fail('Completed event must enter review',code='INVALID_STATE')
 if d['phase'] in ('review','finished') and current(d) is not None:fail('Resolve all entrants first',code='INVALID_STATE')
 for r in d['dogs']:
  if r['faults']%5 or r['faults']<5*min(2,r['refusals']) or r['elapsed_ms']%10:fail('Fault units or timing precision are invalid',code='INVALID_STATE')
  if r['refusals']==3 and r['status'] not in ('eliminated','dq'):fail('Third refusal eliminates the entrant',code='INVALID_STATE')
  if r['status']=='finished' and (r['completed']!=20 or not r['elapsed_ms'] or r['elapsed_ms']>120000):fail('Finish requires every obstacle and a valid course time',code='INVALID_STATE')
  if r['status']=='active' and r['elapsed_ms']>120000:fail('Maximum course time has been exceeded',code='INVALID_STATE')
  if r['status'] in ('pending','dns') and (r['completed'] or r['refusals'] or r['faults'] or r['elapsed_ms']):fail('Unstarted entrant has course history',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase'];i=current(d);r=d['dogs'][i] if i is not None else None
 if k in ('start','finish','withdraw','confirm_result'):
  fields(p,{},'/params')
  if k=='start':
   if phase!='ready':fail('Next entrant cannot start now')
   r['status']='active';d['phase']='course'
  elif k=='finish':
   if phase!='course' or r['completed']!=20 or not r['elapsed_ms']:fail('Finish requires every obstacle and recorded running time')
   r['status']='finished';settle(d)
  elif k=='withdraw':
   if phase not in ('ready','course'):fail('No entrant can withdraw now')
   r['status']='dns' if phase=='ready' else 'eliminated';settle(d)
  else:
   if phase!='review':fail('Resolve and review every entrant first')
   d['phase']='finished'
 elif k=='elapse':
  fields(p,dict(milliseconds=dict(type='integer',minimum=10,maximum=120010)),'/params')
  if phase!='course' or p['milliseconds']%10:fail('Running course time must use hundredth-second increments')
  r['elapsed_ms']+=p['milliseconds']
  if r['elapsed_ms']>120000:r['status']='eliminated';settle(d)
 elif k in ('complete_obstacle','refusal'):
  schema=dict(obstacle=dict(type='integer',minimum=0,maximum=19))
  if k=='complete_obstacle':schema['execution_faults']=dict(type='integer',minimum=0,maximum=3)
  fields(p,schema,'/params')
  if phase!='course' or p['obstacle']!=r['completed']:fail('Attempt the next prescribed obstacle in course order')
  if k=='refusal':
   r['refusals']+=1
   if r['refusals']==3:r['status']='eliminated';settle(d)
   else:r['faults']+=5
  else:
   if p['execution_faults']>({'tunnel':0,'jump':1,'weave':1}.get(COURSE[p['obstacle']],3)):fail('Execution-fault count is not supported for this obstacle type')
   r['faults']+=5*p['execution_faults'];r['completed']+=1
 elif k=='amend_result':
  fields(p,dict(participant=INDEX,result=RESULT),'/params')
  if phase!='review':fail('Official result review is required')
  d['dogs'][p['participant']]=deepcopy(p['result'])
 elif k in ('eliminate','disqualify'):
  schema=dict(reason=dict(type='enum',values=['wrong_course','unsafe_behavior','handler_assistance','equipment','other_official']))
  if k=='disqualify':schema['participant']=INDEX
  fields(p,schema,'/params')
  if k=='eliminate':
   if phase!='course':fail('No active course can be eliminated')
   r['status']='eliminated';settle(d)
  else:
   j=p['participant']
   if d['dogs'][j]['status']=='dq':fail('Entrant is already disqualified')
   d['dogs'][j]['status']='dq'
   if j==i:settle(d)
 else:fail('Unknown agility action')
 return d
def legal(state):
 d=state['data'];phase=d['phase'];i=current(d);specs={}
 if phase=='ready':specs['start']={}
 if phase in ('ready','course'):specs['withdraw']={}
 if phase=='course':
  specs['elapse']=dict(milliseconds=dict(type='integer',minimum=10,maximum=120010))
  if d['dogs'][i]['completed']<20:specs.update(complete_obstacle=dict(obstacle=dict(type='integer',minimum=0,maximum=19),execution_faults=dict(type='integer',minimum=0,maximum=3)),refusal=dict(obstacle=dict(type='integer',minimum=0,maximum=19)))
  else:specs['finish']={}
 reason=dict(type='enum',values=['wrong_course','unsafe_behavior','handler_assistance','equipment','other_official'])
 if phase=='course':specs['eliminate']=dict(reason=reason)
 if phase!='finished':specs['disqualify']=dict(participant=INDEX,reason=reason)
 if phase=='review':specs.update(amend_result=dict(participant=INDEX,result=RESULT),confirm_result={})
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Current entrant, obstacle order, fault kind and timing must permit the event.'],external_observations=['Official obstacle completion, refusal, execution fault, elapsed running time or exclusion.']) for k,v in specs.items()],constraints=dict(phase=phase,current_participant=i,course=COURSE,standard_time_ms=60000,maximum_time_ms=120000),completeness=False,reason='official_agility_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';eligible=[i for i,r in enumerate(d['dogs']) if r['status']=='finished'] if done else [];key=lambda i:(score(d['dogs'][i]),d['dogs'][i]['faults'],d['dogs'][i]['elapsed_ms']);eligible.sort(key=key)
 winners=[state['players'][i]['id'] for i in eligible if key(i)==key(eligible[0])] if eligible else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if eligible else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(key(j)<key(i) for j in eligible),fault_hundredths=key(i)[0],course_faults=key(i)[1],time_ms=key(i)[2]) for i in eligible],reason='course_confirmed' if done else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official course confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
