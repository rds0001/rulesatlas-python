"""2017 adult Sanda: five scorecards, sanctions and round/match precedence."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
P=I(0,1);B=dict(type='boolean')
def wins(d):return [d['rounds'].count(t) for t in (0,1)]
def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason,break_ms=0)
def award_round(d,w):
 d['rounds'].append(w)
 ww=wins(d)
 if max(ww)>=2:finish(d,int(ww[1]>ww[0]),'two_rounds')
 elif len(d['rounds'])>=3:
  if ww[0]!=ww[1]:finish(d,int(ww[1]>ww[0]),'rounds')
  elif d['round_robin']:finish(d,None,'draw')
  elif d['warnings'][0]!=d['warnings'][1]:finish(d,int(d['warnings'][1]<d['warnings'][0]),'fewer_warnings')
  elif d['admonitions'][0]!=d['admonitions'][1]:finish(d,int(d['admonitions'][1]<d['admonitions'][0]),'fewer_admonitions')
  else:d.update(phase='break',break_ms=60000)
 else:d.update(phase='break',break_ms=60000)
def gap(d):
 for t in (0,1):
  if all(s[t]-s[1-t]>=12 for s in d['scores']):finish(d,t,'twelve_point_gap');return
def add_points(d,t,n):
 for s in d['scores']:s[t]+=n
 gap(d)
def votes(d):
 result=[]
 for s in d['scores']:
  w=None
  for pair,more in [(s,True),(d['round_warnings'],False),(d['round_admonitions'],False),(d['weights_grams'],False)]:
   if pair[0]!=pair[1]:w=int(pair[1]>pair[0]) if more else int(pair[1]<pair[0]);break
  result.append(w)
 return result
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if any(d['round_warnings'][t]>d['warnings'][t] or d['round_admonitions'][t]>d['admonitions'][t] or d['round_counts'][t]>d['total_counts'][t] for t in (0,1)):bad('Round counters cannot exceed bout totals')
 if d['phase'] in ('judging','split_review') and d['remaining_ms']:bad('Score review follows the round clock')
 if d['phase']=='break' and (not d['rounds'] or not d['break_ms']):bad('Rest follows a completed round')
 if d['phase']!='break' and d['break_ms']:bad('Rest clock outside a rest')
 if d['phase']=='ready' and d['remaining_ms']!=120000:bad('Ready round has its full duration')
 if d['phase'] in ('fighting','paused') and not d['remaining_ms']:bad('Expired rounds require judging')
 if d['phase'] not in ('finished','break') and (max(d['off_platform'])>=2 or max(d['round_counts'])>=2):bad('Round-ending event must leave active play')
 for j in range(len(d['rounds'])):
  if any(d['rounds'][:j].count(t)>=2 for t in (0,1)):bad('No round follows two round wins')
 if d['phase']=='finished':
  if d['reason'] is None or (d['winner'] is None)!=(d['reason'] in ('draw','no_contest')):bad('Finished result must agree with winner presence')
  if d['reason']=='two_rounds' and wins(d)[d['winner']]!=2:bad('Two-round victory requires two wins')
  if d['reason']=='draw' and (not d['round_robin'] or len(d['rounds'])<3 or wins(d)[0]!=wins(d)[1]):bad('Draw requires tied round-robin bout')
 elif d['winner'] is not None or d['reason'] is not None or max(wins(d))>=2 or max(d['warnings'])>=3 or max(d['total_counts'])>=3:bad('A decided bout must finish')
 if d['phase']!='finished':
  c=deepcopy(d);gap(c)
  if c['phase']=='finished':bad('Twelve-point consensus ends the bout')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='ready':
  s['start_round']={}
  if not d['rounds']:s['configure']=dict(round_robin=B,weights_grams=dict(type='array',minItems=2,maxItems=2,items=I(1,200000)))
 if ph in ('fighting','break'):s['elapse']=dict(milliseconds=I(1,120000))
 if ph=='fighting':s['pause']={}
 if ph=='paused':s['resume']={}
 if ph in ('fighting','paused','judging'):
  s.update(technical_score=dict(player=P,points=dict(type='enum',values=[1,2]),judges=dict(type='array',minItems=5,maxItems=5,items=B)),sanction=dict(player=P,kind=dict(type='enum',values=['admonition','warning'])))
 if ph in ('fighting','paused'):
  s.update(off_platform=dict(player=P),forcible_count=dict(player=P,continued=B))
 if ph=='judging':s['close_round']={}
 if ph=='split_review':s['head_judge_decision']=dict(winner=dict(P,nullable=True))
 s.update(referee_stop=dict(winner=P),withdraw=dict(player=P),disqualify=dict(player=P),no_contest={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='configure':d.update(round_robin=p['round_robin'],weights_grams=p['weights_grams'][:])
 elif k in ('start_round','resume'):d['phase']='fighting'
 elif k=='pause':d['phase']='paused'
 elif k=='elapse':
  field='break_ms' if d['phase']=='break' else 'remaining_ms'
  if p['milliseconds']>d[field]:fail('Elapsed time exceeds the current interval')
  d[field]-=p['milliseconds']
  if not d[field]:
   if field=='break_ms':d.update(phase='ready',remaining_ms=120000,scores=[[0,0] for _ in range(5)],round_warnings=[0,0],round_admonitions=[0,0],round_counts=[0,0],off_platform=[0,0])
   else:d['phase']='judging'
 elif k=='technical_score':
  if not any(p['judges']):fail('At least one judge must award the technical score')
  for j,awarded in enumerate(p['judges']):
   if awarded:d['scores'][j][p['player']]+=p['points']
  gap(d)
 elif k=='sanction':
  t=p['player'];kind=p['kind'];name='warnings' if kind=='warning' else 'admonitions';d[name][t]+=1;d['round_'+name][t]+=1
  add_points(d,1-t,2 if kind=='warning' else 1)
  if d['warnings'][t]==3:finish(d,1-t,'three_warnings')
 elif k=='off_platform':
  t=p['player'];d['off_platform'][t]+=1
  add_points(d,1-t,2)
  if d['phase']!='finished' and d['off_platform'][t]==2:award_round(d,1-t)
  if d['phase']=='fighting':d['phase']='paused'
 elif k=='forcible_count':
  t=p['player'];d['round_counts'][t]+=1;d['total_counts'][t]+=1
  add_points(d,1-t,2)
  if not p['continued']:finish(d,1-t,'knockout')
  elif d['total_counts'][t]==3:finish(d,1-t,'three_counts')
  elif d['phase']!='finished' and d['round_counts'][t]==2:award_round(d,1-t)
  if d['phase']=='fighting':d['phase']='paused'
 elif k=='close_round':
  vv=votes(d)
  for w in (0,1,None):
   if vv.count(w)>=3:award_round(d,w);break
  else:d['phase']='split_review'
 elif k=='head_judge_decision':award_round(d,p['winner'])
 elif k=='referee_stop':finish(d,p['winner'],'referee_stop')
 elif k in ('withdraw','disqualify'):finish(d,1-p['player'],'withdrawal' if k=='withdraw' else 'disqualification')
 elif k=='no_contest':finish(d,None,'no_contest')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Round, referee counters and scoring conditions must permit the event.'],external_observations=['Judge-approved technical points, official completed counts, platform exits and sanctions.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],round=len(d['rounds'])+(0 if d['phase'] in ('break','finished') else 1),remaining_ms=d['remaining_ms'],break_ms=d['break_ms'],rounds_won=wins(d),scores=d['scores'],warnings=d['warnings'],admonitions=d['admonitions'],round_counts=d['round_counts'],total_counts=d['total_counts'],off_platform=d['off_platform']),completeness=False,reason='official_2017_sanda_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner'];review=d['phase'] in ('judging','split_review')
 return dict(status='terminal' if done else 'awaiting_adjudication' if review else 'ongoing',result_kind=('no_contest' if d['reason']=='no_contest' else 'draw' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if w is not None else [],losers=[state['players'][1-w]['id']] if w is not None else [],placements=[],reason=d['reason'] if done else 'round_review_required' if review else 'ongoing',evidence_required=['Official score-sheet review or head judge ruling.'] if review else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
