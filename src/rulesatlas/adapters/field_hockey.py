"""Four-quarter field hockey with roster, cards and extended penalty corners."""
from copy import deepcopy
from ..values import fields,fail
TEAM=dict(type='integer',minimum=0,maximum=1)
PLAYER=dict(type='integer',minimum=0,maximum=17)
NP=dict(PLAYER,nullable=True)
def active(d,t):return [i for i,s in enumerate(d['players'][t]) if s=='active']
def capacity(d,t):return 11-sum(s in ('suspended','dq') for s in d['players'][t])
def corner(d):return d['pending'] is not None and d['pending']['kind']=='corner'
def stroke(d):return d['pending'] is not None and d['pending']['kind']=='stroke'
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if len(active(d,t))>capacity(d,t):bad('Active players exceed available team places')
  if d['goalkeeper'][t] is not None and d['players'][t][d['goalkeeper'][t]]!='active':bad('Goalkeeper designation requires an active player')
  for i,s in enumerate(d['players'][t]):
   if (s=='suspended')!=(d['penalty_ms'][t][i]>0):bad('Timed penalty and player eligibility disagree')
 if d['phase']=='live' and (d['remaining_ms']==0 or stroke(d) or any(not active(d,t) for t in (0,1))):bad('Live play requires time and eligible teams without an outstanding stroke')
 if d['pending'] is not None:
  p=d['pending']
  if d['phase'] not in ('live','stopped'):bad('Outstanding penalty requires an active quarter')
  if p['kind']=='stroke' and (p['thrower'] is None or d['players'][p['team']][p['thrower']]!='active'):bad('Penalty stroke requires an eligible taker')
  if p['kind']=='corner' and p['thrower'] is not None:bad('Corner does not nominate a stroke taker')
 if d['phase']=='interval' and (d['quarter']==4 or d['remaining_ms']!=0 or d['pending'] is not None):bad('Quarter interval must follow a completed nonfinal quarter')
 if d['phase']=='pre' and (d['quarter']!=1 or d['remaining_ms']!=900000 or any(d['score']) or any(s in ('suspended','dq') for row in d['players'] for s in row)):bad('Pre-match state precedes scoring, time and match sanctions')
 if d['phase']=='finished':
  if d['pending'] is not None or d['reason'] is None:bad('Finished match cannot retain an outstanding penalty')
  if d['reason']=='regulation':
   w=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0])
   if d['quarter']!=4 or d['remaining_ms']!=0 or d['winner']!=w:bad('Regulation result must match the final score')
  if (d['reason'] in ('concession','official_result'))!=(d['winner'] is not None) and d['reason']!='regulation':bad('Official result and winner disagree')
 elif d['reason'] is not None or d['winner'] is not None:bad('Only a finished match declares a result')
def schemas(d):
 phase=d['phase'];s={}
 if phase=='finished':return s
 if phase=='abandoned':return dict(official_result=dict(winner=dict(TEAM,nullable=True)))
 if phase=='pre':s['start_match']={}
 if phase=='interval':s['next_quarter']={}
 s.update(substitute=dict(team=TEAM,outgoing=PLAYER,incoming=PLAYER),enter=dict(team=TEAM,player=PLAYER),leave=dict(team=TEAM,player=PLAYER))
 if phase!='live':s['designate_goalkeeper']=dict(team=TEAM,player=NP)
 if phase=='live':s.update(elapse=dict(milliseconds=dict(type='integer',minimum=1,maximum=900000)),stop_clock={},goal=dict(team=TEAM,player=PLAYER))
 if phase=='stopped':
  if d['remaining_ms']>0 and not stroke(d):s['resume_play']={}
  if d['remaining_ms']==0 and d['pending'] is None:s['end_quarter']={}
 if phase in ('live','stopped'):
  s['card']=dict(team=TEAM,player=PLAYER,colour=dict(type='enum',values=['green','yellow','red']),minutes=dict(type='integer',minimum=0,maximum=20),remove_player=NP)
  if d['pending'] is None:s['award_corner']=dict(team=TEAM)
  if not stroke(d):s['award_stroke']=dict(team=TEAM,thrower=PLAYER)
  if corner(d):
   s['corner_result']=dict(result=dict(type='enum',values=['goal','ended','repeat']),scorer=NP)
   s['authorized_keeper_replacement']=dict(outgoing=NP,incoming=PLAYER)
  if stroke(d):s.update(stroke_result=dict(scored=dict(type='boolean')),replace_taker=dict(player=PLAYER))
 s.update(abandon={},concede=dict(team=TEAM))
 return s
