"""Sequential timed heats with official start orders and cumulative classification."""
from copy import deepcopy
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
TIME=dict(type='integer',minimum=1,maximum=1000000000000,nullable=True)
STATUS=dict(type='enum',values=['finished','dns','dnf','dq'])
class TimedHeats:
 def __init__(self,config):self.c=config
 def eligible(self,d):return [i for i in range(8) if all(row[i]['status']=='finished' for row in d['results'][:d['heat']])]
 def next(self,d):return next((i for i in d['order'] if d['results'][d['heat']][i]['status']=='pending'),None)
 def validate(self,d):
  h=d['heat'];phase=d['phase'];eligible=self.eligible(d)
  for j,row in enumerate(d['results']):
   for i,r in enumerate(row):
    if (r['status']=='finished')!=(r['time_us'] is not None):fail('Only completed runs carry elapsed times',code='INVALID_STATE')
    if r['time_us'] is not None and r['time_us']%self.c['quantum_us']:fail('Elapsed time precision mismatch',code='INVALID_STATE')
    if j>h and r['status']!='not_eligible':fail('Future heat already has a result',code='INVALID_STATE')
    if j<h and r['status']=='pending':fail('Prior heat is unresolved',code='INVALID_STATE')
    if j<h and (r['status']=='not_eligible')!=any(old[i]['status']!='finished' for old in d['results'][:j]):fail('Prior heat eligibility mismatch',code='INVALID_STATE')
    if j<=h and j>0 and any(old[i]['status']!='finished' for old in d['results'][:j]) and r['status']!='not_eligible':fail('Failed earlier runs prevent continuation',code='INVALID_STATE')
  if phase=='configure':
   if d['order'] or any(r['status']!='not_eligible' for r in d['results'][h]):fail('Heat must await its official start order',code='INVALID_STATE')
  else:
   if sorted(d['order'])!=eligible:fail('Start order must include every eligible entrant once',code='INVALID_STATE')
   if any((i not in eligible)!=(r['status']=='not_eligible') for i,r in enumerate(d['results'][h])):fail('Current heat eligibility mismatch',code='INVALID_STATE')
   if (phase in ('run','active'))!=(self.next(d) is not None):fail('Heat phase and unresolved starts disagree',code='INVALID_STATE')
  if phase=='finished' and h+1<self.c['heats'] and any(r['status']=='finished' for r in d['results'][h]):fail('Remaining heats must be completed',code='INVALID_STATE')
 def apply(self,state,action):
  d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase'];h=d['heat'];row=d['results'][h]
  if k=='set_start_order':
   fields(p,dict(order=dict(type='array',minItems=0,maxItems=8,items=INDEX)),'/params')
   if phase!='configure' or sorted(p['order'])!=self.eligible(d):fail('Supply one official start for each eligible entrant')
   d['order']=p['order'][:]
   for i in d['order']:row[i]['status']='pending'
   d['phase']='run' if d['order'] else 'review'
  elif k=='start_next':
   fields(p,{},'/params')
   if phase!='run':fail('No next entrant can start now')
   d['phase']='active'
  elif k=='void_start':
   fields(p,{},'/params')
   if phase!='active':fail('Only an active run can be officially voided for a restart')
   d['phase']='run'
  elif k in ('record_result','amend_result'):
   schema=dict(status=STATUS,time_us=TIME)
   if k=='amend_result':schema['participant']=INDEX
   fields(p,schema,'/params')
   if k=='amend_result':
    if phase!='review' or p['participant'] not in d['order']:fail('Amend only an eligible current-heat result during review')
    i=p['participant']
   else:
    if phase not in ('run','active') or (phase=='run' and p['status'] not in ('dns','dq')):fail('A completed run requires a valid start; only DNS or exclusion can be recorded before starting')
    if phase=='active' and p['status']=='dns':fail('A started entrant cannot be DNS')
    i=self.next(d)
   if (p['status']=='finished')!=(p['time_us'] is not None):fail('Only a finished run has an elapsed time')
   if p['time_us'] is not None and p['time_us']%self.c['quantum_us']:fail('Elapsed time precision mismatch')
   row[i]=dict(status=p['status'],time_us=p['time_us'])
   if k=='record_result':d['phase']='run' if self.next(d) is not None else 'review'
  elif k=='confirm_heat':
   fields(p,{},'/params')
   if phase!='review':fail('Resolve every start and review the heat first')
   if h+1==self.c['heats'] or not any(r['status']=='finished' for r in row):d['phase']='finished'
   else:d['heat']+=1;d['order']=[];d['phase']='configure'
  else:fail('Unknown timed-heat action')
  return d
 def legal(self,state):
  d=state['data'];phase=d['phase'];specs={}
  if phase=='configure':specs['set_start_order']=dict(order=dict(type='array',minItems=0,maxItems=8,items=INDEX))
  if phase=='run':specs['start_next']={}
  if phase in ('run','active'):specs['record_result']=dict(status=STATUS,time_us=TIME)
  if phase=='active':specs['void_start']={}
  if phase=='review':specs.update(amend_result=dict(participant=INDEX,status=STATUS,time_us=TIME),confirm_heat={})
  return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Heat phase, next entrant, result status and timing precision must match.'],external_observations=['Official start order, valid completion, elapsed time, exclusion or authorized restart.']) for k,v in specs.items()],constraints=dict(phase=phase,heat=d['heat'],next_participant=self.next(d),quantum_us=self.c['quantum_us']),completeness=False,reason='official_timed_heat_events')
 def outcome(self,state,pack):
  d=state['data'];done=d['phase']=='finished';ranked=[]
  if done:
   ranked=sorted((sum(row[i]['time_us'] for row in d['results']),i) for i in range(8) if all(row[i]['status']=='finished' for row in d['results']))
  winners=[state['players'][i]['id'] for t,i in ranked if t==ranked[0][0]] if ranked else []
  return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(t2<t for t2,_ in ranked),total_time_us=t) for t,i in ranked],reason='aggregate_confirmed' if done else 'heat_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official heat confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
