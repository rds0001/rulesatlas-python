"""Four-player Belote: two-round trump selection, compulsory trumping and totals."""
from copy import deepcopy
from ..values import fields,fail
CARD=dict(type='integer',minimum=0,maximum=31)
NORMAL=[0,1,2,3,4,5,6,7];TRUMP=[0,1,6,7,2,3,4,5]
POINTS=[0,0,0,2,3,4,10,11];TPOINTS=[0,0,14,20,3,4,10,11]
def strength(c,trump):return (TRUMP if c//8==trump else NORMAL)[c%8]
def winner(trick,trump):
 lead=trick[0]['card']//8
 return max(trick,key=lambda x:(2 if x['card']//8==trump else 1 if x['card']//8==lead else 0,strength(x['card'],trump)))['player']
def playable(d):
 hand=d['hands'][d['turn']];trick=d['trick'];trump=d['trump']
 if not trick:return hand
 lead=trick[0]['card']//8;follow=[c for c in hand if c//8==lead];top=next(x['card'] for x in trick if x['player']==winner(trick,trump));trumps=[c for c in hand if c//8==trump]
 higher=[c for c in trumps if top//8!=trump or strength(c,trump)>strength(top,trump)]
 if follow:return (higher or follow) if lead==trump else follow
 if winner(trick,trump)%2==d['turn']%2:return hand
 return higher or trumps or hand

def validate(d):
 cards=sum(d['hands'],[])+d['stock']+sum(d['won'],[])+[x['card'] for x in d['trick']]+([] if d['upcard'] is None else [d['upcard']])
 if d['phase']=='setup':
  if cards or any(d['scores']) or d['carry']:fail('Initial match must be empty',code='INVALID_STATE')
  return
 if sorted(cards)!=list(range(32)):fail('Every card must occur exactly once',code='INVALID_STATE')
 bidding=d['phase'] in ('bid_first','bid_second','redeal')
 if bidding:
  if d['trump'] is not None or d['maker'] is not None or len(d['stock'])!=11 or d['upcard'] is None or any(len(h)!=5 for h in d['hands']) or any(d['won']) or d['trick'] or d['turn']!=(d['dealer']+1+d['passes'])%4:fail('Invalid trump-selection state',code='INVALID_STATE')
 else:
  if d['trump'] is None or d['maker'] is None or d['stock'] or d['upcard'] is not None:fail('Playing contract is incomplete',code='INVALID_STATE')
  if any(len(w)%4 for w in d['won']):fail('Won piles must contain whole tricks',code='INVALID_STATE')
  completed=sum(len(w) for w in d['won'])//4;actors=[x['player'] for x in d['trick']]
  if len(actors)>3 or len(set(actors))!=len(actors) or any(actors[j]!=(actors[j-1]+1)%4 for j in range(1,len(actors))) or (actors and d['turn']!=(actors[-1]+1)%4):fail('Partial trick order is invalid',code='INVALID_STATE')
  if any(len(d['hands'][p])!=8-completed-int(p in actors) for p in range(4)):fail('Hands do not match completed tricks',code='INVALID_STATE')
  if (d['phase'] in ('round_end','finished'))!=(completed==8):fail('Round phase and trick count disagree',code='INVALID_STATE')
 if (d['belote_player'] is None)!=(d['belote_card'] is None):fail('Pending belote announcement is incomplete',code='INVALID_STATE')
 if d['belote_card'] is not None:
  if bidding or d['belote_card']//8!=d['trump'] or d['belote_card']%8 not in (4,5) or d['belote_card'] not in d['hands'][d['belote_player']] or d['belote_team'] is not None:fail('Rebelote must remain in the announcing player hand',code='INVALID_STATE')
 if (d['phase']=='finished')!=(max(d['scores'])>=1000 and d['scores'][0]!=d['scores'][1]):fail('Match threshold disagrees with phase',code='INVALID_STATE')
def score_round(d):
 team=d['maker']%2;points=[sum((TPOINTS if c//8==d['trump'] else POINTS)[c%8] for c in w) for w in d['won']]
 sweep=next((i for i,w in enumerate(d['won']) if len(w)==32),None)
 points[d['turn']%2]+=100 if sweep is not None else 10
 bonus=[20 if d['belote_team']==i else 0 for i in range(2)]
 if points[team]==points[1-team]:
  d['scores'][1-team]+=points[1-team];d['carry']+=points[team]
 else:
  winning=team if points[team]>points[1-team] else 1-team
  if winning==team:
   for i in range(2):d['scores'][i]+=points[i]
  else:d['scores'][winning]+=sum(points)
  d['scores'][winning]+=d['carry'];d['carry']=0
 for i in range(2):d['scores'][i]+=bonus[i]
 d['phase']='finished' if max(d['scores'])>=1000 and d['scores'][0]!=d['scores'][1] else 'round_end'
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];t=d['turn'];phase=d['phase']
 if k=='deal':
  fields(p,dict(deck=dict(type='array',minItems=32,maxItems=32,items=CARD)),'/params')
  if phase not in ('setup','round_end','redeal') or sorted(p['deck'])!=list(range(32)):fail('Supply a complete external deck between deals')
  if phase!='setup':d['dealer']=(d['dealer']+1)%4
  d.update(hands=[[] for _ in range(4)],won=[[],[]],stock=p['deck'][21:],upcard=p['deck'][20],trump=None,maker=None,passes=0,trick=[],turn=(d['dealer']+1)%4,phase='bid_first',belote_player=None,belote_card=None,belote_team=None)
  for i in range(20):d['hands'][(d['dealer']+1+i)%4].append(p['deck'][i])
  return d
 if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
 if phase in ('bid_first','bid_second'):
  if k=='pass':
   fields(p,{},'/params');d['passes']+=1;d['turn']=(t+1)%4
   if d['passes']==4:d['passes']=0;d['phase']='bid_second' if phase=='bid_first' else 'redeal'
  elif k=='take':
   fields(p,dict(trump=dict(type='integer',minimum=0,maximum=3)),'/params')
   if (p['trump']==d['upcard']//8)!=(phase=='bid_first'):fail('First selection uses the upcard suit; second selection must use another suit')
   d['trump']=p['trump'];d['maker']=t;d['hands'][t].append(d['upcard']);d['upcard']=None
   for j in range(4):
    player=(d['dealer']+1+j)%4;n=2 if player==t else 3;d['hands'][player]+=d['stock'][:n];d['stock']=d['stock'][n:]
   d['turn']=(d['dealer']+1)%4;d['phase']='play'
  else:fail('Pass or take the trump contract')
  return d
 if phase!='play' or k!='play':fail('Play a legal card during a trick')
 fields(p,dict(card=CARD,announce=dict(type='boolean')),'/params');c=p['card']
 if c not in playable(d):fail('Follow suit, head trump, and trump opponents according to the selected obligations')
 pending=d['belote_player']==t and d['belote_card']==c
 if p['announce']:
  if pending:d['belote_team']=t%2
  else:
   other=c+1 if c%8==4 else c-1
   if d['belote_team'] is not None or c//8!=d['trump'] or c%8 not in (4,5) or other not in d['hands'][t]:fail('Belote requires both trump Queen and King when first announced')
   d['belote_player']=t;d['belote_card']=other
 if pending:d['belote_player']=None;d['belote_card']=None
 d['hands'][t].remove(c);d['trick'].append(dict(player=t,card=c));d['turn']=(t+1)%4
 if len(d['trick'])==4:
  w=winner(d['trick'],d['trump']);d['won'][w%2]+=[x['card'] for x in d['trick']];d['trick']=[];d['turn']=w
  if sum(len(w) for w in d['won'])==32:score_round(d)
 return d
def legal(state):
 d=state['data'];phase=d['phase']
 if phase in ('setup','round_end','redeal'):return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(deck=dict(type='array',minItems=32,maxItems=32,items=CARD)),preconditions=['A full externally supplied deck permutation is required.'],external_observations=['Externally shuffled deck.'])],constraints={},completeness=False,reason='external_deal')
 if phase in ('bid_first','bid_second'):
  suits=[d['upcard']//8] if phase=='bid_first' else [s for s in range(4) if s!=d['upcard']//8]
  return [dict(type='pass',params={})]+[dict(type='take',params=dict(trump=s)) for s in suits]
 result=[]
 for c in playable(d):
  result.append(dict(type='play',params=dict(card=c,announce=False)))
  other=c+1 if c%8==4 else c-1
  if (d['belote_player']==d['turn'] and d['belote_card']==c) or (c//8==d['trump'] and c%8 in (4,5) and other in d['hands'][d['turn']] and d['belote_team'] is None):result.append(dict(type='play',params=dict(card=c,announce=True)))
 return result
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';team=d['scores'].index(max(d['scores']));winners=[state['players'][i]['id'] for i in range(4) if i%2==team] if done else []
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=winners,losers=[state['players'][i]['id'] for i in range(4) if i%2!=team] if done else [],placements=[],reason='team_reached_one_thousand' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
