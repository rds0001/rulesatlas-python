"""A pre-agreed four-player suit-solo hand, without monetary tariffs."""
from copy import deepcopy
from ..values import fields,fail
CARD=dict(type='integer',minimum=0,maximum=31)
INDEX=dict(type='integer',minimum=0,maximum=3)
POINTS=[0,0,0,2,3,4,10,11]
def category(c,trump):return 4 if c%8 in (3,4) or c//8==trump else c//8
def strength(c):return 100+3-c//8 if c%8==4 else 90+3-c//8 if c%8==3 else c%8
def winner(trick,trump):
 lead=category(trick[0]['card'],trump)
 return max(trick,key=lambda x:(2 if category(x['card'],trump)==4 else 1 if category(x['card'],trump)==lead else 0,strength(x['card'])))['player']
def playable(d):
 hand=d['hands'][d['turn']]
 if not d['trick']:return hand
 led=category(d['trick'][0]['card'],d['trump']);follow=[c for c in hand if category(c,d['trump'])==led]
 return follow or hand
def points(d):return [sum(POINTS[c%8] for c in w) for w in d['won']]
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 cards=sum(d['hands'],[])+sum(d['won'],[])+[x['card'] for x in d['trick']]
 if d['phase']=='setup':
  if cards or d['trump'] is not None or d['declarer'] is not None:bad('Unstarted solo must contain no dealt cards or contract')
  return
 if sorted(cards)!=list(range(32)) or d['trump'] is None or d['declarer'] is None:bad('A complete unique deck and solo contract are required')
 if any(len(w)%4 for w in d['won']):bad('Won piles must contain complete tricks')
 completed=sum(len(w) for w in d['won'])//4;actors=[x['player'] for x in d['trick']]
 if len(set(actors))!=len(actors) or any(actors[j]!=(actors[j-1]+1)%4 for j in range(1,len(actors))) or actors and d['turn']!=(actors[-1]+1)%4:bad('Partial trick turn order is inconsistent')
 if any(len(d['hands'][p])!=8-completed-int(p in actors) for p in range(4)):bad('Hand sizes disagree with the trick count')
 if (d['phase']=='finished')!=(completed==8):bad('Resolve all eight tricks before the hand ends')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];t=d['turn']
 if k=='deal':
  fields(p,dict(deck=dict(type='array',minItems=32,maxItems=32,items=CARD),declarer=INDEX,trump=INDEX,leader=INDEX),'/params')
  if d['phase']!='setup' or sorted(p['deck'])!=list(range(32)):fail('Deal one complete external deck with the agreed solo contract')
  d.update(phase='play',hands=[p['deck'][i::4] for i in range(4)],won=[[],[],[],[]],trick=[],turn=p['leader'],declarer=p['declarer'],trump=p['trump']);return d
 if k!='play' or d['phase']!='play':fail('Play a card during an active solo hand')
 fields(p,dict(card=CARD),'/params')
 if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
 c=p['card']
 if c not in playable(d):fail('Follow the led suit or trump category when possible')
 d['hands'][t].remove(c);d['trick'].append(dict(player=t,card=c));d['turn']=(t+1)%4
 if len(d['trick'])==4:
  w=winner(d['trick'],d['trump']);d['won'][w]+=[x['card'] for x in d['trick']];d['trick']=[];d['turn']=w
  if not any(d['hands']):d['phase']='finished'
 return d
def legal(state):
 d=state['data']
 if d['phase']=='setup':return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(deck=dict(type='array',minItems=32,maxItems=32,items=CARD),declarer=INDEX,trump=INDEX,leader=INDEX),preconditions=['Supply each card once and the pre-agreed solo contract.'],external_observations=['External shuffle and agreed declarer, trump suit and opening player.'])],constraints={},completeness=False,reason='external_solo_deal')
 return [dict(type='play',params=dict(card=c)) for c in playable(d)] if d['phase']=='play' else []
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';p=points(d);decl=d['declarer'];win=done and p[decl]>=61
 ws=([decl] if win else [i for i in range(4) if i!=decl]) if done else []
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][i]['id'] for i in ws],losers=[state['players'][i]['id'] for i in range(4) if i not in ws] if done else [],placements=[],reason=('solo_at_least_sixty_one' if win else 'defenders_at_least_sixty') if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
