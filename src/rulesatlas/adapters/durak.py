"""Two-player non-transferable Durak with a thirty-six-card deck."""
from copy import deepcopy
from ..values import fields,fail

def rank(c):return int(c)%9
def suit(c):return int(c)//9
def beats(a,b,trump):return suit(b)==suit(a) and rank(b)>rank(a) or suit(b)==trump and suit(a)!=trump
def visible_ranks(d):return {rank(c) for pair in d['table'] for c in [pair['attack'],pair['defense']] if c is not None}
def attackable(d):
    if len(d['table'])>=d['limit']:return []
    return [c for c in d['hands'][int(d['attacker'])] if not d['table'] or rank(c) in visible_ranks(d)]
def finish_bout(d,pickup):
    a=int(d['attacker']);b=1-a;cards=[c for pair in d['table'] for c in [pair['attack'],pair['defense']] if c is not None]
    if pickup:d['hands'][b]+=cards
    else:d['discard']+=cards
    d['table']=[]
    for p in (a,b):
        while len(d['hands'][p])<6 and d['stock']:d['hands'][p].append(d['stock'].pop(0))
    if not pickup:d['attacker']=b
    if not d['stock'] and any(not h for h in d['hands']):d['phase']='finished'
    else:d['phase']='attack'
    d['limit']=min(6,len(d['hands'][1-int(d['attacker'])]));return d

def validate(d):
    if d['phase']=='setup':
        if any(d['hands']) or d['stock'] or d['discard'] or d['table'] or d['trump_card'] is not None:fail('Setup must be empty',code='INVALID_STATE')
        return
    cards=sum(d['hands'],[])+d['stock']+d['discard']+[c for pair in d['table'] for c in [pair['attack'],pair['defense']] if c is not None]
    if sorted(cards)!=list(range(36)) or d['trump_card'] is None or len(d['discard'])%2:fail('Invalid deck inventory or trump card',code='INVALID_STATE')
    if d['stock'] and d['stock'][-1]!=d['trump_card']:fail('Face-up trump must remain at the bottom of the stock',code='INVALID_STATE')
    ended=not d['stock'] and not d['table'] and any(not h for h in d['hands'])
    if (d['phase']=='finished')!=ended:fail('Game ends only after completing the bout and drawing available cards',code='INVALID_STATE')
    defender=1-int(d['attacker']);covered=sum(p['defense'] is not None for p in d['table'])
    if d['limit']!=min(6,len(d['hands'][defender])+covered) or len(d['table'])>d['limit']:fail('Attack limit must match the defender’s starting hand, capped at six',code='INVALID_STATE')
    seen=set();uncovered=False
    for pair in d['table']:
        a,b=pair['attack'],pair['defense']
        if seen and rank(a) not in seen:fail('Additional attack rank must already be on the table',code='INVALID_STATE')
        seen.add(rank(a))
        if b is None:uncovered=True
        else:
            if uncovered or not beats(a,b,suit(d['trump_card'])):fail('Invalid cover or cover after pickup began',code='INVALID_STATE')
            seen.add(rank(b))
    missing=len(d['table'])-covered
    if d['phase']=='attack' and missing or d['phase']=='defend' and missing!=1 or d['phase']=='pickup' and missing<1:fail('Bout phase and uncovered attacks mismatch',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type'];a=int(d['attacker']);b=1-a
    if kind=='deal':
        fields(p,dict(deck=dict(type='array',minItems=36,maxItems=36,items=dict(type='integer',minimum=0,maximum=35)),fallback_first=dict(type='integer',minimum=0,maximum=1)),'/params')
        if d['phase']!='setup' or len(set(p['deck']))!=36:fail('Supply the complete thirty-six-card deck once')
        d['hands']=[p['deck'][:12:2],p['deck'][1:12:2]];d['stock']=p['deck'][12:];d['trump_card']=d['stock'][-1];trump=suit(d['trump_card']);trumps=[(rank(c),q) for q in (0,1) for c in d['hands'][q] if suit(c)==trump]
        d['attacker']=min(trumps)[1] if trumps else p['fallback_first'];d['limit']=6;d['phase']='attack';return d
    actor=b if d['phase']=='defend' else a
    if action.get('actor') is not None and action['actor']!=state['players'][actor]['id']:fail('Wrong actor')
    if kind=='attack':
        fields(p,dict(card=dict(type='integer',minimum=0,maximum=35)),'/params');c=p['card']
        if d['phase'] not in ('attack','pickup') or c not in attackable(d):fail('Attack must match a table rank, fit the limit and come from the attacker’s hand')
        d['hands'][a].remove(c);d['table'].append(dict(attack=c,defense=None))
        if d['phase']=='attack':d['phase']='defend'
        return d
    if kind=='cover':
        fields(p,dict(card=dict(type='integer',minimum=0,maximum=35)),'/params');c=p['card']
        if d['phase']!='defend' or c not in d['hands'][b] or not beats(d['table'][-1]['attack'],c,suit(d['trump_card'])):fail('Cover with a higher card of the same suit or a trump against a nontrump')
        d['hands'][b].remove(c);d['table'][-1]['defense']=c;d['phase']='attack';return d
    if kind=='take':
        fields(p,{},'/params')
        if d['phase']!='defend':fail('Only the defender facing an uncovered attack may take')
        d['phase']='pickup';return d
    if kind=='end_bout':
        fields(p,{},'/params')
        if d['phase'] not in ('attack','pickup') or not d['table']:fail('Finish only a covered bout or a declared pickup')
        return finish_bout(d,d['phase']=='pickup')
    fail('Unknown action')

def legal(state):
    d=state['data'];a=int(d['attacker']);b=1-a
    if d['phase']=='setup':return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(deck=dict(type='array',minItems=36,maxItems=36,items=dict(type='integer',minimum=0,maximum=35)),fallback_first=dict(type='integer',minimum=0,maximum=1)),preconditions=['Complete deck in deal/draw order; its last card is the face-up trump. Lowest held trump starts, or fallback_first if neither hand has trump.'],external_observations=['External deck order and fallback starter.'])],constraints={},completeness=False,reason='external_deal')
    if d['phase']=='defend':return [dict(type='take',params={})]+[dict(type='cover',params=dict(card=c)) for c in d['hands'][b] if beats(d['table'][-1]['attack'],c,suit(d['trump_card']))]
    actions=[dict(type='attack',params=dict(card=c)) for c in attackable(d)]
    if d['table']:actions.append(dict(type='end_bout',params={}))
    return actions

def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';wins=[p for p in (0,1) if not d['hands'][p]] if done else []
    return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if len(wins)==2 else 'win') if done else 'none',winners=[state['players'][p]['id'] for p in wins],losers=[state['players'][p]['id'] for p in (0,1) if p not in wins] if done else [],placements=[],reason='stock_exhausted_and_bout_completed' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
