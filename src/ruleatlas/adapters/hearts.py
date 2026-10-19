"""Four-player Hearts with passing, suit restrictions and shoot-the-moon scoring."""
from copy import deepcopy
from ..values import fields,fail
QUEEN_SPADES=36
def points(card):return 1 if int(card)//13==3 else 13 if card==QUEEN_SPADES else 0
def broken(d):return any(int(c)//13==3 for pile in d['won'] for c in pile) or any(int(c)//13==3 for c in d['trick'])
def playable(d):
    p=(int(d['leader'])+len(d['trick']))%4;hand=sorted(d['hands'][p]);first=not any(d['won'])
    if not d['trick']:
        if first:return [0] if 0 in hand else []
        nonhearts=[c for c in hand if int(c)//13!=3]
        return hand if broken(d) or not nonhearts else nonhearts
    suit=int(d['trick'][0])//13;following=[c for c in hand if int(c)//13==suit]
    if following:return following
    nonpoints=[c for c in hand if not points(c)]
    return nonpoints if first and nonpoints else hand
def validate(d):
    cards=[c for h in d['hands'] for c in h]+[c for pile in d['won'] for c in pile]+d['trick']
    if d['round']==0 and d['phase']=='awaiting_deal':
        if cards or any(d['scores']) or any(p is not None for p in d['passes']) or d['leader']!=0:fail('Initial game contains prior play',code='INVALID_STATE')
        return
    if sorted(cards)!=list(range(52)):fail('Card inventory must contain all fifty-two cards once',code='INVALID_STATE')
    if any(len(pile)%4 for pile in d['won']):fail('Captured piles must contain complete tricks',code='INVALID_STATE')
    if (d['phase']=='finished')!=(max(d['scores'])>=100):fail('Scores and game phase mismatch',code='INVALID_STATE')
    if d['phase'] in ('awaiting_deal','finished'):
        if any(d['hands']) or d['trick']:fail('Completed deal still contains playable cards',code='INVALID_STATE')
        return
    if d['round']==0:fail('Active deal requires a positive round number',code='INVALID_STATE')
    if d['phase']=='passing':
        if (d['round']-1)%4==3 or any(len(h)!=13 for h in d['hands']) or d['trick'] or any(d['won']):fail('Invalid passing phase',code='INVALID_STATE')
        for p,cards in enumerate(d['passes']):
            if cards is not None and (len(set(cards))!=3 or not set(cards)<=set(d['hands'][p])):fail('Pass must select three cards from its player hand',code='INVALID_STATE')
        if all(c is not None for c in d['passes']):fail('Completed passing must advance to play',code='INVALID_STATE')
    elif d['phase']=='playing':
        if (d['round']-1)%4==3:
            if any(c is not None for c in d['passes']):fail('No-pass round cannot contain pass selections',code='INVALID_STATE')
        elif any(c is None for c in d['passes']):fail('Passing is incomplete',code='INVALID_STATE')
        sizes=[len(h)+(1 if (p-int(d['leader']))%4<len(d['trick']) else 0) for p,h in enumerate(d['hands'])]
        if len(set(sizes))!=1 or not any(d['hands']):fail('Hand sizes do not match the trick',code='INVALID_STATE')
        if not any(d['won']):
            if d['trick'] and d['trick'][0]!=0 or not d['trick'] and 0 not in d['hands'][int(d['leader'])]:fail('Two of clubs must lead the first trick',code='INVALID_STATE')
def finish_deal(d):
    scores=[sum(points(c) for c in pile) for pile in d['won']]
    if 26 in scores:
        moon=scores.index(26);scores=[0 if p==moon else 26 for p in range(4)]
    d['scores']=[a+b for a,b in zip(d['scores'],scores)];d['phase']='finished' if max(d['scores'])>=100 else 'awaiting_deal';return d
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if d['phase']=='awaiting_deal':
        if kind!='deal':fail('Supply the next shuffled deck')
        fields(p,dict(cards=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51))),'/params')
        if len(set(p['cards']))!=52:fail('Deck must contain each card once')
        d['round']+=1;d['hands']=[deepcopy(p['cards'][t::4]) for t in range(4)];d['won']=[[] for _ in range(4)];d['trick']=[];d['passes']=[None]*4;d['leader']=next(t for t in range(4) if 0 in d['hands'][t]);d['phase']='playing' if (d['round']-1)%4==3 else 'passing';return d
    if d['phase']=='passing':
        if kind!='pass_cards':fail('Complete all card passes before playing')
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=3),cards=dict(type='array',minItems=3,maxItems=3,items=dict(type='integer',minimum=0,maximum=51))),'/params');t=int(p['player'])
        if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        if d['passes'][t] is not None or len(set(p['cards']))!=3 or not set(p['cards'])<=set(d['hands'][t]):fail('Pass is repeated or does not select three owned cards')
        d['passes'][t]=deepcopy(p['cards'])
        if all(c is not None for c in d['passes']):
            shift=[1,3,2][(d['round']-1)%4]
            d['hands']=[[c for c in h if c not in d['passes'][i]] for i,h in enumerate(d['hands'])]
            for i,cards in enumerate(d['passes']):d['hands'][(i+shift)%4]+=cards
            d['leader']=next(t for t in range(4) if 0 in d['hands'][t]);d['phase']='playing'
        return d
    if kind!='play':fail('Unknown action')
    fields(p,dict(card=dict(type='integer',minimum=0,maximum=51)),'/params');t=(int(d['leader'])+len(d['trick']))%4;card=p['card']
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if card not in playable(d):fail('Card violates ownership, follow-suit or heart restrictions')
    d['hands'][t].remove(card);d['trick'].append(card)
    if len(d['trick'])==4:
        suit=int(d['trick'][0])//13;offset=max((i for i,c in enumerate(d['trick']) if int(c)//13==suit),key=lambda i:d['trick'][i]%13);winner=(int(d['leader'])+offset)%4
        d['won'][winner]+=d['trick'];d['trick']=[];d['leader']=winner
        if not any(d['hands']):finish_deal(d)
    return d
def legal(state):
    d=state['data']
    if d['phase']=='playing':return [dict(type='play',params=dict(card=c)) for c in playable(d)]
    if d['phase']=='awaiting_deal':schemas=dict(deal=dict(cards=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51))))
    else:schemas=dict(pass_cards=dict(player=dict(type='integer',minimum=0,maximum=3),cards=dict(type='array',minItems=3,maxItems=3,items=dict(type='integer',minimum=0,maximum=51))))
    return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Deck cards are unique; each pass selects three owned cards once per player.'],external_observations=['Supplied shuffled deck or player pass selection.']) for k,v in schemas.items()],constraints=dict(phase=d['phase'],pass_shift=[1,3,2,0][(d['round']-1)%4] if d['round'] else None),completeness=False,reason='external_deal_or_guarded_card_pass')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';winners=[state['players'][p]['id'] for p in range(4) if d['scores'][p]==min(d['scores'])] if terminal else []
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('draw' if len(winners)>1 else 'win') if terminal else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if terminal else [],placements=[dict(player_id=state['players'][p]['id'],place=1+sum(v<d['scores'][p] for v in d['scores']),score=d['scores'][p]) for p in range(4)] if terminal else [],reason='hundred_point_game_completed' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
