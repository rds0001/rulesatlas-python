"""Heads-up Hold'em/Omaha betting state machines, without strategy or simulation."""
from copy import deepcopy
from itertools import combinations
from ..values import fields,fail
from .poker_rank import five

class Poker:
    def __init__(self,hole_count,pot_limit):self.hole_count=hole_count;self.pot_limit=pot_limit
    def strength(self,d,p):
        if self.hole_count==2:return max(five(c) for c in combinations(d['holes'][p]+d['board'],5))
        return max(five(list(h)+list(b)) for h in combinations(d['holes'][p],2) for b in combinations(d['board'],3))
    def winners(self,d):
        if d['folded'] is not None:return [1-int(d['folded'])]
        ranks=[self.strength(d,p) for p in (0,1)];return [p for p in (0,1) if ranks[p]==max(ranks)]
    def settle(self,d):
        winners=self.winners(d);pot=sum(d['committed']);d['payouts']=[pot//len(winners) if p in winners else 0 for p in (0,1)]
        for p in (0,1):d['stacks'][p]+=d['payouts'][p]
        d['phase']='finished';return d
    def board_next(self,d):
        d['burned'].append(d['deck'].pop(0));n=3 if d['street']==0 else 1;d['board']+=d['deck'][:n];d['deck']=d['deck'][n:];d['street']+=1
    def runout(self,d):
        a,b=d['committed'];p=0 if a>b else 1;refund=abs(a-b)
        d['committed'][p]-=refund;d['street_bets'][p]-=refund;d['stacks'][p]+=refund
        while d['street']<3:
            self.board_next(d);d['street_bets']=[0,0]
        return self.settle(d)
    def progress(self,d):
        active=[p for p in (0,1) if d['stacks'][p]>0]
        if not active:return self.runout(d)
        if len(active)==1:
            p=active[0]
            if d['street_bets'][p]>=d['street_bets'][1-p]:return self.runout(d)
            d['turn']=p;return d
        if all(d['acted']) and d['street_bets'][0]==d['street_bets'][1]:
            if d['street']==3:return self.settle(d)
            self.board_next(d);d['street_bets']=[0,0];d['acted']=[False,False];d['last_raise']=40;d['turn']=1-d['dealer']
        return d
    def cap(self,d):
        t=int(d['turn']);owed=max(d['street_bets'])-d['street_bets'][t];maximum=d['street_bets'][t]+d['stacks'][t]
        return min(maximum,d['street_bets'][t]+sum(d['committed'])+2*owed) if self.pot_limit else maximum
    def validate(self,d):
        if d['phase']=='setup':
            if any(d['holes']) or d['deck'] or d['board'] or d['burned'] or any(d['initial_stacks']+d['stacks']+d['committed']+d['street_bets']+d['payouts']) or d['folded'] is not None:fail('Setup must have no cards or committed chips',code='INVALID_STATE')
            return
        cards=sum(d['holes'],[])+d['deck']+d['board']+d['burned']
        if sorted(cards)!=list(range(52)) or any(len(h)!=self.hole_count for h in d['holes']) or len(d['board'])!=[0,3,4,5][int(d['street'])] or len(d['burned'])!=d['street']:fail('Card inventory does not match the betting street',code='INVALID_STATE')
        if any(d['stacks'][p]!=d['initial_stacks'][p]-d['committed'][p]+d['payouts'][p] or d['street_bets'][p]>d['committed'][p] or d['committed'][p]>d['initial_stacks'][p] for p in (0,1)):fail('Stacks and contributions do not reconcile',code='INVALID_STATE')
        if d['phase']=='finished':
            if d['folded'] is None and (d['street']!=3 or d['committed'][0]!=d['committed'][1]):fail('Showdown needs five board cards and matched contributions',code='INVALID_STATE')
            winners=self.winners(d);pot=sum(d['committed'])
            if d['payouts']!=[pot//len(winners) if p in winners else 0 for p in (0,1)]:fail('Final pot distribution is inconsistent',code='INVALID_STATE')
        else:
            t=int(d['turn'])
            if d['folded'] is not None or any(d['payouts']) or d['stacks'][t]==0 or d['street_bets'][t]>d['street_bets'][1-t]:fail('Invalid pending betting decision',code='INVALID_STATE')
            if all(d['acted']) and d['street_bets'][0]==d['street_bets'][1]:fail('Closed betting street must advance',code='INVALID_STATE')
            if d['stacks'][1-t]==0 and d['street_bets'][t]>=d['street_bets'][1-t]:fail('Matched all-in must proceed to showdown',code='INVALID_STATE')
    def apply(self,state,action):
        d=deepcopy(state['data']);p=action['params'];kind=action['type'];t=int(d['turn'])
        if kind=='start':
            fields(p,dict(deck=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51)),dealer=dict(type='integer',minimum=0,maximum=1),stacks=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=1,maximum=1000000))),'/params')
            if d['phase']!='setup' or len(set(p['deck']))!=52:fail('Supply all cards and starting stacks once')
            d['dealer']=p['dealer'];d['initial_stacks']=p['stacks'][:];d['stacks']=p['stacks'][:];d['deck']=p['deck'][:];d['phase']='betting';d['turn']=d['dealer']
            for i in range(2*self.hole_count):d['holes'][(1-int(d['dealer'])+i)%2].append(d['deck'].pop(0))
            for q in (0,1):
                amount=min(d['stacks'][q],20 if q==d['dealer'] else 40);d['stacks'][q]-=amount;d['committed'][q]=amount;d['street_bets'][q]=amount
            return self.progress(d)
        if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        owed=max(d['street_bets'])-d['street_bets'][t]
        if kind=='fold':fields(p,{},'/params');d['folded']=t;return self.settle(d)
        if kind in ('check','call'):
            fields(p,{},'/params')
            if (kind=='check')!=(owed==0):fail('Check only with nothing owed; call only when facing a bet')
            amount=min(owed,d['stacks'][t]);d['stacks'][t]-=amount;d['committed'][t]+=amount;d['street_bets'][t]+=amount;d['acted'][t]=True
        elif kind=='raise':
            fields(p,dict(to=dict(type='integer',minimum=1,maximum=1000000)),'/params');target=p['to'];high=max(d['street_bets']);increment=target-high
            if d['stacks'][1-t]==0 or target<=high or target>self.cap(d):fail('Raise exceeds available chips or the betting limit, or the opponent is all-in')
            if increment<d['last_raise'] and target!=d['street_bets'][t]+d['stacks'][t]:fail('A smaller-than-minimum raise is permitted only as an all-in')
            amount=target-d['street_bets'][t];d['stacks'][t]-=amount;d['committed'][t]+=amount;d['street_bets'][t]=target;d['acted']=[False,False];d['acted'][t]=True
            if increment>=d['last_raise']:d['last_raise']=increment
        else:fail('Unknown action')
        d['turn']=1-t;return self.progress(d)
    def legal(self,state):
        d=state['data']
        if d['phase']=='setup':return dict(mode='event_types',actions=[],action_types=[dict(type='start',params_schema=dict(deck=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51)),dealer=dict(type='integer',minimum=0,maximum=1),stacks=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=1,maximum=1000000))),preconditions=['Supply a complete deck and positive starting stacks; dealer posts small blind twenty, opponent big blind forty, capped by available chips.'],external_observations=['External deck order and starting stacks.'])],constraints={},completeness=False,reason='external_deal')
        t=int(d['turn']);owed=max(d['street_bets'])-d['street_bets'][t];high=max(d['street_bets']);cap=self.cap(d);minimum=high+d['last_raise'];actions=[dict(type='fold',params={}),dict(type='call' if owed else 'check',params={})];types=[]
        if d['stacks'][1-t]>0 and cap>high and (cap>=minimum or cap==d['street_bets'][t]+d['stacks'][t]):types=[dict(type='raise',params_schema=dict(to=dict(type='integer',minimum=high+1,maximum=cap)),preconditions=['At least the full minimum raise, except an all-in may be smaller. The opponent must retain chips.'],external_observations=[])]
        return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(to_call=min(owed,d['stacks'][t]),pot=sum(d['committed']),minimum_full_raise_to=minimum,maximum_raise_to=cap,limit='pot_limit' if self.pot_limit else 'no_limit'),completeness=False,reason='bounded_bet_amounts')
    def outcome(self,state,pack):
        d=state['data'];done=d['phase']=='finished';winners=self.winners(d) if done else []
        return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if len(winners)>1 else 'win') if done else 'none',winners=[state['players'][p]['id'] for p in winners],losers=[state['players'][p]['id'] for p in (0,1) if p not in winners] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p in winners else 2,stack=d['stacks'][p],net=d['stacks'][p]-d['initial_stacks'][p]) for p in (0,1)] if done else [],reason=('opponent_folded' if d['folded'] is not None else 'showdown') if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
