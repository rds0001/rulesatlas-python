"""Single-player, single-deck blackjack; all amounts are integer half-chip units."""
from copy import deepcopy
from ..values import fields,fail

def value(c):return 11 if int(c)%13==12 else min(int(c)%13+2,10)
def total(cards):
    n=sum(value(c) for c in cards);aces=sum(value(c)==11 for c in cards)
    while n>21 and aces:n-=10;aces-=1
    return n

def natural(hand):return not hand['split'] and len(hand['cards'])==2 and total(hand['cards'])==21
def dealer_natural(d):return len(d['dealer'])==2 and total(d['dealer'])==21
def draw(d):
    if not d['deck']:fail('Deck is exhausted')
    return d['deck'].pop(0)

def expected_returns(d):
    dn=dealer_natural(d);dt=total(d['dealer']);result=[]
    for h in d['hands']:
        wager=h['wager'];pt=total(h['cards'])
        if h['status']=='surrendered':pay=wager//2
        elif pt>21:pay=0
        elif dn:pay=wager if natural(h) else 0
        elif natural(h):pay=5*wager//2
        elif dt>21 or pt>dt:pay=2*wager
        elif pt==dt:pay=wager
        else:pay=0
        result.append(pay)
    return result

def settle(d):
    if not dealer_natural(d) and any(h['status'] not in ('bust','surrendered') and not natural(h) for h in d['hands']):
        while total(d['dealer'])<17:d['dealer'].append(draw(d))
    for h in d['hands']:
        if h['status']=='active':h['status']='stood'
    d['returns']=expected_returns(d);d['insurance_return']=3*d['insurance'] if dealer_natural(d) else 0;d['balance']+=sum(d['returns'])+d['insurance_return'];d['phase']='finished';return d

def advance(d):
    while d['current']<len(d['hands']):
        h=d['hands'][int(d['current'])]
        if h['status']=='waiting':
            h['cards'].append(draw(d));h['status']='stood' if h['split_aces'] or total(h['cards'])==21 else 'active'
        if h['status']=='active':return d
        d['current']+=1
    d['current']=len(d['hands'])-1;return settle(d)

def after_peek(d):
    if dealer_natural(d) or natural(d['hands'][0]):return settle(d)
    d['phase']='player';return d

