"""Heads-up no-limit Five Card Draw sharing the table-stakes betting engine."""
from copy import deepcopy
from itertools import combinations
from ..values import fields,fail
from .poker import Poker
from .poker_rank import five

class DrawPoker(Poker):
    def __init__(self):super().__init__(5,False)
    def strength(self,d,p):return five(d['holes'][p])
    def begin_draw(self,d):
        d['street']=1;d['phase']='drawing';d['street_bets']=[0,0];d['acted']=[False,False];d['last_raise']=40;d['turn']=1-d['dealer'];return d
    def runout(self,d):
        a,b=d['committed'];p=0 if a>b else 1;refund=abs(a-b);d['committed'][p]-=refund;d['street_bets'][p]-=refund;d['stacks'][p]+=refund
        return self.begin_draw(d) if d['street']==0 else self.settle(d)
    def progress(self,d):
        active=[p for p in (0,1) if d['stacks'][p]>0]
        if not active:return self.runout(d)
        if len(active)==1:
            p=active[0]
            if d['street_bets'][p]>=d['street_bets'][1-p]:return self.runout(d)
            d['turn']=p;return d
        if all(d['acted']) and d['street_bets'][0]==d['street_bets'][1]:return self.begin_draw(d) if d['street']==0 else self.settle(d)
        return d
    def validate(self,d):
        if d['phase']=='setup':
            super().validate(d)
            if d['discard'] or any(d['draw_done']):fail('Setup cannot contain draws or discards',code='INVALID_STATE')
            return
        cards=sum(d['holes'],[])+d['deck']+d['discard']
        if sorted(cards)!=list(range(52)) or any(len(h)!=5 for h in d['holes']) or d['board'] or d['burned'] or d['street'] not in (0,1):fail('Invalid five-card draw inventory',code='INVALID_STATE')
        if any(d['stacks'][p]!=d['initial_stacks'][p]-d['committed'][p]+d['payouts'][p] or d['street_bets'][p]>d['committed'][p] or d['committed'][p]>d['initial_stacks'][p] for p in (0,1)):fail('Stacks and contributions do not reconcile',code='INVALID_STATE')
        if d['street']==0 and (d['discard'] or any(d['draw_done'])):fail('Cards cannot be exchanged before the draw phase',code='INVALID_STATE')
        if len(d['discard'])>5*sum(d['draw_done']):fail('More discarded cards than completed draws permit',code='INVALID_STATE')
        if d['phase']=='drawing':
            first=1-int(d['dealer']);count=sum(d['draw_done'])
            if d['street']!=1 or count>=2 or d['turn']!=(first if count==0 else 1-first) or d['draw_done'][int(d['turn'])] or d['committed'][0]!=d['committed'][1] or any(d['street_bets']+d['payouts']):fail('Invalid pending draw order or unsettled contributions',code='INVALID_STATE')
        elif d['phase']=='finished':
            if d['folded'] is None and (d['street']!=1 or not all(d['draw_done']) or d['committed'][0]!=d['committed'][1]):fail('Showdown requires completed draws and matched contributions',code='INVALID_STATE')
            winners=self.winners(d);pot=sum(d['committed'])
            if d['payouts']!=[pot//len(winners) if p in winners else 0 for p in (0,1)]:fail('Final pot distribution is inconsistent',code='INVALID_STATE')
        else:
            t=int(d['turn'])
            if d['street']==1 and not all(d['draw_done']) or d['folded'] is not None or any(d['payouts']) or d['stacks'][t]==0 or d['street_bets'][t]>d['street_bets'][1-t]:fail('Invalid pending betting decision',code='INVALID_STATE')
            if all(d['acted']) and d['street_bets'][0]==d['street_bets'][1] or d['stacks'][1-t]==0 and d['street_bets'][t]>=d['street_bets'][1-t]:fail('Completed betting must advance',code='INVALID_STATE')
    def apply(self,state,action):
        if state['data']['phase']!='drawing':return super().apply(state,action)
        d=deepcopy(state['data']);p=action['params'];t=int(d['turn'])
        if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        if action['type']=='fold':
            fields(p,{},'/params');d['folded']=t;return self.settle(d)
        if action['type']!='draw':fail('Select zero through five cards to exchange')
        fields(p,dict(indices=dict(type='array',minItems=0,maxItems=5,items=dict(type='integer',minimum=0,maximum=4))),'/params')
        if len(set(p['indices']))!=len(p['indices']):fail('Draw indices must be distinct')
        if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        for i in sorted(p['indices']):
            i=int(i);d['discard'].append(d['holes'][t][i]);d['holes'][t][i]=d['deck'].pop(0)
        d['draw_done'][t]=True;d['turn']=1-t
        if all(d['draw_done']):d['phase']='betting';d['turn']=1-d['dealer'];return self.progress(d)
        return d
    def legal(self,state):
        if state['data']['phase']!='drawing':return super().legal(state)
        return [dict(type='fold',params={})]+[dict(type='draw',params=dict(indices=list(indices))) for n in range(6) for indices in combinations(range(5),n)]
