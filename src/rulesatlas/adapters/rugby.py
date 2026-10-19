"""Official scoring, player eligibility and timed sanctions for two rugby codes."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
TEAM=I(0,1);SLOT=I(0,22);B=dict(type='boolean')
def active(t):return [i for i,s in enumerate(t['status']) if s=='active' and t['sin_bin_ms'][i]==0]
def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason,pending_kick=None,extra_penalty=False)
class Rugby:
 def __init__(self,code):
  self.code=code;self.union=code=='union';self.size=15 if self.union else 13;self.roster=23 if self.union else 17;self.values=dict(try_score=5 if self.union else 4,penalty=3 if self.union else 2,drop_goal=3 if self.union else 1,penalty_try=7 if self.union else 4)
  if not self.union:self.values['eight_point_try']=4
  self.schemas=dict(set_lineup=dict(team=TEAM,roster_size=I(self.size,self.roster),starters=dict(type='array',minItems=self.size,maxItems=self.size,items=SLOT)),start_half={},end_half={},score=dict(team=TEAM,player=SLOT,kind=dict(type='string',enum=list(self.values))),award_penalty_kick=dict(team=TEAM),resolve_kick=dict(player=SLOT,scored=B),card=dict(team=TEAM,player=SLOT,colour=dict(type='string',enum=['yellow','red'])),elapse_play=dict(milliseconds=I(1,3600000)),substitute=dict(team=TEAM,out=SLOT,**{'in':SLOT}),authorise_return=dict(team=TEAM,player=SLOT),abandon={},official_result=dict(winner=dict(TEAM,nullable=True)),concede=dict(team=TEAM))
 def limit(self,t):return self.size-t['permanent_reductions']
 def validate(self,d):
  bad=lambda m:fail(m,code='INVALID_STATE')
  for t in d['teams']:
   n=len(t['status'])
   if n<self.size or n>self.roster or any(len(t[k])!=n for k in ('yellow','sin_bin_ms','return_authorised')):bad('Rugby roster vectors must match the declared team size')
   if sum(s=='active' for s in t['status'])>self.limit(t):bad('Dismissal permanently reduces the permitted on-field complement')
   if t['permanent_reductions']>sum(s=='dismissed' for s in t['status']):bad('Permanent team reductions require dismissed players')
   if t['substitutions']>8:bad('This format allows eight replacement or interchange events')
   for i,s in enumerate(t['status']):
    if s=='dismissed' and t['sin_bin_ms'][i] or t['return_authorised'][i] and s!='off':bad('Player status conflicts with a temporary sanction or return permission')
    if self.union and t['yellow'][i]>=2 and s!='dismissed':bad('A second yellow card dismisses the union player')
  if d['phase']=='pre_match' and (d['scores']!=[0,0] or d['half']!=1 or any(t['substitutions'] or any(t['yellow']) or any(t['sin_bin_ms']) or t['permanent_reductions'] for t in d['teams'])):bad('Unstarted match cannot contain playing history')
  if d['phase']=='halftime' and d['half']!=1:bad('Halftime follows only the first half')
  if d['extra_penalty'] and (self.union or d['pending_kick'] is None or d['pending_kick']['kind']!='conversion'):bad('Additional penalty follows only a league eight-point-try conversion')
  if d['pending_kick'] is not None and d['phase']!='play':bad('Only a playing half may retain a pending kick')
  if d['phase']=='finished':
   if d['reason'] is None or (d['reason']=='draw')!=(d['winner'] is None) and d['reason']!='official':bad('Finished match requires a consistent result')
   if d['reason']=='points' and (d['half']!=2 or d['scores'][d['winner']]<=d['scores'][1-d['winner']]):bad('Points victory requires two completed halves and a lead')
   if d['reason']=='draw' and (d['half']!=2 or d['scores'][0]!=d['scores'][1]):bad('Regulation draw requires tied scores after two halves')
  elif d['winner'] is not None or d['reason'] is not None:bad('An open or abandoned match has no final competition result')
 def player(self,d,team,i):
  if i not in active(d['teams'][team]):fail('The event requires an eligible active player')
 def apply(self,state,action):
  d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase']
  if k not in self.schemas:fail('Unknown rugby event')
  fields(p,self.schemas[k],'/params')
  if phase=='finished' or phase=='abandoned' and k!='official_result':fail('Match is not open for playing events')
  if k=='set_lineup':
   if phase!='pre_match':fail('Rosters are fixed after kick-off')
   n=p['roster_size'];a=p['starters']
   if len(set(a))!=self.size or max(a)>=n:fail('Starting lineup must name distinct roster players')
   d['teams'][p['team']]=dict(status=['active' if i in a else 'bench' for i in range(n)],yellow=[0]*n,sin_bin_ms=[0]*n,return_authorised=[False]*n,permanent_reductions=0,substitutions=0)
  elif k=='start_half':
   if phase not in ('pre_match','halftime') or any(not active(t) for t in d['teams']):fail('No eligible half can start')
   if phase=='pre_match' and any(len(active(t))!=self.size for t in d['teams']):fail('This format starts with a full team')
   d['phase']='play'
   if phase=='halftime':d['half']=2
  elif k=='end_half':
   if phase!='play' or d['pending_kick'] is not None:fail('Resolve any awarded kick before the official half-end event')
   if d['half']==1:d['phase']='halftime'
   else:finish(d,None if d['scores'][0]==d['scores'][1] else 0 if d['scores'][0]>d['scores'][1] else 1,'draw' if d['scores'][0]==d['scores'][1] else 'points')
  elif k=='score':
   if phase!='play' or d['pending_kick'] is not None:fail('Scoring requires an open half without a pending kick')
   team=p['team'];self.player(d,team,p['player']);kind=p['kind'];d['scores'][team]+=self.values[kind]
   if kind=='try_score' or kind in ('penalty_try','eight_point_try') and not self.union:d['pending_kick']=dict(team=team,kind='conversion',value=2)
   d['extra_penalty']=kind=='eight_point_try'
  elif k=='award_penalty_kick':
   if phase!='play' or d['pending_kick'] is not None:fail('Only one penalty kick may be pending')
   d['pending_kick']=dict(team=p['team'],kind='penalty',value=self.values['penalty'])
  elif k=='resolve_kick':
   r=d['pending_kick']
   if phase!='play' or r is None:fail('No kick is pending')
   self.player(d,r['team'],p['player'])
   if p['scored']:d['scores'][r['team']]+=r['value']
   d['pending_kick']=dict(team=r['team'],kind='penalty',value=2) if d['extra_penalty'] else None;d['extra_penalty']=False
  elif k=='card':
   if phase not in ('play','halftime'):fail('Discipline is recorded during the match')
   t=d['teams'][p['team']];i=p['player']
   if i>=len(t['status']) or t['status'][i]=='dismissed':fail('Dismissed or absent player cannot receive another card')
   if p['colour']=='yellow':t['yellow'][i]+=1
   red=p['colour']=='red' or self.union and t['yellow'][i]>=2
   if red:
    if t['status'][i]=='active':t['permanent_reductions']+=1
    t['status'][i]='dismissed';t['sin_bin_ms'][i]=0;t['return_authorised'][i]=False
   else:t['sin_bin_ms'][i]+=600000
   if len(active(t))<(1 if self.union else 9):d['phase']='abandoned';d['pending_kick']=None;d['extra_penalty']=False
  elif k=='elapse_play':
   if phase!='play':fail('Only actual playing time serves temporary sanctions')
   for t in d['teams']:t['sin_bin_ms']=[max(0,x-p['milliseconds']) for x in t['sin_bin_ms']]
  elif k=='substitute':
   if phase not in ('play','halftime'):fail('Replacement requires a match opportunity certified by officials')
   t=d['teams'][p['team']];out=p['out'];inc=p['in'];self.player(d,p['team'],out)
   if inc>=len(t['status']) or inc==out or t['sin_bin_ms'][inc] or t['status'][inc] not in ('bench','off') or self.union and t['status'][inc]=='off' and not t['return_authorised'][inc]:fail('Incoming player is unavailable or lacks required return permission')
   counted=not self.union or t['status'][inc]=='bench'
   if counted and t['substitutions']>=8:fail('The replacement allowance is exhausted')
   t['status'][out]='off';t['status'][inc]='active';t['return_authorised'][inc]=False;t['substitutions']+=int(counted)
  elif k=='authorise_return':
   if not self.union or phase not in ('play','halftime'):fail('Special returning replacements apply only to this union format')
   t=d['teams'][p['team']];i=p['player']
   if i>=len(t['status']) or t['status'][i]!='off' or t['return_authorised'][i]:fail('Permission requires a previously replaced player')
   t['return_authorised'][i]=True
  elif k=='abandon':
   if phase=='pre_match':fail('The match has not started')
   d.update(phase='abandoned',pending_kick=None,extra_penalty=False)
  elif k=='official_result':
   if phase!='abandoned':fail('An external competition result applies only after abandonment')
   finish(d,p['winner'],'official')
  elif k=='concede':finish(d,1-p['team'],'concession')
  return d
 def legal(self,state):
  d=state['data'];phase=d['phase'];names=[]
  if phase=='pre_match':names=['set_lineup','start_half','concede']
  elif phase=='abandoned':names=['official_result']
  elif phase in ('play','halftime'):
   names=['card','substitute','abandon','concede']
   if self.union:names+=['authorise_return']
   if phase=='halftime':names+=['start_half']
   elif d['pending_kick'] is not None:names+=['resolve_kick','elapse_play']
   else:names+=['score','award_penalty_kick','end_half','elapse_play']
  return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=self.schemas[k],preconditions=['Half, active-player eligibility, pending kick and replacement allowance must permit the event.'],external_observations=['Official score, replacement entitlement, card, playing-time duration or completed half including required added time.']) for k in names],constraints=dict(phase=phase,half=d['half'],active=[active(t) for t in d['teams']],replacements_remaining=[8-t['substitutions'] for t in d['teams']],pending_kick=d['pending_kick']),completeness=False,reason='official_rugby_'+self.code+'_events')
 def outcome(self,state,pack):
  d=state['data'];done=d['phase']=='finished';w=d['winner'];abandoned=d['phase']=='abandoned'
  return dict(status='terminal' if done else 'awaiting_adjudication' if abandoned else 'ongoing',result_kind=('draw' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason=d['reason'] if done else 'competition_result_required' if abandoned else 'ongoing',evidence_required=['Official competition result after abandonment.'] if abandoned else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
