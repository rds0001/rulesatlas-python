"""Single-zero roulette round with strict layout bets and integer-chip settlement."""
from copy import deepcopy
from ..values import fields,fail
RED={1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
KINDS=['straight','split','street','trio','corner','first_four','six_line','dozen','column','red','black','odd','even','low','high']
BET=dict(kind=dict(type='string',enum=KINDS),numbers=dict(type='array',minItems=0,maxItems=6,items=dict(type='integer',minimum=0,maximum=36)),stake=dict(type='integer',minimum=1,maximum=1000))
def selection(kind,numbers):
    n=sorted(int(v) for v in numbers)
    if len(set(n))!=len(n):return None
    if kind=='straight' and len(n)==1:return set(n),35
    if kind=='split' and len(n)==2:
        a,b=n
        if a==0 and b in (1,2,3) or a>0 and (b-a==3 or b-a==1 and (a-1)//3==(b-1)//3):return set(n),17
    if kind=='street' and len(n)==3 and n[0]%3==1 and n==list(range(n[0],n[0]+3)):return set(n),11
    if kind=='trio' and n in ([0,1,2],[0,2,3]):return set(n),11
    if kind=='corner' and len(n)==4 and n[0]>0 and n[0]%3 in (1,2) and n==[n[0],n[0]+1,n[0]+3,n[0]+4]:return set(n),8
    if kind=='first_four' and not n:return {0,1,2,3},8
    if kind=='six_line' and len(n)==6 and n[0]%3==1 and n==list(range(n[0],n[0]+6)):return set(n),5
    if kind=='dozen' and len(n)==1 and n[0] in (1,2,3):return set(range((n[0]-1)*12+1,n[0]*12+1)),2
    if kind=='column' and len(n)==1 and n[0] in (1,2,3):return set(range(n[0],37,3)),2
    if n:return None
    groups=dict(red=RED,black=set(range(1,37))-RED,odd=set(range(1,37,2)),even=set(range(2,37,2)),low=set(range(1,19)),high=set(range(19,37)))
    return (groups[kind],1) if kind in groups else None
def validate(d):
    if sum(b['stake'] for b in d['bets'])>1000:fail('Bets exceed the chip budget',code='INVALID_STATE')
    if any(selection(b['kind'],b['numbers']) is None for b in d['bets']):fail('Bet does not match the wheel layout',code='INVALID_STATE')
    if (d['phase']=='settled')!=(d['result'] is not None):fail('Result and betting phase mismatch',code='INVALID_STATE')
    if d['phase']!='betting' and not d['bets']:fail('A closed round must contain a bet',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if d['phase']=='betting':
        if kind=='bet':
            fields(p,BET,'/params')
            if selection(p['kind'],p['numbers']) is None:fail('Bet does not match the wheel layout')
            if sum(b['stake'] for b in d['bets'])+p['stake']>1000:fail('Bets exceed the chip budget')
            d['bets'].append(deepcopy(p));return d
        if kind=='cancel':
            fields(p,dict(index=dict(type='integer',minimum=0,maximum=max(0,len(d['bets'])-1))),'/params')
            if not d['bets']:fail('There is no bet to cancel')
            del d['bets'][int(p['index'])];return d
        if kind=='close_bets':
            fields(p,{},'/params')
            if not d['bets']:fail('Place at least one bet')
            d['phase']='closed';return d
        fail('Action is not permitted while betting')
    if kind!='settle':fail('Only settlement is permitted after betting closes')
    fields(p,dict(number=dict(type='integer',minimum=0,maximum=36)),'/params');d['result']=p['number'];d['phase']='settled';return d
def legal(state):
    d=state['data']
    if d['phase']=='betting':
        schemas=dict(bet=BET)
        if d['bets']:schemas.update(cancel=dict(index=dict(type='integer',minimum=0,maximum=len(d['bets'])-1)),close_bets={})
    else:schemas=dict(settle=dict(number=dict(type='integer',minimum=0,maximum=36)))
    return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['The betting phase, layout selection and available chip budget must permit the action.'],external_observations=['Player bet selection or the official single-zero wheel result.']) for k,v in schemas.items()],constraints=dict(available_chips=1000-sum(b['stake'] for b in d['bets'])),completeness=False,reason='guarded_layout_bets_and_external_wheel_result')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='settled';net=0
    if terminal:
        for b in d['bets']:
            numbers,odds=selection(b['kind'],b['numbers']);net+=b['stake']*(odds if d['result'] in numbers else -1)
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('win' if net>0 else 'draw' if net==0 else 'other') if terminal else 'none',winners=[state['players'][0]['id']] if terminal and net>0 else [],losers=[state['players'][0]['id']] if terminal and net<0 else [],placements=[dict(player_id=state['players'][0]['id'],place=1,balance=1000+net,net=net)] if terminal else [],reason='round_settled' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
