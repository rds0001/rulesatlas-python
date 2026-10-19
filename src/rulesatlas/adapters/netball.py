"""Traditional seven-position netball, four timed quarters, drawn games allowed."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
TEAM=I(0,1);SLOT=I(0,11);BOOL=dict(type='boolean');POSITIONS=['GS','GA','WA','C','WD','GD','GK']
LINE=dict(type='array',minItems=7,maxItems=7,items=dict(I(0,11),nullable=True))
SCHEMAS=dict(set_roster=dict(team=TEAM,size=I(7,12),lineup=LINE),start_match=dict(first_centre=TEAM),centre_pass=dict(team=TEAM,player=SLOT),goal=dict(team=TEAM,player=SLOT),elapse=dict(milliseconds=I(1,900000)),pause={},resume={},change_lineup=dict(team=TEAM,lineup=LINE),warn=dict(team=TEAM,player=SLOT),suspend=dict(team=TEAM,player=SLOT),dismiss=dict(team=TEAM,player=SLOT),award_expiry_shot=dict(team=TEAM,player=SLOT),expiry_shot=dict(scored=BOOL),end_quarter={},start_next_quarter={},concede=dict(team=TEAM),no_contest={})
def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason,running=False,pending_shot=None,expiry_open=False)
def available(t,i):return not t['dismissed'][i] and t['suspension_ms'][i]==0

def lineup(t,new):
 ids=[i for i in new if i is not None]
 if len(ids)<5 or len(ids)!=len(set(ids)) or any(i>=len(t['warned']) or not available(t,i) for i in ids):fail('Lineup requires five to seven distinct eligible roster players')
 # A sanctioned position remains vacant until its occupant becomes eligible.
 for j,old in enumerate(t['lineup']):
  if old is not None and not available(t,old) and new[j]!=old:fail('A suspended or dismissed position cannot be filled by a substitute')
 t['lineup']=new

def playing(t):return [i for i in t['lineup'] if i is not None and available(t,i)]
def period(d):
 if d['phase']!='quarter':fail('Event requires an open quarter')
def scorer(d,team,i):
 t=d['teams'][team]
 if i not in t['lineup'][:2] or not available(t,i):fail('Only an eligible goal shooter or goal attack may score')
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in d['teams']:
  n=len(t['warned']);ids=[i for i in t['lineup'] if i is not None]
  if len(t['suspension_ms'])!=n or len(t['dismissed'])!=n or len(ids)!=len(set(ids)) or any(i>=n for i in ids):bad('Roster vectors and distinct position assignments must agree')
  if any(t['dismissed'][i] and t['suspension_ms'][i] for i in range(n)):bad('Dismissal supersedes a temporary suspension')
  if d['phase']!='finished' and len(playing(t))<5:bad('At least five eligible players are required to continue')
 if d['phase']=='pre_game' and (d['quarter']!=1 or d['remaining_ms']!=900000 or d['scores']!=[0,0] or any(any(t['warned']) or any(t['dismissed']) or any(t['suspension_ms']) for t in d['teams'])):bad('New match cannot contain playing or disciplinary history')
 if d['running'] and (d['phase']!='quarter' or not d['remaining_ms'] or d['pending_shot'] is not None):bad('Running clock requires an open quarter with time remaining')
 if d['phase'] in ('pre_game','interval','finished') and (d['running'] or d['pending_shot'] is not None or d['expiry_open']):bad('Inactive phase cannot retain an unresolved expiry play')
 if d['phase']=='interval' and (d['remaining_ms'] or d['quarter']>=4):bad('Quarter interval requires a completed non-final quarter')
 if d['expiry_open'] and (d['phase']!='quarter' or d['remaining_ms']):bad('Expiry decision requires a quarter at zero time')
 if d['pending_shot'] is not None:
  r=d['pending_shot']
  if d['phase']!='quarter' or d['remaining_ms'] or d['expiry_open'] or r['player'] not in d['teams'][r['team']]['lineup'][:2]:bad('Pending penalty shot must follow the expiry ruling and a shooting position')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason'] in ('draw','no_contest'))!=(d['winner'] is None):bad('Finished match needs a consistent result')
  if d['reason']=='points' and (d['quarter']!=4 or d['remaining_ms'] or d['scores'][d['winner']]<=d['scores'][1-d['winner']]):bad('Points win requires completed regulation and a lead')
  if d['reason']=='draw' and (d['quarter']!=4 or d['remaining_ms'] or d['scores'][0]!=d['scores'][1]):bad('Draw requires tied completed regulation')
 elif d['winner'] is not None or d['reason'] is not None:bad('Open match has no final result')

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in SCHEMAS:fail('Unknown netball event')
 fields(p,SCHEMAS[k],'/params')
 if d['phase']=='finished':fail('Match is finished')
 if k=='set_roster':
  if d['phase']!='pre_game':fail('Set rosters before starting')
  n=p['size'];t=dict(lineup=[None]*7,warned=[False]*n,suspension_ms=[0]*n,dismissed=[False]*n);lineup(t,p['lineup']);d['teams'][p['team']]=t
 elif k=='start_match':
  if d['phase']!='pre_game' or any(len(playing(t))!=7 for t in d['teams']):fail('This format starts with all seven positions occupied')
  d.update(phase='quarter',centre_team=p['first_centre'],centre_due=True,running=True)
 elif k=='centre_pass':
  period(d);t=d['teams'][p['team']]
  if not d['remaining_ms'] or not d['centre_due'] or p['team']!=d['centre_team'] or t['lineup'][3]!=p['player'] or not available(t,p['player']):fail('The next centre pass belongs to the eligible centre of the due team')
  d['centre_due']=False;d['centre_team']=1-d['centre_team']
 elif k=='goal':
  period(d)
  if d['centre_due'] or not d['remaining_ms']:fail('A goal requires a completed centre pass and time remaining')
  scorer(d,p['team'],p['player']);d['scores'][p['team']]+=1;d['centre_due']=True
 elif k=='elapse':
  period(d)
  if not d['running'] or p['milliseconds']>d['remaining_ms']:fail('Advance only running time within the quarter')
  dt=p['milliseconds'];d['remaining_ms']-=dt
  for t in d['teams']:t['suspension_ms']=[max(0,x-dt) for x in t['suspension_ms']]
  if not d['remaining_ms']:d['running']=False;d['expiry_open']=True
 elif k=='pause':
  period(d)
  if not d['running']:fail('Clock is already stopped')
  d['running']=False
 elif k=='resume':
  period(d)
  if d['running'] or not d['remaining_ms'] or d['pending_shot'] is not None:fail('Clock cannot resume at this stoppage')
  d['running']=True
 elif k=='change_lineup':
  if d['phase'] not in ('pre_game','interval') and (d['phase']!='quarter' or d['running'] or not d['remaining_ms']):fail('Lineup changes require an official substitution stoppage or interval')
  t=d['teams'][p['team']];new=p['lineup'];blocked={j:i for j,i in enumerate(t['lineup']) if i is not None and not available(t,i)}
  # Retain sanctioned player identifiers as vacancies; other players may change positions.
  eligible=[i for i in new if i is not None and i not in blocked.values()]
  if any(i not in new for i in blocked.values()) or len(eligible)<5 or len([i for i in new if i is not None])!=len(set(i for i in new if i is not None)) or any(i>=len(t['warned']) or not available(t,i) for i in eligible):fail('Substitution cannot fill a sanctioned position or introduce an ineligible player')
  t['lineup']=new
 elif k in ('warn','suspend','dismiss'):
  period(d);t=d['teams'][p['team']];i=p['player']
  if i>=len(t['warned']) or t['dismissed'][i]:fail('Discipline requires a roster player who has not been dismissed')
  if k=='warn':
   if t['warned'][i]:fail('An existing formal warning cannot be repeated')
   t['warned'][i]=True
  elif k=='suspend':
   if i not in playing(t):fail('Suspension requires an active eligible player')
   t['suspension_ms'][i]=120000
  else:t['dismissed'][i]=True;t['suspension_ms'][i]=0
  d['running']=False
  if len(playing(t))<5:finish(d,1-p['team'],'default')
 elif k=='award_expiry_shot':
  period(d)
  if not d['expiry_open'] or d['pending_shot'] is not None:fail('Only one unresolved expiry ruling is available')
  scorer(d,p['team'],p['player']);d['pending_shot']=dict(team=p['team'],player=p['player']);d['expiry_open']=False
 elif k=='expiry_shot':
  period(d);r=d['pending_shot']
  if r is None:fail('No expiry penalty shot is pending')
  scorer(d,r['team'],r['player'])
  if p['scored']:d['scores'][r['team']]+=1
  d['pending_shot']=None
 elif k=='end_quarter':
  period(d)
  if d['remaining_ms'] or d['pending_shot'] is not None:fail('Resolve time and any awarded penalty shot first')
  d['expiry_open']=False
  if d['quarter']==4:finish(d,None if d['scores'][0]==d['scores'][1] else 0 if d['scores'][0]>d['scores'][1] else 1,'draw' if d['scores'][0]==d['scores'][1] else 'points')
  else:d['phase']='interval'
 elif k=='start_next_quarter':
  if d['phase']!='interval':fail('No quarter interval is active')
  d.update(phase='quarter',quarter=d['quarter']+1,remaining_ms=900000,running=True,centre_due=True)
 elif k=='concede':finish(d,1-p['team'],'concession')
 elif k=='no_contest':finish(d,None,'no_contest')
 return d

def legal(state):
 d=state['data'];phase=d['phase'];names=[]
 if phase=='pre_game':names=['set_roster','change_lineup','start_match']
 elif phase=='interval':names=['change_lineup','start_next_quarter']
 elif phase=='quarter':
  names=['warn','suspend','dismiss']
  if d['remaining_ms']:
   names+=['centre_pass' if d['centre_due'] else 'goal']+(['pause','elapse'] if d['running'] else ['resume','change_lineup'])
  elif d['pending_shot'] is not None:names+=['expiry_shot']
  else:names+=['end_quarter']+(['award_expiry_shot'] if d['expiry_open'] else [])
 if phase!='finished':names+=['concede','no_contest']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Quarter, centre-pass order, position eligibility and sanction time must permit the event.'],external_observations=['Official goals, disciplinary rulings, substitution opportunities and expiry penalty shots.']) for k in names],constraints=dict(phase=phase,quarter=d['quarter'],remaining_ms=d['remaining_ms'],centre_team=d['centre_team'],centre_due=d['centre_due'],active=[playing(t) for t in d['teams']],shooters=[[i for i in t['lineup'][:2] if i is not None and available(t,i)] for t in d['teams']],pending_shot=d['pending_shot']),completeness=False,reason='official_netball_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if d['reason']=='draw' else 'no_contest' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
