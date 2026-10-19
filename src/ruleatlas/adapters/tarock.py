"""One pre-agreed three-player Tarock contract, with a three-card talon pickup."""
from copy import deepcopy
from ..values import fields, fail
CARD=dict(type='integer',minimum=0,maximum=53)
PLAYER=dict(type='integer',minimum=0,maximum=2)
def category(c):return 4 if c>=32 else c//8
def strength(c):return c-32 if c>=32 else c%8
def protected(c):return c in (32,52,53) or c<32 and c%8==7
def value(c):return 5 if protected(c) else 1 if c>=32 or c%8<4 else c%8-2
def points(cards):
 # All scoring piles have a multiple of three cards in this contract.
 return sum(value(c) for c in cards)-2*(len(cards)//3)
def solo_points(d):return 0 if d['declarer'] is None else points(d['won'][d['declarer']]+d['discard'])
def playable(d):
 hand=d['hands'][d['turn']]
 if not d['trick']:return hand
 led=category(d['trick'][0]['card']);same=[c for c in hand if category(c)==led]
 return same or [c for c in hand if c>=32] or hand
def trick_winner(trick):
 led=category(trick[0]['card'])
 return max(trick,key=lambda e:(2 if e['card']>=32 else 1 if category(e['card'])==led else 0,strength(e['card'])))['player']
def discardable(d,cards):
 hand=d['hands'][d['declarer']]
 if len(set(cards))!=3 or any(c not in hand or protected(c) for c in cards):return False
 plain=[c for c in hand if c<32 and not protected(c)]
 return sum(c<32 for c in cards)==min(3,len(plain))
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 allcards=sum(d['hands'],[])+sum(d['won'],[])+d['talon']+d['discard']+[r['card'] for r in d['trick']]
 if d['phase']=='setup':
  if allcards or d['declarer'] is not None:bad('Setup must precede dealing and the agreed contract')
  return
 if sorted(allcards)!=list(range(54)) or d['declarer'] is None:bad('The state requires one complete unique deck and a declarer')
 if any(len(w)%3 for w in d['won']):bad('Won piles contain complete three-card tricks')
 if any(protected(c) for c in d['discard']):bad('Kings and the three highest-value trumps cannot be discarded')
 if d['phase'] in ('choose','discard'):
  if any(d['won']) or d['trick'] or d['discard'] or d['turn']!=d['declarer']:bad('Talon selection and discarding precede all tricks')
  expected=[16]*3
  if d['phase']=='discard':expected[d['declarer']]=19
  if [len(h) for h in d['hands']]!=expected or len(d['talon'])!=(6 if d['phase']=='choose' else 3):bad('Talon phase hand sizes are inconsistent')
  return
 if len(d['discard'])!=3 or len(d['talon'])!=3:bad('Play requires three discarded and three unselected talon cards')
 completed=sum(len(w) for w in d['won'])//3;actors=[r['player'] for r in d['trick']]
 if len(set(actors))!=len(actors) or any(actors[j]!=(actors[j-1]+1)%3 for j in range(1,len(actors))) or actors and d['turn']!=(actors[-1]+1)%3:bad('Trick order and next player disagree')
 if any(len(d['hands'][i])!=16-completed-int(i in actors) for i in range(3)):bad('Hand sizes disagree with completed and partial tricks')
 if (d['phase']=='finished')!=(completed==16):bad('The hand ends after sixteen complete tricks')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase']
 if k=='deal':
  fields(p,dict(deck=dict(type='array',minItems=54,maxItems=54,items=CARD),declarer=PLAYER,leader=PLAYER),'/params')
  if phase!='setup' or sorted(p['deck'])!=list(range(54)):fail('Deal one complete deck and an agreed contract before play')
  d.update(phase='choose',hands=[p['deck'][i:48:3] for i in range(3)],talon=p['deck'][48:],declarer=p['declarer'],leader=p['leader'],turn=p['declarer']);return d
 if action.get('actor') is not None and action['actor']!=state['players'][d['turn']]['id']:fail('Wrong actor')
 if k=='choose_talon':
  fields(p,dict(half=dict(type='integer',minimum=0,maximum=1)),'/params')
  if phase!='choose':fail('Choose a talon half immediately after the deal')
  h=p['half'];d['hands'][d['declarer']]+=d['talon'][3*h:3*h+3];d['talon']=d['talon'][3*(1-h):3*(1-h)+3];d['phase']='discard'
 elif k=='discard':
  fields(p,dict(cards=dict(type='array',minItems=3,maxItems=3,items=CARD)),'/params')
  if phase!='discard' or not discardable(d,p['cards']):fail('Discard three owned unprotected cards, exhausting eligible plain cards before trumps')
  for c in p['cards']:d['hands'][d['declarer']].remove(c)
  d.update(discard=sorted(p['cards']),phase='play',turn=d['leader'])
 elif k=='play':
  fields(p,dict(card=CARD),'/params')
  if phase!='play' or p['card'] not in playable(d):fail('Follow suit when possible; otherwise play a trump if available')
  c=p['card'];t=d['turn'];d['hands'][t].remove(c);d['trick'].append(dict(player=t,card=c));d['turn']=(t+1)%3
  if len(d['trick'])==3:
   w=trick_winner(d['trick']);d['won'][w]+=[r['card'] for r in d['trick']];d['trick']=[];d['turn']=w
   if not any(d['hands']):d['phase']='finished'
 else:fail('Unknown Tarock action')
 return d
def legal(state):
 d=state['data'];ph=d['phase']
 if ph in ('setup','discard'):
  schema=dict(deck=dict(type='array',minItems=54,maxItems=54,items=CARD),declarer=PLAYER,leader=PLAYER) if ph=='setup' else dict(cards=dict(type='array',minItems=3,maxItems=3,items=CARD))
  return dict(mode='event_types',actions=[],action_types=[dict(type='deal' if ph=='setup' else 'discard',params_schema=schema,preconditions=['External complete deck and agreed contract.' if ph=='setup' else 'Three owned cards; kings and trull protected; plain cards before trumps.'],external_observations=['External shuffle and contract agreement.'] if ph=='setup' else [])],constraints=dict(phase=ph,declarer=d['declarer'],exposed_discard=[c for c in d['discard'] if c>=32]),completeness=False,reason='external_deal' if ph=='setup' else 'constrained_card_selection')
 if ph=='choose':return [dict(type='choose_talon',params=dict(half=h)) for h in (0,1)]
 if ph=='play':return [dict(type='play',params=dict(card=c)) for c in playable(d)]
 return []
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';decl=d['declarer'];win=done and solo_points(d)>=36
 winners=([decl] if win else [i for i in range(3) if i!=decl]) if done else []
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][i]['id'] for i in winners],losers=[state['players'][i]['id'] for i in range(3) if i not in winners] if done else [],placements=[],reason=('declarer_at_least_thirty_six' if win else 'defenders_at_least_thirty_five') if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
