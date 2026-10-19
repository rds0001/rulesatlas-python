"""Forty-eight-card Doppelkopf normal hand without announcements or tariffs."""
from copy import deepcopy
from ..values import fields,fail
CARD=dict(type='integer',minimum=0,maximum=47)
INDEX=dict(type='integer',minimum=0,maximum=3)
POINTS=[0,2,3,4,10,11]
def category(c):
 c%=24;s,r=divmod(c,6)
 return 4 if r in (1,2) or s==3 or c==16 else s
def strength(c):
 c%=24;s,r=divmod(c,6)
 return 200 if c==16 else 103-s if r==2 else 93-s if r==1 else r
def winner(trick):
 led=category(trick[0]['card'])
 return max(trick,key=lambda x:(2 if category(x['card'])==4 else 1 if category(x['card'])==led else 0,strength(x['card'])))['player']
def playable(d):
 hand=d['hands'][d['turn']]
 if not d['trick']:return hand
 led=category(d['trick'][0]['card']);follow=[c for c in hand if category(c)==led]
 return follow or hand
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');cards=sum(d['hands'],[])+sum(d['won'],[])+[x['card'] for x in d['trick']]
 if d['phase']=='setup':
  if cards or d['re_players']:bad('Unstarted hand must be empty')
  return
 if sorted(cards)!=list(range(48)):bad('Each physical card must occur exactly once')
 if len(set(d['re_players']))!=len(d['re_players']) or len(d['re_players']) not in (1,2):bad('Re consists of the original clubs-queen holders')
 for i,h in enumerate(d['hands']):
  if any(c in (2,26) for c in h) and i not in d['re_players']:bad('A clubs-queen holder must belong to Re')
 if any(len(w)%4 for w in d['won']):bad('Won piles contain complete tricks')
 completed=sum(len(w) for w in d['won'])//4;actors=[x['player'] for x in d['trick']]
 if len(set(actors))!=len(actors) or any(actors[j]!=(actors[j-1]+1)%4 for j in range(1,len(actors))) or actors and d['turn']!=(actors[-1]+1)%4:bad('Partial trick order is inconsistent')
 if any(len(d['hands'][p])!=12-completed-int(p in actors) for p in range(4)):bad('Hand sizes disagree with completed tricks')
 if (d['phase']=='finished')!=(completed==12):bad('All twelve tricks must resolve')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];t=d['turn']
 if k=='deal':
  fields(p,dict(deck=dict(type='array',minItems=48,maxItems=48,items=CARD),leader=INDEX),'/params')
  if d['phase']!='setup' or sorted(p['deck'])!=list(range(48)):fail('Supply one complete external deck before play')
  hands=[p['deck'][i::4] for i in range(4)]
  d.update(phase='play',hands=hands,won=[[],[],[],[]],trick=[],turn=p['leader'],re_players=[i for i,h in enumerate(hands) if any(c in (2,26) for c in h)]);return d
 if k!='play' or d['phase']!='play':fail('Play a card during the hand')
 fields(p,dict(card=CARD),'/params')
 if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
 c=p['card']
 if c not in playable(d):fail('Follow the led effective suit or trump when possible')
 d['hands'][t].remove(c);d['trick'].append(dict(player=t,card=c));d['turn']=(t+1)%4
 if len(d['trick'])==4:
  w=winner(d['trick']);d['won'][w]+=[x['card'] for x in d['trick']];d['trick']=[];d['turn']=w
  if not any(d['hands']):d['phase']='finished'
 return d
def legal(state):
 d=state['data']
 if d['phase']=='setup':return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(deck=dict(type='array',minItems=48,maxItems=48,items=CARD),leader=INDEX),preconditions=['Supply every physical card once.'],external_observations=['External shuffled deck and opening player.'])],constraints={},completeness=False,reason='external_doppelkopf_deal')
 return [dict(type='play',params=dict(card=c)) for c in playable(d)] if d['phase']=='play' else []
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';score=sum(POINTS[c%6] for i,w in enumerate(d['won']) if i in d['re_players'] for c in w);re_wins=score>=121
 ws=[i for i in range(4) if (i in d['re_players'])==re_wins] if done else []
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][i]['id'] for i in ws],losers=[state['players'][i]['id'] for i in range(4) if i not in ws] if done else [],placements=[],reason=('re_at_least_one_hundred_twenty_one' if re_wins else 'contra_at_least_one_hundred_twenty') if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
