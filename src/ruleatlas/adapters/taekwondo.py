"""2019 cumulative-score Taekwondo, with a one-minute golden round."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
P=I(0,1);B=dict(type='boolean');VALUES=dict(punch=1,body=2,turn_body=4,head=3,turn_head=5)
def round_scores(d,r):return [sum(row[k]*VALUES[k] for k in VALUES)+d['gam_jeom'][r][1-t] for t,row in enumerate(d['techniques'][r])]
def scores(d):return round_scores(d,3) if d['round']==4 else [sum(round_scores(d,r)[t] for r in range(3)) for t in (0,1)]
def penalties(d,all_rounds=False):return [sum(d['gam_jeom'][r][t] for r in range(4 if all_rounds else 3)) for t in (0,1)]
def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason,count=None,break_ms=0)
def evaluate(d):
 s=scores(d)
 if d['round']==4:
  for t in (0,1):
   if d['gam_jeom'][3][t]>=2:finish(d,1-t,'golden_penalties');return
  for t in (0,1):
   if s[t]>=2:finish(d,t,'golden_points');return
 else:
  for t in (0,1):
   if penalties(d)[t]>=10:finish(d,1-t,'punitive');return
  if d['point_gap'] and (d['round']==3 or d['round']==2 and d['phase']=='round_review') and abs(s[0]-s[1])>=20:finish(d,int(s[1]>s[0]),'point_gap')
def superiority(d):
 values=[[d['techniques'][3][t]['punch'] for t in (0,1)],d['pss_hits'],[sum(round_scores(d,r)[t]>round_scores(d,r)[1-t] for r in range(3)) for t in (0,1)],[-v for v in penalties(d,True)]]
 for pair in values:
  if pair[0]!=pair[1]:return int(pair[1]>pair[0])
 return None
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');r=d['round']
 for j in range(r,4):
  if any(any(v for v in x.values()) for x in d['techniques'][j]) or any(d['gam_jeom'][j]):bad('Future rounds cannot contain scores or penalties')
 if d['phase']=='ready' and (d['remaining_ms']!=(60000 if r==4 else 120000) or d['break_ms']):bad('Ready round requires its full duration')
 if d['phase']=='break' and (r==1 or not d['break_ms'] or d['remaining_ms']!=(60000 if r==4 else 120000)):bad('Inter-round rest precedes the next full round')
 if d['phase']!='break' and d['break_ms']:bad('Rest clock outside the inter-round break')
 if d['phase'] in ('fighting','paused') and not d['remaining_ms']:bad('Expired round requires review')
 if d['phase'] in ('round_review','superiority') and d['remaining_ms']:bad('Round review requires an expired clock')
 if d['phase']=='superiority' and (r!=4 or d['pss_hits'] is None):bad('Superiority follows the golden round and recorded PSS hits')
 if r==4 and d['remaining_ms']>60000:bad('Golden round lasts one minute')
 if r==4 and sum(round_scores(d,j)[0]-round_scores(d,j)[1] for j in range(3))!=0:bad('Golden round requires tied regulation scores')
 if r!=4 and d['pss_hits'] is not None:bad('PSS tie-break totals belong to the golden round')
 if d['phase']=='count':
  if d['count'] is None or not d['remaining_ms']:bad('Count requires an unexpired stopped round')
  if len(set(d['count']['players']))!=len(d['count']['players']):bad('Counted athletes must be distinct')
  if any(d['count']['ready'][t] and t not in d['count']['players'] for t in (0,1)):bad('Recovery concerns counted athletes only')
 elif d['count'] is not None:bad('Count data outside a count')
 if d['phase']=='finished':
  if d['reason'] is None or (d['winner'] is None)!=(d['reason']=='no_contest'):bad('Terminal result must identify winner or no contest')
  if d['reason']=='punitive' and (r==4 or penalties(d)[1-d['winner']]<10):bad('Punitive victory requires ten opponent penalties')
  if d['reason']=='point_gap' and (not d['point_gap'] or r not in (2,3) or scores(d)[d['winner']]-scores(d)[1-d['winner']]<20):bad('Point-gap victory requires the configured twenty-point margin')
  if d['reason'] in ('golden_points','golden_penalties') and (r!=4 or scores(d)[d['winner']]<2):bad('Golden victory requires two points')
  if d['reason']=='points' and (r!=3 or d['remaining_ms'] or scores(d)[d['winner']]<=scores(d)[1-d['winner']]):bad('Points victory follows the third round')
  if d['reason']=='superiority' and (r!=4 or d['remaining_ms']):bad('Superiority follows the golden round')
 else:
  if d['winner'] is not None or d['reason'] is not None:bad('Ongoing match cannot have a result')
  copy=deepcopy(d);evaluate(copy)
  if copy['phase']=='finished':bad('A reached score or penalty limit must terminate play')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='ready':
  s['start_round']={}
  if d['round']==1:s['configure']=dict(point_gap=B)
 if ph in ('fighting','break'):s['elapse']=dict(milliseconds=I(1,120000))
 if ph=='fighting':s.update(pause={},knockdown=dict(players=dict(type='array',minItems=1,maxItems=2,items=P)))
 if ph=='paused':s['resume']={}
 if ph in ('fighting','paused','round_review'):s['score']=dict(player=P,technique=dict(type='enum',values=list(VALUES)))
 if ph in ('ready','fighting','paused','break','round_review'):s['gam_jeom']=dict(player=P)
 if ph=='round_review':s['close_round']={}
 if ph=='round_review' and d['round']==4:s['set_pss_hits']=dict(hits=dict(type='array',minItems=2,maxItems=2,items=I(0,10000)))
 if ph=='superiority':s['declare_superiority']=dict(referee=P,judges=dict(type='array',minItems=3,maxItems=3,items=P))
 if ph=='count':
  s['advance_count']=dict(number=I(1,10))
  if d['count']['number']<=8:s['ready_signal']=dict(player=P)
  if d['count']['number']>=8:s['recover']={}
 if ph=='double_count_review':s['official_result']=dict(winner=P)
 s.update(referee_stop=dict(winner=P),withdraw=dict(player=P),disqualify=dict(player=P),no_contest={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='configure':d['point_gap']=p['point_gap']
 elif k in ('start_round','resume'):d['phase']='fighting'
 elif k=='pause':d['phase']='paused'
 elif k=='elapse':
  f='break_ms' if d['phase']=='break' else 'remaining_ms'
  if p['milliseconds']>d[f]:fail('Elapsed time exceeds this interval')
  d[f]-=p['milliseconds']
  if not d[f]:d['phase']='ready' if f=='break_ms' else 'round_review';evaluate(d)
 elif k=='score':d['techniques'][d['round']-1][p['player']][p['technique']]+=1;evaluate(d)
 elif k=='gam_jeom':d['gam_jeom'][d['round']-1][p['player']]+=1;evaluate(d)
 elif k=='close_round':
  evaluate(d)
  if d['phase']=='finished':return d
  if d['round']==4:
   if d['pss_hits'] is None:fail('Golden-round PSS hit totals must be supplied')
   w=superiority(d)
   if w is None:d['phase']='superiority'
   else:finish(d,w,'superiority')
  elif d['round']==3 and scores(d)[0]!=scores(d)[1]:finish(d,int(scores(d)[1]>scores(d)[0]),'points')
  else:d['round']+=1;d.update(phase='break',break_ms=60000,remaining_ms=60000 if d['round']==4 else 120000)
 elif k=='set_pss_hits':d['pss_hits']=p['hits'][:]
 elif k=='declare_superiority':
  if superiority(d) is not None:fail('Numeric superiority must be resolved before a judge vote')
  votes=[p['referee']]+p['judges'];w=p['referee'] if votes.count(0)==2 else int(votes.count(1)>2);finish(d,w,'superiority')
 elif k=='knockdown':
  if len(set(p['players']))!=len(p['players']):fail('Knockdown recipients must be distinct')
  d.update(phase='count',count=dict(players=p['players'][:],number=0,ready=[False,False]))
 elif k=='ready_signal':
  if p['player'] not in d['count']['players']:fail('Only a counted athlete may signal readiness')
  d['count']['ready'][p['player']]=True
 elif k=='advance_count':
  c=d['count']
  if p['number']!=c['number']+1:fail('Counts advance one number at a time')
  c['number']=p['number']
  if c['number']==10:
   not_ready=[t for t in c['players'] if not c['ready'][t]]
   if len(not_ready)==1:finish(d,1-not_ready[0],'referee_stop')
   elif len(not_ready)==2:
    sc=scores(d)
    if sc[0]!=sc[1]:finish(d,int(sc[1]>sc[0]),'double_count_score')
    else:d.update(phase='double_count_review',count=None)
   else:d.update(phase='paused',count=None)
 elif k=='recover':
  if not all(d['count']['ready'][t] for t in d['count']['players']):fail('All counted athletes must have signalled readiness by eight')
  d.update(phase='fighting',count=None)
 elif k in ('referee_stop','official_result'):finish(d,p['winner'],'referee_stop' if k=='referee_stop' else 'official_result')
 elif k in ('withdraw','disqualify'):finish(d,1-p['player'],'withdrawal' if k=='withdraw' else 'disqualification')
 elif k=='no_contest':finish(d,None,'no_contest')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Round, clock, score, penalty and count conditions must permit the event.'],external_observations=['Confirmed scoring techniques, referee penalties, count signals and PSS hit totals.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],round=d['round'],remaining_ms=d['remaining_ms'],break_ms=d['break_ms'],scores=scores(d),gam_jeom=penalties(d,True),count=d['count']),completeness=False,reason='official_2019_taekwondo_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner'];review=d['phase'] in ('round_review','superiority','double_count_review')
 return dict(status='terminal' if done else 'awaiting_adjudication' if review else 'ongoing',result_kind=('no_contest' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if w is not None else [],losers=[state['players'][1-w]['id']] if w is not None else [],placements=[],reason=d['reason'] if done else 'official_review_required' if review else 'ongoing',evidence_required=['Official round review or superiority decision.'] if review else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
