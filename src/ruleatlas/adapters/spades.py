"""Partnership Spades with nil contracts, sandbags and a 500-point target."""
from copy import deepcopy
from ..values import fields,fail
def broken(d):return any(int(c)//13==3 for pile in d['won'] for c in pile) or any(int(c)//13==3 for c in d['trick'])
def playable(d):
    p=(int(d['leader'])+len(d['trick']))%4;hand=sorted(d['hands'][p])
    if d['trick']:
        following=[c for c in hand if int(c)//13==int(d['trick'][0])//13];return following or hand
    nontrumps=[c for c in hand if int(c)//13!=3]
    return hand if broken(d) or not nontrumps else nontrumps
def ended(d):return max(d['scores'])>=500 and d['scores'][0]!=d['scores'][1]
def validate(d):
    cards=[c for h in d['hands'] for c in h]+[c for pile in d['won'] for c in pile]+d['trick']
    if d['round']==0 and d['phase']=='awaiting_deal':
        if cards or any(d['scores']) or any(d['bags']) or any(b is not None for b in d['bids']) or d['leader']!=0:fail('Initial game contains prior play',code='INVALID_STATE')
        return
    if sorted(cards)!=list(range(52)):fail('Card inventory must contain all fifty-two cards once',code='INVALID_STATE')
    if any(len(pile)%4 for pile in d['won']):fail('Captured piles must contain complete tricks',code='INVALID_STATE')
    if (d['phase']=='finished')!=ended(d):fail('Scores and game phase mismatch',code='INVALID_STATE')
    if d['phase'] in ('awaiting_deal','finished'):
        if any(d['hands']) or d['trick']:fail('Completed deal still contains playable cards',code='INVALID_STATE')
        return
    if d['round']==0:fail('Active deal requires a positive round number',code='INVALID_STATE')
    if d['phase']=='bidding':
        if any(len(h)!=13 for h in d['hands']) or d['trick'] or any(d['won']) or d['leader']!=(d['round']-1)%4:fail('Invalid bidding phase',code='INVALID_STATE')
        order=[(int(d['leader'])+i)%4 for i in range(4)];seen_empty=False
        for p in order:
            if d['bids'][p] is None:seen_empty=True
            elif seen_empty:fail('Bids must follow player order',code='INVALID_STATE')
        if not seen_empty:fail('Completed bidding must advance',code='INVALID_STATE')
    elif d['phase']=='playing':
        if any(b is None for b in d['bids']):fail('Bidding is incomplete',code='INVALID_STATE')
        sizes=[len(h)+(1 if (p-int(d['leader']))%4<len(d['trick']) else 0) for p,h in enumerate(d['hands'])]
        if len(set(sizes))!=1 or not any(d['hands']):fail('Hand sizes do not match the trick',code='INVALID_STATE')
def finish(d):
    tricks=[len(pile)//4 for pile in d['won']]
    for team in (0,1):
        players=(team,team+2);bid=sum(d['bids'][p] for p in players);taken=sum(tricks[p] for p in players if d['bids'][p]>0)
        bags=sum(tricks[p] for p in players if d['bids'][p]==0)+max(0,taken-bid)
        points=(10*bid if taken>=bid else -10*bid)+bags
        points+=sum(100 if tricks[p]==0 else -100 for p in players if d['bids'][p]==0)
        accumulated=d['bags'][team]+bags;points-=100*(accumulated//10);d['bags'][team]=accumulated%10;d['scores'][team]+=points
    d['phase']='finished' if ended(d) else 'awaiting_deal';return d
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if d['phase']=='awaiting_deal':
        if kind!='deal':fail('Supply the next shuffled deck')
        fields(p,dict(cards=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51))),'/params')
        if len(set(p['cards']))!=52:fail('Deck must contain each card once')
        d['round']+=1;d['hands']=[deepcopy(p['cards'][t::4]) for t in range(4)];d['won']=[[] for _ in range(4)];d['trick']=[];d['bids']=[None]*4;d['leader']=(d['round']-1)%4;d['phase']='bidding';return d
    if d['phase']=='bidding':
        if kind!='bid':fail('Complete bidding before playing')
        fields(p,dict(tricks=dict(type='integer',minimum=0,maximum=13)),'/params');t=next((int(d['leader'])+i)%4 for i in range(4) if d['bids'][(int(d['leader'])+i)%4] is None)
        if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        d['bids'][t]=p['tricks']
        if all(b is not None for b in d['bids']):d['phase']='playing'
        return d
    if kind!='play':fail('Unknown action')
    fields(p,dict(card=dict(type='integer',minimum=0,maximum=51)),'/params');t=(int(d['leader'])+len(d['trick']))%4;card=p['card']
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if card not in playable(d):fail('Card violates ownership, follow-suit or trump restrictions')
    d['hands'][t].remove(card);d['trick'].append(card)
    if len(d['trick'])==4:
        suit=3 if any(int(c)//13==3 for c in d['trick']) else int(d['trick'][0])//13;offset=max((i for i,c in enumerate(d['trick']) if int(c)//13==suit),key=lambda i:d['trick'][i]%13);winner=(int(d['leader'])+offset)%4
        d['won'][winner]+=d['trick'];d['trick']=[];d['leader']=winner
        if not any(d['hands']):finish(d)
    return d
def legal(state):
    d=state['data']
    if d['phase']=='playing':return [dict(type='play',params=dict(card=c)) for c in playable(d)]
    if d['phase']=='bidding':return [dict(type='bid',params=dict(tricks=n)) for n in range(14)]
    return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(cards=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51))),preconditions=['The supplied deck is a permutation of all fifty-two cards.'],external_observations=['Supplied shuffled deck.'])],constraints={},completeness=False,reason='external_deck_required')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';team=0 if d['scores'][0]>d['scores'][1] else 1
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if terminal else 'none',winners=[state['players'][p]['id'] for p in (team,team+2)] if terminal else [],losers=[state['players'][p]['id'] for p in (1-team,3-team)] if terminal else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p%2==team else 2,score=d['scores'][p%2],bags=d['bags'][p%2]) for p in range(4)] if terminal else [],reason='five_hundred_point_game_completed' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
