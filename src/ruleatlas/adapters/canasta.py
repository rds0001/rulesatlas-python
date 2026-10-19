"""Four-player partnership Canasta, with explicit Bicycle-style pile freezing."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
A=lambda x,a,b:dict(type='array',minItems=a,maxItems=b,items=x)
CARD=I(0,107);GROUP=dict(type='object',properties=dict(rank=I(1,13),cards=A(CARD,1,11)),required=['rank','cards'])
SCHEMAS=dict(configure_scores=dict(scores=A(I(-100000,100000),2,2)),deal=dict(deck=A(CARD,108,108)),draw_stock={},take_discard=dict(groups=A(GROUP,1,12)),meld=dict(groups=A(GROUP,1,12)),discard=dict(card=CARD),ask_to_go_out={},answer_permission=dict(player=I(0,3),allow=dict(type='boolean')),end_stock={},next_round={})
def rank(c):return c%54%13+1 if c%54<52 else 0
def wild(c):return rank(c) in (0,2)
def red_three(c):return rank(c)==3 and c%54//13 in (1,2)
def value(c):return 50 if rank(c)==0 else 100 if red_three(c) else 20 if rank(c) in (1,2) else 10 if rank(c)>=8 else 5
def valid_meld(m):
 cards=m['cards'];r=m['rank'];natural=[c for c in cards if not wild(c)]
 if len(cards)<3 or len(set(cards))!=len(cards):return False
 if r==3:return len(cards)<=4 and all(rank(c)==3 and not red_three(c) for c in cards)
 return r in (1,4,5,6,7,8,9,10,11,12,13) and len(natural)>=2 and all(rank(c)==r for c in natural) and sum(wild(c) for c in cards)<=3

def canasta(m):return m['rank']!=3 and len(m['cards'])>=7

def frozen(d,team):return not d['melds'][team] or any(wild(c) or rank(c)==3 for c in d['discard'])
def threshold(d,team):
 score=d['round_start_scores'][team];return 15 if score<0 else 50 if score<1500 else 90 if score<3000 else 120

def own_turn_canasta(d):
 cards=d['turn_cards_melded']
 return any(len([c for c in m['cards'] if c in cards])>=7 and len([c for c in m['cards'] if c in cards and not wild(c)])>=4 for m in d['melds'][d['turn']%2] if m['rank']!=3)

def round_points(d):
 scores=[]
 for team in (0,1):
  melds=d['melds'][team];reds=len(d['red_threes'][team]);bonus=(800 if reds==4 else reds*100)*(1 if melds else -1)
  bonus+=sum(300 if any(wild(c) for c in m['cards']) else 500 for m in melds if canasta(m))
  if d['out_team']==team:bonus+=100+100*int(d['concealed'])
  scores.append(bonus+sum(value(c) for m in melds for c in m['cards'])-sum(value(c) for i,h in enumerate(d['hands']) if i%2==team for c in h))
 return scores

def end_round(d,reason,out=None):
 d.update(end_reason=reason,out_team=out,concealed=out is not None and d['concealed_candidate'] and own_turn_canasta(d),permission_pending=False)
 d['last_round_scores']=round_points(d);d['scores']=[d['round_start_scores'][i]+d['last_round_scores'][i] for i in (0,1)]
 d['phase']='finished' if max(d['scores'])>=5000 and d['scores'][0]!=d['scores'][1] else 'round_end'

def go_out(d):
 team=d['turn']%2
 if not any(canasta(m) for m in d['melds'][team]) or d['permission'] is False:fail('Going out requires a partnership canasta and no binding refusal')
 end_round(d,'go_out',team)

def draw_replacing_reds(d,player):
 while d['stock']:
  c=d['stock'].pop(0)
  if red_three(c):
   d['red_threes'][player%2].append(c)
   if not d['stock']:return False
  else:d['hands'][player].append(c);return True
 return False

def reset_turn(d):
 d.update(draw_source=None,turn_cards_melded=[],concealed_candidate=not d['has_melded'][d['turn']],permission=None,permission_asked=False,permission_pending=False,must_go_out=False)

def meld_groups(d,groups,future_cards=0):
 t=d['turn'];team=t%2;cards=[c for g in groups for c in g['cards']];ranks=[g['rank'] for g in groups]
 if len(cards)!=len(set(cards)) or len(ranks)!=len(set(ranks)) or any(c not in d['hands'][t] for c in cards):fail('Meld additions must use distinct held cards and distinct ranks')
 proposed=deepcopy(d['melds'][team]);opening=not proposed
 for g in groups:
  m=next((m for m in proposed if m['rank']==g['rank']),None)
  if m is None:m=dict(rank=g['rank'],cards=[]);proposed.append(m)
  m['cards']+=g['cards']
  if not valid_meld(m):fail('Meld requires matching naturals, at most three wild cards, and valid black-three use')
 remaining=len(d['hands'][t])-len(cards)+future_cards;has_canasta=any(canasta(m) for m in proposed)
 if remaining==0 and (not has_canasta or d['permission'] is False):fail('Cannot empty the hand without a permitted going-out condition')
 black=any(g['rank']==3 for g in groups)
 if black and (remaining>1 or not has_canasta or d['permission'] is False):fail('Black threes may be melded only while going out')
 contributed=d['turn_cards_melded']+cards
 concealed_canasta=any(len([c for c in m['cards'] if c in contributed])>=7 and len([c for c in m['cards'] if c in contributed and not wild(c)])>=4 for m in proposed if m['rank']!=3)
 waive=remaining<=1 and d['concealed_candidate'] and concealed_canasta and d['draw_source']=='stock' and d['permission'] is not False
 if opening and sum(value(c) for c in cards)<threshold(d,team) and not waive:fail('Initial meld does not meet the partnership minimum')
 d['melds'][team]=proposed;d['hands'][t]=[c for c in d['hands'][t] if c not in cards];d['turn_cards_melded']=contributed;d['has_melded'][t]=True
 if black or opening and sum(value(c) for c in cards)<threshold(d,team):d['must_go_out']=True

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');phase=d['phase']
 if any(v%5 for v in d['scores']+d['round_start_scores']):bad('Canasta cumulative scores use five-point increments')
 if phase=='setup':
  if any(d['hands']) or d['stock'] or d['discard'] or any(d['melds']) or any(d['red_threes']):bad('Setup must have no dealt cards')
  return
 cards=sum(d['hands'],[])+d['stock']+d['discard']+sum(d['red_threes'],[])+[c for team in d['melds'] for m in team for c in m['cards']]
 if sorted(cards)!=list(range(108)):bad('Every physical card must occur exactly once')
 if any(red_three(c) for h in d['hands'] for c in h) or any(not red_three(c) for row in d['red_threes'] for c in row):bad('Red threes must be exposed outside hands')
 for team in d['melds']:
  if len({m['rank'] for m in team})!=len(team) or any(not valid_meld(m) for m in team):bad('Partnership melds require unique valid ranks')
 if phase in ('round_end','finished'):
  if d['end_reason'] is None or d['last_round_scores']!=round_points(d) or d['scores']!=[d['round_start_scores'][i]+d['last_round_scores'][i] for i in (0,1)]:bad('Completed hand requires its exact score ledger')
  if d['end_reason']=='go_out' and (d['hands'][d['turn']] or d['out_team']!=d['turn']%2 or not any(canasta(m) for m in d['melds'][d['out_team']])):bad('Going-out result requires an empty hand and a team canasta')
  if (phase=='finished')!=(max(d['scores'])>=5000 and d['scores'][0]!=d['scores'][1]):bad('Game ends only after a completed hand reaches five thousand with unequal totals')
 else:
  if d['scores']!=d['round_start_scores'] or d['end_reason'] is not None or d['out_team'] is not None or d['concealed']:bad('Open hand cannot retain a result')
  if any(not h for h in d['hands']):bad('An emptied hand must end the round')
 if phase=='draw' and (d['draw_source'] is not None or d['turn_cards_melded'] or d['must_go_out']):bad('New turn cannot retain melding activity')
 if phase=='meld' and d['draw_source'] is None:bad('Melding follows a draw or legal discard pickup')
 if d['permission_pending'] and (not d['permission_asked'] or d['permission'] is not None):bad('Pending permission must await its partner answer')
 if d['permission'] is not None and not d['permission_asked']:bad('Binding permission requires a recorded request')
 if d['must_go_out'] and len(d['hands'][d['turn']])>1:bad('Special final meld must leave at most the final discard')

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase'];t=d['turn'];team=t%2
 if k not in SCHEMAS:fail('Unknown Canasta action')
 fields(p,SCHEMAS[k],'/params')
 if phase=='finished':fail('Game is finished')
 actor=action.get('actor')
 if actor is not None and k not in ('deal','configure_scores','next_round') and actor!=state['players'][(t+2)%4 if k=='answer_permission' else t]['id']:fail('Wrong actor for this Canasta decision')
 if d['permission_pending'] and k!='answer_permission':fail('The partner must answer the pending going-out request')
 if k=='configure_scores':
  if phase!='setup' or d['round']!=1 or any(x%5 for x in p['scores']) or max(p['scores'])>=5000 and p['scores'][0]!=p['scores'][1]:fail('Configure initial five-point cumulative totals before the first deal')
  d['scores']=p['scores'][:];d['round_start_scores']=p['scores'][:]
 elif k=='deal':
  if phase!='setup' or len(set(p['deck']))!=108:fail('Supply the complete double deck once')
  deck=p['deck'][:]
  for n,c in enumerate(deck[:44]):d['hands'][(d['dealer']+1+n)%4].append(c)
  d['stock']=deck[44:]
  while d['stock']:
   c=d['stock'].pop(0);d['discard'].append(c)
   if rank(c) not in (0,2,3):break
  for step in range(4):
   i=(d['dealer']+1+step)%4;reds=[c for c in d['hands'][i] if red_three(c)];d['hands'][i]=[c for c in d['hands'][i] if not red_three(c)];d['red_threes'][i%2]+=reds
   for _ in reds:
    if not draw_replacing_reds(d,i):end_round(d,'red_three_exhaustion');return d
  d['phase']='draw';reset_turn(d)
 elif k=='next_round':
  if phase!='round_end':fail('Complete the current hand before dealing again')
  d.update(phase='setup',round=d['round']+1,dealer=(d['dealer']+1)%4,turn=(d['dealer']+2)%4,hands=[[],[],[],[]],stock=[],discard=[],melds=[[],[]],red_threes=[[],[]],has_melded=[False]*4,round_start_scores=d['scores'][:],last_round_scores=[0,0],out_team=None,concealed=False,end_reason=None);reset_turn(d)
 elif k=='ask_to_go_out':
  if phase not in ('draw','meld') or d['permission_asked'] or d['turn_cards_melded'] or d['draw_source']=='discard':fail('Ask only before melding or indicating a discard-pile pickup')
  d['permission_asked']=True;d['permission_pending']=True
 elif k=='answer_permission':
  if not d['permission_pending'] or p['player']!=(t+2)%4:fail('Only the current player partner may answer')
  d['permission']=p['allow'];d['permission_pending']=False
 elif k=='draw_stock':
  if phase!='draw' or not d['stock']:fail('Draw one available stock card before melding')
  d['draw_source']='stock'
  if not draw_replacing_reds(d,t):end_round(d,'red_three_exhaustion')
  else:d['phase']='meld'
 elif k=='take_discard':
  if phase!='draw' or not d['discard'] or len(d['hands'][t])==len(d['discard'])==1:fail('Discard pickup is unavailable')
  top=d['discard'][-1];r=rank(top);groups=p['groups'];used=[c for g in groups for c in g['cards']]
  if wild(top) or r==3 or top not in used:fail('The natural top discard must be used immediately in a meld')
  if frozen(d,team) and sum(rank(c)==r and c in used for c in d['hands'][t])<2:fail('A frozen pile requires two matching natural cards from the hand')
  d['discard'].pop();rest=d['discard'][:];d['discard']=[];d['hands'][t].append(top);d['draw_source']='discard'
  meld_groups(d,groups,sum(not red_three(c) for c in rest))
  for c in rest:
   if red_three(c):d['red_threes'][team].append(c)
   else:d['hands'][t].append(c)
  d['phase']='meld'
  if not d['hands'][t]:go_out(d)
 elif k=='meld':
  if phase!='meld' or d['must_go_out']:fail('Draw first; a special final meld must be followed by its discard')
  meld_groups(d,p['groups'])
  if not d['hands'][t]:go_out(d)
 elif k=='discard':
  if phase!='meld' or p['card'] not in d['hands'][t]:fail('Discard one held card after drawing')
  if d['permission'] is True and len(d['hands'][t])!=1:fail('A positive partner answer binds this turn to going out')
  d['hands'][t].remove(p['card']);d['discard'].append(p['card'])
  if not d['hands'][t]:go_out(d)
  else:d['turn']=(t+1)%4;d['phase']='draw';reset_turn(d)
 elif k=='end_stock':
  if phase!='draw' or d['stock']:fail('Voluntary stock exhaustion is available only when no stock remains')
  top=d['discard'][-1] if d['discard'] else None
  mandatory=top is not None and not wild(top) and rank(top)!=3 and not frozen(d,team) and any(m['rank']==rank(top) for m in d['melds'][team]) and not(len(d['hands'][t])==len(d['discard'])==1)
  if mandatory:fail('An unfrozen matching discard must be taken when the stock is empty')
  end_round(d,'stock_empty')
 return d

def legal(state):
 d=state['data'];phase=d['phase'];t=d['turn'];names=[]
 if d['permission_pending']:names=['answer_permission']
 elif phase=='setup':names=['deal']+(['configure_scores'] if d['round']==1 else [])
 elif phase=='round_end':names=['next_round']
 elif phase=='draw':names=(['draw_stock'] if d['stock'] else ['end_stock'])+(['take_discard'] if d['discard'] else [])+([] if d['permission_asked'] else ['ask_to_go_out'])
 elif phase=='meld':names=['discard']+([] if d['must_go_out'] else ['meld'])+(['ask_to_go_out'] if not d['permission_asked'] and not d['turn_cards_melded'] and d['draw_source']!='discard' else [])
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Turn, held-card membership, meld composition, opening minimum, frozen pile and partner permission must permit the action.'],external_observations=['External shuffled double deck; partner answer is an explicit player decision.']) for k in names],constraints=dict(phase=phase,turn=t,partnership=t%2,initial_minimum=threshold(d,t%2),discard_frozen=frozen(d,t%2),stock_count=len(d['stock']),hand_counts=[len(h) for h in d['hands']],canastas=[sum(canasta(m) for m in row) for row in d['melds']],permission_pending=d['permission_pending']),completeness=False,reason='bounded_parameterized_canasta_actions')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=0 if d['scores'][0]>d['scores'][1] else 1
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][i]['id'] for i in range(4) if i%2==w] if done else [],losers=[state['players'][i]['id'] for i in range(4) if i%2!=w] if done else [],placements=[dict(partnership=i,place=1 if i==w else 2,score=d['scores'][i]) for i in (0,1)] if done else [],reason='five_thousand_after_completed_hand' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
