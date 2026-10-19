"""Futsal match events, rolling substitutes, timed reductions and shoot-outs."""
from copy import deepcopy
from . import football as fb
from ..values import fields,fail
TEAM=dict(type='integer',minimum=0,maximum=1)
SLOT=dict(type='integer',minimum=0,maximum=13)
BOOL=dict(type='boolean')
SCHEMAS=dict(configure=dict(knockout=BOOL,extra_time=BOOL),start_period={},end_period={},goal=dict(team=TEAM),card=dict(team=TEAM,player=SLOT,color=dict(type='string',enum=['yellow','red'])),substitute=dict(team=TEAM,out=SLOT,**{'in':SLOT}),enter_player=dict(team=TEAM,player=SLOT),set_goalkeeper=dict(team=TEAM,player=SLOT),elapsed_play=dict(milliseconds=dict(type='integer',minimum=1,maximum=1200000)),accumulated_foul=dict(team=TEAM,penalty_area=BOOL),award_penalty=dict(team=TEAM),resolve_kick=dict(scored=BOOL),timeout=dict(team=TEAM),end_timeout={},abandon_match={},start_shootout=dict(first_team=TEAM,excluded=dict(type='array',minItems=2,maxItems=2,items=dict(type='array',items=SLOT,maxItems=14))),exclude_kicker=dict(team=TEAM,player=SLOT),shootout_kick=dict(team=TEAM,player=SLOT,scored=BOOL))
SCHEMAS['set_lineup']=dict(team=TEAM,roster_size=dict(type='integer',minimum=3,maximum=14),starters=dict(type='array',minItems=3,maxItems=5,items=SLOT),goalkeeper=SLOT)
def active(t):return [i for i,s in enumerate(t['status']) if s=='active']
def available(t):return [i for i,s in enumerate(t['status']) if s!='dismissed']
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 phase=d['phase'];shoot=phase in ('shootout_setup','shootout') or d['shootout_started']
 if d['rules']['extra_time'] and not d['rules']['knockout']:bad('Extra time requires a knockout match')
 if d['extra_started'] and not (d['rules']['knockout'] and d['rules']['extra_time']):bad('Extra time is disabled')
 if phase in fb.EXTRA and not d['extra_started']:bad('Extra-time phase mismatch')
 if d['extra_started'] and phase in ('pre_match','first_half','halftime','second_half'):bad('Extra time has not begun')
 if shoot and (not d['rules']['knockout'] or d['goals'][0]!=d['goals'][1]):bad('Shoot-out requires a tied knockout match')
 if d['shootout_started'] and phase not in ('shootout','finished','abandoned'):bad('Shoot-out phase mismatch')
 if phase=='shootout' and not d['shootout_started']:bad('Shoot-out has not started')
 if d['timeout_team'] is not None and phase not in ('first_half','second_half'):bad('Timeout requires a regulation half')
 if d['pending_kick'] is not None and phase not in fb.PLAY:bad('Pending kick requires a playing period')
 if d['timeout_team'] is not None and d['pending_kick'] is not None:bad('Resolve the pending kick before a timeout')
 for t in d['teams']:
  n=len(t['status'])
  if len(t['yellow'])!=n or len(t['red'])!=n:bad('Player vectors differ in length')
  if any(red!=(s=='dismissed') or (y==2 and not red) for s,y,red in zip(t['status'],t['yellow'],t['red'])):bad('Card and eligibility mismatch')
  cap=5 if shoot else 5-len(t['reductions_ms'])
  if len(active(t))>cap or (phase in fb.PLAY+fb.BREAKS and len(active(t))<3):bad('Active player count conflicts with team reductions')
  if t['goalkeeper'] is not None and t['goalkeeper'] not in active(t):bad('Goalkeeper must be active')
  if phase=='pre_match' and t['reductions_ms']:bad('Pre-match dismissals do not start playing-time reductions')
  if len(set(t['eligible']))!=len(t['eligible']) or any(i not in available(t) for i in t['eligible']):bad('Invalid shoot-out eligibility')
  if len(set(t['taken']))!=len(t['taken']) or any(i not in t['eligible'] for i in t['taken']):bad('Invalid kicker cycle')
  if not shoot and (t['eligible'] or t['taken']):bad('Kicker cycle exists before a shoot-out')
  if d['shootout_started'] and t['goalkeeper'] is not None and t['goalkeeper'] not in t['eligible']:bad('Shoot-out goalkeeper must be eligible')
 a=d['shootout_attempts'];g=d['shootout_goals'];first=d['shootout_first']
 if any(g[i]>a[i] for i in (0,1)) or a[first]-a[1-first] not in (0,1):bad('Invalid shoot-out counters')
 if not d['shootout_started'] and (a!=[0,0] or g!=[0,0]):bad('Shoot-out has not started')
 if phase=='shootout' and fb.penalty_winner(d) is not None:bad('Shoot-out is already decided')
 if phase=='finished' and d['rules']['knockout'] and d['goals'][0]==d['goals'][1] and fb.penalty_winner(d) is None:bad('Knockout winner is unresolved')
 if phase=='pre_match' and (d['goals']!=[0,0] or d['extra_started'] or d['shootout_started'] or any(t['fouls'] or t['timeout_used'] for t in d['teams'])):bad('Pre-match counters are not empty')
