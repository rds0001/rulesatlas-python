"""Standard 9-by-9 Sudoku rule checks; no solving or puzzle generation."""
from copy import deepcopy
from ..values import fields,fail
BOARD={'type':'array','items':{'type':'integer','minimum':0,'maximum':9},'minItems':81,'maxItems':81}
GROUPS=([[r*9+c for c in range(9)] for r in range(9)]+[[r*9+c for r in range(9)] for c in range(9)]+[[(r+dr)*9+c+dc for dr in range(3) for dc in range(3)] for r in (0,3,6) for c in (0,3,6)])
def consistent(board):return all(len([board[i] for i in group if board[i]])==len({board[i] for i in group if board[i]}) for group in GROUPS)
def validate(d):
    if not consistent(d['board']) or not consistent(d['givens']):fail('Repeated digit in a row, column or box',code='INVALID_STATE')
    if any(g and g!=d['board'][i] for i,g in enumerate(d['givens'])):fail('A given was changed',code='INVALID_STATE')
    if not d['configured'] and (any(d['board']) or any(d['givens'])):fail('Puzzle is not configured',code='INVALID_STATE')
def candidates(board,cell):
    used={board[i] for group in GROUPS if cell in group for i in group if i!=cell}
    return [v for v in range(1,10) if v not in used]
def apply(state,action):
    d=deepcopy(state['data']);p=action['params']
    if not d['configured']:
        if action['type']!='set_puzzle':fail('Supply the puzzle first')
        fields(p,{'givens':BOARD},'/params');d['givens']=deepcopy(p['givens']);d['board']=deepcopy(p['givens']);d['configured']=True;return d
    if action['type']!='write':fail('Unknown action')
    fields(p,{'cell':{'type':'integer','minimum':0,'maximum':80},'value':{'type':'integer','minimum':0,'maximum':9}},'/params');i=int(p['cell']);v=int(p['value'])
    if d['givens'][i]:fail('A given cannot be changed')
    if v and v not in candidates(d['board'],i):fail('Digit conflicts with row, column or box')
    if d['board'][i]==v:fail('Cell already contains this value')
    d['board'][i]=v;return d
def legal(state):
    d=state['data']
    if not d['configured']:return dict(mode='event_types',actions=[],action_types=[dict(type='set_puzzle',params_schema={'givens':BOARD},preconditions=['Given digits must obey row, column and box constraints.'],external_observations=['A supplied puzzle; zero denotes an empty cell.'])],constraints={},completeness=False,reason='external_puzzle_required')
    result=[]
    for i in range(81):
        if d['givens'][i]:continue
        values=([0] if d['board'][i] else [])+candidates(d['board'],i)
        result.extend(dict(type='write',params={'cell':i,'value':v}) for v in values if v!=d['board'][i])
    return result
def outcome(state,pack):
    solved=state['data']['configured'] and 0 not in state['data']['board']
    return dict(status='terminal' if solved else 'ongoing',result_kind='win' if solved else 'none',winners=[state['players'][0]['id']] if solved else [],losers=[],placements=[],reason='puzzle_completed' if solved else 'ongoing' if state['data']['configured'] else 'awaiting_puzzle',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if solved else None)
