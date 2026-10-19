"""Freestyle Gomoku and no-swap Hex: local board rules and connection outcomes."""
from copy import deepcopy
from ..values import fields,fail

class Connection:
    def __init__(self,config):self.size=config['size'];self.mode=config['mode']
    def winners(self,b):
        n=self.size
        if self.mode=='gomoku':
            wins=set()
            for r in range(n):
                for c in range(n):
                    p=b[r*n+c]
                    if p==-1:continue
                    for dr,dc in [(0,1),(1,0),(1,1),(1,-1)]:
                        if 0<=r+4*dr<n and 0<=c+4*dc<n and all(b[(r+k*dr)*n+c+k*dc]==p for k in range(1,5)):wins.add(p)
            return sorted(wins)
        wins=[]
        for p in (0,1):
            starts=[i for i in range(n*n) if b[i]==p and (i//n==0 if p==0 else i%n==0)]
            seen=set(starts);todo=list(starts)
            while todo:
                i=todo.pop();r,c=divmod(i,n)
                if (r==n-1 if p==0 else c==n-1):wins.append(p);break
                for dr,dc in [(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0)]:
                    rr,cc=r+dr,c+dc;j=rr*n+cc
                    if 0<=rr<n and 0<=cc<n and j not in seen and b[j]==p:seen.add(j);todo.append(j)
        return wins
    def validate(self,d):
        b=d['board'];a=b.count(0);c=b.count(1);wins=self.winners(b)
        if a not in (c,c+1) or d['turn']!=(0 if a==c else 1):fail('Invalid mark counts or turn',code='INVALID_STATE')
        if len(wins)>1:fail('Simultaneous winners',code='INVALID_STATE')
        if wins and a-c!=(1 if wins[0]==0 else 0):fail('Winner is not the last mover',code='INVALID_STATE')
    def legal(self,state):return [dict(type='place',params={'cell':i}) for i,p in enumerate(state['data']['board']) if p==-1]
    def apply(self,state,action):
        if action['type']!='place':fail('Unknown action')
        fields(action['params'],{'cell':{'type':'integer','minimum':0,'maximum':self.size**2-1}},'/params')
        d=deepcopy(state['data']);i=int(action['params']['cell']);p=int(d['turn'])
        if d['board'][i]!=-1:fail('Occupied square')
        if action.get('actor') is not None and action['actor']!=state['players'][p]['id']:fail('Wrong actor')
        d['board'][i]=p;d['turn']=1-p;return d
    def outcome(self,state,pack):
        b=state['data']['board'];wins=self.winners(b);terminal=bool(wins) or -1 not in b;w=int(wins[0]) if wins else None
        return dict(status='terminal' if terminal else 'ongoing',result_kind=('win' if w is not None else 'draw') if terminal else 'none',winners=[] if w is None else [state['players'][w]['id']],losers=[] if w is None else [state['players'][1-w]['id']],placements=[],reason=('five_in_a_row' if self.mode=='gomoku' else 'connected_edges') if w is not None else 'board_full' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
