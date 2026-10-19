"""Two-player Chinese checkers on the 121-hole star, without strategic search."""
from copy import deepcopy
from ..values import fields,fail
DIRECTIONS=[(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)]
BASE={(q,r) for r in range(-8,-4) for q in range(-r-4,5)}
ARMS=[];arm=BASE
for _ in range(6):ARMS.append(arm);arm={(-r,q+r) for q,r in arm}
COORDS=sorted({(q,r) for q in range(-4,5) for r in range(-4,5) if abs(q+r)<=4}|set().union(*ARMS))
INDEX={c:i for i,c in enumerate(COORDS)}
HOMES=[{INDEX[c] for c in ARMS[i]} for i in (0,3)]
def allowed_goal(start,end,p):return start not in HOMES[1-p] or end in HOMES[1-p]
def steps(d):
    p=int(d['turn']);occupied=set(d['pawns'][0]+d['pawns'][1]);result=[]
    for start in sorted(d['pawns'][p]):
        q,r=COORDS[int(start)]
        for dq,dr in DIRECTIONS:
            dest=INDEX.get((q+dq,r+dr))
            if dest is not None and dest not in occupied and allowed_goal(start,dest,p):result.append([start,dest])
        fixed=occupied-{start};seen={start};todo=[[start]]
        while todo:
            path=todo.pop(0);here=path[-1];q,r=COORDS[int(here)]
            for dq,dr in DIRECTIONS:
                middle=INDEX.get((q+dq,r+dr));dest=INDEX.get((q+2*dq,r+2*dr))
                if middle in fixed and dest is not None and dest not in fixed and dest not in seen and allowed_goal(here,dest,p):
                    seen.add(dest);new=path+[dest];result.append(new);todo.append(new)
    return sorted(result,key=lambda path:(path[0],path[-1],len(path),path))
def validate(d):
    if len(set(d['pawns'][0]+d['pawns'][1]))!=20:fail('Marbles overlap',code='INVALID_STATE')
    wins=[p for p in (0,1) if set(d['pawns'][p])==HOMES[1-p]]
    if len(wins)>1 or wins and wins[0]!=1-d['turn']:fail('Winner is not the last mover',code='INVALID_STATE')
def apply(state,action):
    if action['type']!='move':fail('Unknown action')
    fields(action['params'],dict(path=dict(type='array',minItems=2,maxItems=121,items=dict(type='integer',minimum=0,maximum=120))),'/params')
    d=deepcopy(state['data']);p=int(d['turn']);path=[int(i) for i in action['params']['path']]
    if action.get('actor') is not None and action['actor']!=state['players'][p]['id']:fail('Wrong actor')
    if path[0] not in d['pawns'][p] or len(set(path))!=len(path):fail('Path must start at an owned marble and not repeat holes')
    fixed=set(d['pawns'][0]+d['pawns'][1])-{path[0]}
    for k,(a,b) in enumerate(zip(path,path[1:])):
        q,r=COORDS[a];qq,rr=COORDS[b];delta=(qq-q,rr-r)
        adjacent=delta in DIRECTIONS
        jump=delta in [(2*x,2*y) for x,y in DIRECTIONS] and INDEX.get(((q+qq)//2,(r+rr)//2)) in fixed
        if b in fixed or not allowed_goal(a,b,p) or not (adjacent and len(path)==2 or jump):fail('Path violates step, jump or target-camp rules')
    d['pawns'][p].remove(path[0]);d['pawns'][p].append(path[-1]);d['pawns'][p].sort();d['turn']=1-p;return d
def legal(state):
    return dict(mode='event_types',actions=[dict(type='move',params=dict(path=path)) for path in steps(state['data'])],action_types=[dict(type='move',params_schema=dict(path=dict(type='array',minItems=2,maxItems=121,items=dict(type='integer',minimum=0,maximum=120))),preconditions=['A single adjacent step or a nonrepeating sequence of occupied-hole jumps; target-camp marbles remain inside the camp.'],external_observations=[])],constraints={},completeness=False,reason='representative_routes_for_reachable_destinations')
def outcome(state,pack):
    d=state['data'];wins=[p for p in (0,1) if set(d['pawns'][p])==HOMES[1-p]];w=wins[0] if wins else None
    return dict(status='terminal' if wins else 'ongoing',result_kind='win' if wins else 'none',winners=[state['players'][w]['id']] if wins else [],losers=[state['players'][1-w]['id']] if wins else [],placements=[],reason='opposite_camp_filled' if wins else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if wins else None)
