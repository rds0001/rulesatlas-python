"""Six-dive three-metre springboard final with seven official judges."""
from copy import deepcopy
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
MARKS=dict(type='array',minItems=7,maxItems=7,items=dict(type='integer',minimum=0,maximum=20))
DIVE=dict(type='object',properties=dict(number=dict(type='integer',minimum=100,maximum=5999),position=dict(type='enum',values=['A','B','C','D']),group=dict(type='integer',minimum=1,maximum=5),difficulty_tenths=dict(type='integer',minimum=10,maximum=60)),required=['number','position','group','difficulty_tenths'])
RESULT=dict(type='object',properties=dict(marks=dict(MARKS,nullable=True),failed=dict(type='boolean'),balks=dict(type='integer',minimum=0,maximum=2)),required=['marks','failed','balks'])
def current(d):return min((i for i,r in enumerate(d['entrants']) if r['status']=='eligible' and len(r['results'])<6),key=lambda i:(len(d['entrants'][i]['results']),i),default=None)
def settle(d):d.update(phase='review' if current(d) is None else 'ready',balks=0)
def score(result,difficulty):
 if result['failed']:return 0
 marks=sorted(max(0,m-4*result['balks']) for m in result['marks'])
 return sum(marks[2:5])*difficulty
def validate(d):
 if d['phase']=='setup':
  if d['catalog'] or any(d['programs']) or any(r['results'] for r in d['entrants']) or d['balks']:fail('Initial diving contest must be empty',code='INVALID_STATE')
  return
 if not d['catalog'] or len(set((x['number'],x['position']) for x in d['catalog']))!=len(d['catalog']) or any(int(str(x['number'])[0])!=x['group'] for x in d['catalog']):fail('Dive catalog must use unique numbered positions and consistent groups',code='INVALID_STATE')
 for i,program in enumerate(d['programs']):
  if len(program)!=6 or any(k>=len(d['catalog']) for k in program):fail('Every entrant must declare six catalog dives',code='INVALID_STATE')
  dives=[d['catalog'][k] for k in program]
  if len({x['number'] for x in dives})!=6 or {x['group'] for x in dives}!=set(range(1,6)):fail('Program must cover all five groups without repeating a dive number',code='INVALID_STATE')
  for result in d['entrants'][i]['results']:
   if result['failed']!=(result['marks'] is None) or (not result['failed'] and result['balks']==2):fail('Failed dives have no marks; a second balk must fail',code='INVALID_STATE')
  if d['entrants'][i]['status']=='dns' and d['entrants'][i]['results']:fail('DNS entrant already has competition dives',code='INVALID_STATE')
  if d['entrants'][i]['status']=='dnf' and not d['entrants'][i]['results']:fail('DNF requires a previously attempted dive',code='INVALID_STATE')
 if d['phase']!='dive' and d['balks']:fail('Balk counter exists outside an active dive',code='INVALID_STATE')
 if (d['phase'] in ('ready','dive'))!=(current(d) is not None):fail('Contest phase and remaining dives disagree',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase'];i=current(d)
 if k=='declare_programs':
  fields(p,dict(catalog=dict(type='array',minItems=6,maxItems=100,items=DIVE),programs=dict(type='array',minItems=8,maxItems=8,items=dict(type='array',minItems=6,maxItems=6,items=dict(type='integer',minimum=0,maximum=99)))),'/params')
  if phase!='setup':fail('Programs are locked when the contest starts')
  d['catalog']=deepcopy(p['catalog']);d['programs']=deepcopy(p['programs']);settle(d)
 elif k=='start_dive':
  fields(p,dict(participant=INDEX),'/params')
  if phase!='ready' or p['participant']!=i:fail('The next scheduled diver must start')
  d['phase']='dive'
 elif k in ('balk','fail_dive','judge_dive'):
  fields(p,dict(marks=MARKS) if k=='judge_dive' else {},'/params')
  if phase!='dive':fail('No announced dive is active')
  if k=='balk' and d['balks']==0:d['balks']=1
  else:
   result=dict(marks=p['marks'][:] if k=='judge_dive' else None,failed=k!='judge_dive',balks=2 if k=='balk' else d['balks'])
   d['entrants'][i]['results'].append(result);settle(d)
 elif k in ('withdraw','disqualify'):
  fields(p,dict(participant=INDEX),'/params');j=p['participant'];r=d['entrants'][j]
  if r['status']!='eligible':fail('Entrant is already excluded from classification')
  if k=='withdraw':
   if phase not in ('setup','ready') or len(r['results'])==6:fail('Withdraw between scheduled dives before completing the program')
   r['status']='dnf' if r['results'] else 'dns'
  else:r['status']='dq'
  if phase!='setup' and (phase!='dive' or i==j):settle(d)
 elif k=='correct_dive':
  fields(p,dict(participant=INDEX,dive=dict(type='integer',minimum=0,maximum=5),result=RESULT),'/params');r=d['entrants'][p['participant']]
  if phase!='review' or p['dive']>=len(r['results']):fail('Correct an existing dive during result review')
  r['results'][p['dive']]=deepcopy(p['result'])
 elif k=='confirm_result':
  fields(p,{},'/params')
  if phase!='review':fail('Resolve every scheduled dive first')
  d['phase']='finished'
 else:fail('Unknown diving action')
 return d
def legal(state):
 d=state['data'];phase=d['phase'];specs={};i=current(d)
 if phase=='setup':specs['declare_programs']=dict(catalog=dict(type='array',minItems=6,maxItems=100,items=DIVE),programs=dict(type='array',minItems=8,maxItems=8,items=dict(type='array',minItems=6,maxItems=6,items=dict(type='integer',minimum=0,maximum=99))))
 if phase=='ready':specs['start_dive']=dict(participant=INDEX)
 if phase=='dive':specs.update(balk={},fail_dive={},judge_dive=dict(marks=MARKS))
 if phase in ('setup','ready'):specs['withdraw']=dict(participant=INDEX)
 if phase!='finished':specs['disqualify']=dict(participant=INDEX)
 if phase=='review':specs.update(correct_dive=dict(participant=INDEX,dive=dict(type='integer',minimum=0,maximum=5),result=RESULT),confirm_result={})
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Locked program, round order, balk limit and result-review phase must permit the event.'],external_observations=['Official dive metadata and difficulty, seven final judge marks, balk or failed-dive decision.']) for k,v in specs.items()],constraints=dict(phase=phase,current_participant=i,next_dive=None if i is None else len(d['entrants'][i]['results']),score_unit_denominator=20),completeness=False,reason='official_diving_judgments')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';ranked=[]
 if done:
  for i,r in enumerate(d['entrants']):
   if r['status']=='eligible':ranked.append((sum(score(x,d['catalog'][d['programs'][i][j]]['difficulty_tenths']) for j,x in enumerate(r['results'])),i))
  ranked.sort(key=lambda x:(-x[0],x[1]))
 winners=[state['players'][i]['id'] for s,i in ranked if s==ranked[0][0]] if ranked else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other>s for other,_ in ranked),score_units=s,score_unit_denominator=20) for s,i in ranked],reason='dives_confirmed' if done else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official dive result confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
