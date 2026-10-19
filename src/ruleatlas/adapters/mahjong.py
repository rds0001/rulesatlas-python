"""Unscored 136-tile Mahjong hand with explicit claims and structural wins."""
from copy import deepcopy
from collections import Counter
from ..values import fields,fail
P=dict(type='integer',minimum=0,maximum=3)
C=dict(type='integer',minimum=0,maximum=135)
ORPHANS={0,8,9,17,18,26,*range(27,34)}
def tile(c):return c//4
def sequence(cards):
 rr=sorted(tile(c) for c in cards)
 return len(rr)==3 and rr[0]<27 and rr[0]//9==rr[2]//9 and rr==list(range(rr[0],rr[0]+3))
def groups(counts):
 if not any(counts):return True
 r=next(i for i,x in enumerate(counts) if x)
 if counts[r]>=3:
  cc=counts[:];cc[r]-=3
  if groups(cc):return True
 if r<27 and r%9<=6 and counts[r+1] and counts[r+2]:
  cc=counts[:]
  for i in (r,r+1,r+2):cc[i]-=1
  if groups(cc):return True
 return False
def winning(hand,melds):
 if len(hand)!=14-3*len(melds):return False
 counts=[0]*34
 for c in hand:counts[tile(c)]+=1
 if not melds:
  if sum(x==2 for x in counts)==7:return True
  if {i for i,x in enumerate(counts) if x}==ORPHANS and max(counts)==2:return True
 for r,x in enumerate(counts):
  if x>=2:
   cc=counts[:];cc[r]-=2
   if groups(cc):return True
 return False
def kong_count(d):return sum(m['kind']=='kong' for ms in d['melds'] for m in ms)
def can_replace(d):return bool(d['wall']) and bool(d['dead_wall']) and kong_count(d)<4
def replacement(d):
 d['hands'][d['turn']].append(d['dead_wall'].pop());d['dead_wall'].insert(0,d['wall'].pop());d['phase']='discard';d['drawn']=True

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 cards=sum(d['hands'],[])+sum(d['rivers'],[])+d['wall']+d['dead_wall']+[c for ms in d['melds'] for m in ms for c in m['cards']]
 if d['phase']=='setup':
  if cards or d['pending'] is not None or d['winner'] is not None:bad('Setup precedes the complete external tile deal')
  return
 if sorted(cards)!=list(range(136)):bad('All 136 physical tiles must occur exactly once')
 if len(d['dead_wall'])!=14 or kong_count(d)>4:bad('The declared hand retains fourteen dead-wall tiles and at most four kongs')
 for t in range(4):
  for m in d['melds'][t]:
   cc=m['cards']
   if m['kind']=='chow' and not sequence(cc) or m['kind']=='pung' and (len(cc)!=3 or len({tile(c) for c in cc})!=1) or m['kind']=='kong' and (len(cc)!=4 or len({tile(c) for c in cc})!=1):bad('Declared meld tiles must match their kind')
   if m['kind']=='chow' and m['from_player']!=(t-1)%4:bad('A chow must originate from the preceding seat')
   if m['open']!=(m['from_player'] is not None) or not m['open'] and m['kind']!='kong' or m['from_player']==t:bad('Meld source and visibility are inconsistent')
  expected=14 if t==d['turn'] and d['phase'] in ('discard','kong_reaction') or t==d['winner'] and d['phase']=='finished' else 13
  if len(d['hands'][t])+3*len(d['melds'][t])!=expected:bad('Concealed hand size disagrees with melds and phase')
 if d['phase'] in ('reaction','kong_reaction'):
  p=d['pending']
  if p is None or p['player']!=d['turn']:bad('Claim window needs the source player and tile')
  if d['phase']=='reaction':
   if not d['rivers'][p['player']] or d['rivers'][p['player']][-1]!=p['tile']:bad('Claims refer to the latest discard')
  else:
   if p['tile'] not in d['hands'][p['player']] or p['meld_index']>=len(d['melds'][p['player']]):bad('Added-kong tile and meld must exist')
   m=d['melds'][p['player']][p['meld_index']]
   if m['kind']!='pung' or tile(m['cards'][0])!=tile(p['tile']):bad('Added kong must extend a matching pung')
  if d['claims'][p['player']] is not None:bad('Source player cannot claim their own tile')
  for who,claim in enumerate(d['claims']):
   if claim is None:continue
   cc=claim['cards'];kind=claim['kind']
   if len(set(cc))!=len(cc) or any(x not in d['hands'][who] for x in cc):bad('Recorded claims require distinct owned tiles')
   if d['phase']=='kong_reaction' and kind not in ('pass','win'):bad('Only a win can interrupt an added kong')
   if kind in ('pass','win') and cc or kind=='win' and not winning(d['hands'][who]+[p['tile']],d['melds'][who]):bad('Recorded pass or win claim is inconsistent')
   if kind=='chow' and (who!=(p['player']+1)%4 or len(cc)!=2 or not sequence(cc+[p['tile']])):bad('Recorded chow claim is inconsistent')
   if kind in ('pung','kong') and (len(cc)!=(2 if kind=='pung' else 3) or any(tile(x)!=tile(p['tile']) for x in cc) or kind=='kong' and not can_replace(d)):bad('Recorded matching-set claim is inconsistent')
 elif d['pending'] is not None or any(x is not None for x in d['claims']):bad('Claims exist only during a claim window')
 if d['phase']=='finished':
  if d['reason']=='exhausted':
   if d['wall'] or d['winner'] is not None:bad('Exhaustion needs an empty live wall and no winner')
  elif d['reason'] in ('self_draw','discard_win','robbed_kong'):
   if d['winner'] is None or not winning(d['hands'][d['winner']],d['melds'][d['winner']]):bad('Winning result requires a structurally complete hand')
  else:bad('Finished hand requires a result reason')
 elif d['winner'] is not None or d['reason'] is not None:bad('Only a finished hand has a result')