def remove(d,t,i):
 d['players'][t][i]='bench'
 if d['goalkeeper'][t]==i:d['goalkeeper'][t]=None
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params');t=p.get('team')
 if k=='start_match':
  if any(not active(d,j) for j in (0,1)):fail('Both teams require active players')
  d['phase']='stopped'
 elif k=='next_quarter':d['quarter']+=1;d['remaining_ms']=900000;d['phase']='stopped'
 elif k=='resume_play':
  if any(not active(d,j) for j in (0,1)):fail('Both teams require active players')
  d['phase']='live'
 elif k=='stop_clock':d['phase']='stopped'
 elif k=='elapse':
  ms=p['milliseconds']
  if ms>d['remaining_ms']:fail('Playing time cannot pass the quarter boundary')
  d['remaining_ms']-=ms
  for j in (0,1):
   for i,n in enumerate(d['penalty_ms'][j]):
    if n:
     d['penalty_ms'][j][i]=max(0,n-ms)
     if n<=ms:d['players'][j][i]='bench'
  if d['remaining_ms']==0:d['phase']='stopped'
 elif k=='goal':
  if d['pending'] is not None or d['players'][t][p['player']]!='active':fail('Ordinary goal needs an active scorer and no unresolved penalty')
  d['score'][t]+=1
 elif k in ('substitute','enter','leave'):
  old=p.get('outgoing',p.get('player'));new=p.get('incoming',p.get('player'));was_keeper=old==d['goalkeeper'][t]
  if corner(d):fail('Ordinary substitutions wait until the corner is completed')
  if k!='enter':
   if d['players'][t][old]!='active':fail('Outgoing player must be active')
   if stroke(d) and d['pending']['team']==t and d['pending']['thrower']==old:fail('Replace the stroke taker first')
   remove(d,t,old)
  if k!='leave':
   if d['players'][t][new]!='bench' or len(active(d,t))>=capacity(d,t) or k=='substitute' and new==old:fail('Incoming player needs eligibility and a free team place')
   d['players'][t][new]='active'
   if k=='substitute' and was_keeper:d['goalkeeper'][t]=new
 elif k=='authorized_keeper_replacement':
  t=1-d['pending']['team'];old=p['outgoing'];new=p['incoming']
  if d['goalkeeper'][t] is not None and old!=d['goalkeeper'][t]:fail('Replace the designated defending goalkeeper')
  if old is not None:
   if d['players'][t][old]!='active':fail('Outgoing player must be active')
   remove(d,t,old)
  if d['players'][t][new]!='bench' or len(active(d,t))>=capacity(d,t) or new==old:fail('Replacement goalkeeper needs eligibility and a team place')
  d['players'][t][new]='active';d['goalkeeper'][t]=new
 elif k=='designate_goalkeeper':
  if corner(d):fail('Resolve the corner before changing goalkeeper designation')
  if p['player'] is not None and d['players'][t][p['player']]!='active':fail('Goalkeeper must be active')
  d['goalkeeper'][t]=p['player']
 elif k=='card':
  i=p['player'];colour=p['colour'];old=d['players'][t][i]
  if old=='dq' or old=='suspended' and colour!='red':fail('Only red can upgrade a current suspension')
  if stroke(d) and d['pending']['team']==t and d['pending']['thrower']==i:fail('Replace the stroke taker first')
  if colour=='green':
   if p['minutes']!=2 or d['green'][t][i]:fail('A single green card gives two minutes; further discipline requires yellow or red')
   d['green'][t][i]=True
  elif colour=='yellow':
   if p['minutes']<5 or p['minutes']<=d['last_yellow_minutes'][t][i]:fail('Yellow is at least five minutes; a repeat suspension must be longer')
   d['last_yellow_minutes'][t][i]=p['minutes']
  elif p['minutes']!=0:fail('Red is a permanent exclusion, not a timed penalty')
  d['players'][t][i]='dq' if colour=='red' else 'suspended';d['penalty_ms'][t][i]=0 if colour=='red' else p['minutes']*60000
  if d['goalkeeper'][t]==i:d['goalkeeper'][t]=None
  if len(active(d,t))>capacity(d,t):
   if p['remove_player'] is None or d['players'][t][p['remove_player']]!='active':fail('Nominate an active teammate to implement a bench-player reduction')
   remove(d,t,p['remove_player'])
  elif p['remove_player'] is not None:fail('No further player needs to leave')
  d['phase']='stopped'
 elif k=='award_corner':d['pending']=dict(kind='corner',team=t,thrower=None);d['phase']='stopped'
 elif k=='award_stroke':
  if d['players'][t][p['thrower']]!='active':fail('Stroke taker must be active')
  d['pending']=dict(kind='stroke',team=t,thrower=p['thrower']);d['phase']='stopped'
 elif k=='corner_result':
  if p['result']=='goal':
   if p['scorer'] is None or d['players'][d['pending']['team']][p['scorer']]!='active':fail('A corner goal requires an active attacking scorer')
   d['score'][d['pending']['team']]+=1
  elif p['scorer'] is not None:fail('A non-goal corner result cannot name a scorer')
  if p['result']!='repeat':d['pending']=None
  d['phase']='stopped'
 elif k=='stroke_result':
  if p['scored']:d['score'][d['pending']['team']]+=1
  d['pending']=None
 elif k=='replace_taker':
  if d['players'][d['pending']['team']][p['player']]!='active':fail('Replacement taker must be active')
  d['pending']['thrower']=p['player']
 elif k=='end_quarter':
  if d['quarter']<4:d['phase']='interval'
  else:d.update(phase='finished',reason='regulation',winner=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0]))
 elif k=='abandon':d.update(phase='abandoned',pending=None)
 elif k=='concede':d.update(phase='finished',winner=1-t,reason='concession',pending=None)
 elif k=='official_result':d.update(phase='finished',winner=p['winner'],reason='no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Quarter, pending penalty, eligibility and team capacity must permit the event.'],external_observations=['Official goals, cards, clock and penalty decisions.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],quarter=d['quarter'],remaining_ms=d['remaining_ms'],capacity=[capacity(d,t) for t in (0,1)],goalkeeper=d['goalkeeper'],pending_penalty=d['pending']),completeness=False,reason='official_field_hockey_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner'];draw=done and d['reason']=='regulation' and w is None
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='abandoned' else 'ongoing',result_kind=('draw' if draw else 'no_contest' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if w is not None else [],losers=[state['players'][1-w]['id']] if w is not None else [],placements=[],reason=d['reason'] if done else 'official_result_required' if d['phase']=='abandoned' else 'ongoing',evidence_required=['Official result decision.'] if d['phase']=='abandoned' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
