"""Indoor handball: regulation match, eligibility, timed reductions and throws."""
from copy import deepcopy
from ..values import fields,fail
TEAM=dict(type='integer',minimum=0,maximum=1)
PLAYER=dict(type='integer',minimum=0,maximum=13)
NULL_PLAYER=dict(PLAYER,nullable=True)
def capacity(d,t):return 7-sum(r['team']==t for r in d['reductions'])
def active(d,t):return [i for i,s in enumerate(d['players'][t]) if s=='active']
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if len(active(d,t))>capacity(d,t):bad('Active lineup exceeds the reduced team capacity')
  if sum(d['warned'][t])>3:bad('A team may receive at most three player warnings')
  for i,s in enumerate(d['players'][t]):
   reductions=[r for r in d['reductions'] if r['team']==t and r['player']==i]
   if len(reductions)>1:bad('One player cannot create simultaneous independent reductions')
   if s=='suspended' and not reductions or reductions and s not in ('suspended','dq'):bad('Suspension and eligibility disagree')
   if d['suspensions'][t][i]==3 and s!='dq':bad('A third suspension disqualifies the player')
 for r in d['reductions']:
  if r['unserved'] and r['remaining_ms'] not in (120000,240000):bad('Unserved reduction must retain its full duration')
 if d['phase']=='live' and (d['remaining_ms']==0 or d['pending'] is not None or any(not active(d,t) for t in (0,1))):bad('Live play requires time, active teams and no pending throw')
 if d['pending'] is not None:
  p=d['pending']
  if d['phase']!='stopped' or d['players'][p['team']][p['thrower']]!='active':bad('A pending throw requires an eligible thrower and stopped clock')
  if p['kind']=='free_throw' and d['remaining_ms']!=0:bad('Only an end-of-half free throw is tracked separately')
 if d['phase']=='pre' and (d['half']!=1 or d['remaining_ms']!=1800000 or any(d['score']) or d['reductions']):bad('Pre-match state precedes playing time and scoring')
 if d['phase']=='interval' and (d['half']!=1 or d['remaining_ms']!=0 or d['pending'] is not None):bad('Interval follows the completed first half')
 if d['phase']=='finished':
  if d['reason']=='regulation':
   w=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0])
   if d['half']!=2 or d['remaining_ms'] or d['winner']!=w:bad('Regulation result must match the final score')
  elif d['reason']=='concession':
   if d['winner'] is None:bad('Concession requires a winner')
  elif d['reason'] not in ('official_result','no_contest'):bad('Finished match needs its reason')
 elif d['winner'] is not None or d['reason'] is not None:bad('Nonterminal state cannot declare a result')
def schemas(d):
 phase=d['phase'];s={}
 if phase=='finished':return s
 if phase=='abandoned':return dict(official_result=dict(winner=dict(TEAM,nullable=True)))
 if phase=='pre':s['start_match']={}
 if phase in ('pre','live','stopped','interval'):
  s.update(substitute=dict(team=TEAM,outgoing=PLAYER,incoming=PLAYER),enter=dict(team=TEAM,player=PLAYER),leave=dict(team=TEAM,player=PLAYER))
 if phase=='interval':s['start_second_half']={}
 if phase=='live':s.update(elapse=dict(milliseconds=dict(type='integer',minimum=1,maximum=1800000)),stop_clock={},goal=dict(team=TEAM,player=PLAYER))
 if phase=='stopped' and d['pending'] is None:
  if d['remaining_ms']>0:s['resume_play']={}
  else:s['end_half']={}
 if phase in ('live','stopped'):
  s.update(caution=dict(team=TEAM,player=PLAYER,remove_player=NULL_PLAYER),suspend=dict(team=TEAM,player=PLAYER,remove_player=NULL_PLAYER),disqualify=dict(team=TEAM,player=PLAYER,remove_player=NULL_PLAYER),additional_misconduct=dict(team=TEAM,player=PLAYER,disqualify=dict(type='boolean')),team_reduction=dict(team=TEAM,remove_player=NULL_PLAYER))
  if d['pending'] is None:
   s.update(grant_timeout=dict(team=TEAM),award_throw=dict(team=TEAM,thrower=PLAYER,kind=dict(type='enum',values=['seven_metre','free_throw'])))
  else:s.update(resolve_throw=dict(scored=dict(type='boolean')),replace_thrower=dict(player=PLAYER))
 s.update(abandon={},concede=dict(team=TEAM))
 return s
