"""Single-deal three-player President, rank groups and pass-out climbing tricks."""
from copy import deepcopy
from ..values import fields,fail

def rank(c):return (int(c)%13-1)%13
def living(d):return [p for p in range(3) if d['hands'][p]]
def next_player(d,p,eligible):return next((p+i)%3 for i in range(1,4) if (p+i)%3 in eligible)
def resolve(d):
    alive=living(d);last=int(d['last']['player']);eligible=[p for p in alive if not d['passed'][p] and p!=last]
    if not eligible:
        d['last']=None;d['passed']=[False]*3;d['turn']=last if last in alive else next_player(d,last,alive)
    else:d['turn']=next_player(d,last if d['last_action']=='play' else int(d['turn']),eligible)
    d.pop('last_action',None);return d

def validate(d):
    if d['phase']=='setup':
        if any(d['hands']) or d['discard'] or d['order'] or d['last'] is not None or not d['opening']:fail('Setup must be empty',code='INVALID_STATE')
        return
    if sorted(sum(d['hands'],[])+d['discard'])!=list(range(52)):fail('Every card must occur exactly once',code='INVALID_STATE')
    order=d['order'];alive=living(d)
    if len(set(order))!=len(order):fail('Finishing order must contain distinct players',code='INVALID_STATE')
    if d['phase']=='finished':
        if len(order)!=3 or len(alive)!=1 or order[-1]!=alive[0] or any(d['hands'][int(p)] for p in order[:-1]):fail('Final ranking must put the remaining hand last',code='INVALID_STATE')
    elif len(alive)<2 or sorted(order)!=[p for p in range(3) if p not in alive] or d['turn'] not in alive or d['passed'][int(d['turn'])]:fail('Active players, turn and finishing order mismatch',code='INVALID_STATE')
    if d['opening']:
        if d['discard'] or d['last'] is not None or 1 not in d['hands'][int(d['turn'])]:fail('Opening belongs to the holder of the three of clubs',code='INVALID_STATE')
    if d['last'] is None:
        if any(d['passed']):fail('A new trick clears all passes',code='INVALID_STATE')
    else:
        last=d['last'];n=int(last['count']);cards=d['discard'][-n:]
        if len(cards)!=n or any(rank(c)!=last['rank'] for c in cards) or d['passed'][int(last['player'])]:fail('Last group and discarded cards mismatch',code='INVALID_STATE')
        if d['phase']=='playing' and d['turn']==last['player']:fail('A player cannot overbid their own group',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type'];t=int(d['turn'])
    if kind=='deal':
        fields(p,dict(deck=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51))),'/params')
        if d['phase']!='setup' or len(set(p['deck']))!=52:fail('Supply a complete deck for the initial deal')
        d['hands']=[p['deck'][q::3] for q in range(3)];d['turn']=next(q for q in range(3) if 1 in d['hands'][q]);d['phase']='playing';return d
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if kind=='pass':
        fields(p,{},'/params')
        if d['last'] is None:fail('The leader must play a group')
        d['passed'][t]=True;d['last_action']='pass';return resolve(d)
    if kind!='play':fail('Unknown action')
    fields(p,dict(cards=dict(type='array',minItems=1,maxItems=4,items=dict(type='integer',minimum=0,maximum=51))),'/params');cards=p['cards']
    if len(set(cards))!=len(cards) or any(c not in d['hands'][t] for c in cards) or len({rank(c) for c in cards})!=1:fail('Play distinct held cards of one rank')
    if d['opening'] and 1 not in cards:fail('Opening group must contain the three of clubs')
    if d['last'] is not None and (len(cards)!=d['last']['count'] or rank(cards[0])<=d['last']['rank']):fail('Match the group size and strictly exceed its rank')
    d['hands'][t]=[c for c in d['hands'][t] if c not in cards];d['discard']+=cards;d['opening']=False;d['last']=dict(player=t,count=len(cards),rank=rank(cards[0]))
    if not d['hands'][t]:d['order'].append(t)
    if len(d['order'])==2:
        d['order']+=living(d);d['phase']='finished';return d
    d['last_action']='play';return resolve(d)

def legal(state):
    from itertools import combinations
    d=state['data']
    if d['phase']=='setup':return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(deck=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51))),preconditions=['Permutation of all 52 cards.'],external_observations=['Externally shuffled deck.'])],constraints={},completeness=False,reason='external_deal')
    actions=[dict(type='pass',params={})] if d['last'] is not None else []
    for r in range(13):
        hand=[c for c in d['hands'][int(d['turn'])] if rank(c)==r]
        sizes=[int(d['last']['count'])] if d['last'] else range(1,len(hand)+1)
        if d['last'] and r<=d['last']['rank']:continue
        for n in sizes:
            for group in combinations(sorted(hand),n):
                if not d['opening'] or 1 in group:actions.append(dict(type='play',params=dict(cards=list(group))))
    return actions

def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';order=d['order']
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if terminal else 'none',winners=[state['players'][int(order[0])]['id']] if terminal else [],losers=[state['players'][int(p)]['id'] for p in order[1:]] if terminal else [],placements=[dict(player_id=state['players'][int(p)]['id'],place=i+1) for i,p in enumerate(order)] if terminal else [],reason='single_deal_ranking_complete' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
