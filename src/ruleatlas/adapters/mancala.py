"""Oware and Toguz Kumalak: sowing, captures, feeding and material accounting."""
from copy import deepcopy
from ..values import fields,fail
class Mancala:
    def __init__(self,config):self.mode=config['mode'];self.n=6 if self.mode=='oware' else 9;self.total=48 if self.mode=='oware' else 162
    def own(self,p):return range(p*self.n,(p+1)*self.n)
    def sow(self,d,pit):
        d=deepcopy(d);p=int(d['turn']);count=int(d['pits'][pit]);last=pit
        if self.mode=='toguz' and count>1:d['pits'][pit]=1;count-=1
        else:d['pits'][pit]=0
        while count:
            last=(last+1)%(2*self.n)
            if self.mode=='oware' and last==pit:continue
            owner=next((t for t,x in enumerate(d.get('tuzdyk',[])) if x==last),None)
            if owner is None:d['pits'][last]+=1
            else:d['scores'][owner]+=1
            count-=1
        return d,last
    def pits(self,d):
        p=int(d['turn']);candidates=[i for i in self.own(p) if d['pits'][i]>0]
        if self.mode=='oware' and not any(d['pits'][i] for i in self.own(1-p)):candidates=[i for i in candidates if any(self.sow(d,i)[0]['pits'][j]>0 for j in self.own(1-p))]
        return candidates
    def tuz_available(self,d,last):
        p=int(d['turn']);other=d['tuzdyk'][1-p]
        return last in self.own(1-p) and last%9!=8 and d['pits'][last]==3 and d['tuzdyk'][p] is None and (other is None or other%9!=last%9)
    def collect(self,d):
        for p in (0,1):
            for i in self.own(p):d['scores'][p]+=d['pits'][i];d['pits'][i]=0
        return d
    def validate(self,d):
        if sum(d['pits'])+sum(d['scores'])!=self.total:fail('Seed inventory is not conserved',code='INVALID_STATE')
        if self.mode=='toguz':
            for p,pit in enumerate(d['tuzdyk']):
                if pit is not None and (pit not in self.own(1-p) or pit%9==8 or d['pits'][int(pit)]!=0):fail('Invalid tuzdyk location or seed count',code='INVALID_STATE')
            if all(x is not None for x in d['tuzdyk']) and d['tuzdyk'][0]%9==d['tuzdyk'][1]%9:fail('Opposing tuzdyks cannot share a pit number',code='INVALID_STATE')
        elif all(d['agreement']) and any(d['pits']):fail('Agreed ending must collect the remaining seeds',code='INVALID_STATE')
        if max(d['scores'])<=self.total//2 and sum(d['scores'])<self.total and not self.pits(d):fail('An unplayable position must settle remaining seeds',code='INVALID_STATE')
    def apply(self,state,action):
        d=deepcopy(state['data']);p=int(d['turn']);params=action['params'];kind=action['type']
        if self.mode=='oware' and kind=='agree_end':
            fields(params,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params');t=int(params['player'])
            if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
            if d['agreement'][t]:fail('Player already agreed')
            d['agreement'][t]=True
            return self.collect(d) if all(d['agreement']) else d
        if kind!='sow':fail('Unknown action')
        schema=dict(pit=dict(type='integer',minimum=0,maximum=2*self.n-1))
        if self.mode=='toguz':schema['claim_tuzdyk']=dict(type='boolean')
        fields(params,schema,'/params');pit=int(params['pit'])
        if action.get('actor') is not None and action['actor']!=state['players'][p]['id']:fail('Wrong actor')
        if pit not in self.pits(d):fail('Pit is empty, belongs to the opponent or fails the feeding obligation')
        d,last=self.sow(d,pit)
        if self.mode=='oware':
            captured=[];i=last
            while i in self.own(1-p) and d['pits'][i] in (2,3):captured.append(i);i=(i-1)%(2*self.n)
            if sum(d['pits'][i] for i in captured)<sum(d['pits'][i] for i in self.own(1-p)):
                for i in captured:d['scores'][p]+=d['pits'][i];d['pits'][i]=0
            d['agreement']=[False,False]
        else:
            if params['claim_tuzdyk']:
                if not self.tuz_available(d,last):fail('This landing cannot create a tuzdyk')
                d['tuzdyk'][p]=last;d['scores'][p]+=3;d['pits'][last]=0
            elif last in self.own(1-p) and d['pits'][last]>0 and d['pits'][last]%2==0:d['scores'][p]+=d['pits'][last];d['pits'][last]=0
        d['turn']=1-p
        if max(d['scores'])<=self.total//2 and sum(d['scores'])<self.total and not self.pits(d):self.collect(d)
        return d
    def legal(self,state):
        d=state['data'];actions=[]
        for pit in self.pits(d):
            if self.mode=='oware':actions.append(dict(type='sow',params=dict(pit=pit)))
            else:
                after,last=self.sow(d,pit);actions.append(dict(type='sow',params=dict(pit=pit,claim_tuzdyk=False)))
                if self.tuz_available(after,last):actions.append(dict(type='sow',params=dict(pit=pit,claim_tuzdyk=True)))
        if self.mode=='oware':actions.extend(dict(type='agree_end',params=dict(player=p)) for p in (0,1) if not d['agreement'][p])
        return actions
    def outcome(self,state,pack):
        d=state['data'];terminal=max(d['scores'])>self.total//2 or sum(d['scores'])==self.total;tie=d['scores'][0]==d['scores'][1];w=0 if d['scores'][0]>d['scores'][1] else 1
        return dict(status='terminal' if terminal else 'ongoing',result_kind=('draw' if tie else 'win') if terminal else 'none',winners=[state['players'][w]['id']] if terminal and not tie else [],losers=[state['players'][1-w]['id']] if terminal and not tie else [],placements=[],reason='majority_or_seed_exhaustion' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
