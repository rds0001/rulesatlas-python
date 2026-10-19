"""Two-player Scopa with compulsory captures and complete round scoring."""
from copy import deepcopy
from ..values import fields,fail

def rank(c):return int(c)%10+1
def capture_possible(table,target):
    reachable={0}
    for c in table:reachable|={v+rank(c) for v in tuple(reachable) if v+rank(c)<=target}
    return target in reachable
def round_points(d):
    piles=d['won'];points=d['sweeps'][:]
    categories=[[len(p) for p in piles],[sum(int(c)//10==0 for c in p) for p in piles]]
    prime={1:16,2:12,3:13,4:14,5:15,6:18,7:21,8:10,9:10,10:10};primiera=[]
    for pile in piles:
        values=[max([prime[rank(c)] for c in pile if int(c)//10==s] or [0]) for s in range(4)];primiera.append(sum(values) if all(values) else 0)
    categories.append(primiera)
    for values in categories:
        if values[0]!=values[1]:points[0 if values[0]>values[1] else 1]+=1
    for p in (0,1):
        if 6 in piles[p]:points[p]+=1
    return points

def validate(d):
    cards=d['stock']+d['table']+sum(d['hands'],[])+sum(d['won'],[])
    if d['phase']=='setup':
        if cards or d['last'] is not None or any(d['sweeps']) or any(d['scores']):fail('Setup must be empty',code='INVALID_STATE')
        return
    if sorted(cards)!=list(range(40)) or len(d['stock'])%6 or len(d['stock'])>30:fail('Invalid deck inventory or undealt stock',code='INVALID_STATE')
    if d['last'] is None and any(d['won']):fail('Captured cards require a last capturing player',code='INVALID_STATE')
    if d['last'] is not None and not d['won'][int(d['last'])]:fail('Last capturing player has no captured cards',code='INVALID_STATE')
    if any(d['sweeps'][p]>len(d['won'][p])//2 for p in (0,1)):fail('More sweeps than captured pairs',code='INVALID_STATE')
    if d['phase']=='playing':
        first=1-int(d['dealer']);sizes=[len(h) for h in d['hands']]
        if not sizes[int(d['turn'])] or sizes[first]-sizes[1-first] not in (0,-1) or d['turn']!=(first if sizes[0]==sizes[1] else 1-first):fail('Hand sizes and turn mismatch',code='INVALID_STATE')
        if max(d['scores'])>=11 and d['scores'][0]!=d['scores'][1]:fail('Match should already have ended',code='INVALID_STATE')
    else:
        if d['stock'] or d['table'] or any(d['hands']) or sum(map(len,d['won']))!=40:fail('Round must be fully collected before scoring',code='INVALID_STATE')
        ended=max(d['scores'])>=11 and d['scores'][0]!=d['scores'][1]
        if (d['phase']=='finished')!=ended:fail('Match target and phase mismatch',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if kind=='deal':
        fields(p,dict(deck=dict(type='array',minItems=40,maxItems=40,items=dict(type='integer',minimum=0,maximum=39))),'/params')
        if d['phase'] not in ('setup','round_end') or len(set(p['deck']))!=40:fail('Deal requires a complete new shuffled deck between rounds')
        if d['phase']=='round_end':d['dealer']=1-d['dealer']
        if sum(rank(c)==10 for c in p['deck'][6:10])>=3:fail('Initial table with three or four kings requires a redeal')
        first=1-int(d['dealer']);deck=p['deck'];d['hands']=[[],[]];d['hands'][first]=deck[:6:2];d['hands'][1-first]=deck[1:6:2];d['table']=deck[6:10];d['stock']=deck[10:];d['won']=[[],[]];d['sweeps']=[0,0];d['last']=None;d['turn']=first;d['phase']='playing';return d
    if kind!='play' or d['phase']!='playing':fail('Play a card during a round or deal between rounds')
    fields(p,dict(card=dict(type='integer',minimum=0,maximum=39),take=dict(type='array',minItems=0,maxItems=10,items=dict(type='integer',minimum=0,maximum=39))),'/params');t=int(d['turn']);card=p['card'];take=p['take']
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if card not in d['hands'][t] or len(set(take))!=len(take) or any(c not in d['table'] for c in take):fail('Card must be in hand and distinct selected cards on the table')
    target=rank(card);equals=[c for c in d['table'] if rank(c)==target]
    if take:
        if sum(rank(c) for c in take)!=target or equals and len(take)!=1:fail('Capture must match rank; a matching single card takes priority over sums')
    elif capture_possible(d['table'],target):fail('Available capture is compulsory')
    d['hands'][t].remove(card)
    if take:
        d['table']=[c for c in d['table'] if c not in take];d['won'][t]+=take+[card];d['last']=t
        if not d['table'] and (d['stock'] or any(d['hands'])):d['sweeps'][t]+=1
    else:d['table'].append(card)
    d['turn']=1-t
    if not any(d['hands']):
        if d['stock']:
            first=1-int(d['dealer']);deck=d['stock'];d['hands'][first]=deck[:6:2];d['hands'][1-first]=deck[1:6:2];d['stock']=deck[6:];d['turn']=first
        else:
            if d['table']:
                if d['last'] is None:fail('Final collection requires a last capturing player')
                d['won'][int(d['last'])]+=d['table'];d['table']=[]
            points=round_points(d);d['scores']=[d['scores'][i]+points[i] for i in (0,1)];d['phase']='finished' if max(d['scores'])>=11 and d['scores'][0]!=d['scores'][1] else 'round_end'
    return d

def legal(state):
    d=state['data'];playing=d['phase']=='playing'
    spec=dict(card=dict(type='integer',minimum=0,maximum=39),take=dict(type='array',minItems=0,maxItems=10,items=dict(type='integer',minimum=0,maximum=39))) if playing else dict(deck=dict(type='array',minItems=40,maxItems=40,items=dict(type='integer',minimum=0,maximum=39)))
    return dict(mode='event_types',actions=[],action_types=[dict(type='play' if playing else 'deal',params_schema=spec,preconditions=['Play a held card; capture a matching single table card if present, otherwise a subset with matching sum if available.'] if playing else ['Supply a permutation of all 40 cards.'],external_observations=[] if playing else ['Externally shuffled deck.'])],constraints=dict(turn=d['turn']),completeness=False,reason='guarded_card_selection')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';wins=[p for p in (0,1) if d['scores'][p]==max(d['scores'])] if terminal else []
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if terminal else 'none',winners=[state['players'][p]['id'] for p in wins],losers=[state['players'][p]['id'] for p in (0,1) if p not in wins] if terminal else [],placements=[dict(player_id=state['players'][p]['id'],place=1+sum(v>d['scores'][p] for v in d['scores']),score=d['scores'][p]) for p in (0,1)] if terminal else [],reason='round_target_reached' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
