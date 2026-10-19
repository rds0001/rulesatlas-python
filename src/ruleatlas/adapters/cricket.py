"""Twenty-over league cricket, expressed as completed delivery and official events."""
from copy import deepcopy
from ..values import fields,fail
T=dict(type='integer',minimum=0,maximum=1)
P=dict(type='integer',minimum=0,maximum=10)
NP=dict(P,nullable=True)
B=dict(type='boolean')
def enum(*x):return dict(type='enum',values=list(x))
def batting(d):return d['first_batting'] if d['innings']==1 else 1-d['first_batting']
def fielding(d):return 1-batting(d)
def end_innings(d):
 t=batting(d);d['bowler']=None;d['striker']=None;d['non_striker']=None;d['free_hit']=False
 if d['innings']==1:d['phase']='interval';d['target']=d['runs'][t]+1
 else:
  d['phase']='finished';d['reason']='chase' if d['runs'][t]>=d['target'] else 'tie' if d['runs'][t]==d['target']-1 else 'defended'
  d['winner']=t if d['reason']=='chase' else None if d['reason']=='tie' else 1-t

def check_end(d):
 t=batting(d)
 if d['innings']==2 and d['runs'][t]>=d['target'] or d['wickets'][t]>=10 or d['balls'][t]>=120:end_innings(d)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if sum(d['bowled'][1-t])!=d['balls'][t]:bad('Bowler legal-ball totals must equal the opposing innings ball count')
  if sum(x=='out' for x in d['batters'][t])!=d['wickets'][t]:bad('Wickets must agree with dismissed batters')
 if len(set(d['over_bowlers']))!=len(d['over_bowlers']) or len(set(d['previous_bowlers']))!=len(d['previous_bowlers']):bad('Over bowler lists cannot repeat a player')
 t=batting(d);f=1-t
 if d['phase']=='play':
  positions=[i for i in (d['striker'],d['non_striker']) if i is not None]
  if len(set(positions))!=len(positions):bad('The two batting ends require different batters')
  if any(d['batters'][t][i]!='in' or not d['eligible'][t][i] for i in positions):bad('Assigned batters must be eligible and at the crease')
  if [i for i,s in enumerate(d['batters'][t]) if s=='in']!=sorted(positions):bad('Crease assignments and batting statuses must agree')
  if d['bowler'] is not None and (not d['eligible'][f][d['bowler']] or d['bowler'] in d['previous_bowlers'] or d['bowler'] not in d['over_bowlers'] or d['bowled'][f][d['bowler']]>=24):bad('Current bowler violates eligibility, consecutive-over or quota restrictions')
  if d['wickets'][t]>=10 or d['balls'][t]>=120 or d['innings']==2 and d['runs'][t]>=d['target']:bad('Completed innings cannot remain active')
 if d['innings']==1 and d['phase'] in ('pre','play') and d['target'] is not None or (d['innings']==2 or d['phase']=='interval') and (d['target'] is None or d['target']!=d['runs'][d['first_batting']]+1):bad('Chase target must be one above the first innings total')
 if d['phase']=='interval' and d['innings']!=1:bad('Only the first innings is followed by the innings interval')
 if d['phase']=='interval' or d['phase']=='finished' and d['reason'] in ('tie','defended'):
  available=sum(d['eligible'][t][j] and d['batters'][t][j]!='out' for j in range(11))
  if d['balls'][t]<120 and d['wickets'][t]<10 and available>=2:bad('An innings cannot end before its ball limit, dismissal limit or lack of eligible batters')
 if d['phase']=='pre' and (d['innings']!=1 or any(d['runs']) or any(d['balls']) or any(d['wickets'])):bad('Pre-match state precedes scoring and dismissals')
 if d['phase']=='finished':
  if d['reason'] in ('chase','tie','defended'):
   if d['innings']!=2:bad('A regulation result needs two innings')
   expected=t if d['runs'][t]>=d['target'] else None if d['runs'][t]==d['target']-1 else 1-t
   if d['winner']!=expected:bad('Final winner disagrees with the chase score')
   expected_reason='chase' if d['runs'][t]>=d['target'] else 'tie' if expected is None else 'defended'
   if d['reason']!=expected_reason:bad('Result reason disagrees with the chase score')
  elif d['reason']=='forfeit':
   if d['winner'] is None:bad('Forfeit needs a winner')
  elif d['reason'] not in ('official_result','no_result'):bad('Finished match needs a reason')
 elif d['winner'] is not None or d['reason'] is not None:bad('Only a finished match has a declared result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 if ph=='pre':s['start_match']=dict(first_batting=T)
 if ph=='interval':s['start_second_innings']={}
 if ph=='play':
  s.update(nominate_batter=dict(player=P,end=enum('striker','non_striker')),nominate_bowler=dict(player=P),replace_bowler={},retire=dict(player=P,may_return=B),dismiss_non_delivery=dict(player=P,kind=enum('timed_out','obstructing','retired_out')),penalty_runs=dict(team=T,runs=dict(type='integer',minimum=5,maximum=5)),end_unavailable={})
  if d['bowler'] is not None and d['striker'] is not None and d['non_striker'] is not None:
   s['delivery']=dict(kind=enum('legal','wide','no_ball','dead'),bat_runs=dict(type='integer',minimum=0,maximum=12),extra_runs=dict(type='integer',minimum=0,maximum=12),extra_kind=enum('none','byes','leg_byes'),completed_runs=dict(type='integer',minimum=0,maximum=12),boundary=dict(type='integer',minimum=0,maximum=6),dismissal=enum('none','bowled','caught','lbw','stumped','hit_wicket','run_out','obstructing','hit_ball_twice'),out_player=NP)
 s.update(exclude=dict(team=T,player=P),abandon={},forfeit=dict(team=T))
 return s
def dismiss(d,i):
 t=batting(d)
 if d['batters'][t][i]=='out':fail('Batter has already been dismissed')
 d['batters'][t][i]='out';d['wickets'][t]+=1
 if d['striker']==i:d['striker']=None
 if d['non_striker']==i:d['non_striker']=None

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 t=batting(d);f=1-t;i=p.get('player')
 if k=='start_match':d.update(first_batting=p['first_batting'],phase='play')
 elif k=='start_second_innings':
  d.update(innings=2,phase='play',striker=None,non_striker=None,bowler=None,over_bowlers=[],previous_bowlers=[],free_hit=False);check_end(d)
 elif k=='nominate_batter':
  end=p['end']
  if d[end] is not None or not d['eligible'][t][i] or d['batters'][t][i] not in ('unused','retired'):fail('Choose an eligible unused or returning batter for an empty end')
  d[end]=i;d['batters'][t][i]='in'
 elif k=='nominate_bowler':
  if d['bowler'] is not None or not d['eligible'][f][i] or d['bowled'][f][i]>=24 or i in d['previous_bowlers'] or i in d['over_bowlers']:fail('Bowler must be eligible, below quota and absent from the preceding and current over')
  d['bowler']=i;d['over_bowlers'].append(i)
 elif k=='replace_bowler':
  if d['bowler'] is None:fail('There is no current bowler to replace')
  d['bowler']=None
 elif k=='retire':
  if d['batters'][t][i]!='in':fail('Only a current batter may retire')
  if p['may_return']:
   d['batters'][t][i]='retired'
   if d['striker']==i:d['striker']=None
   else:d['non_striker']=None
  else:dismiss(d,i)
  check_end(d)
 elif k=='dismiss_non_delivery':
  if p['kind']=='timed_out':
   if d['striker'] is not None and d['non_striker'] is not None or d['batters'][t][i] not in ('unused','retired'):fail('Timed-out dismissal requires a due incoming batter and a vacant end')
  elif d['batters'][t][i] not in ('in','retired'):fail('This dismissal requires a current or retired batter')
  dismiss(d,i);check_end(d)
 elif k=='exclude':
  team=p['team']
  if not d['eligible'][team][i]:fail('Player is already excluded')
  d['eligible'][team][i]=False
  if team==t and d['batters'][team][i]=='in':
   d['batters'][team][i]='retired'
   if d['striker']==i:d['striker']=None
   if d['non_striker']==i:d['non_striker']=None
  if team==f and d['bowler']==i:d['bowler']=None
 elif k=='delivery':
  kind=p['kind'];bat=p['bat_runs'];extra=p['extra_runs'];running=p['completed_runs'];boundary=p['boundary'];w=p['dismissal'];out=p['out_player'];striker=d['striker'];other=d['non_striker']
  if boundary not in (0,4,6):fail('A boundary is zero, four or six')
  if (w=='none')!=(out is None):fail('Dismissal kind and dismissed player must agree')
  if kind=='dead':
   if bat or extra or running or boundary or w!='none' or p['extra_kind']!='none':fail('This dead-delivery event carries no runs, dismissal or legal ball')
   return d
  if bat and extra or bool(extra)!=(p['extra_kind']!='none') and kind!='wide':fail('Bat runs and byes/leg-byes are mutually exclusive and extras must be classified')
  if kind=='wide':
   if bat or p['extra_kind']!='none' or boundary==6:fail('A wide cannot carry bat runs, byes or a six')
  elif not extra and p['extra_kind']!='none':fail('Zero byes cannot carry an extras classification')
  if boundary==6 and (extra or kind=='wide' or bat!=6 or running):fail('Six requires exactly six bat runs and no running component')
  if boundary==4 and bat+extra!=running+4:fail('Boundary-four totals must equal completed runs plus four')
  if boundary==0 and bat+extra!=running:fail('Non-boundary scoring must equal the completed running component')
  if w!='none':
   if out not in (striker,other):fail('A delivery dismissal must concern a current batter')
   if w not in ('run_out','obstructing') and out!=striker:fail('This dismissal can only remove the striker')
   allowed={'run_out','obstructing','hit_ball_twice'}
   if (kind=='no_ball' or d['free_hit']) and w not in allowed:fail('This dismissal is unavailable on a no-ball or free hit')
   if kind=='wide' and w not in ('stumped','hit_wicket','run_out','obstructing'):fail('This dismissal is unavailable on a wide')
   if w in ('bowled','caught','lbw','stumped','hit_wicket') and (bat or extra or running or boundary):fail('This wicket cannot retain bat or running runs')
  bonus=int(kind in ('wide','no_ball'));total=bat+extra+bonus
  # A winning non-boundary delivery ends at the required completed run.
  if d['innings']==2 and not boundary and d['runs'][t]+total>=d['target']:
   total=d['target']-d['runs'][t];w='none';out=None
  d['runs'][t]+=total
  if running%2:d['striker'],d['non_striker']=d['non_striker'],d['striker']
  if w!='none':dismiss(d,out)
  if kind=='legal':
   d['balls'][t]+=1;d['bowled'][f][d['bowler']]+=1
   if d['balls'][t]%6==0:
    d['striker'],d['non_striker']=d['non_striker'],d['striker'];d['previous_bowlers']=d['over_bowlers'];d['over_bowlers']=[];d['bowler']=None
   elif d['bowled'][f][d['bowler']]>=24:d['bowler']=None
  d['free_hit']=kind=='no_ball' or d['free_hit'] and kind=='wide'
  check_end(d)
 elif k=='penalty_runs':
  d['runs'][p['team']]+=5
  if d['innings']==2:d['target']=d['runs'][d['first_batting']]+1
  check_end(d)
 elif k=='end_unavailable':
  available=sum(d['eligible'][t][j] and d['batters'][t][j]!='out' for j in range(11))
  if available>=2:fail('At least two eligible undismissed batters remain')
  end_innings(d)
 elif k=='abandon':d['phase']='abandoned'
 elif k=='forfeit':d.update(phase='finished',winner=1-p['team'],reason='forfeit')
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_result' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data'];t=batting(d)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Innings, eligibility, scoring, dismissal and bowling restrictions must permit the event.'],external_observations=['Official completed delivery, boundary, dismissal, penalty or eligibility decision.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],innings=d['innings'],batting=t,runs=d['runs'],wickets=d['wickets'],balls=d['balls'],target=d['target'],striker=d['striker'],non_striker=d['non_striker'],bowler=d['bowler'],free_hit=d['free_hit'],bowled=d['bowled']),completeness=False,reason='official_cricket_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='abandoned' else 'ongoing',result_kind=('draw' if d['reason']=='tie' else 'no_contest' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if w is not None else [],losers=[state['players'][1-w]['id']] if w is not None else [],placements=[],reason=d['reason'] if done else 'official_result_required' if d['phase']=='abandoned' else 'ongoing',evidence_required=['Official result decision.'] if d['phase']=='abandoned' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
