"""Seven-a-side Tchoukball: official attacks, restart rights and eligibility."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
T=I(0,1);P=I(0,11);B=dict(type='boolean')
def active(d,t):return [i for i,x in enumerate(d['status'][t]) if x=='active']
def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason,clock_running=False)
def forfeit(d,t):d['scores']=[30 if j!=t else 0 for j in (0,1)];finish(d,1-t,'forfeit')
def reset(d,phase,t):d.update(phase=phase,next_team=t,last_frame=None,frame_count=0)
def point(d,t):
 d['scores'][t]+=1;reset(d,'restart',1-t);d['entry_limit']=[7,7]
def end_period(d):
 d['clock_running']=False
 if d['period']>=3 and (d['scores'][0]!=d['scores'][1] or d['allow_draw']):finish(d,None if d['scores'][0]==d['scores'][1] else int(d['scores'][1]>d['scores'][0]),'regulation' if d['period']==3 else 'extra_time')
 else:d['phase']='interval'
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if len(active(d,t))>d['entry_limit'][t]:bad('Active lineup exceeds current replacement entitlement')
  if d['phase'] not in ('pre_game','finished','abandoned') and len(active(d,t))<5:bad('Fewer than five active players requires forfeiture')
  for i,y in enumerate(d['yellow'][t]):
   if y==2 and d['status'][t][i]!='excluded':bad('Two yellow cards expel the player')
 if (d['last_frame'] is None)!=(d['frame_count']==0):bad('Frame identity and consecutive shot count must agree')
 if d['phase'] in ('restart','breakdown','pre_game') and d['frame_count']:bad('Restarts and breakdowns reset the frame count')
 if d['phase']=='pre_game' and (any(d['scores']) or d['period']!=1 or d['clock_running'] or d['first_team'] is not None):bad('Pre-game state precedes score, clock and toss')
 if d['phase'] not in ('pre_game','finished','abandoned') and d['first_team'] is None:bad('Play requires initial restart choice')
 if d['period']>3 and d['remaining_ms']>300000:bad('Extra periods last five minutes')
 if d['phase']=='interval' and (d['remaining_ms'] or d['clock_running']):bad('Interval follows an expired period')
 if d['phase'] in ('restart','play','breakdown') and not d['remaining_ms']:bad('Period expiry immediately stops play')
 if d['clock_running'] and d['phase'] not in ('restart','play','breakdown'):bad('Clock runs only during a period')
 if d['phase']=='finished':
  if d['reason'] is None:bad('Finished match requires a result')
  if d['reason'] in ('regulation','extra_time'):
   expected=None if d['scores'][0]==d['scores'][1] else int(d['scores'][1]>d['scores'][0])
   if d['period']<3 or d['remaining_ms'] or expected!=d['winner'] or expected is None and not d['allow_draw']:bad('Timed result must agree with score and match format')
  if d['reason']=='forfeit' and (d['winner'] is None or d['scores'][d['winner']]!=30 or d['scores'][1-d['winner']]!=0):bad('Forfeit is recorded as thirty to nil')
 elif d['winner'] is not None or d['reason'] is not None:bad('Only finished matches have a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 if ph=='pre_game':s.update(configure=dict(allow_draw=B),start_game=dict(first_team=T))
 if ph=='interval':s['next_period']={}
 if ph in ('pre_game','interval','restart'):s.update(substitute=dict(team=T,out=P,**{'in':P}),enter=dict(team=T,player=P))
 if ph in ('restart','play','breakdown'):
  s.update(withdraw=dict(team=T,player=P),sanction=dict(team=T,player=P,kind=dict(type='enum',values=['oral','oral_breakdown','yellow','red'])),official_breakdown=dict(team=T))
  if d['clock_running']:
   s.update(elapse=dict(milliseconds=I(1,900000)),stop_clock={})
   if ph=='restart':s.update(restart=dict(team=T,player=P),restart_fault={})
   if ph=='breakdown':s['take_breakdown']=dict(team=T,player=P,correct=B)
   if ph=='play':s['shot']=dict(team=T,player=P,frame=T,passes=I(0,3),median_crossed=B,result=dict(type='enum',values=['scored','conceded','caught','faulty_rebound']))
  else:s['resume_clock']={}
 s.update(concede=dict(team=T),abandon={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 t=p.get('team')
 if k=='configure':d['allow_draw']=p['allow_draw']
 elif k=='start_game':
  if any(len(active(d,t))<5 for t in (0,1)):fail('At least five players per team are required')
  d.update(first_team=p['first_team'],period_starter=p['first_team'],clock_running=True);reset(d,'restart',p['first_team'])
 elif k=='next_period':
  d['period']+=1
  starter=1-d['first_team'] if d['period']==2 else (d['first_team'] if d['scores'][0]==d['scores'][1] else int(d['scores'][1]<d['scores'][0])) if d['period']==3 else 1-d['period_starter']
  d.update(period_starter=starter,remaining_ms=900000 if d['period']<=3 else 300000,clock_running=True,entry_limit=[7,7]);reset(d,'restart',starter)
 elif k=='substitute':
  if p['out'] not in active(d,t) or d['status'][t][p['in']]!='bench':fail('Substitution requires an active player and eligible bench player')
  d['status'][t][p['out']]='bench';d['status'][t][p['in']]='active'
 elif k=='enter':
  if d['status'][t][p['player']]!='bench' or len(active(d,t))>=d['entry_limit'][t]:fail('No eligible replacement place is available')
  d['status'][t][p['player']]='active'
 elif k=='withdraw':
  if p['player'] not in active(d,t):fail('Only an active player may leave play')
  d['status'][t][p['player']]='unavailable';d['entry_limit'][t]=len(active(d,t))
  if len(active(d,t))<5:forfeit(d,t)
 elif k=='sanction':
  i=p['player'];kind=p['kind']
  if d['status'][t][i]=='excluded':fail('An expelled player cannot receive another match sanction')
  if kind=='yellow':d['yellow'][t][i]+=1
  if kind=='red' or d['yellow'][t][i]==2:
   was_active=i in active(d,t);d['status'][t][i]='excluded'
   if was_active:d['entry_limit'][t]=len(active(d,t))
  if kind!='oral':reset(d,'breakdown',1-t)
  if len(active(d,t))<5:forfeit(d,t)
 elif k=='official_breakdown':reset(d,'breakdown',t)
 elif k=='restart_fault':reset(d,'restart',1-d['next_team'])
 elif k in ('restart','take_breakdown'):
  if t!=d['next_team'] or p['player'] not in active(d,t):fail('Restart requires an active player from the entitled team')
  if k=='restart' or p['correct']:d.update(phase='play',attack_origin='restart' if k=='restart' else 'breakdown')
 elif k=='shot':
  if t!=d['next_team'] or p['player'] not in active(d,t):fail('Shot requires an active player from the entitled team')
  if d['attack_origin']=='restart' and not p['median_crossed']:fail('First shot after restart requires crossing the median line')
  if d['attack_origin']=='breakdown' and not p['passes']:fail('A breakdown requires at least one pass before shooting')
  if d['last_frame']==p['frame'] and d['frame_count']==3:fail('A fourth consecutive shot at the same frame is prohibited')
  d['frame_count']=d['frame_count']+1 if d['last_frame']==p['frame'] else 1;d['last_frame']=p['frame']
  if p['result']=='scored':point(d,t)
  elif p['result']=='conceded':point(d,1-t)
  elif p['result']=='faulty_rebound':reset(d,'breakdown',1-t)
  else:d.update(next_team=1-t,attack_origin='catch')
 elif k=='elapse':
  if p['milliseconds']>d['remaining_ms']:fail('Elapsed time exceeds the current period')
  d['remaining_ms']-=p['milliseconds']
  if d['remaining_ms']==0:end_period(d)
 elif k=='stop_clock':d['clock_running']=False
 elif k=='resume_clock':d['clock_running']=True
 elif k=='concede':forfeit(d,t)
 elif k=='abandon':d.update(phase='abandoned',clock_running=False)
 elif k=='official_result':finish(d,p['winner'],'no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Period, restart entitlement, active lineup and attack restrictions must permit the event.'],external_observations=['Official shot outcome, pass count, median-line crossing and sanctions.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],period=d['period'],remaining_ms=d['remaining_ms'],clock_running=d['clock_running'],next_team=d['next_team'],active=[active(d,t) for t in (0,1)],entry_limit=d['entry_limit'],last_frame=d['last_frame'],frame_count=d['frame_count'],minimum_passes=1 if d['phase']=='play' and d['attack_origin']=='breakdown' else 0,median_required=d['phase']=='play' and d['attack_origin']=='restart'),completeness=False,reason='official_tchoukball_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='abandoned' else 'ongoing',result_kind=('win' if w is not None else 'no_contest' if d['reason']=='no_contest' else 'draw') if done else 'none',winners=[state['players'][w]['id']] if w is not None else [],losers=[state['players'][1-w]['id']] if w is not None else [],placements=[],reason=d['reason'] if done else 'official_result_required' if d['phase']=='abandoned' else 'ongoing',evidence_required=['Official result decision.'] if d['phase']=='abandoned' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
