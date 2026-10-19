"""An 80-number, 20-draw Keno round with a supplied gross-return table."""
from copy import deepcopy
from ..values import fields,fail
BET=dict(picks=dict(type='array',minItems=1,maxItems=20,items=dict(type='integer',minimum=1,maximum=80)),stake=dict(type='integer',minimum=1,maximum=1000),returns=dict(type='array',minItems=2,maxItems=21,items=dict(type='integer',minimum=0,maximum=1000000)))
def validate(d):
    if len(d['drawn'])!=len(set(d['drawn'])):fail('Drawn numbers must be distinct',code='INVALID_STATE')
    if d['bet'] is None:
        if d['drawn']:fail('Drawing requires a locked bet',code='INVALID_STATE')
        return
    b=d['bet']
    if len(b['picks'])!=len(set(b['picks'])) or len(b['returns'])!=len(b['picks'])+1:fail('Picks must be distinct and the table must cover every hit count',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params']
    if d['bet'] is None:
        if action['type']!='bet':fail('Supply a bet and return table first')
        fields(p,BET,'/params')
        if len(p['picks'])!=len(set(p['picks'])) or len(p['returns'])!=len(p['picks'])+1:fail('Picks must be distinct and the table must cover every hit count')
        d['bet']=deepcopy(p);return d
    if action['type']!='draw':fail('Only the next draw is permitted after the bet is locked')
    fields(p,dict(number=dict(type='integer',minimum=1,maximum=80)),'/params')
    if p['number'] in d['drawn']:fail('Number was already drawn')
    d['drawn'].append(p['number']);return d
def legal(state):
    d=state['data']
    if d['bet'] is not None:return [dict(type='draw',params=dict(number=n)) for n in range(1,81) if n not in d['drawn']]
    return dict(mode='event_types',actions=[],action_types=[dict(type='bet',params_schema=BET,preconditions=['Distinct picks and a gross-return multiplier for each hit count from zero through the number of picks.'],external_observations=['Selected numbers, abstract-chip stake and the published payout table.'])],constraints=dict(available_chips=1000),completeness=False,reason='external_payout_table_required')
def outcome(state,pack):
    d=state['data'];terminal=len(d['drawn'])==20;net=0;hits=0
    if terminal:
        b=d['bet'];hits=len(set(b['picks'])&set(d['drawn']));net=b['stake']*(b['returns'][hits]-1)
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('win' if net>0 else 'draw' if net==0 else 'other') if terminal else 'none',winners=[state['players'][0]['id']] if terminal and net>0 else [],losers=[state['players'][0]['id']] if terminal and net<0 else [],placements=[dict(player_id=state['players'][0]['id'],place=1,balance=1000+net,net=net,hits=hits)] if terminal else [],reason='twenty_numbers_drawn' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
