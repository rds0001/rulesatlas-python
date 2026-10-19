"""Punto banco: natural totals, mandatory third-card tableau and commission."""
from copy import deepcopy
from ..values import fields,fail
BET=dict(target=dict(type='string',enum=['player','banker','tie']),stake=dict(type='integer',minimum=20,maximum=1000))
def next_hand(hands):
    p,b=hands
    if len(p)<2 or len(b)<2:return 0 if len(p)==len(b) else 1
    pt=sum(p[:2])%10;bt=sum(b[:2])%10
    if pt>=8 or bt>=8:return None
    if len(p)==2 and pt<=5:return 0
    if len(b)==3:return None
    if len(p)==2:return 1 if bt<=5 else None
    third=p[2]
    draw=bt<=2 or bt==3 and third!=8 or bt==4 and 2<=third<=7 or bt==5 and 4<=third<=7 or bt==6 and third in (6,7)
    return 1 if draw else None
def inspect(cards):
    hands=[[],[]]
    for value in cards:
        target=next_hand(hands)
        if target is None:fail('Cards continued after the tableau ended',code='INVALID_STATE')
        hands[target].append(value)
    return hands,next_hand(hands)
def validate(d):
    if d['bet'] is not None and d['bet']['stake']%20:fail('Stake must use twenty-chip units',code='INVALID_STATE')
    if d['phase']=='betting':
        if d['bet'] is not None or d['cards']:fail('Betting state already contains a locked bet or cards',code='INVALID_STATE')
        return
    if d['bet'] is None:fail('A locked bet is required',code='INVALID_STATE')
    _,target=inspect(d['cards'])
    if (d['phase']=='settled')!=(target is None):fail('Phase does not match the drawing tableau',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params']
    if d['phase']=='betting':
        if action['type']!='bet':fail('Lock a bet before dealing')
        fields(p,BET,'/params')
        if p['stake']%20:fail('Stake must use twenty-chip units')
        d['bet']=deepcopy(p);d['phase']='dealing';return d
    if action['type']!='deal_card':fail('Only the required next card may be dealt')
    fields(p,dict(hand=dict(type='string',enum=['player','banker']),value=dict(type='integer',minimum=0,maximum=9)),'/params')
    _,target=inspect(d['cards'])
    if p['hand']!=('player' if target==0 else 'banker'):fail('Card was dealt to the wrong hand')
    d['cards'].append(p['value']);_,target=inspect(d['cards'])
    if target is None:d['phase']='settled'
    return d
def legal(state):
    d=state['data']
    if d['phase']=='betting':schemas=dict(bet=BET);constraints=dict(available_chips=1000)
    else:
        _,target=inspect(d['cards']);hand='player' if target==0 else 'banker';schemas=dict(deal_card=dict(hand=dict(type='string',enum=[hand]),value=dict(type='integer',minimum=0,maximum=9)));constraints=dict(next_hand=hand)
    return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Stakes use twenty-chip units; cards follow the mandatory punto banco tableau.'],external_observations=['A locked wager or the next officially dealt card value; tens and face cards count zero.']) for k,v in schemas.items()],constraints=constraints,completeness=False,reason='external_cards_mandatory_tableau')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='settled';net=0
    if terminal:
        hands,_=inspect(d['cards']);p,b=[sum(h)%10 for h in hands];winner='tie' if p==b else 'player' if p>b else 'banker';bet=d['bet'];stake=bet['stake']
        if bet['target']==winner:net=stake*8 if winner=='tie' else stake*19//20 if winner=='banker' else stake
        elif winner!='tie' or bet['target']=='tie':net=-stake
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('win' if net>0 else 'draw' if net==0 else 'other') if terminal else 'none',winners=[state['players'][0]['id']] if terminal and net>0 else [],losers=[state['players'][0]['id']] if terminal and net<0 else [],placements=[dict(player_id=state['players'][0]['id'],place=1,balance=1000+net,net=net)] if terminal else [],reason='round_settled' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
