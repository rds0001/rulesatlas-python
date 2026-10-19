"""Two-player basic Rummy, static melds and no jokers or opening threshold."""
from copy import deepcopy
from itertools import combinations
from ..values import fields,fail

def rank(c):return int(c)%13+1
def suit(c):return int(c)//13
def meld_type(cards):
    if len(cards)!=len(set(cards)) or len(cards)<3:return None
    if len(cards)<=4 and len({rank(c) for c in cards})==1:return 'set'
    ranks=sorted(rank(c) for c in cards)
    if len({suit(c) for c in cards})==1 and ranks==list(range(ranks[0],ranks[0]+len(cards))) and ranks[-1]<=13:return 'run'
    return None

def finish_if_empty(d):
    if not d['hands'][int(d['turn'])]:d['phase']='finished';d['winner']=d['turn']
    return d

def validate(d):
    if d['phase']=='setup':
        if any(d['hands']) or d['stock'] or d['discard'] or d['melds'] or d['winner'] is not None or d['drawn_discard'] is not None or d['agreed_draw']:fail('Setup must be empty',code='INVALID_STATE')
        return
    cards=sum(d['hands'],[])+d['stock']+d['discard']+sum([m['cards'] for m in d['melds']],[])
    if sorted(cards)!=list(range(52)):fail('Every card must occur exactly once',code='INVALID_STATE')
    if any(meld_type(m['cards'])!=m['kind'] for m in d['melds']):fail('Invalid group or same-suit run',code='INVALID_STATE')
    if d['phase']=='draw' and d['drawn_discard'] is not None:fail('A new turn must clear the discarded-card restriction',code='INVALID_STATE')
    if d['phase']=='finished':
        if d['agreed_draw']:
            if d['winner'] is not None:fail('An agreed draw has no winner',code='INVALID_STATE')
        elif d['winner'] is None or d['winner']!=d['turn'] or d['hands'][int(d['winner'])]:fail('Winner must have emptied the current hand',code='INVALID_STATE')
    elif d['winner'] is not None or d['agreed_draw'] or any(not h for h in d['hands']):fail('An empty hand must finish the round',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type'];t=int(d['turn'])
    if kind=='deal':
        fields(p,dict(deck=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51))),'/params')
        if d['phase']!='setup' or len(set(p['deck']))!=52:fail('Supply the full deck once')
        d['hands']=[p['deck'][:20:2],p['deck'][1:20:2]];d['discard']=[p['deck'][20]];d['stock']=p['deck'][21:];d['phase']='draw';return d
    if kind in ('offer_draw','accept_draw'):
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params');q=int(p['player'])
        if d['phase']=='setup':fail('Deal before requesting a draw')
        if action.get('actor') is not None and action['actor']!=state['players'][q]['id']:fail('Wrong actor')
        if kind=='offer_draw':d['offer']=q
        else:
            if d['offer'] is None or d['offer']==q:fail('Only the opponent may accept a draw offer')
            d['agreed_draw']=True;d['phase']='finished'
        return d
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if kind=='recycle':
        fields(p,dict(order=dict(type='array',minItems=1,maxItems=51,items=dict(type='integer',minimum=0,maximum=51))),'/params')
        if d['phase']!='draw' or d['stock'] or len(d['discard'])<2 or sorted(p['order'])!=sorted(d['discard'][:-1]):fail('Recycle all discards except the top only when the stock is empty')
        d['stock']=p['order'][:];d['discard']=d['discard'][-1:];return d
    if kind=='draw':
        fields(p,dict(source=dict(type='string',enum=['stock','discard'])),'/params')
        if d['phase']!='draw' or not d[p['source']]:fail('Draw exactly one available card before melding')
        card=d['stock'].pop(0) if p['source']=='stock' else d['discard'].pop();d['hands'][t].append(card);d['drawn_discard']=card if p['source']=='discard' else None;d['phase']='meld';return d
    if d['phase']!='meld':fail('Draw a card before melding, laying off or discarding')
    if kind=='meld':
        fields(p,dict(cards=dict(type='array',minItems=3,maxItems=13,items=dict(type='integer',minimum=0,maximum=51))),'/params');cards=p['cards'];mkind=meld_type(cards)
        if mkind is None or any(c not in d['hands'][t] for c in cards):fail('Meld must consist of distinct held cards forming a group or run')
        d['hands'][t]=[c for c in d['hands'][t] if c not in cards];d['melds'].append(dict(cards=sorted(cards,key=lambda c:(rank(c),suit(c))),kind=mkind,owner=t));return finish_if_empty(d)
    if kind=='lay_off':
        fields(p,dict(card=dict(type='integer',minimum=0,maximum=51),meld=dict(type='integer',minimum=0,maximum=16)),'/params');i=int(p['meld']);c=p['card']
        if i>=len(d['melds']) or c not in d['hands'][t] or meld_type(d['melds'][i]['cards']+[c])!=d['melds'][i]['kind']:fail('Held card must legally extend the selected existing meld')
        d['hands'][t].remove(c);d['melds'][i]['cards']=sorted(d['melds'][i]['cards']+[c],key=lambda c:(rank(c),suit(c)));return finish_if_empty(d)
    if kind=='discard':
        fields(p,dict(card=dict(type='integer',minimum=0,maximum=51)),'/params');c=p['card']
        if c not in d['hands'][t] or c==d['drawn_discard']:fail('Discard a held card other than the card just taken from the discard pile')
        d['hands'][t].remove(c);d['discard'].append(c);finish_if_empty(d)
        if d['phase']!='finished':d['turn']=1-t;d['phase']='draw';d['drawn_discard']=None
        if d['offer'] is not None and d['offer']!=t:d['offer']=None
        return d
    fail('Unknown action')

