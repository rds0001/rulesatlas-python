"""Single-round Pai Gow Poker with externally supplied banker setting."""
from copy import deepcopy
from itertools import combinations
from ..values import fields,fail
from .poker_rank import pai_five,pai_two

def ranks(cards,low):return pai_five([c for i,c in enumerate(cards) if i not in low]),pai_two([cards[int(i)] for i in low])
def valid_setting(cards,low):return len(low)==2 and len(set(low))==2 and ranks(cards,low)[0]>=ranks(cards,low)[1]
def validate(d):
    phase=d['phase']
    if phase=='betting':
        if d['stake'] is not None or d['player'] or d['banker'] or d['player_low'] is not None or d['banker_low'] is not None:fail('Betting must precede cards and settings',code='INVALID_STATE')
        return
    if d['stake'] is None or d['stake']%20:fail('Stake must be a multiple of twenty',code='INVALID_STATE')
    if phase=='awaiting_deal':
        if d['player'] or d['banker'] or d['player_low'] is not None or d['banker_low'] is not None:fail('No cards or settings before the deal',code='INVALID_STATE')
        return
    cards=d['player']+d['banker']
    if len(d['player'])!=7 or len(d['banker'])!=7 or len(set(cards))!=14:fail('Two seven-card hands must contain distinct cards',code='INVALID_STATE')
    if (d['player_low'] is not None)!=(phase in ('banker','settled')) or (d['banker_low'] is not None)!=(phase=='settled'):fail('Hand setting and phase mismatch',code='INVALID_STATE')
    for name in ('player','banker'):
        if d[name+'_low'] is not None and not valid_setting(d[name],d[name+'_low']):fail('Five-card high hand must rank at least as high as two-card low hand',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if d['phase']=='betting':
        if kind!='bet':fail('Lock the wager first')
        fields(p,dict(stake=dict(type='integer',minimum=20,maximum=1000)),'/params')
        if p['stake']%20:fail('Stake must be a multiple of twenty for exact commission')
        d['stake']=p['stake'];d['phase']='awaiting_deal';return d
    if d['phase']=='awaiting_deal':
        if kind!='deal':fail('Supply both seven-card hands')
        hand=dict(type='array',minItems=7,maxItems=7,items=dict(type='integer',minimum=0,maximum=52));fields(p,dict(player=hand,banker=hand),'/params')
        if len(set(p['player']+p['banker']))!=14:fail('All fourteen cards must be distinct')
        d['player']=p['player'][:];d['banker']=p['banker'][:];d['phase']='player';return d
    expected='set_player' if d['phase']=='player' else 'set_banker'
    if kind!=expected:fail('Set the player first, then the banker')
    fields(p,dict(low=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=0,maximum=6))),'/params');name=d['phase']
    if not valid_setting(d[name],p['low']):fail('Distinct low-card indices must leave a five-card hand at least as strong')
    d[name+'_low']=sorted(p['low']);d['phase']='banker' if name=='player' else 'settled';return d

def legal(state):
    d=state['data'];phase=d['phase']
    if phase=='player':return [dict(type='set_player',params=dict(low=list(pair))) for pair in combinations(range(7),2) if valid_setting(d['player'],pair)]
    if phase=='banker':return dict(mode='event_types',actions=[],action_types=[dict(type='set_banker',params_schema=dict(low=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=0,maximum=6))),preconditions=['Distinct low-card indices; the remaining high hand must rank at least as high.'],external_observations=['Banker setting under the externally selected house way.'])],constraints={},completeness=False,reason='external_banker_setting')
    if phase=='betting':spec=dict(stake=dict(type='integer',minimum=20,maximum=1000));kind='bet'
    else:
        hand=dict(type='array',minItems=7,maxItems=7,items=dict(type='integer',minimum=0,maximum=52));spec=dict(player=hand,banker=hand);kind='deal'
    return dict(mode='event_types',actions=[],action_types=[dict(type=kind,params_schema=spec,preconditions=['Stake is a multiple of twenty within the 1000-chip budget; both seven-card hands are distinct.'],external_observations=['Stake or externally dealt hands.'])],constraints={},completeness=False,reason='external_wager_and_cards')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='settled';net=0
    if done:
        player=ranks(d['player'],d['player_low']);banker=ranks(d['banker'],d['banker_low']);won=sum(a>b for a,b in zip(player,banker));net=d['stake']*19//20 if won==2 else 0 if won==1 else -d['stake']
    pid=state['players'][0]['id']
    return dict(status='terminal' if done else 'ongoing',result_kind=('win' if net>0 else 'draw' if net==0 else 'other') if done else 'none',winners=[pid] if done and net>0 else [],losers=[pid] if done and net<0 else [],placements=[dict(player_id=pid,place=1,balance=1000+net,net=net)] if done else [],reason='both_hands_compared_banker_wins_copies' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
