"""Two-player forty-card Briscola with unrestricted following and ordered draws."""
from copy import deepcopy
from ..values import fields,fail
POINTS=[11,0,10,0,0,0,0,2,3,4]
POWER=[10,1,9,2,3,4,5,6,7,8]
def winner(first,second,trump):
    a,b=int(first),int(second);suit=int(trump)//10
    if a//10==b//10:return 1 if POWER[b%10]>POWER[a%10] else 0
    return 1 if b//10==suit else 0
def validate(d):
    if not d['configured']:
        if any(d['hands']) or d['stock'] or any(d['won']) or d['trick'] or d['trump'] is not None or d['leader'] or d['turn']:fail('Unconfigured deal contains cards',code='INVALID_STATE')
        return
    cards=d['stock']+[c for hand in d['hands'] for c in hand]+[c for pile in d['won'] for c in pile]+d['trick']
    if sorted(cards)!=list(range(40)):fail('Card inventory must contain all forty cards once',code='INVALID_STATE')
    if d['trump'] is None or len(d['stock'])%2 or any(len(pile)%2 for pile in d['won']):fail('Invalid trump, stock or captured-pair count',code='INVALID_STATE')
    if d['stock'] and d['stock'][-1]!=d['trump']:fail('Exposed trump must remain at the bottom of the stock',code='INVALID_STATE')
    if d['turn']!=(1-d['leader'] if d['trick'] else d['leader']):fail('Trick and turn mismatch',code='INVALID_STATE')
    sizes=[len(h)+(1 if d['trick'] and p==d['leader'] else 0) for p,h in enumerate(d['hands'])]
    if sizes[0]!=sizes[1] or d['stock'] and sizes!=[3,3]:fail('Hand sizes do not match trick and draw phase',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);params=action['params']
    if not d['configured']:
        if action['type']!='deal':fail('Supply the shuffled deck first')
        fields(params,dict(cards=dict(type='array',minItems=40,maxItems=40,items=dict(type='integer',minimum=0,maximum=39))),'/params');cards=params['cards']
        if len(set(cards))!=40:fail('Deck must contain every card once')
        d.update(configured=True,hands=[deepcopy(cards[:6:2]),deepcopy(cards[1:6:2])],stock=deepcopy(cards[6:]),trump=cards[-1]);return d
    if action['type']!='play':fail('Unknown action')
    fields(params,dict(card=dict(type='integer',minimum=0,maximum=39)),'/params');p=int(d['turn']);card=params['card']
    if action.get('actor') is not None and action['actor']!=state['players'][p]['id']:fail('Wrong actor')
    if card not in d['hands'][p]:fail('Card is not in the current hand')
    d['hands'][p].remove(card);d['trick'].append(card)
    if len(d['trick'])==1:d['turn']=1-p;return d
    w=(int(d['leader'])+winner(d['trick'][0],d['trick'][1],d['trump']))%2
    d['won'][w]+=d['trick'];d['trick']=[]
    if d['stock']:
        d['hands'][w].append(d['stock'].pop(0));d['hands'][1-w].append(d['stock'].pop(0))
    d['turn']=w;d['leader']=w;return d
def legal(state):
    d=state['data']
    if not d['configured']:return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(cards=dict(type='array',minItems=40,maxItems=40,items=dict(type='integer',minimum=0,maximum=39))),preconditions=['The supplied order is a permutation of all forty cards.'],external_observations=['First six cards alternate between players; the remaining stock ends with the exposed trump.'])],constraints={},completeness=False,reason='external_deck_required')
    return [dict(type='play',params=dict(card=c)) for c in sorted(d['hands'][int(d['turn'])])]
def outcome(state,pack):
    d=state['data'];terminal=d['configured'] and not any(d['hands']) and not d['trick'];scores=[sum(POINTS[int(c)%10] for c in pile) for pile in d['won']];tie=scores[0]==scores[1];w=0 if scores[0]>scores[1] else 1
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('draw' if tie else 'win') if terminal else 'none',winners=[state['players'][w]['id']] if terminal and not tie else [],losers=[state['players'][1-w]['id']] if terminal and not tie else [],placements=[dict(player_id=state['players'][p]['id'],place=1+sum(v>scores[p] for v in scores),score=scores[p]) for p in (0,1)] if terminal else [],reason='twenty_tricks_completed' if terminal else 'ongoing' if d['configured'] else 'awaiting_deck',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
