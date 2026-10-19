"""Heads-up fixed-limit Seven Card Stud, four-bet cap and fourth-street pair option."""
from copy import deepcopy
from itertools import combinations
from collections import Counter
from ..values import fields,fail
from .poker import Poker
from .poker_rank import five

class Stud(Poker):
    def __init__(self):super().__init__(7,False)
    def strength(self,d,p):return max(five(c) for c in combinations(d['holes'][p],5))
    def exposed(self,d,p):return d['holes'][p][2:6]
    def first(self,d):
        if d['street']==0:return min((0,1),key=lambda p:(int(d['holes'][p][2])%13,int(d['holes'][p][2])//13))
        def rank(p):
            counts=Counter(int(c)%13+2 for c in self.exposed(d,p));groups=sorted(((n,r) for r,n in counts.items()),reverse=True)
            category=7 if groups[0][0]==4 else 3 if groups[0][0]==3 else 2 if len(groups)>1 and groups[0][0]==groups[1][0]==2 else 1 if groups[0][0]==2 else 0
            return (category,*[r for n,r in groups])
        ranks=[rank(p) for p in (0,1)];return 1-int(d['dealer']) if ranks[0]==ranks[1] else 0 if ranks[0]>ranks[1] else 1
    def pair_option(self,d):return d['street']==1 and not d['big_fourth'] and any(len({int(c)%13 for c in self.exposed(d,p)})==1 for p in (0,1))
    def unit(self,d):return 40 if d['street']>=2 or d['big_fourth'] else 20
    def next_street(self,d):
        d['burned'].append(d['deck'].pop(0))
        for p in (1-int(d['dealer']),int(d['dealer'])):d['holes'][p].append(d['deck'].pop(0))
        d['street']+=1;d['street_bets']=[0,0];d['acted']=[False,False];d['raise_count']=0;d['turn']=self.first(d);return d
    def runout(self,d):
        a,b=d['committed'];p=0 if a>b else 1;refund=abs(a-b);d['committed'][p]-=refund;d['street_bets'][p]=max(0,d['street_bets'][p]-refund);d['stacks'][p]+=refund
        while d['street']<4:self.next_street(d)
        return self.settle(d)
    def progress(self,d):
        active=[p for p in (0,1) if d['stacks'][p]>0]
        if not active:return self.runout(d)
        if len(active)==1:
            p=active[0]
            if d['street_bets'][p]>=d['street_bets'][1-p]:return self.runout(d)
            d['turn']=p;return d
        if all(d['acted']) and d['street_bets'][0]==d['street_bets'][1]:return self.settle(d) if d['street']==4 else self.next_street(d)
        return d
    def raises(self,d):
        t=int(d['turn']);high=max(d['street_bets']);available=d['street_bets'][t]+d['stacks'][t]
        if d['raise_count']>=4 or d['stacks'][1-t]==0:return []
        units=[self.unit(d)]+([40] if self.pair_option(d) else [])
        return sorted({min(available,unit if d['street']==0 and high<20 else high+unit) for unit in units if available>high})
    def validate(self,d):
        if d['phase']=='setup':
            if any(d['holes']) or d['deck'] or d['burned'] or any(d['initial_stacks']+d['stacks']+d['committed']+d['street_bets']+d['payouts']) or d['folded'] is not None:fail('Setup must be empty',code='INVALID_STATE')
            return
        cards=sum(d['holes'],[])+d['deck']+d['burned']
        if sorted(cards)!=list(range(52)) or any(len(h)!=3+d['street'] for h in d['holes']) or len(d['burned'])!=d['street']:fail('Card inventory does not match the stud street',code='INVALID_STATE')
        if any(d['stacks'][p]!=d['initial_stacks'][p]-d['committed'][p]+d['payouts'][p] or d['street_bets'][p]>d['committed'][p] or d['committed'][p]>d['initial_stacks'][p] for p in (0,1)):fail('Stacks and contributions do not reconcile',code='INVALID_STATE')
        if d['big_fourth'] and (d['street']==0 or not any(len({int(c)%13 for c in h[2:4]})==1 for h in d['holes'])):fail('Large fourth-street bet requires an exposed pair',code='INVALID_STATE')
        if d['phase']=='bring_in':
            if d['street']!=0 or any(d['street_bets']+d['payouts']) or d['turn']!=self.first(d) or any(d['acted']) or d['folded'] is not None or min(d['stacks'])==0:fail('Invalid bring-in decision',code='INVALID_STATE')
        elif d['phase']=='finished':
            if d['folded'] is None and (d['street']!=4 or d['committed'][0]!=d['committed'][1]):fail('Showdown requires seven cards and matched contributions',code='INVALID_STATE')
            winners=self.winners(d);pot=sum(d['committed'])
            if d['payouts']!=[pot//len(winners) if p in winners else 0 for p in (0,1)]:fail('Final pot distribution is inconsistent',code='INVALID_STATE')
        else:
            t=int(d['turn'])
            if d['folded'] is not None or any(d['payouts']) or d['stacks'][t]==0 or d['street_bets'][t]>d['street_bets'][1-t]:fail('Invalid pending betting decision',code='INVALID_STATE')
            if all(d['acted']) and d['street_bets'][0]==d['street_bets'][1] or d['stacks'][1-t]==0 and d['street_bets'][t]>=d['street_bets'][1-t]:fail('Closed betting must advance',code='INVALID_STATE')
    def apply(self,state,action):
        d=deepcopy(state['data']);p=action['params'];kind=action['type'];t=int(d['turn'])
        if kind=='start':
            fields(p,dict(deck=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51)),dealer=dict(type='integer',minimum=0,maximum=1),stacks=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=1,maximum=1000000))),'/params')
            if d['phase']!='setup' or len(set(p['deck']))!=52:fail('Supply all cards and starting stacks once')
            d['dealer']=p['dealer'];d['initial_stacks']=p['stacks'][:];d['stacks']=p['stacks'][:];d['deck']=p['deck'][:]
            for i in range(6):d['holes'][(1-int(d['dealer'])+i)%2].append(d['deck'].pop(0))
            for q in (0,1):amount=min(5,d['stacks'][q]);d['stacks'][q]-=amount;d['committed'][q]=amount
            d['turn']=self.first(d);d['phase']='bring_in'
            return self.progress(d) if min(d['stacks'])==0 else d
        if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        if d['phase']=='bring_in':
            if kind!='bring_in':fail('The lowest door card must post the bring-in or complete')
            fields(p,dict(complete=dict(type='boolean')),'/params')
            if p['complete'] and d['stacks'][t]<20:fail('Completing the bring-in requires twenty available chips')
            amount=min(d['stacks'][t],20 if p['complete'] else 10);d['stacks'][t]-=amount;d['committed'][t]+=amount;d['street_bets'][t]=amount;d['raise_count']=1 if amount==20 else 0;d['acted'][t]=True;d['turn']=1-t;d['phase']='betting';return self.progress(d)
        if kind=='fold':fields(p,{},'/params');d['folded']=t;return self.settle(d)
        if kind in ('check','call'):
            fields(p,{},'/params');owed=max(d['street_bets'])-d['street_bets'][t]
            if (kind=='check')!=(owed==0):fail('Check only with nothing owed; call only facing a bet')
            amount=min(owed,d['stacks'][t]);d['stacks'][t]-=amount;d['committed'][t]+=amount;d['street_bets'][t]+=amount;d['acted'][t]=True
        elif kind=='raise':
            fields(p,dict(to=dict(type='integer',minimum=1,maximum=1000000)),'/params');target=p['to'];high=max(d['street_bets'])
            if target not in self.raises(d):fail('Raise must use the fixed betting unit, available all-in amount and four-bet cap')
            increment=target if d['street']==0 and high<20 else target-high
            if self.pair_option(d) and increment==40:d['big_fourth']=True
            if increment>=self.unit(d):d['raise_count']+=1
            amount=target-d['street_bets'][t];d['stacks'][t]-=amount;d['committed'][t]+=amount;d['street_bets'][t]=target;d['acted']=[False,False];d['acted'][t]=True
        else:fail('Unknown action')
        d['turn']=1-t;return self.progress(d)
    def legal(self,state):
        d=state['data']
        if d['phase']=='setup':return dict(mode='event_types',actions=[],action_types=[dict(type='start',params_schema=dict(deck=dict(type='array',minItems=52,maxItems=52,items=dict(type='integer',minimum=0,maximum=51)),dealer=dict(type='integer',minimum=0,maximum=1),stacks=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=1,maximum=1000000))),preconditions=['Complete deck and positive stacks; five-chip ante, ten-chip bring-in, twenty/forty limits.'],external_observations=['External deck order and table stacks.'])],constraints={},completeness=False,reason='external_deal')
        if d['phase']=='bring_in':return [dict(type='bring_in',params=dict(complete=x)) for x in (False,True) if not x or d['stacks'][int(d['turn'])]>=20]
        owed=max(d['street_bets'])-d['street_bets'][int(d['turn'])]
        return [dict(type='fold',params={}),dict(type='call' if owed else 'check',params={})]+[dict(type='raise',params=dict(to=v)) for v in self.raises(d)]