def reduce_team(d,t,i,remove):
 if i is not None and any(r['team']==t and r['player']==i for r in d['reductions']):fail('Use additional misconduct for an unserved player reduction')
 d['reductions'].append(dict(team=t,player=i,remaining_ms=120000,unserved=True))
 if len(active(d,t))>capacity(d,t):
  if remove is None or d['players'][t][remove]!='active':fail('Nominate an active teammate to implement the reduction')
  d['players'][t][remove]='bench'
 elif remove is not None:fail('No additional player needs to leave')
 d['phase']='stopped'
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params');t=p.get('team')
 if k=='start_match':
  if any(len(active(d,j))<5 for j in (0,1)):fail('Both teams need at least five players to start')
  d['phase']='stopped'
 elif k=='start_second_half':d.update(half=2,remaining_ms=1800000,phase='stopped',timeouts=[False,False])
 elif k=='resume_play':
  if any(not active(d,j) for j in (0,1)):fail('A team without an active player cannot resume')
  d['phase']='live'
  for r in d['reductions']:r['unserved']=False
 elif k=='stop_clock':d['phase']='stopped'
 elif k=='elapse':
  ms=p['milliseconds']
  if ms>d['remaining_ms']:fail('Playing time cannot pass the half boundary')
  d['remaining_ms']-=ms;remaining=[]
  for r in d['reductions']:
   r['remaining_ms']-=ms
   if r['remaining_ms']>0:remaining.append(r)
   elif r['player'] is not None and d['players'][r['team']][r['player']]=='suspended':d['players'][r['team']][r['player']]='bench'
  d['reductions']=remaining
  if d['remaining_ms']==0:d['phase']='stopped'
 elif k=='goal':
  if d['players'][t][p['player']]!='active':fail('Only an eligible active player can score')
  d['score'][t]+=1
 elif k in ('substitute','enter','leave'):
  if k!='enter':
   old=p['outgoing'] if k=='substitute' else p['player']
   if d['players'][t][old]!='active':fail('The outgoing player must be active')
   if d['pending'] is not None and d['pending']['team']==t and d['pending']['thrower']==old:fail('Replace the pending thrower before removing that player')
   d['players'][t][old]='bench'
  if k!='leave':
   new=p['incoming'] if k=='substitute' else p['player']
   if d['players'][t][new]!='bench' or len(active(d,t))>=capacity(d,t):fail('Entry requires an eligible bench player and an available slot')
   if k=='substitute' and new==old:fail('Substitution requires different players')
   d['players'][t][new]='active'
 elif k=='grant_timeout':
  if d['timeouts'][t] or d['remaining_ms']==0:fail('One granted team timeout is available in each half')
  d['timeouts'][t]=True;d['phase']='stopped'
 elif k=='award_throw':
  if d['players'][t][p['thrower']]!='active' or p['kind']=='free_throw' and d['remaining_ms']!=0:fail('Use an active thrower; only an end-of-half free throw is recorded')
  d['pending']=deepcopy(p);d['phase']='stopped'
 elif k=='resolve_throw':
  if p['scored']:d['score'][d['pending']['team']]+=1
  d['pending']=None
 elif k=='replace_thrower':
  if d['players'][d['pending']['team']][p['player']]!='active':fail('Replacement thrower must be active')
  d['pending']['thrower']=p['player']
 elif k in ('caution','suspend','disqualify'):
  i=p['player']
  if d['players'][t][i] in ('dq','suspended'):fail('Player is already unavailable; use the additional-misconduct event where applicable')
  if d['pending'] is not None and d['pending']['team']==t and d['pending']['thrower']==i:fail('Replace the pending thrower before imposing this sanction')
  if k=='caution' and not d['warned'][t][i] and sum(d['warned'][t])<3 and d['suspensions'][t][i]==0:
   if p['remove_player'] is not None:fail('A warning does not reduce the team')
   d['warned'][t][i]=True
  else:
   if k!='disqualify':d['suspensions'][t][i]+=1
   d['players'][t][i]='dq' if k=='disqualify' or d['suspensions'][t][i]==3 else 'suspended'
   reduce_team(d,t,i,p['remove_player'])
 elif k=='additional_misconduct':
  i=p['player'];r=next((r for r in d['reductions'] if r['team']==t and r['player']==i),None)
  if r is None or not r['unserved'] or r['remaining_ms']!=120000:fail('Additional misconduct must precede resumption after the initial reduction')
  if d['players'][t][i]!='dq':d['suspensions'][t][i]=min(3,d['suspensions'][t][i]+1)
  if p['disqualify'] or d['suspensions'][t][i]==3:d['players'][t][i]='dq'
  r['remaining_ms']=240000
 elif k=='team_reduction':reduce_team(d,t,None,p['remove_player'])
 elif k=='end_half':
  if d['half']==1:d['phase']='interval'
  else:d.update(phase='finished',reason='regulation',winner=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0]))
 elif k=='abandon':d['phase']='abandoned';d['pending']=None
 elif k=='concede':d.update(phase='finished',winner=1-t,reason='concession',pending=None)
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Phase, eligible lineup, team capacity and remaining allowances must permit the event.'],external_observations=['Official goals, throws, clock, discipline and timeout decisions.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],half=d['half'],remaining_ms=d['remaining_ms'],capacity=[capacity(d,t) for t in (0,1)],active_players=[active(d,t) for t in (0,1)],pending_throw=d['pending']),completeness=False,reason='official_handball_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner'];draw=done and d['reason']=='regulation' and w is None
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='abandoned' else 'ongoing',result_kind=('draw' if draw else 'no_contest' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if w is not None else [],losers=[state['players'][1-w]['id']] if w is not None else [],placements=[],reason=d['reason'] if done else 'official_result_required' if d['phase']=='abandoned' else 'ongoing',evidence_required=['Official result decision.'] if d['phase']=='abandoned' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
