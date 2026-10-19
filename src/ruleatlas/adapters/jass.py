"""Trump-only partnership Schieber Jass with Stoeck and no other declarations."""
from copy import deepcopy
from ..values import fields,fail
CARD=dict(type='integer',minimum=0,maximum=35)
TRUMP=[0,1,2,7,5,8,3,4,6]
POINTS=[0,0,0,0,10,2,3,4,11];TPOINTS=[0,0,0,14,10,20,3,4,11]
def strength(c,trump):return TRUMP[c%9] if c//9==trump else [0,1,2,3,7,4,5,6,8][c%9]
def winner(trick,trump):
 lead=trick[0]['card']//9
 return max(trick,key=lambda x:(2 if x['card']//9==trump else 1 if x['card']//9==lead else 0,strength(x['card'],trump)))['player']
def playable(d):
 hand=d['hands'][d['turn']];trick=d['trick'];trump=d['trump']
 if not trick:return hand
 lead=trick[0]['card']//9;trumps=[c for c in hand if c//9==trump]
 if lead==trump:
  if trumps==[trump*9+5]:return hand
  return trumps or hand
 follow=[c for c in hand if c//9==lead];played_trumps=[x['card'] for x in trick if x['card']//9==trump]
 if len(trumps)==len(hand):return hand
 allowed_trumps=[c for c in trumps if not played_trumps or strength(c,trump)>max(strength(x,trump) for x in played_trumps)]
 return [c for c in hand if c in allowed_trumps or (c in follow if follow else c//9!=trump)]
def validate(d):
 cards=sum(d['hands'],[])+sum(d['won'],[])+[x['card'] for x in d['trick']]
 if d['phase']=='setup':
  if cards or any(d['scores']) or d['trump'] is not None:fail('Initial Jass match must be empty',code='INVALID_STATE')
  return
 if sorted(cards)!=list(range(36)):fail('Every Jass card must occur exactly once',code='INVALID_STATE')
 choosing=d['phase'] in ('choose_trump','choose_partner')
 if choosing:
  if d['trump'] is not None or any(len(h)!=9 for h in d['hands']) or any(d['won']) or d['trick'] or d['turn']!=(d['dealer']+ (1 if d['phase']=='choose_trump' else 3))%4:fail('Invalid trump-choice state',code='INVALID_STATE')
 else:
  if d['trump'] is None or any(len(w)%4 for w in d['won']):fail('Contract or won tricks are invalid',code='INVALID_STATE')
  completed=sum(len(w) for w in d['won'])//4;actors=[x['player'] for x in d['trick']]
  if len(actors)>3 or len(set(actors))!=len(actors) or any(actors[j]!=(actors[j-1]+1)%4 for j in range(1,len(actors))) or (actors and d['turn']!=(actors[-1]+1)%4):fail('Partial trick order is invalid',code='INVALID_STATE')
  if any(len(d['hands'][p])!=9-completed-int(p in actors) for p in range(4)):fail('Hands do not match completed tricks',code='INVALID_STATE')
  if (d['phase'] in ('round_end','finished'))!=(completed==9):fail('Round phase and trick count disagree',code='INVALID_STATE')
 if (d['stoeck_player'] is None)!=(d['stoeck_card'] is None):fail('Pending Stoeck announcement is incomplete',code='INVALID_STATE')
 if d['stoeck_card'] is not None and (choosing or d['stoeck_card']//9!=d['trump'] or d['stoeck_card']%9 not in (6,7) or d['stoeck_card'] not in d['hands'][d['stoeck_player']] or d['stoeck_team'] is not None):fail('Second Stoeck card must remain in the announcing hand',code='INVALID_STATE')
 if (d['phase']=='finished')!=(max(d['scores'])>=1000 and d['scores'][0]!=d['scores'][1]):fail('Match threshold disagrees with phase',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];t=d['turn'];phase=d['phase']
 if k=='deal':
  fields(p,dict(deck=dict(type='array',minItems=36,maxItems=36,items=CARD)),'/params')
  if phase not in ('setup','round_end') or sorted(p['deck'])!=list(range(36)):fail('Supply a complete external deck between deals')
  if phase!='setup':d['dealer']=(d['dealer']+1)%4
  d.update(hands=[[] for _ in range(4)],won=[[],[]],trump=None,trick=[],turn=(d['dealer']+1)%4,phase='choose_trump',stoeck_player=None,stoeck_card=None,stoeck_team=None)
  for i,c in enumerate(p['deck']):d['hands'][(d['dealer']+1+i)%4].append(c)
  return d
 if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
 if phase in ('choose_trump','choose_partner'):
  if k=='push':
   fields(p,{},'/params')
   if phase!='choose_trump':fail('Partner cannot push the choice back')
   d['turn']=(t+2)%4;d['phase']='choose_partner'
  elif k=='choose_trump':
   fields(p,dict(trump=dict(type='integer',minimum=0,maximum=3)),'/params');d['trump']=p['trump'];d['turn']=(d['dealer']+1)%4;d['phase']='play'
  else:fail('Choose trump or push the initial choice to the partner')
  return d
 if phase!='play' or k!='play':fail('Play a legal Jass card during a trick')
 fields(p,dict(card=CARD,announce=dict(type='boolean')),'/params');c=p['card']
 if c not in playable(d):fail('Follow suit or legally trump; undertrumping and the sole trump Jack exception are checked')
 pending=d['stoeck_player']==t and d['stoeck_card']==c
 if p['announce']:
  if pending:d['stoeck_team']=t%2
  else:
   other=c+1 if c%9==6 else c-1
   if d['stoeck_team'] is not None or c//9!=d['trump'] or c%9 not in (6,7) or other not in d['hands'][t]:fail('Stoeck requires the trump Queen and King held together')
   d['stoeck_player']=t;d['stoeck_card']=other
 if pending:d['stoeck_player']=None;d['stoeck_card']=None
 d['hands'][t].remove(c);d['trick'].append(dict(player=t,card=c));d['turn']=(t+1)%4
 if len(d['trick'])==4:
  w=winner(d['trick'],d['trump']);d['won'][w%2]+=[x['card'] for x in d['trick']];d['trick']=[];d['turn']=w
  if sum(len(w) for w in d['won'])==36:
   for team in range(2):
    d['scores'][team]+=sum((TPOINTS if c//9==d['trump'] else POINTS)[c%9] for c in d['won'][team])+(5 if w%2==team else 0)+(100 if len(d['won'][team])==36 else 0)+(20 if d['stoeck_team']==team else 0)
   d['phase']='finished' if max(d['scores'])>=1000 and d['scores'][0]!=d['scores'][1] else 'round_end'
 return d
def legal(state):
 d=state['data'];phase=d['phase']
 if phase in ('setup','round_end'):return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(deck=dict(type='array',minItems=36,maxItems=36,items=CARD)),preconditions=['A full externally supplied deck permutation is required.'],external_observations=['Externally shuffled deck.'])],constraints={},completeness=False,reason='external_deal')
 if phase in ('choose_trump','choose_partner'):return ([dict(type='push',params={})] if phase=='choose_trump' else [])+[dict(type='choose_trump',params=dict(trump=s)) for s in range(4)]
 result=[]
 for c in playable(d):
  result.append(dict(type='play',params=dict(card=c,announce=False)));other=c+1 if c%9==6 else c-1
  if (d['stoeck_player']==d['turn'] and d['stoeck_card']==c) or (c//9==d['trump'] and c%9 in (6,7) and other in d['hands'][d['turn']] and d['stoeck_team'] is None):result.append(dict(type='play',params=dict(card=c,announce=True)))
 return result
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';team=d['scores'].index(max(d['scores']))
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][i]['id'] for i in range(4) if i%2==team] if done else [],losers=[state['players'][i]['id'] for i in range(4) if i%2!=team] if done else [],placements=[],reason='team_reached_one_thousand' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
