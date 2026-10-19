"""Two-player double-six draw dominoes, one hand with an explicit tile order."""
from copy import deepcopy
from ..values import fields,fail
TILES=[(a,b) for a in range(7) for b in range(a,7)]
TILE={'type':'integer','minimum':0,'maximum':27}
def opening(d):
    pairs=[(int(tile),t) for t,hand in enumerate(d['hands']) for tile in hand]
    doubles=[x for x in pairs if TILES[x[0]][0]==TILES[x[0]][1]]
    return max(doubles or pairs,key=lambda x:(sum(TILES[x[0]]),max(TILES[x[0]])))
def moves(d,t):
    if not d['layout']:
        tile,first=opening(d)
        return [dict(type='play',params={'tile':tile,'end':'right'})] if t==first else []
    left=d['layout'][0][0];right=d['layout'][-1][1];result=[]
    for tile in d['hands'][t]:
        if left in TILES[int(tile)]:result.append(dict(type='play',params={'tile':tile,'end':'left'}))
        if right in TILES[int(tile)]:result.append(dict(type='play',params={'tile':tile,'end':'right'}))
    return result
def validate(d):
    if not d['configured']:
        if any(d['hands']) or d['stock'] or d['layout'] or d['turn']!=0 or d['passes']!=0:fail('Invalid unconfigured hand',code='INVALID_STATE')
        return
    played=[TILES.index(tuple(sorted(tile))) for tile in d['layout']]
    alltiles=d['hands'][0]+d['hands'][1]+d['stock']+played
    if sorted(alltiles)!=list(range(28)):fail('Tiles must conserve the double-six set',code='INVALID_STATE')
    if any(a[1]!=b[0] for a,b in zip(d['layout'],d['layout'][1:])):fail('Domino chain does not connect',code='INVALID_STATE')
    if not d['layout']:
        if [len(h) for h in d['hands']]!=[7,7] or len(d['stock'])!=14 or d['turn']!=opening(d)[1]:fail('Opening hand mismatch',code='INVALID_STATE')
    if not d['hands'][0] and not d['hands'][1]:fail('Both hands cannot finish together',code='INVALID_STATE')
    if d['passes']:
        if d['stock'] or moves(d,1-int(d['turn'])):fail('Invalid pass state',code='INVALID_STATE')
        if d['passes']==2 and moves(d,int(d['turn'])):fail('A blocked hand still has a legal play',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params']
    if not d['configured']:
        if action['type']!='deal':fail('Supply the tile order first')
        fields(p,{'tiles':{'type':'array','items':TILE,'minItems':28,'maxItems':28}},'/params')
        if sorted(p['tiles'])!=list(range(28)):fail('Tile order must contain every tile exactly once')
        d['hands']=[deepcopy(p['tiles'][:7]),deepcopy(p['tiles'][7:14])];d['stock']=deepcopy(p['tiles'][14:]);d['configured']=True;d['turn']=opening(d)[1];return d
    t=int(d['turn']);allowed=moves(d,t)
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if action['type']=='play':
        fields(p,{'tile':TILE,'end':{'type':'enum','values':['left','right']}},'/params')
        if not any(a['params']==p for a in allowed):fail('Tile cannot be played at that end')
        a,b=TILES[int(p['tile'])]
        if not d['layout']:d['layout']=[[a,b]]
        elif p['end']=='left':
            end=d['layout'][0][0];d['layout'].insert(0,[b,a] if a==end else [a,b])
        else:
            end=d['layout'][-1][1];d['layout'].append([a,b] if a==end else [b,a])
        d['hands'][t].remove(p['tile']);d['turn']=1-t;d['passes']=0
    elif action['type']=='draw':
        fields(p,{},'/params')
        if allowed or not d['stock']:fail('Draw only when blocked and stock remains')
        d['hands'][t].append(d['stock'].pop(0))
    elif action['type']=='pass':
        fields(p,{},'/params')
        if allowed or d['stock']:fail('Pass only when blocked with empty stock')
        d['passes']+=1;d['turn']=1-t
    else:fail('Unknown action')
    return d
def legal(state):
    d=state['data']
    if not d['configured']:return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema={'tiles':{'type':'array','items':TILE,'minItems':28,'maxItems':28}},preconditions=['A permutation of all 28 canonical double-six tile IDs.'],external_observations=['An externally supplied shuffled tile order.'])],constraints={},completeness=False,reason='external_deal_required')
    return moves(d,int(d['turn'])) or [dict(type='draw' if d['stock'] else 'pass',params={})]
def outcome(state,pack):
    d=state['data'];terminal=d['configured'] and (not all(d['hands']) or d['passes']==2);w=None
    if terminal:
        pips=[sum(sum(TILES[int(tile)]) for tile in hand) for hand in d['hands']]
        w=0 if not d['hands'][0] else 1 if not d['hands'][1] else None if pips[0]==pips[1] else 0 if pips[0]<pips[1] else 1
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('draw' if w is None else 'win') if terminal else 'none',winners=[] if w is None else [state['players'][w]['id']],losers=[] if w is None else [state['players'][1-w]['id']],placements=[],reason='hand_completed' if terminal else 'ongoing' if d['configured'] else 'awaiting_deal',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
