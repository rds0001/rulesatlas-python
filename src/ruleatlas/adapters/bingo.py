"""75-ball line bingo with free centers and simultaneous automatic claims."""
from copy import deepcopy
from ..values import fields,fail
CARDS=dict(type='array',minItems=2,maxItems=2,items=dict(type='array',minItems=25,maxItems=25,items=dict(type='integer',minimum=0,maximum=75)))
LINES=[[r*5+c for c in range(5)] for r in range(5)]+[[r*5+c for r in range(5)] for c in range(5)]+[[0,6,12,18,24],[4,8,12,16,20]]
def winners(d,calls=None):
    if not d['configured']:return []
    called=set(d['called'] if calls is None else calls)|{0}
    return [p for p,card in enumerate(d['cards']) if any(all(card[i] in called for i in line) for line in LINES)]
def validate(d):
    if not d['configured']:
        if d['cards'] or d['called']:fail('Unconfigured game contains data',code='INVALID_STATE')
        return
    if len(d['cards'])!=2:fail('Two cards are required',code='INVALID_STATE')
    for card in d['cards']:
        if card[12]!=0 or len(set(card))!=25:fail('Card requires a free center and distinct numbers',code='INVALID_STATE')
        if any(not 15*(i%5)+1<=v<=15*(i%5+1) for i,v in enumerate(card) if i!=12):fail('Number is outside its column range',code='INVALID_STATE')
    if len(d['called'])!=len(set(d['called'])):fail('Number has been called twice',code='INVALID_STATE')
    if d['called'] and winners(d,d['called'][:-1]):fail('Calls continued after bingo',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params']
    if not d['configured']:
        if action['type']!='set_cards':fail('Supply both cards first')
        fields(p,dict(cards=CARDS),'/params');d.update(configured=True,cards=deepcopy(p['cards']));return d
    if action['type']!='call':fail('Unknown action')
    fields(p,dict(number=dict(type='integer',minimum=1,maximum=75)),'/params')
    if p['number'] in d['called']:fail('Number has already been called')
    d['called'].append(p['number']);return d
def legal(state):
    d=state['data']
    if not d['configured']:return dict(mode='event_types',actions=[],action_types=[dict(type='set_cards',params_schema=dict(cards=CARDS),preconditions=['Each card has distinct numbers in the B/I/N/G/O column ranges and zero at the free center.'],external_observations=['Two supplied 5-by-5 bingo cards in row-major order.'])],constraints={},completeness=False,reason='external_cards_required')
    return [dict(type='call',params=dict(number=n)) for n in range(1,76) if n not in d['called']]
def outcome(state,pack):
    wins=winners(state['data'])
    return dict(status='terminal' if wins else 'ongoing',result_kind=('draw' if len(wins)>1 else 'win') if wins else 'none',winners=[state['players'][p]['id'] for p in wins],losers=[state['players'][p]['id'] for p in range(2) if p not in wins] if wins else [],placements=[],reason='completed_line' if wins else 'ongoing' if state['data']['configured'] else 'awaiting_cards',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if wins else None)
