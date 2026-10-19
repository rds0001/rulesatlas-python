"""Twenty-four-card Sixty-Six: stock, strict following, marriages and closing."""
from copy import deepcopy
from ..values import fields,fail
POINTS=[0,2,3,4,10,11]
CARD=dict(type='integer',minimum=0,maximum=23)
def scores(d):return [sum(POINTS[c%6] for c in d['won'][p])+(sum(40 if s==d['trump_suit'] else 20 for s in d['marriages'][p]) if d['won'][p] else 0) for p in (0,1)]
def playable(d):
 h=d['hands'][d['turn']]
 if not d['trick'] or d['stock'] and d['closer'] is None:return sorted(h)
 lead=d['trick'][0];same=[c for c in h if c//6==lead//6];higher=[c for c in same if c%6>lead%6]
 return sorted(higher or same or [c for c in h if c//6==d['trump_suit']] or h)
def award(d,w,n,reason):
 d.update(phase='hand_end',hand_winner=w,hand_value=n,reason=reason);d['match_points'][w]+=n
 if d['match_points'][w]>=7:d['phase']='finished'
 return d
def reached(d,p):
 if scores(d)[p]<66:return False
 if d['closer'] is not None:
  if p!=d['closer']:award(d,p,3 if not d['close_opponent_tricks'] else 2,'closure_failed')
  else:award(d,p,3 if not d['close_opponent_tricks'] else 2 if d['close_opponent_score']<33 else 1,'closed_sixty_six')
 else:
  q=1-p;award(d,p,3 if not d['won'][q] else 2 if scores(d)[q]<33 else 1,'sixty_six')
 return True
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['phase']=='deal':
  if any(d['hands']) or d['stock'] or any(d['won']) or d['trick'] or d['trump_suit'] is not None or any(d['marriages']) or d['closer'] is not None or d['hand_winner'] is not None or d['hand_value'] or d['reason'] is not None or max(d['match_points'])>=7:bad('A new hand starts with cleared card and result fields')
  return
 if sorted(sum(d['hands'],[])+d['stock']+sum(d['won'],[])+d['trick'])!=list(range(24)):bad('Each of the twenty-four cards must occur once')
 if d['trump_suit'] is None or len(d['stock'])%2 or any(len(h)%2 for h in d['won']):bad('Trump, stock and captured pairs are inconsistent')
 if d['stock'] and d['stock'][-1]//6!=d['trump_suit']:bad('Exposed bottom card must have the trump suit')
 if d['turn']!=(1-d['leader'] if d['trick'] else d['leader']):bad('Current player must follow the trick leader')
 sizes=[len(d['hands'][p])+(1 if d['trick'] and p==d['leader'] else 0) for p in (0,1)]
 if sizes[0]!=sizes[1] or d['stock'] and d['closer'] is None and (sizes not in ([6,6],[5,5]) or d['phase']=='play' and sizes!=[6,6]):bad('Hand sizes must agree with trick and stock status')
 marriages=sum(d['marriages'],[])
 if len(set(marriages))!=len(marriages):bad('A suit marriage can be announced only once')
 for p in (0,1):
  for s in d['marriages'][p]:
   if any(s*6+r in d['stock']+d['hands'][1-p] for r in (2,3)):bad('An announced king and queen cannot be in the stock or opposing hand')
 if d['closer'] is None:
  if d['close_opponent_score'] or d['close_opponent_tricks']:bad('Closure snapshots require a closed stock')
 elif not d['stock'] or d['close_opponent_score']>scores(d)[1-d['closer']] or d['close_opponent_tricks']>len(d['won'][1-d['closer']])//2:bad('A closed stock retains its cards and a plausible opponent snapshot')
 if d['phase']=='play':
  if not any(d['hands']) or d['hand_winner'] is not None or d['hand_value'] or d['reason'] is not None or max(d['match_points'])>=7 or max(scores(d))>=66:bad('Ongoing hand must have cards and no achieved winning score')
 else:
  w=d['hand_winner'];n=d['hand_value'];reason=d['reason']
  if w is None or n<1 or d['match_points'][w]<n or (d['phase']=='finished')!=(d['match_points'][w]>=7) or d['match_points'][1-w]>=7 or d['trick']:bad('Completed hand and match result are inconsistent')
  if reason=='sixty_six':
   expected=3 if not d['won'][1-w] else 2 if scores(d)[1-w]<33 else 1
   if d['closer'] is not None or scores(d)[w]<66 or n!=expected:bad('Open-stock hand value must follow the losing score and captured tricks')
  elif reason=='closed_sixty_six':
   expected=3 if not d['close_opponent_tricks'] else 2 if d['close_opponent_score']<33 else 1
   if d['closer']!=w or scores(d)[w]<66 or n!=expected:bad('Successful closure uses the opponent snapshot')
  elif reason=='closure_failed':
   if d['closer']!=1-w or n!=(3 if not d['close_opponent_tricks'] else 2) or scores(d)[1-w]>=66 or (any(d['hands']) and scores(d)[w]<66):bad('Failed closure awards the opponent two or three game points')
  elif reason=='last_trick':
   if d['closer'] is not None or any(d['hands']) or d['stock'] or n!=1 or d['leader']!=w or max(scores(d))>=66:bad('Without sixty-six, the final trick wins one game point')
  else:bad('Unknown completed-hand reason')
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];t=d['turn']
 if k=='next_hand':
  fields(p,{},'/params')
  if d['phase']!='hand_end':fail('Finish the current hand before dealing the next')
  d.update(phase='deal',dealer=1-d['dealer'],hands=[[],[]],stock=[],won=[[],[]],trick=[],trump_suit=None,marriages=[[],[]],closer=None,close_opponent_score=0,close_opponent_tricks=0,hand_winner=None,hand_value=0,reason=None)
  d['turn']=d['leader']=1-d['dealer'];return d
 if k=='deal':
  fields(p,dict(cards=dict(type='array',minItems=24,maxItems=24,items=CARD)),'/params');cards=p['cards']
  if d['phase']!='deal' or len(set(cards))!=24:fail('Supply a permutation of all twenty-four cards for the next hand')
  lead=1-d['dealer'];d['hands'][lead]=cards[:12:2];d['hands'][1-lead]=cards[1:12:2];d.update(stock=cards[12:],trump_suit=cards[-1]//6,phase='play',turn=lead,leader=lead);return d
 if d['phase']!='play':fail('No card action outside a playing hand')
 if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
 if k=='exchange_trump':
  fields(p,{},'/params');jack=d['trump_suit']*6+1
  if d['trick'] or d['closer'] is not None or not d['stock'] or not d['won'][t] or jack not in d['hands'][t]:fail('A leader with a won trick may exchange the trump jack while the stock is open')
  d['hands'][t].remove(jack);d['hands'][t].append(d['stock'][-1]);d['stock'][-1]=jack;return d
 if k=='close_stock':
  fields(p,{},'/params')
  if d['trick'] or d['closer'] is not None or not d['stock']:fail('Only the leader can close a nonempty open stock before leading')
  d.update(closer=t,close_opponent_score=scores(d)[1-t],close_opponent_tricks=len(d['won'][1-t])//2);return d
 if k!='play':fail('Unknown action')
 fields(p,dict(card=CARD,marriage=dict(type='boolean')),'/params');c=p['card']
 if c not in playable(d):fail('Play a held card, obeying mandatory suit, heading and trumping after stock closure or exhaustion')
 if p['marriage']:
  s=c//6
  if d['trick'] or c%6 not in (2,3) or s*6+(5-c%6) not in d['hands'][t] or s in sum(d['marriages'],[]):fail('Announce a held king-queen pair by leading one of its cards once per suit')
  d['marriages'][t].append(s)
  if reached(d,t):return d
 d['hands'][t].remove(c);d['trick'].append(c)
 if len(d['trick'])==1:d['turn']=1-t;return d
 a,b=d['trick'];second=(a//6==b//6 and b%6>a%6) or (a//6!=b//6 and b//6==d['trump_suit']);w=1-d['leader'] if second else d['leader']
 d['won'][w]+=d['trick'];d['trick']=[];d['turn']=d['leader']=w
 if reached(d,w):return d
 if not any(d['hands']):
  if d['closer'] is not None:return award(d,1-d['closer'],3 if not d['close_opponent_tricks'] else 2,'closure_failed')
  return award(d,w,1,'last_trick')
 if d['stock'] and d['closer'] is None:
  d['hands'][w].append(d['stock'].pop(0));d['hands'][1-w].append(d['stock'].pop(0))
 return d
def legal(state):
 d=state['data'];t=d['turn']
 if d['phase']=='deal':return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(cards=dict(type='array',minItems=24,maxItems=24,items=CARD)),preconditions=['Permutation of all twenty-four cards.'],external_observations=['First twelve alternate from nondealer; the stock bottom is exposed trump.'])],constraints={},completeness=False,reason='external_deck_required')
 if d['phase']=='hand_end':return [dict(type='next_hand',params={})]
 result=[]
 for c in playable(d):
  result.append(dict(type='play',params=dict(card=c,marriage=False)))
  if not d['trick'] and c%6 in (2,3) and c//6*6+(5-c%6) in d['hands'][t] and c//6 not in sum(d['marriages'],[]):result.append(dict(type='play',params=dict(card=c,marriage=True)))
 if not d['trick'] and d['stock'] and d['closer'] is None:
  result.append(dict(type='close_stock',params={}))
  if d['won'][t] and d['trump_suit']*6+1 in d['hands'][t]:result.append(dict(type='exchange_trump',params={}))
 return result
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['hand_winner']
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p==w else 2,game_points=d['match_points'][p]) for p in (0,1)] if done else [],reason='seven_game_points' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
