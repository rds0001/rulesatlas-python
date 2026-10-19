"""BC2 individual ends from official proximity ranks, without physical positions."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b,**kw:dict(type='integer',minimum=a,maximum=b,**kw)
TEAM=I(0,1);BOOL=dict(type='boolean')
BALL=dict(status=dict(type='enum',values=['unplayed','live','dead']),rank=I(1,12,nullable=True),retracted=BOOL)
BOARD=dict(type='array',minItems=12,maxItems=12,items=dict(type='object',properties=BALL,required=list(BALL)))
CLOCKS=dict(type='array',minItems=2,maxItems=2,items=I(0,210000))
SCHEMAS=dict(configure=dict(prior_yellow=dict(type='array',minItems=2,maxItems=2,items=I(0,100)),forfeit_margin=I(6,1000000)),start_match={},play_jack=dict(valid=BOOL,elapsed_ms=I(0,210000)),play_ball=dict(ball=I(0,11),board=BOARD,elapsed_ms=I(0,210000)),elapse=dict(milliseconds=I(1,210000)),correct_clock=dict(team=TEAM,milliseconds=I(0,210000)),decline_remaining={},award_penalty=dict(team=TEAM),confirm_board={},correct_board=dict(board=BOARD),resolve_penalty=dict(scored=BOOL,elapsed_ms=I(0,60000)),confirm_end={},start_tiebreak=dict(first_team=TEAM),replay_end=dict(offender=dict(TEAM,nullable=True),jack_thrower=TEAM,clocks_ms=CLOCKS),card=dict(team=TEAM,color=dict(type='enum',values=['yellow','red'])),forfeit=dict(team=TEAM),set_forfeit_margin=dict(points=I(6,1000000)),confirm_result={},confirm_no_contest={})
SCHEMAS['retract_release']=dict(balls=dict(type='array',minItems=1,maxItems=6,items=I(0,11)),elapsed_ms=I(0,210000))
def fresh_balls():return [dict(status='unplayed',rank=None,retracted=False) for _ in range(12)]
def reset_end(d,first,tiebreak=False):
 d.update(balls=fresh_balls(),clocks_ms=[210000,210000],turn=first,equal_chain=False,pending_penalties=[0,0],penalty_first=None,end_points=[0,0],phase='play' if tiebreak else 'jack')
def remaining(d,t):return [i for i,b in enumerate(d['balls']) if i//6==t and b['status']=='unplayed']
def near(d):return [min((b['rank'] for i,b in enumerate(d['balls']) if i//6==t and b['status']=='live'),default=99) for t in (0,1)]
def board_points(d):
 n=near(d)
 if n==[99,99]:return [0,0]
 if n[0]==n[1]:return [sum(i//6==t and b['status']=='live' and b['rank']==n[t] for i,b in enumerate(d['balls'])) for t in (0,1)]
 w=0 if n[0]<n[1] else 1
 return [sum(b['status']=='live' and i//6==t and b['rank']<n[1-t] for i,b in enumerate(d['balls'])) if t==w else 0 for t in (0,1)]
def settle_play(d,last):
 left=[bool(remaining(d,t)) for t in (0,1)]
 if not any(left):d.update(phase='end_review',equal_chain=False);return
 n=near(d);p=board_points(d)
 if n[0]==n[1] and n[0]!=99 and p[0]==p[1]:
  nxt=1-last if d['equal_chain'] else last;d['equal_chain']=True
 else:
  d['equal_chain']=False
  nxt=(0 if p[0]<p[1] else 1) if n[0]==n[1] and n[0]!=99 else last if n==[99,99] else 0 if n[0]>n[1] else 1
 d['turn']=nxt if left[nxt] else 1-nxt;d['phase']='play'
def expire(d,t):
 for i in remaining(d,t):d['balls'][i]=dict(status='dead',rank=None,retracted=False)
 if d['phase']=='jack':
  if remaining(d,1-t) and d['clocks_ms'][1-t]>0:d['turn']=1-t
  else:d['phase']='end_review'
 else:settle_play(d,t)
def spend(d,amount):
 t=d['turn']
 if amount>d['clocks_ms'][t]:fail('Elapsed time exceeds the active side allowance')
 d['clocks_ms'][t]-=amount

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for b in d['balls']:
  if (b['status']=='live')!=(b['rank'] is not None) or b['retracted'] and b['status']!='dead':bad('Ball rank and retraction status disagree')
 if d['phase']=='setup':
  if d['ends_completed'] or any(d['scores']) or any(b['status']!='unplayed' for b in d['balls']) or any(d['forfeited']):bad('Initial match must be empty')
 if d['phase']=='jack' and any(b['status']=='live' for b in d['balls']):bad('Coloured balls cannot precede the valid jack')
 if d['phase'] in ('jack','play') and (not remaining(d,d['turn']) or d['clocks_ms'][d['turn']]==0):bad('The next side needs a ball and available time')
 if d['phase'] in ('end_review','penalty','end_ready') and any(b['status']=='unplayed' for b in d['balls']):bad('Resolve all regular balls before end scoring')
 if d['phase'] in ('jack','play') and any(d['clocks_ms'][t]==0 and remaining(d,t) for t in (0,1)):bad('Expired time cannot leave unplayed balls')
 if d['phase']=='play' and all(remaining(d,t) for t in (0,1)):
  n=near(d);p=board_points(d)
  if n[0]!=n[1] and d['turn']!=(0 if n[0]>n[1] else 1):bad('The side farther from the jack must play')
  if n[0]==n[1] and p[0]!=p[1] and d['turn']!=(0 if p[0]<p[1] else 1):bad('The side with fewer equally near balls must play')
 if d['phase'] in ('match_review','finished') and not any(d['forfeited']):
  p=d['end_points'] if d['tiebreak'] else d['scores']
  if d['ends_completed']!=4 or p[0]==p[1] or d['winner']!=(0 if p[0]>p[1] else 1):bad('The completed match score must determine the winner')
 if d['no_contest'] and not all(d['forfeited']):bad('No contest requires both forfeits')
 if d['phase'] in ('penalty','end_ready','match_review','finished') and not any(d['forfeited']) and any(a<b for a,b in zip(d['end_points'],board_points(d))):bad('End points cannot be below the confirmed board score')
 if d['phase']=='penalty' and d['pending_penalties'][d['turn']]==0:bad('The next penalty ball must exist')
 if d['phase']=='end_ready' and any(d['pending_penalties']):bad('Resolve every penalty ball before confirming the end')
 if any(d['pending_penalties']) and d['penalty_first'] is None:bad('The first penalty recipient is required')
 if d['tiebreak'] and (d['ends_completed']!=4 or d['scores'][0]!=d['scores'][1]):bad('Tiebreak follows four regulation ends')
 if d['phase']=='tiebreak_setup' and (d['ends_completed']!=4 or d['scores'][0]!=d['scores'][1]):bad('A tied regulation match is required')
 if d['tiebreak'] and d['tiebreak_first'] is None:bad('Tiebreak first side is missing')
 if d['phase'] in ('match_review','finished') and not any(d['forfeited']) and d['winner'] is None and not d['no_contest']:bad('Match result has not been decided')
 if d['phase']=='finished' and sum(d['forfeited'])==2 and not d['no_contest']:bad('Double forfeits require an official no-contest decision')
 for t in (0,1):
  if d['yellow'][t] and d['yellow'][t]+d['prior_yellow'][t]>=2 and not d['forfeited'][t]:bad('Accumulated yellow cards require forfeiture')
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase'];t=d['turn']
 if k not in SCHEMAS:fail('Unknown boccia event')
 fields(p,SCHEMAS[k],'/params')
 if k=='configure':
  if phase!='setup':fail('Configure competition history before the match')
  d['prior_yellow']=p['prior_yellow'][:];d['forfeit_margin']=p['forfeit_margin']
 elif k=='start_match':
  if phase!='setup':fail('Match already started')
  pending=d['pending_penalties'][:];first=d['penalty_first'];reset_end(d,0);d['pending_penalties']=pending;d['penalty_first']=first
 elif k=='play_jack':
  if phase!='jack':fail('No jack delivery is pending')
  spend(d,p['elapsed_ms'])
  if p['valid']:d['phase']='play'
  else:d['turn']=1-t
  if d['clocks_ms'][t]==0:
   d['turn']=t;expire(d,t)
  elif not p['valid'] and not remaining(d,1-t):d['turn']=t
 elif k=='play_ball':
  j=p['ball'];new=p['board']
  if phase!='play' or j not in remaining(d,t):fail('Play one unplayed ball of the indicated side')
  for i,(old,b) in enumerate(zip(d['balls'],new)):
   if i==j:
    if b['status']=='unplayed':fail('The played ball must resolve')
   elif old['status'] in ('unplayed','dead') and b!=old:fail('Unplayed and dead balls cannot move back into play')
   elif old['status']=='live' and (b['status']=='unplayed' or b['retracted']):fail('A live ball can remain live or become dead after the shot')
  spend(d,p['elapsed_ms']);d['balls']=deepcopy(new)
  if d['clocks_ms'][t]==0:
   for i in remaining(d,t):d['balls'][i]=dict(status='dead',rank=None,retracted=False)
  settle_play(d,t)
 elif k=='retract_release':
  if phase!='play' or len(set(p['balls']))!=len(p['balls']) or any(i not in remaining(d,t) for i in p['balls']):fail('Retract distinct unplayed balls released by the indicated side')
  spend(d,p['elapsed_ms'])
  for i in p['balls']:d['balls'][i]=dict(status='dead',rank=None,retracted=True)
  if d['clocks_ms'][t]==0:
   for i in remaining(d,t):d['balls'][i]=dict(status='dead',rank=None,retracted=False)
  settle_play(d,t)
 elif k=='elapse':
  if phase not in ('jack','play'):fail('Regular play clock is not active')
  spend(d,p['milliseconds'])
  if d['clocks_ms'][t]==0:expire(d,t)
 elif k=='correct_clock':
  if phase not in ('jack','play'):fail('Correct clocks during regular play')
  d['clocks_ms'][p['team']]=p['milliseconds']
  if p['milliseconds']==0:expire(d,p['team'])
 elif k=='decline_remaining':
  if phase!='play':fail('Decline balls only during coloured-ball play')
  expire(d,t)
 elif k=='award_penalty':
  if phase not in ('setup','jack','play','end_review','penalty','end_ready'):fail('No open end can receive a penalty ball')
  q=p['team'];d['pending_penalties'][q]+=1
  if d['penalty_first'] is None:d['penalty_first']=q
  if phase=='end_ready':d['phase']='penalty';d['turn']=q
 elif k=='correct_board':
  if phase!='end_review' or any(b['status']=='unplayed' for b in p['board']):fail('Correct a resolved end before scoring')
  d['balls']=deepcopy(p['board'])
 elif k=='confirm_board':
  if phase!='end_review':fail('Resolve all coloured balls first')
  d['end_points']=board_points(d)
  if any(d['pending_penalties']):d['phase']='penalty';d['turn']=d['penalty_first'] if d['pending_penalties'][d['penalty_first']] else 1-d['penalty_first']
  else:d['phase']='end_ready'
 elif k=='resolve_penalty':
  if phase!='penalty':fail('No penalty ball is pending')
  d['end_points'][t]+=int(p['scored']);d['pending_penalties'][t]-=1
  if d['pending_penalties'][1-t]:d['turn']=1-t
  elif not d['pending_penalties'][t]:d['phase']='end_ready'
 elif k=='confirm_end':
  if phase!='end_ready':fail('Review regular scoring and resolve all penalty balls first')
  if d['tiebreak']:
   if d['end_points'][0]!=d['end_points'][1]:d['winner']=0 if d['end_points'][0]>d['end_points'][1] else 1;d['phase']='match_review'
   else:d['tiebreak_first']=1-d['tiebreak_first'];reset_end(d,d['tiebreak_first'],True)
  else:
   d['scores']=[a+b for a,b in zip(d['scores'],d['end_points'])];d['ends_completed']+=1
   if d['ends_completed']<4:reset_end(d,d['ends_completed']%2)
   elif d['scores'][0]==d['scores'][1]:d['phase']='tiebreak_setup'
   else:d['winner']=0 if d['scores'][0]>d['scores'][1] else 1;d['phase']='match_review'
 elif k=='start_tiebreak':
  if phase!='tiebreak_setup':fail('No initial tiebreak is pending')
  d['tiebreak']=True;d['tiebreak_first']=p['first_team'];reset_end(d,p['first_team'],True)
 elif k=='replay_end':
  if phase not in ('jack','play','end_review'):fail('Only an unresolved disrupted end can restart')
  for i,b in enumerate(d['balls']):
   if not b['retracted']:d['balls'][i]=dict(status='unplayed',rank=None,retracted=False)
  if p['offender'] is not None:d['pending_penalties'][p['offender']]=0
  d.update(clocks_ms=p['clocks_ms'][:],turn=p['jack_thrower'],equal_chain=False,phase='play' if d['tiebreak'] else 'jack')
  for q in (0,1):
   if d['clocks_ms'][q]==0:
    for i in remaining(d,q):d['balls'][i]=dict(status='dead',rank=None,retracted=False)
  if not remaining(d,d['turn']):
   if d['phase']=='jack':
    if remaining(d,1-d['turn']):d['turn']=1-d['turn']
    else:d['phase']='end_review'
   else:settle_play(d,d['turn'])
 elif k in ('card','forfeit'):
  q=p['team']
  if d['forfeited'][q]:fail('Side has already forfeited')
  if k=='card' and p['color']=='yellow':d['yellow'][q]+=1
  if k=='forfeit' or p.get('color')=='red' or d['yellow'][q]+d['prior_yellow'][q]>=2:d['forfeited'][q]=True;d['phase']='match_review';d['winner']=None if all(d['forfeited']) else 1-q
 elif k=='set_forfeit_margin':d['forfeit_margin']=p['points']
 elif k=='confirm_no_contest':
  if phase!='match_review' or not all(d['forfeited']):fail('Official no-contest decision requires both sides to have forfeited')
  d.update(phase='finished',no_contest=True,winner=None)
 elif k=='confirm_result':
  if phase!='match_review' or all(d['forfeited']):fail('Resolve the match result before confirmation')
  d['phase']='finished'
 return d
def legal(state):
 d=state['data'];phase=d['phase'];names={'setup':['configure','start_match'],'jack':['play_jack','elapse','correct_clock','replay_end'],'play':['play_ball','retract_release','elapse','correct_clock','decline_remaining','replay_end'],'end_review':['correct_board','confirm_board','replay_end'],'penalty':['resolve_penalty'],'end_ready':['confirm_end'],'tiebreak_setup':['start_tiebreak'],'match_review':['confirm_no_contest'] if all(d['forfeited']) else ['confirm_result']}.get(phase,[])
 if phase!='finished':names+=['card','forfeit','set_forfeit_margin']
 if phase in ('setup','jack','play','end_review','penalty','end_ready'):names+=['award_penalty']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['End phase, indicated side, available balls and official judgment must permit the event.'],external_observations=['Official proximity ranks, elapsed playing time, valid delivery or sanction.']) for k in names],constraints=dict(phase=phase,next_team=d['turn'],remaining_balls=[remaining(d,t) for t in (0,1)],provisional_points=board_points(d),pending_penalties=d['pending_penalties']),completeness=False,reason='official_boccia_observations')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner'];scores=d['scores'][:]
 if sum(d['forfeited'])==1:scores=[0,0];scores[w]=d['forfeit_margin']
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase'] in ('end_review','match_review') else 'ongoing',result_kind=('no_contest' if d['no_contest'] else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[dict(player_id=p['id'],place=1 if i==w else 2,score=scores[i]) for i,p in enumerate(state['players'])] if done and w is not None else [],reason='boccia_confirmed' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
