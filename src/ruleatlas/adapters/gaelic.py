"""Traditional one-point Gaelic football and hurling match bookkeeping."""
from copy import deepcopy
from .rugby import Rugby,active
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
class Gaelic:
 def __init__(self,kind):
  self.kind=kind;self.football=kind=='football';self.base=Rugby('union');self.schemas=deepcopy(self.base.schemas)
  self.schemas['score']=dict(team=I(0,1),player=I(0,22),kind=dict(type='string',enum=['goal','point']))
  self.schemas['resolve_kick']=dict(player=I(0,22),result=dict(type='string',enum=['goal','point','none']))
  self.schemas['card']['colour']['enum']=['yellow','red']+(['black'] if self.football else [])
  self.schemas['set_goalkeeper']=dict(team=I(0,1),player=I(0,22))
 def enrich(self,d):
  d=deepcopy(d)
  if not self.football:
   for t in d['teams']:t.update(black=[0]*len(t['status']),sin_bin_ms=[0]*len(t['status']))
  return d
 def project(self,d):return dict(self.enrich(d),extra_penalty=False)
 def validate(self,d):
  d=self.enrich(d);self.base.validate(self.project(d));bad=lambda m:fail(m,code='INVALID_STATE')
  if d['phase']=='pre_match' and any(any(t['black']) for t in d['teams']):bad('Unstarted match cannot contain black cards')
  if d['scores']!=[3*d['goals'][i]+d['points'][i] for i in (0,1)]:bad('Total must equal three per goal plus one per point')
  for t in d['teams']:
   if len(t['black'])!=len(t['status']) or not self.football and any(t['black']):bad('Black-card vector must match the declared code and roster')
   if t['substitutions']>5:bad('This regulation format permits five ordinary permanent substitutions')
   if t['goalkeeper'] is not None and t['goalkeeper'] not in active(t):bad('Goalkeeper must be an eligible active player')
   if any(t['yellow'][i]+t['black'][i]>=2 and s!='dismissed' for i,s in enumerate(t['status'])):bad('Combined repeat cards require dismissal')
  if d['pending_kick'] is not None and (d['pending_kick']['kind']!='penalty' or d['pending_kick']['value']!=3):bad('Only a three-point penalty-goal opportunity may remain pending')
 def apply(self,state,action):
  d=self.enrich(state['data']);k=action['type'];p=action['params'];phase=d['phase']
  if k not in self.schemas:fail('Unknown Gaelic games event')
  fields(p,self.schemas[k],'/params')
  if phase=='finished' or phase=='abandoned' and k!='official_result':fail('Match is not open')
  if k=='score':
   if phase!='play' or d['pending_kick'] is not None or any(t['goalkeeper'] is None for t in d['teams']):fail('Resolve the pending penalty and goalkeeper assignments before scoring')
   team=p['team'];self.base.player(d,team,p['player']);d['goals' if p['kind']=='goal' else 'points'][team]+=1;d['scores'][team]+=3 if p['kind']=='goal' else 1
  elif k=='resolve_kick':
   r=d['pending_kick']
   if phase!='play' or r is None or any(t['goalkeeper'] is None for t in d['teams']):fail('An eligible penalty and both goalkeepers are required')
   self.base.player(d,r['team'],p['player'])
   if p['result']!='none':d['goals' if p['result']=='goal' else 'points'][r['team']]+=1;d['scores'][r['team']]+=3 if p['result']=='goal' else 1
   d['pending_kick']=None
  elif k=='set_goalkeeper':
   if phase not in ('pre_match','play','halftime'):fail('Goalkeeper designation requires an open match')
   self.base.player(d,p['team'],p['player']);d['teams'][p['team']]['goalkeeper']=p['player']
  elif k=='card':
   if phase not in ('play','halftime'):fail('Cards require a started match')
   t=d['teams'][p['team']];i=p['player'];colour=p['colour']
   if i>=len(t['status']) or t['status'][i]=='dismissed':fail('Player is absent or already dismissed')
   if colour=='black' and i not in active(t):fail('A black-card suspension requires an active eligible player')
   if colour in ('yellow','black'):t[colour][i]+=1
   red=colour=='red' or t['yellow'][i]+t['black'][i]>=2
   if red:
    if t['status'][i]=='active':t['permanent_reductions']+=1
    t['status'][i]='dismissed';t['sin_bin_ms'][i]=0;t['return_authorised'][i]=False
   elif colour=='black':t['sin_bin_ms'][i]=600000
   if t['goalkeeper']==i and i not in active(t):t['goalkeeper']=None
   if not active(t):d.update(phase='abandoned',pending_kick=None)
  else:
   if k=='start_half' and any(t['goalkeeper'] is None for t in d['teams']):fail('Designate both goalkeepers before starting the half')
   if k=='substitute':
    t=d['teams'][p['team']];inc=p['in']
    if inc<len(t['status']) and t['status'][inc]=='bench' and t['substitutions']>=5:fail('The five-substitution allowance is exhausted')
   projected=dict(state,data=self.project(d));d=self.base.apply(projected,action);d.pop('extra_penalty')
   if k=='set_lineup':d['teams'][p['team']].update(black=[0]*p['roster_size'],goalkeeper=p['starters'][0])
   if k=='substitute' and d['teams'][p['team']]['goalkeeper']==p['out']:d['teams'][p['team']]['goalkeeper']=p['in']
  if not self.football:
   for t in d['teams']:t.pop('black');t.pop('sin_bin_ms')
  return d
 def legal(self,state):
  d=self.enrich(state['data']);phase=d['phase'];names=[]
  if phase=='pre_match':names=['set_lineup','set_goalkeeper','start_half','concede']
  elif phase=='abandoned':names=['official_result']
  elif phase in ('play','halftime'):
   names=['card','set_goalkeeper','substitute','authorise_return','abandon','concede']
   if phase=='halftime':names+=['start_half']
   else:
    names+=['elapse_play']
    if d['pending_kick'] is None:names+=['end_half','award_penalty_kick']+([] if any(t['goalkeeper'] is None for t in d['teams']) else ['score'])
    elif all(t['goalkeeper'] is not None for t in d['teams']):names+=['resolve_kick']
  return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=self.schemas[k],preconditions=['Half, player and goalkeeper eligibility, pending penalty and substitution allowance must permit the event.'],external_observations=['Official score, card, replacement entitlement and completed playing time.']) for k in names],constraints=dict(phase=phase,half=d['half'],totals=d['scores'],active=[active(t) for t in d['teams']],substitutions_remaining=[5-t['substitutions'] for t in d['teams']],pending_kick=d['pending_kick']),completeness=False,reason='official_gaelic_'+self.kind+'_events')
 def outcome(self,state,pack):return self.base.outcome(state,pack)
