"""Three-player non-wild Liar's Dice with increasing bids and one-die challenges."""
from copy import deepcopy
from ..values import fields,fail
def next_player(d,p):return next((p+i)%3 for i in range(1,4) if d['counts'][(p+i)%3]>0)
def validate(d):
    active=[i for i,n in enumerate(d['counts']) if n>0]
    if not active or (d['phase']=='finished')!=(len(active)==1):fail('Remaining dice and game phase mismatch',code='INVALID_STATE')
    if d['starter'] not in active or d['turn'] not in active:fail('Current and starting players must have dice',code='INVALID_STATE')
    if d['phase']=='bidding':
        if any(len(d['dice'][p])!=d['counts'][p] for p in range(3)):fail('Roll sizes must match remaining dice',code='INVALID_STATE')
        bid=d['bid']
        if bid is None:
            if d['turn']!=d['starter']:fail('Starter must make the opening bid',code='INVALID_STATE')
        elif bid['player'] not in active or bid['quantity']>sum(d['counts']) or d['turn']!=next_player(d,int(bid['player'])):fail('Bid and current player mismatch',code='INVALID_STATE')
    elif any(d['dice']) or d['bid'] is not None or d['turn']!=d['starter']:fail('Old bids or dice remain outside a round',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type'];t=int(d['turn'])
    if d['phase']=='awaiting_roll':
        if kind!='roll_round':fail('Supply every remaining die for the round')
        fields(p,dict(dice=dict(type='array',minItems=3,maxItems=3,items=dict(type='array',minItems=0,maxItems=5,items=dict(type='integer',minimum=1,maximum=6)))),'/params')
        if any(len(p['dice'][i])!=d['counts'][i] for i in range(3)):fail('Roll sizes must match remaining dice')
        d['dice']=deepcopy(p['dice']);d['phase']='bidding';return d
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if kind=='bid':
        fields(p,dict(quantity=dict(type='integer',minimum=1,maximum=sum(d['counts'])),face=dict(type='integer',minimum=1,maximum=6)),'/params')
        if d['bid'] is not None and (p['quantity'],p['face'])<=(d['bid']['quantity'],d['bid']['face']):fail('Bid must increase quantity or face at equal quantity')
        d['bid']=dict(**p,player=t);d['turn']=next_player(d,t);return d
    if kind!='challenge':fail('Unknown action')
    fields(p,{},'/params')
    if d['bid'] is None:fail('There is no bid to challenge')
    bid=d['bid'];actual=sum(row.count(bid['face']) for row in d['dice']);loser=t if actual>=bid['quantity'] else int(bid['player']);d['counts'][loser]-=1
    d['starter']=loser if d['counts'][loser]>0 else next_player(d,loser);d['turn']=d['starter'];d['dice']=[[],[],[]];d['bid']=None;d['phase']='finished' if sum(n>0 for n in d['counts'])==1 else 'awaiting_roll';return d
def legal(state):
    d=state['data']
    if d['phase']=='awaiting_roll':return dict(mode='event_types',actions=[],action_types=[dict(type='roll_round',params_schema=dict(dice=dict(type='array',minItems=3,maxItems=3,items=dict(type='array',minItems=0,maxItems=5,items=dict(type='integer',minimum=1,maximum=6)))),preconditions=['Each player supplies exactly their remaining number of dice; eliminated players supply an empty list.'],external_observations=['Private dice results supplied to the authoritative host.'])],constraints=dict(counts=d['counts']),completeness=False,reason='external_round_rolls')
    bid=d['bid'];actions=[dict(type='bid',params=dict(quantity=q,face=f)) for q in range(1,int(sum(d['counts']))+1) for f in range(1,7) if bid is None or (q,f)>(bid['quantity'],bid['face'])]
    if bid is not None:actions.append(dict(type='challenge',params={}))
    return actions
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';wins=[p for p,n in enumerate(d['counts']) if n>0] if terminal else []
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if terminal else 'none',winners=[state['players'][p]['id'] for p in wins],losers=[state['players'][p]['id'] for p in range(3) if p not in wins] if terminal else [],placements=[],reason='last_player_with_dice' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
