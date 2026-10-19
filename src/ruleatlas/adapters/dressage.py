"""Five-judge prescribed dressage test with exact weighted percentages."""
from copy import deepcopy
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
MARKS=dict(type='array',minItems=5,maxItems=5,items=dict(type='integer',minimum=0,maximum=20))
TEST=dict(type='array',minItems=1,maxItems=40,items=dict(type='object',properties=dict(name=dict(type='string',minLength=1,maxLength=80),coefficient=dict(type='integer',minimum=1,maximum=2),collective=dict(type='boolean')),required=['name','coefficient','collective']))
def current(d):return next((i for i,r in enumerate(d['entrants']) if r['status']=='eligible' and len(r['marks'])<len(d['test'])),None)
def settle(d):d['phase']='review' if current(d) is None else 'ready'
def totals(d,r):
 weighted=sum(sum(m)*element['coefficient'] for m,element in zip(r['marks'],d['test']));collective=sum(sum(m)*element['coefficient'] for m,element in zip(r['marks'],d['test']) if element['collective'])
 denominator=5*20*sum(element['coefficient'] for element in d['test']);penalty=r['penalty_basis_points']+200*int(r['errors']>=1)
 return 10000*weighted-penalty*denominator,collective,denominator
def validate(d):
 if d['phase']=='setup':
  if d['test'] or any(r['marks'] or r['errors'] or r['penalty_basis_points'] for r in d['entrants']):fail('Initial test must have no scored movements',code='INVALID_STATE')
  return
 if not d['test']:fail('A prescribed test is required',code='INVALID_STATE')
 for r in d['entrants']:
  if len(r['marks'])>len(d['test']):fail('Too many scored test elements',code='INVALID_STATE')
  if r['errors']==2 and r['status'] not in ('eliminated','dq'):fail('Second course error eliminates the entrant',code='INVALID_STATE')
  if r['status']=='dns' and (r['marks'] or r['errors'] or r['penalty_basis_points']):fail('DNS entrant already has test history',code='INVALID_STATE')
  if r['status']=='eligible' and r['errors'] and not r['marks'] and d['phase'] not in ('test',):fail('Course-error history requires an active or completed test',code='INVALID_STATE')
 if (d['phase'] in ('ready','test'))!=(current(d) is not None):fail('Phase and incomplete test sheets disagree',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase'];i=current(d)
 if k=='configure_test':
  fields(p,dict(test=TEST),'/params')
  if phase!='setup':fail('The prescribed test is locked after configuration')
  d['test']=deepcopy(p['test']);settle(d)
 elif k=='start_test':
  fields(p,dict(participant=INDEX),'/params')
  if phase!='ready' or p['participant']!=i:fail('Start the next eligible entrant in the declared order')
  d['phase']='test'
 elif k=='score_movement':
  fields(p,dict(movement=dict(type='integer',minimum=0,maximum=39),marks=MARKS),'/params')
  if phase!='test' or p['movement']!=len(d['entrants'][i]['marks']):fail('Enter all five marks for the next test element')
  d['entrants'][i]['marks'].append(p['marks'][:])
  if len(d['entrants'][i]['marks'])==len(d['test']):settle(d)
 elif k=='course_error':
  fields(p,{},'/params')
  if phase!='test':fail('Course error requires an active test')
  d['entrants'][i]['errors']+=1
  if d['entrants'][i]['errors']==2:d['entrants'][i]['status']='eliminated';settle(d)
 elif k in ('assess_penalty','correct_penalty'):
  fields(p,dict(participant=INDEX,basis_points=dict(type='integer',minimum=1 if k=='assess_penalty' else 0,maximum=10000)),'/params');r=d['entrants'][p['participant']]
  if r['status']!='eligible' or (k=='correct_penalty' and phase!='review') or (k=='assess_penalty' and not (phase=='review' or phase=='test' and p['participant']==i)):fail('Penalty assessment requires the active test or official result review')
  value=r['penalty_basis_points']+p['basis_points'] if k=='assess_penalty' else p['basis_points']
  if value>10000:fail('Technical penalty exceeds the supported bound')
  r['penalty_basis_points']=value
 elif k=='correct_errors':
  fields(p,dict(participant=INDEX,errors=dict(type='integer',minimum=0,maximum=1)),'/params')
  if phase!='review' or d['entrants'][p['participant']]['status']!='eligible':fail('Correct a classified entrant course-error count during review')
  d['entrants'][p['participant']]['errors']=p['errors']
 elif k=='correct_mark':
  fields(p,dict(participant=INDEX,movement=dict(type='integer',minimum=0,maximum=39),marks=MARKS),'/params');r=d['entrants'][p['participant']]
  if phase!='review' or p['movement']>=len(r['marks']):fail('Correct an existing mark row during result review')
  r['marks'][p['movement']]=p['marks'][:]
 elif k in ('withdraw','eliminate','disqualify'):
  fields(p,dict(participant=INDEX),'/params');j=p['participant'];r=d['entrants'][j]
  if r['status']!='eligible':fail('Entrant is already excluded')
  if k=='withdraw':
   if phase not in ('setup','ready') or r['marks']:fail('Withdraw as DNS before starting the test')
   r['status']='dns'
  elif k=='eliminate':
   if phase!='test' or j!=i:fail('Only the active test can be officially eliminated')
   r['status']='eliminated'
  else:r['status']='dq'
  if phase!='setup' and (phase!='test' or i==j):settle(d)
 elif k=='confirm_result':
  fields(p,{},'/params')
  if phase!='review':fail('Resolve every entrant before confirmation')
  d['phase']='finished'
 else:fail('Unknown dressage action')
 return d
def legal(state):
 d=state['data'];phase=d['phase'];i=current(d);specs={}
 if phase=='setup':specs['configure_test']=dict(test=TEST)
 if phase=='ready':specs['start_test']=dict(participant=INDEX)
 if phase=='test':specs.update(score_movement=dict(movement=dict(type='integer',minimum=0,maximum=39),marks=MARKS),course_error={},eliminate=dict(participant=INDEX))
 if phase in ('test','review'):specs['assess_penalty']=dict(participant=INDEX,basis_points=dict(type='integer',minimum=1,maximum=10000))
 if phase in ('setup','ready'):specs['withdraw']=dict(participant=INDEX)
 if phase!='finished':specs['disqualify']=dict(participant=INDEX)
 if phase=='review':specs.update(correct_errors=dict(participant=INDEX,errors=dict(type='integer',minimum=0,maximum=1)),correct_mark=dict(participant=INDEX,movement=dict(type='integer',minimum=0,maximum=39),marks=MARKS),correct_penalty=dict(participant=INDEX,basis_points=dict(type='integer',minimum=0,maximum=10000)),confirm_result={})
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Prescribed test order, judge count, course-error limit and review phase must permit the decision.'],external_observations=['Official test coefficients, five judge marks, technical deduction or elimination.']) for k,v in specs.items()],constraints=dict(phase=phase,current_participant=i,next_movement=None if i is None else len(d['entrants'][i]['marks'])),completeness=False,reason='official_dressage_judgments')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';ranked=[]
 if done:
  ranked=[(*totals(d,r),i) for i,r in enumerate(d['entrants']) if r['status']=='eligible'];ranked.sort(key=lambda x:(-x[0],-x[1],x[3]))
 winners=[state['players'][i]['id'] for a,b,den,i in ranked if (a,b)==ranked[0][:2]] if ranked else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum((a2,b2)>(a,b) for a2,b2,_,_ in ranked),basis_points_numerator=a,denominator=den,collective_half_points=b) for a,b,den,i in ranked],reason='test_confirmed' if done else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official test confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
