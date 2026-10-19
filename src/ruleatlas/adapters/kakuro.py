"""Kakuro sums and distinct digits, with local bounds and no search."""
from copy import deepcopy
from ..values import fields,fail
RUN=dict(type='object',properties=dict(cells=dict(type='array',minItems=2,maxItems=9,items=dict(type='integer',minimum=0,maximum=624)),total=dict(type='integer',minimum=3,maximum=45)),required=['cells','total'])
RUNS=dict(type='array',minItems=2,maxItems=625,items=RUN)
def consistent(values,total):
    used=[v for v in values if v>0]
    if len(used)!=len(set(used)):return False
    missing=len(values)-len(used);available=[v for v in range(1,10) if v not in used]
    return sum(used)+sum(available[:missing])<=total<=sum(used)+(sum(available[-missing:]) if missing else 0)
def validate(d):
    if not d['configured']:
        if d['width'] or d['height'] or d['runs'] or d['board']:fail('Unconfigured puzzle contains data',code='INVALID_STATE')
        return
    w=int(d['width']);h=int(d['height']);b=d['board']
    if w<1 or h<1 or len(b)!=w*h:fail('Puzzle dimensions mismatch',code='INVALID_STATE')
    counts=[[0,0] for _ in b]
    for r in d['runs']:
        cells=[int(i) for i in r['cells']]
        if any(i>=len(b) for i in cells):fail('Run cell outside board',code='INVALID_STATE')
        horizontal=all(i==cells[0]+k and i//w==cells[0]//w for k,i in enumerate(cells))
        vertical=all(i==cells[0]+k*w for k,i in enumerate(cells))
        if not horizontal and not vertical:fail('Run must be contiguous and ordered',code='INVALID_STATE')
        step=1 if horizontal else w
        neighbors=[i for i in (cells[0]-step,cells[-1]+step) if 0<=i<len(b) and (not horizontal or i//w==cells[0]//w)]
        if any(b[i]>=0 for i in neighbors):fail('Runs must span the entire white segment',code='INVALID_STATE')
        for i in cells:counts[i][0 if horizontal else 1]+=1
        if any(b[i]<0 for i in cells) or not consistent([b[i] for i in cells],r['total']):fail('Run digits violate the clue',code='INVALID_STATE')
    if not d['runs'] or any(c!=([0,0] if v==-1 else [1,1]) for c,v in zip(counts,b)):fail('Each white cell needs one horizontal and one vertical run',code='INVALID_STATE')
def options(d,i):
    result=[]
    for v in range(10):
        if v==d['board'][i]:continue
        if all(consistent([v if int(j)==i else d['board'][int(j)] for j in r['cells']],r['total']) for r in d['runs'] if i in r['cells']):result.append(v)
    return result
def apply(state,action):
    d=deepcopy(state['data']);p=action['params']
    if not d['configured']:
        if action['type']!='set_puzzle':fail('Supply the puzzle first')
        fields(p,dict(width=dict(type='integer',minimum=1,maximum=25),height=dict(type='integer',minimum=1,maximum=25),runs=RUNS),'/params')
        b=[-1]*int(p['width']*p['height'])
        for r in p['runs']:
            for i in r['cells']:
                if i>=len(b):fail('Run cell outside board')
                b[int(i)]=0
        d.update(configured=True,width=p['width'],height=p['height'],runs=deepcopy(p['runs']),board=b);return d
    if action['type']!='write':fail('Unknown action')
    fields(p,dict(cell=dict(type='integer',minimum=0,maximum=len(d['board'])-1),value=dict(type='integer',minimum=0,maximum=9)),'/params');i=int(p['cell'])
    if d['board'][i]<0:fail('Black cells cannot be edited')
    if p['value'] not in options(d,i):fail('Digit is unchanged or violates a run')
    d['board'][i]=p['value'];return d
def legal(state):
    d=state['data']
    if not d['configured']:return dict(mode='event_types',actions=[],action_types=[dict(type='set_puzzle',params_schema=dict(width=dict(type='integer',minimum=1,maximum=25),height=dict(type='integer',minimum=1,maximum=25),runs=RUNS),preconditions=['Every white cell belongs to one horizontal and one vertical run; clues have feasible distinct-digit sums.'],external_observations=['Supplied Kakuro runs and sums; other cells are black.'])],constraints={},completeness=False,reason='external_puzzle_required')
    return [dict(type='write',params=dict(cell=i,value=v)) for i,x in enumerate(d['board']) if x>=0 for v in options(d,i)]
def outcome(state,pack):
    d=state['data'];solved=d['configured'] and 0 not in d['board']
    return dict(status='terminal' if solved else 'ongoing',result_kind='win' if solved else 'none',winners=[state['players'][0]['id']] if solved else [],losers=[],placements=[],reason='puzzle_completed' if solved else 'ongoing' if d['configured'] else 'awaiting_puzzle',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if solved else None)