def score(d,team):
 d['goals'][team]+=1;other=d['teams'][1-team]
 if len(active(d['teams'][team]))>len(active(other)) and other['reductions_ms']:
  other['reductions_ms'].remove(min(other['reductions_ms']))
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase']
 if k not in SCHEMAS:fail('Unknown futsal event')
 fields(p,SCHEMAS[k],'/params')
 if phase in ('finished','abandoned'):fail('Match is not open')
 if k=='configure':
  if phase!='pre_match':fail('Rules are fixed after kick-off')
  d['rules']=deepcopy(p)
 elif k=='set_lineup':
  t=d['teams'][p['team']];n=p['roster_size'];starters=p['starters']
  if phase!='pre_match' or any(t['yellow']) or any(t['red']):fail('Set the lineup before kickoff and disciplinary events')
  if len(set(starters))!=len(starters) or max(starters)>=n or p['goalkeeper'] not in starters:fail('Invalid starting lineup')
  t.update(status=['active' if i in starters else 'bench' for i in range(n)],yellow=[0]*n,red=[False]*n,goalkeeper=p['goalkeeper'])
 elif k=='start_period':
  mapping={'pre_match':'first_half','halftime':'second_half','extra_break':'extra_first','extra_halftime':'extra_second'}
  if phase not in mapping or any(len(active(t))<3 or t['goalkeeper'] is None for t in d['teams']):fail('A new period requires three eligible players and a goalkeeper per team')
  d['phase']=mapping[phase]
  if phase in ('pre_match','halftime'):
   for t in d['teams']:t['fouls']=0;t['timeout_used']=False
 elif k=='end_period':
  if phase not in fb.PLAY or d['pending_kick'] is not None or d['timeout_team'] is not None:fail('Resolve the pending kick or timeout before ending a period')
  if phase=='first_half':d['phase']='halftime'
  elif phase=='extra_first':d['phase']='extra_halftime'
  elif d['goals'][0]!=d['goals'][1] or not d['rules']['knockout']:d['phase']='finished'
  elif phase=='second_half' and d['rules']['extra_time']:d['phase']='extra_break';d['extra_started']=True
  else:
   d['phase']='shootout_setup'
   for t in d['teams']:t['yellow']=[0]*len(t['status']);t['eligible']=available(t);t['taken']=[];t['reductions_ms']=[]
 elif k in ('goal','accumulated_foul','award_penalty','elapsed_play','timeout'):
  if phase not in fb.PLAY or d['timeout_team'] is not None:fail('Event requires an active playing period')
  if k=='elapsed_play':
   for t in d['teams']:t['reductions_ms']=[x-p['milliseconds'] for x in t['reductions_ms'] if x>p['milliseconds']]
  elif k=='accumulated_foul':
   if d['pending_kick'] is not None:fail('Resolve the pending kick first')
   t=d['teams'][p['team']];t['fouls']+=1
   if p['penalty_area'] or t['fouls']>=6:d['pending_kick']=dict(team=1-p['team'],kind='penalty' if p['penalty_area'] else 'sixth_foul')
  elif k=='award_penalty':
   if d['pending_kick'] is not None:fail('Resolve the pending kick first')
   d['teams'][1-p['team']]['fouls']+=1;d['pending_kick']=dict(team=p['team'],kind='penalty')
  elif k=='goal':
   if d['pending_kick'] is not None or any(t['goalkeeper'] is None for t in d['teams']):fail('Resolve the pending kick and goalkeeper eligibility first')
   score(d,p['team'])
  else:
   if phase not in ('first_half','second_half') or d['pending_kick'] is not None or d['teams'][p['team']]['timeout_used']:fail('One timeout per regulation half is available')
   d['teams'][p['team']]['timeout_used']=True;d['timeout_team']=p['team']
 elif k=='end_timeout':
  if d['timeout_team'] is None:fail('No timeout is active')
  d['timeout_team']=None
 elif k=='resolve_kick':
  if d['pending_kick'] is None or any(t['goalkeeper'] is None for t in d['teams']):fail('A pending kick and eligible goalkeepers are required')
  if p['scored']:score(d,d['pending_kick']['team'])
  d['pending_kick']=None
 elif k=='card':
  t=d['teams'][p['team']];i=p['player']
  if i>=len(t['status']) or t['red'][i]:fail('Player is unavailable for another card')
  if p['color']=='yellow':t['yellow'][i]+=1
  if p['color']=='red' or t['yellow'][i]==2:
   was_active=t['status'][i]=='active';t['red'][i]=True;t['status'][i]='dismissed'
   if t['goalkeeper']==i:t['goalkeeper']=None
   t['eligible']=[x for x in t['eligible'] if x!=i];t['taken']=[x for x in t['taken'] if x!=i]
   if was_active and phase in fb.PLAY+fb.BREAKS:
    t['reductions_ms'].append(120000)
    if len(active(t))<3:d['phase']='abandoned';d['pending_kick']=None;d['timeout_team']=None
 elif k in ('substitute','enter_player','set_goalkeeper'):
  t=d['teams'][p['team']];i=p.get('in',p.get('player'));shoot=phase in ('shootout_setup','shootout')
  if i>=len(t['status']) or t['status'][i]=='dismissed':fail('Player is ineligible')
  if k=='set_goalkeeper':
   if shoot and i in t['eligible'] and t['status'][i]=='bench':
    if t['goalkeeper'] is not None:t['status'][t['goalkeeper']]='bench'
    elif len(active(t))>=5:fail('Choose an active eligible goalkeeper')
    t['status'][i]='active'
   if i not in active(t) or (d['shootout_started'] and i not in t['eligible']):fail('Goalkeeper must be active and eligible')
   t['goalkeeper']=i
  else:
   if shoot:fail('Normal substitutions end before the shoot-out')
   if t['status'][i]!='bench':fail('An available substitute must enter')
   if k=='substitute':
    j=p['out']
    if j not in active(t):fail('Only an active player can leave')
    t['status'][j]='bench'
    if t['goalkeeper']==j:t['goalkeeper']=i
   elif len(active(t))>=5-len(t['reductions_ms']):fail('No replacement slot is available')
   t['status'][i]='active'
 elif k=='start_shootout':
  if phase!='shootout_setup':fail('Shoot-out is not ready')
  target=min(len(t['eligible']) for t in d['teams'])
  for t,excluded in zip(d['teams'],p['excluded']):
   if len(excluded)!=len(t['eligible'])-target:fail('Only the larger eligible squad is reduced to equal numbers')
   if len(set(excluded))!=len(excluded) or any(i not in t['eligible'] for i in excluded) or t['goalkeeper'] in excluded:fail('Invalid shoot-out exclusions')
   t['eligible']=[i for i in t['eligible'] if i not in excluded]
  if not d['teams'][0]['eligible'] or len(d['teams'][0]['eligible'])!=len(d['teams'][1]['eligible']) or any(t['goalkeeper'] is None for t in d['teams']):fail('Shoot-out requires equal eligible squads and goalkeepers')
  d['shootout_first']=p['first_team'];d['shootout_started']=True;d['phase']='shootout'
 elif k=='exclude_kicker':
  if phase!='shootout':fail('Shoot-out is not active')
  t=d['teams'][p['team']];i=p['player']
  if len(t['eligible'])<=len(d['teams'][1-p['team']]['eligible']) or i not in t['eligible'] or i==t['goalkeeper']:fail('Exclusion must equalize eligible squads')
  t['eligible'].remove(i);t['taken']=[x for x in t['taken'] if x!=i]
 elif k=='shootout_kick':
  if phase!='shootout':fail('Shoot-out is not active')
  a=d['shootout_attempts'];team=p['team'];t=d['teams'][team];i=p['player'];expected=d['shootout_first'] if a[0]==a[1] else 1-d['shootout_first']
  if team!=expected or len(t['eligible'])!=len(d['teams'][1-team]['eligible']) or any(x['goalkeeper'] is None for x in d['teams']):fail('Wrong turn or unresolved shoot-out eligibility')
  if set(t['taken'])==set(t['eligible']):t['taken']=[]
  if i not in t['eligible'] or i in t['taken']:fail('Kicker is ineligible or has already kicked this cycle')
  t['taken'].append(i);a[team]+=1;d['shootout_goals'][team]+=int(p['scored'])
  if fb.penalty_winner(d) is not None:d['phase']='finished'
 elif k=='abandon_match':d['phase']='abandoned';d['pending_kick']=None;d['timeout_team']=None
 return d
