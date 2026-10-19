"""Lap-based sprint classification from official timing-line crossings."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
P=I(0,7);TIME=I(1,1000000000)
SCHEMAS=dict(configure=dict(laps=I(1,200)),start={},cross_line=dict(player=P,elapsed_ms=TIME),withdraw=dict(player=P),disqualify=dict(player=P),time_penalty=dict(player=P,milliseconds=I(0,1000000)),suspend={},resume={},cancel_race={},end_early=dict(cutoff_ms=I(0,1000000000)),confirm={},amend_timing=dict(player=P,laps=dict(type='array',minItems=0,maxItems=200,items=TIME),status=dict(type='string',enum=['finished','retired','dns','dq'])))
class CircuitRace:
 def __init__(self,kind):self.kind=kind;self.percent=90 if kind=='circuit' else 0
 def classified(self,d):
  if d['end_mode'] is None:return []
  maxlaps=max((len(r['laps']) for r in d['runners'] if r['status'] not in ('dns','dq')),default=0)
  if maxlaps==0:return []
  threshold=maxlaps*self.percent//100
  return [i for i,r in enumerate(d['runners']) if r['status'] not in ('ready','dns','dq','running') and len(r['laps'])>=threshold and (self.kind!='circuit' or len(r['laps'])>0)]
 def key(self,r):return (-len(r['laps']),(r['laps'][-1] if r['laps'] else 0)+r['penalty_ms'])
 def settle(self,d):
  if not any(r['status']=='running' for r in d['runners']):d['phase']='review' if d['end_mode'] is not None else 'suspended'
 def validate(self,d):
  bad=lambda m:fail(m,code='INVALID_STATE');phase=d['phase']
  for r in d['runners']:
   times=r['laps']
   if len(times)>d['target_laps'] or any(a>=b for a,b in zip(times,times[1:])) or times and times[-1]>d['elapsed_ms']:bad('Lap crossings must increase and stay within race timing and distance')
   if r['status'] in ('ready','dns') and times:bad('A nonstarter cannot have completed laps')
   if r['status']=='ready' and phase!='ready' or r['status']=='running' and phase not in ('racing','suspended'):bad('Participant status disagrees with race phase')
   if r['status']=='finished' and d['end_mode'] is None:bad('Finisher requires an official race-end condition')
   if r['status']=='finished' and d['end_mode']=='normal' and (not times or times[-1]<d['checkered_ms']):bad('Normal finisher must cross after the leader receives the checkered flag')
   if d['end_mode']=='early' and times and times[-1]>d['cutoff_ms']:bad('Early result cannot retain timing beyond the official countback cutoff')
  if (d['end_mode']=='normal')!=(d['checkered_ms'] is not None) or (d['end_mode']=='early')!=(d['cutoff_ms'] is not None):bad('Race-end mode must match its flag or countback timestamp')
  if d['checkered_ms'] is not None and d['checkered_ms']>d['elapsed_ms']:bad('Checkered flag cannot occur after the latest official timing event')
  if phase=='ready' and (d['elapsed_ms'] or d['end_mode'] is not None or any(r['laps'] for r in d['runners'])):bad('Unstarted race cannot contain timing or a result')
  if phase in ('review','finished') and (d['end_mode'] is None or any(r['status'] in ('ready','running') for r in d['runners'])):bad('Result review requires every entrant resolved and an end condition')
 def apply(self,state,action):
  d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase']
  if k not in SCHEMAS:fail('Unknown circuit-race event')
  fields(p,SCHEMAS[k],'/params')
  if phase=='finished':fail('Result is final')
  if k=='configure':
   if phase!='ready':fail('Race distance is fixed after the start')
   d['target_laps']=p['laps']
  elif k=='start':
   if phase!='ready' or not any(r['status']=='ready' for r in d['runners']):fail('Start requires an eligible grid')
   for r in d['runners']:
    if r['status']=='ready':r['status']='running'
   d['phase']='racing'
  elif k=='cross_line':
   r=d['runners'][p['player']];time=p['elapsed_ms']
   if phase!='racing' or r['status']!='running' or time<d['elapsed_ms'] or r['laps'] and time<=r['laps'][-1]:fail('Timing crossings must be chronological for an active racer')
   r['laps'].append(time);d['elapsed_ms']=time
   if d['end_mode'] is None and len(r['laps'])==d['target_laps']:d.update(end_mode='normal',checkered_ms=time)
   if d['end_mode']=='normal':r['status']='finished'
   self.settle(d)
  elif k in ('withdraw','disqualify'):
   r=d['runners'][p['player']]
   if k=='withdraw':
    if r['status'] not in ('ready','running') or phase not in ('ready','racing','suspended'):fail('Only an unstarted or active racer may withdraw')
    r['status']='dns' if phase=='ready' else 'retired'
   else:
    if r['status']=='dq':fail('Racer is already disqualified')
    r['status']='dq'
   if phase in ('racing','suspended'):self.settle(d)
  elif k=='time_penalty':
   if phase not in ('racing','suspended','review') or d['runners'][p['player']]['status'] in ('dns','dq'):fail('A time penalty requires a started, non-disqualified racer')
   d['runners'][p['player']]['penalty_ms']=p['milliseconds']
  elif k=='suspend':
   if phase!='racing' or d['end_mode'] is not None:fail('Suspend an unfinished race before the checkered flag')
   d['phase']='suspended'
  elif k=='resume':
   if phase!='suspended' or not any(r['status']=='running' for r in d['runners']):fail('Resume requires an active racer in a suspended race')
   d['phase']='racing'
  elif k=='end_early':
   if phase!='suspended' or p['cutoff_ms']>d['elapsed_ms']:fail('Early classification requires suspension and a recorded timing cutoff')
   cutoff=p['cutoff_ms'];d.update(end_mode='early',cutoff_ms=cutoff,checkered_ms=None)
   for r in d['runners']:
    r['laps']=[t for t in r['laps'] if t<=cutoff]
    if r['status']=='running':r['status']='retired'
   d['phase']='review'
  elif k=='cancel_race':
   if phase not in ('ready','suspended'):fail('Cancel only an unstarted or suspended race')
   d.update(phase='review',end_mode='early',cutoff_ms=0,checkered_ms=None)
   for r in d['runners']:
    r['laps']=[]
    if r['status']=='ready':r['status']='dns'
    elif r['status']=='running':r['status']='retired'
  elif k=='amend_timing':
   if phase!='review':fail('Timing corrections require result review')
   r=d['runners'][p['player']];r.update(laps=p['laps'],status=p['status']);d['elapsed_ms']=max(d['elapsed_ms'],max(p['laps'],default=0))
  elif k=='confirm':
   if phase!='review':fail('Resolve all racers before confirming classification')
   d['phase']='finished'
  return d
 def legal(self,state):
  d=state['data'];phase=d['phase'];names=dict(ready=['configure','start','withdraw','disqualify','cancel_race'],racing=['cross_line','withdraw','disqualify','time_penalty']+(['suspend'] if d['end_mode'] is None else []),suspended=['resume','withdraw','disqualify','time_penalty','end_early','cancel_race'],review=['amend_timing','disqualify','time_penalty','confirm'],finished=[])[phase]
  return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Race phase, chronological crossings, distance and participant eligibility must permit the event.'],external_observations=['Official timing-line crossings, penalties, retirements, suspension or classification cutoff.']) for k in names],constraints=dict(phase=phase,target_laps=d['target_laps'],completed_laps=[len(r['laps']) for r in d['runners']],checkered_ms=d['checkered_ms'],classification_percent=self.percent,provisionally_classified=self.classified(d)),completeness=False,reason='official_'+self.kind+'_sprint_events')
 def outcome(self,state,pack):
  d=state['data'];done=d['phase']=='finished';ids=self.classified(d);ids.sort(key=lambda i:(self.key(d['runners'][i]),i));best=self.key(d['runners'][ids[0]]) if ids else None;w=[i for i in ids if self.key(d['runners'][i])==best]
  return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ids else 'no_contest') if done else 'none',winners=[state['players'][i]['id'] for i in w] if done else [],losers=[state['players'][i]['id'] for i in ids if i not in w] if done else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(self.key(d['runners'][j])<self.key(d['runners'][i]) for j in ids),laps=len(d['runners'][i]['laps']),adjusted_ms=self.key(d['runners'][i])[1]) for i in ids] if done else [],reason='classification_confirmed' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
