"""Sic Bo round: strict bet forms, actual dice and an explicit payout table."""
from copy import deepcopy
from ..values import fields,fail
KINDS=['single','double','triple','combination','total','any_triple','big','small']
BET=dict(kind=dict(type='string',enum=KINDS),numbers=dict(type='array',minItems=0,maxItems=2,items=dict(type='integer',minimum=1,maximum=17)),stake=dict(type='integer',minimum=1,maximum=1000))
def selection(kind,numbers):
    n=sorted(numbers)
    if kind in ('single','double','triple') and len(n)==1 and 1<=n[0]<=6:return True
    if kind=='combination' and len(n)==2 and 1<=n[0]<n[1]<=6:return True
    if kind=='total' and len(n)==1 and 4<=n[0]<=17:return True
    if kind in ('any_triple','big','small') and not n:return True
    return None
def payout(b,dice):
    k=b['kind'];n=b['numbers'];triple=len(set(dice))==1;total=sum(dice);odds=None
    if k=='single':odds=dice.count(n[0]) or None
    elif k=='double' and dice.count(n[0])>=2:odds=10
    elif k=='triple' and dice.count(n[0])==3:odds=180
    elif k=='combination' and all(v in dice for v in n):odds=5
    elif k=='total' and n[0]==total:odds={4:50,5:18,6:14,7:12,8:8,9:6,10:6,11:6,12:6,13:8,14:12,15:14,16:18,17:50}[total]
    elif k=='any_triple' and triple:odds=30
    elif k=='big' and not triple and 11<=total<=17:odds=1
    elif k=='small' and not triple and 4<=total<=10:odds=1
    return b['stake']*(odds if odds is not None else -1)
def validate(d):
    if sum(b['stake'] for b in d['bets'])>1000:fail('Bets exceed the chip budget',code='INVALID_STATE')
    if any(selection(b['kind'],b['numbers']) is None for b in d['bets']):fail('Bet does not match the bet form',code='INVALID_STATE')
    if (d['phase']=='settled')!=(d['result'] is not None):fail('Result and betting phase mismatch',code='INVALID_STATE')
    if d['phase']!='betting' and not d['bets']:fail('A closed round must contain a bet',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if d['phase']=='betting':
        if kind=='bet':
            fields(p,BET,'/params')
            if selection(p['kind'],p['numbers']) is None:fail('Bet does not match the bet form')
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
    fields(p,dict(dice=dict(type='array',minItems=3,maxItems=3,items=dict(type='integer',minimum=1,maximum=6))),'/params');d['result']=deepcopy(p['dice']);d['phase']='settled';return d
def legal(state):
    d=state['data']
    if d['phase']=='betting':
        schemas=dict(bet=BET)
        if d['bets']:schemas.update(cancel=dict(index=dict(type='integer',minimum=0,maximum=len(d['bets'])-1)),close_bets={})
    else:schemas=dict(settle=dict(dice=dict(type='array',minItems=3,maxItems=3,items=dict(type='integer',minimum=1,maximum=6))))
    return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['The betting phase, bet selection and available chip budget must permit the action.'],external_observations=['Player bet selection or the official three-dice result.']) for k,v in schemas.items()],constraints=dict(available_chips=1000-sum(b['stake'] for b in d['bets'])),completeness=False,reason='guarded_bets_and_external_dice_result')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='settled';net=0
    if terminal:
        for b in d['bets']:
            net+=payout(b,d['result'])
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('win' if net>0 else 'draw' if net==0 else 'other') if terminal else 'none',winners=[state['players'][0]['id']] if terminal and net>0 else [],losers=[state['players'][0]['id']] if terminal and net<0 else [],placements=[dict(player_id=state['players'][0]['id'],place=1,balance=1000+net,net=net)] if terminal else [],reason='round_settled' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
