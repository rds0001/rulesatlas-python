"""Monochrome nonograms: supplied clues and editable marks, without a solver."""
from copy import deepcopy
from ..values import fields, fail
CLUES = dict(type='array', minItems=1, maxItems=25, items=dict(type='array', minItems=0, maxItems=13, items=dict(type='integer', minimum=1, maximum=25)))
def runs(line):
    result=[]; n=0
    for v in list(line)+[0]:
        if v==1:n+=1
        elif n:result.append(n);n=0
    return result

def validate(d):
    if not d['configured']:
        if d['rows'] or d['columns'] or d['board']:fail('Unconfigured puzzle contains data',code='INVALID_STATE')
        return
    rows=d['rows'];cols=d['columns']
    if not rows or not cols or len(d['board'])!=len(rows)*len(cols):fail('Puzzle dimensions mismatch',code='INVALID_STATE')
    for clues,size in ((rows,len(cols)),(cols,len(rows))):
        if any(sum(c)+max(0,len(c)-1)>size for c in clues):fail('Clues do not fit the line',code='INVALID_STATE')
    if sum(map(sum,rows))!=sum(map(sum,cols)):fail('Row and column fill totals differ',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params']
    if not d['configured']:
        if action['type']!='set_puzzle':fail('Supply the puzzle first')
        fields(p,dict(rows=CLUES,columns=CLUES),'/params')
        d.update(configured=True,rows=deepcopy(p['rows']),columns=deepcopy(p['columns']),board=[-1]*(len(p['rows'])*len(p['columns'])))
        return d
    if action['type']!='write':fail('Unknown action')
    fields(p,dict(cell=dict(type='integer',minimum=0,maximum=len(d['board'])-1),value=dict(type='integer',minimum=-1,maximum=1)),'/params')
    i=int(p['cell'])
    if d['board'][i]==p['value']:fail('Cell already contains this value')
    d['board'][i]=p['value'];return d

def legal(state):
    d=state['data']
    if not d['configured']:return dict(mode='event_types',actions=[],action_types=[dict(type='set_puzzle',params_schema=dict(rows=CLUES,columns=CLUES),preconditions=['Clues fit each line and row and column fill totals agree.'],external_observations=['Supplied monochrome puzzle clues; an empty list denotes an empty line.'])],constraints={},completeness=False,reason='external_puzzle_required')
    return [dict(type='write',params=dict(cell=i,value=v)) for i,x in enumerate(d['board']) for v in (-1,0,1) if x!=v]
def outcome(state,pack):
    d=state['data'];w=len(d['columns']);solved=d['configured'] and -1 not in d['board']
    if solved:solved=all(runs(d['board'][r*w:(r+1)*w])==c for r,c in enumerate(d['rows'])) and all(runs(d['board'][c::w])==clue for c,clue in enumerate(d['columns']))
    return dict(status='terminal' if solved else 'ongoing',result_kind='win' if solved else 'none',winners=[state['players'][0]['id']] if solved else [],losers=[],placements=[],reason='puzzle_completed' if solved else 'ongoing' if d['configured'] else 'awaiting_puzzle',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if solved else None)