def legal(state):
    d=state['data'];t=int(d['turn'])
    if d['phase']=='setup':return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(deck=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51))),preconditions=['Supply every card once, in deal/draw order.'],external_observations=['External shuffled deck.'])],constraints={},completeness=False,reason='external_deal')
    actions=[dict(type='offer_draw',params=dict(player=p)) for p in (0,1)];types=[]
    if d['offer'] is not None:actions.append(dict(type='accept_draw',params=dict(player=1-d['offer'])))
    if d['phase']=='draw':
        actions+=[dict(type='draw',params=dict(source=s)) for s in ('stock','discard') if d[s]]
        if not d['stock'] and len(d['discard'])>1:types.append(dict(type='recycle',params_schema=dict(order=dict(type='array',minItems=1,maxItems=51,items=dict(type='integer',minimum=0,maximum=51))),preconditions=['Permutation of all discards except the retained top card.'],external_observations=['External reshuffle order.']))
    else:
        hand=d['hands'][t];groups=[]
        for r in range(1,14):
            same=[c for c in hand if rank(c)==r]
            for n in (3,4):groups += [list(g) for g in combinations(same,n)]
        for s in range(4):
            same=sorted((c for c in hand if suit(c)==s),key=rank)
            for i in range(len(same)):
                for j in range(i+3,len(same)+1):
                    if meld_type(same[i:j])=='run':groups.append(same[i:j])
        actions += [dict(type='meld',params=dict(cards=cards)) for cards in groups]
        actions += [dict(type='lay_off',params=dict(card=c,meld=i)) for c in hand for i,m in enumerate(d['melds']) if meld_type(m['cards']+[c])==m['kind']]
        actions += [dict(type='discard',params=dict(card=c)) for c in hand if c!=d['drawn_discard']]
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(turn=t,phase=d['phase']),completeness=False,reason='legal_card_actions_and_external_recycle')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';winner=d['winner'];points=[sum(min(10,rank(c)) for c in h) for h in d['hands']]
    return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if d['agreed_draw'] else 'win') if done else 'none',winners=[state['players'][int(winner)]['id']] if done and winner is not None else [],losers=[state['players'][1-int(winner)]['id']] if done and winner is not None else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if d['agreed_draw'] or p==winner else 2,hand_points=points[p],round_score=points[1-p] if p==winner else 0) for p in (0,1)] if done else [],reason='agreed_draw' if done and d['agreed_draw'] else 'hand_emptied' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