def schemas(d):
 ph=d['phase']
 if ph=='setup':return dict(deal=dict(deck=dict(type='array',minItems=136,maxItems=136,items=C),dealer=P))
 if ph=='draw':return dict(draw={})
 if ph=='discard':
  s=dict(discard=dict(tile=C))
  if d['drawn']:s.update(win={},kong=dict(cards=dict(type='array',minItems=1,maxItems=4,items=C)))
  return s
 if ph in ('reaction','kong_reaction'):return dict(claim=dict(player=P,kind=dict(type='enum',values=['pass','win'] if ph=='kong_reaction' else ['pass','win','chow','pung','kong']),cards=dict(type='array',minItems=0,maxItems=3,items=C)))
 return {}
def resolve_claims(d):
 p=d['pending'];source=p['player'];c=p['tile'];robbing=d['phase']=='kong_reaction';claimants=[(i,d['claims'][i]) for i in range(4) if i!=source and d['claims'][i]['kind']!='pass']
 if not claimants:
  if robbing:
   d['hands'][source].remove(c);m=d['melds'][source][p['meld_index']];m['cards'].append(c);m['kind']='kong';replacement(d)
  else:
   d['turn']=(source+1)%4;d['phase']='draw';d['drawn']=False
   if not d['wall']:d.update(phase='finished',reason='exhausted')
 else:
  priority=dict(chow=1,pung=2,kong=2,win=3)
  who,claim=max(claimants,key=lambda x:(priority[x[1]['kind']],-((x[0]-source)%4)))
  kind=claim['kind']
  if robbing:d['hands'][source].remove(c)
  else:d['rivers'][source].pop()
  if kind=='win':
   d['hands'][who].append(c);d.update(phase='finished',winner=who,reason='robbed_kong' if robbing else 'discard_win')
  else:
   for x in claim['cards']:d['hands'][who].remove(x)
   d['melds'][who].append(dict(kind=kind,cards=claim['cards']+[c],open=True,from_player=source));d.update(turn=who,phase='discard',drawn=False)
   if kind=='kong':replacement(d)
 d['pending']=None;d['claims']=[None]*4

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params');t=p.get('player',d['turn'])
 if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
 if k=='deal':
  if sorted(p['deck'])!=list(range(136)):fail('Supply each physical tile exactly once')
  dealer=p['dealer'];d['hands']=[p['deck'][i:52:4] for i in range(4)];d['hands'][dealer].append(p['deck'][52]);d.update(phase='discard',turn=dealer,dealer=dealer,wall=p['deck'][53:122],dead_wall=p['deck'][122:],drawn=True)
 elif k=='draw':
  if not d['wall']:d.update(phase='finished',reason='exhausted')
  else:d['hands'][t].append(d['wall'].pop(0));d.update(phase='discard',drawn=True)
 elif k=='discard':
  c=p['tile']
  if c not in d['hands'][t]:fail('Discard a tile currently held')
  d['hands'][t].remove(c);d['rivers'][t].append(c);d.update(phase='reaction',pending=dict(player=t,tile=c,meld_index=0),claims=[None]*4,drawn=False)
 elif k=='win':
  if not winning(d['hands'][t],d['melds'][t]):fail('Hand is not a permitted complete winning structure')
  d.update(phase='finished',winner=t,reason='self_draw')
 elif k=='kong':
  cc=p['cards']
  if not can_replace(d) or len(set(cc))!=len(cc) or any(c not in d['hands'][t] for c in cc):fail('Kong requires owned distinct tiles, a replacement draw and fewer than four existing kongs')
  if len(cc)==4 and len({tile(c) for c in cc})==1:
   for c in cc:d['hands'][t].remove(c)
   d['melds'][t].append(dict(kind='kong',cards=cc,open=False,from_player=None));replacement(d)
  elif len(cc)==1:
   ix=next((i for i,m in enumerate(d['melds'][t]) if m['kind']=='pung' and tile(m['cards'][0])==tile(cc[0])),None)
   if ix is None:fail('An added kong must extend an exposed matching pung')
   d.update(phase='kong_reaction',pending=dict(player=t,tile=cc[0],meld_index=ix),claims=[None]*4)
  else:fail('Declare four identical tiles or one tile extending an exposed pung')
 elif k=='claim':
  source=d['pending']['player'];c=d['pending']['tile'];kind=p['kind'];cc=p['cards']
  if t==source or d['claims'][t] is not None:fail('Each other player may respond exactly once')
  if len(set(cc))!=len(cc) or any(x not in d['hands'][t] for x in cc):fail('Claim tiles must be distinct and owned')
  if kind in ('pass','win'):
   if cc:fail('Pass and win claims do not nominate meld tiles')
   if kind=='win' and not winning(d['hands'][t]+[c],d['melds'][t]):fail('Claimed tile does not complete a winning hand')
  elif kind=='chow':
   if t!=(source+1)%4 or len(cc)!=2 or not sequence(cc+[c]):fail('Only the next player may claim a suited sequence')
  elif kind=='pung':
   if len(cc)!=2 or any(tile(x)!=tile(c) for x in cc):fail('Pung requires two matching tiles')
  elif kind=='kong':
   if len(cc)!=3 or any(tile(x)!=tile(c) for x in cc) or not can_replace(d):fail('Exposed kong requires three matching tiles and a replacement draw')
  d['claims'][t]=dict(kind=kind,cards=cc)
  if all(d['claims'][i] is not None for i in range(4) if i!=source):resolve_claims(d)
 return d
def legal(state):
 d=state['data'];s=schemas(d)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Turn, ownership, hand size, meld shape and claim priority must permit the action.'],external_observations=['External shuffled physical-tile deck.'] if k=='deal' else []) for k,v in s.items()],constraints=dict(phase=d['phase'],turn=d['turn'],live_tiles=len(d['wall']),kongs=kong_count(d),pending=d['pending'],can_win=d['phase']=='discard' and d['drawn'] and winning(d['hands'][d['turn']],d['melds'][d['turn']])),completeness=False,reason='constrained_mahjong_claims')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if w is not None else [],losers=[state['players'][i]['id'] for i in range(4) if i!=w] if done and w is not None else [],placements=[],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