def validate(d):
    hands=d['hands']
    if d['phase']=='bet':
        if hands or d['dealer'] or d['deck'] or d['base_wager'] or d['insurance'] or d['returns'] or d['insurance_return'] or d['balance']!=2000:fail('Initial bankroll state must be empty',code='INVALID_STATE')
        return
    cards=d['dealer']+d['deck']+sum([h['cards'] for h in hands],[])
    if sorted(cards)!=list(range(52)) or not hands or d['current']>=len(hands) or len(d['dealer'])<2:fail('Invalid card inventory or active hand index',code='INVALID_STATE')
    base=d['base_wager']
    if base<2 or base%2 or d['insurance'] not in (0,base//2) or d['insurance'] and value(d['dealer'][0])!=11:fail('Invalid stake or insurance amount',code='INVALID_STATE')
    if len(d['returns'])!=len(hands) or d['balance']!=2000-sum(h['wager'] for h in hands)-d['insurance']+sum(d['returns'])+d['insurance_return']:fail('Bankroll and stakes do not reconcile',code='INVALID_STATE')
    for i,h in enumerate(hands):
        status=h['status'];n=len(h['cards']);v=total(h['cards'])
        if h['wager'] not in (base,2*base) or (status=='waiting')!=(n==1) or n<1:fail('Invalid hand size or wager',code='INVALID_STATE')
        if status=='waiting' and (not h['split'] or i<=d['current']):fail('Only later split hands may await their first draw',code='INVALID_STATE')
        if (status=='bust')!=(v>21) or status=='active' and v>=21:fail('Hand status does not match its total',code='INVALID_STATE')
        if h['split_aces'] and (not h['split'] or value(h['cards'][0])!=11 or n>2 or status not in ('waiting','stood')):fail('Split aces get exactly one additional card',code='INVALID_STATE')
        if status=='surrendered' and (h['split'] or n!=2 or h['wager']!=base):fail('Surrender is only available on an original two-card hand',code='INVALID_STATE')
    if dealer_natural(d) and (len(hands)!=1 or hands[0]['split'] or len(hands[0]['cards'])!=2 or hands[0]['status']=='surrendered'):fail('Dealer blackjack ends before player actions',code='INVALID_STATE')
    if len(hands)>1 and any(not h['split'] for h in hands):fail('Multiple hands must all arise from splitting',code='INVALID_STATE')
    if d['phase']=='finished':
        if any(h['status'] in ('active','waiting') for h in hands) or d['returns']!=expected_returns(d) or d['insurance_return']!=(3*d['insurance'] if dealer_natural(d) else 0):fail('Final hand settlement is inconsistent',code='INVALID_STATE')
        if not dealer_natural(d) and any(h['status'] not in ('bust','surrendered') and not natural(h) for h in hands) and total(d['dealer'])<17:fail('Dealer must draw through sixteen',code='INVALID_STATE')
    else:
        if any(d['returns']) or d['insurance_return'] or len(d['dealer'])!=2:fail('Dealer drawing and returns occur only at settlement',code='INVALID_STATE')
        if d['phase']=='insurance':
            if value(d['dealer'][0])!=11 or len(hands)!=1 or len(hands[0]['cards'])!=2 or d['insurance']:fail('Insurance is offered only before the ace-upcard peek',code='INVALID_STATE')
        elif hands[int(d['current'])]['status']!='active' or any(h['status']=='active' for h in hands[:int(d['current'])]) or dealer_natural(d) or any(natural(h) for h in hands):fail('Invalid player decision state',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if kind=='bet':
        fields(p,dict(stake=dict(type='integer',minimum=2,maximum=1000),deck=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51))),'/params')
        if d['phase']!='bet' or p['stake']%2 or len(set(p['deck']))!=52:fail('Bet an even number of half-chip units and supply all fifty-two cards')
        stake=p['stake'];deck=p['deck'];d['base_wager']=stake;d['balance']-=stake;d['hands']=[dict(cards=[deck[0],deck[2]],wager=stake,status='stood' if total([deck[0],deck[2]])==21 else 'active',split=False,split_aces=False)];d['dealer']=[deck[1],deck[3]];d['deck']=deck[4:];d['returns']=[0]
        if value(d['dealer'][0])==11:d['phase']='insurance';return d
        return after_peek(d)
    if kind=='insurance':
        fields(p,dict(take=dict(type='boolean')),'/params')
        if d['phase']!='insurance':fail('No insurance decision is pending')
        if p['take']:
            amount=d['base_wager']//2
            if d['balance']<amount:fail('Insufficient bankroll for insurance')
            d['insurance']=amount;d['balance']-=amount
        return after_peek(d)
    if d['phase']!='player':fail('No player decision is pending')
    fields(p,{},'/params');h=d['hands'][int(d['current'])]
    if kind=='hit':
        h['cards'].append(draw(d));v=total(h['cards']);h['status']='bust' if v>21 else 'stood' if v==21 else 'active';return advance(d)
    if kind=='stand':h['status']='stood';return advance(d)
    if kind=='surrender':
        if h['split'] or len(h['cards'])!=2:fail('Late surrender requires an original two-card hand after the dealer peek')
        h['status']='surrendered';return advance(d)
    if kind=='double':
        if len(h['cards'])!=2 or d['balance']<h['wager']:fail('Doubling requires two cards and an equal available stake')
        d['balance']-=h['wager'];h['wager']*=2;h['cards'].append(draw(d));h['status']='bust' if total(h['cards'])>21 else 'stood';return advance(d)
    if kind=='split':
        if len(h['cards'])!=2 or int(h['cards'][0])%13!=int(h['cards'][1])%13 or len(d['hands'])>=4 or d['balance']<h['wager']:fail('Split requires an equal-rank pair, available stake and fewer than four hands')
        d['balance']-=h['wager'];new=[dict(cards=[c],wager=h['wager'],status='waiting',split=True,split_aces=value(c)==11) for c in h['cards']];i=int(d['current']);d['hands'][i:i+1]=new;d['returns'].insert(i,0);return advance(d)
    fail('Unknown action')

def legal(state):
    d=state['data']
    if d['phase']=='bet':return dict(mode='event_types',actions=[],action_types=[dict(type='bet',params_schema=dict(stake=dict(type='integer',minimum=2,maximum=1000),deck=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51))),preconditions=['Stake is even in half-chip units; deck is a permutation of all fifty-two cards.'],external_observations=['External deck order.'])],constraints=dict(balance=d['balance']),completeness=False,reason='external_deal')
    if d['phase']=='insurance':return [dict(type='insurance',params=dict(take=t)) for t in (False,True) if not t or d['balance']>=d['base_wager']//2]
    h=d['hands'][int(d['current'])];kinds=['hit','stand']
    if not h['split'] and len(h['cards'])==2:kinds.append('surrender')
    if len(h['cards'])==2 and d['balance']>=h['wager']:
        kinds.append('double')
        if int(h['cards'][0])%13==int(h['cards'][1])%13 and len(d['hands'])<4:kinds.append('split')
    return [dict(type=k,params={}) for k in kinds]
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';net=d['balance']-2000;pid=state['players'][0]['id']
    return dict(status='terminal' if done else 'ongoing',result_kind=('win' if net>0 else 'draw' if net==0 else 'other') if done else 'none',winners=[pid] if done and net>0 else [],losers=[pid] if done and net<0 else [],placements=[dict(player_id=pid,place=1,balance_half_chips=d['balance'],net_half_chips=net)] if done else [],reason='single_round_settled' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