def legal(state):
 d=state['data'];phase=d['phase'];names=[]
 if phase not in ('finished','abandoned'):
  names=['card','set_goalkeeper','abandon_match']
  if phase not in ('shootout_setup','shootout'):names+=['substitute','enter_player']
 if phase=='pre_match':names+=['configure','set_lineup','start_period']
 if phase in fb.BREAKS:names+=['start_period']
 if phase in fb.PLAY:
  if d['timeout_team'] is not None:names+=['end_timeout']
  elif d['pending_kick'] is not None:names+=['resolve_kick','elapsed_play']
  else:names+=['goal','accumulated_foul','award_penalty','elapsed_play','end_period']+(['timeout'] if phase in ('first_half','second_half') else [])
 if phase=='shootout_setup':names+=['start_shootout']
 if phase=='shootout':names+=['exclude_kicker','shootout_kick']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Match phase, player eligibility and pending decisions must permit the event.'],external_observations=['Official period timing, playing-time elapsed, foul, timeout entitlement or goal decision.']) for k in names],constraints=dict(phase=phase,teams=[dict(active=active(t),replacement_slots=max(0,5-len(t['reductions_ms'])-len(active(t))),fouls=t['fouls'],next_kickers=[i for i in t['eligible'] if i not in t['taken']] or t['eligible']) for t in d['teams']]),completeness=False,reason='official_futsal_events')
def outcome(state,pack):return fb.outcome(state,pack)
