"""Standard three-by-three placement with complete finite legality."""
from ..values import fail,fields
LINES=((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6))

def winners(board):
    return {board[a] for a,b,c in LINES if board[a]!=-1 and board[a]==board[b]==board[c]}


def validate(data):
    board=data['board']; n0=board.count(0); n1=board.count(1); win=winners(board)
    if n0 not in (n1,n1+1) or data['turn']!=(0 if n0==n1 else 1): fail('Invalid mark counts or turn',code='INVALID_STATE')
    if len(win)>1: fail('Simultaneous winners',code='INVALID_STATE')
    if win:
        w=next(iter(win))
        if n0-n1!=(1 if w==0 else 0): fail('Moves continued after a win',code='INVALID_STATE')
        if not any(not winners(board[:i]+[-1]+board[i+1:]) for i,v in enumerate(board) if v==w): fail('No legal last winning move',code='INVALID_STATE')


def outcome(state,pack):
    win=winners(state['data']['board']); full=-1 not in state['data']['board']
    ids=[p['id'] for p in state['players']]
    ws=[ids[next(iter(win))]] if win else []
    return dict(status='terminal' if win or full else 'ongoing',result_kind='win' if win else 'draw' if full else 'none',winners=ws,losers=[p for p in ids if p not in ws] if win else [],placements=[],reason='three_in_a_row' if win else 'board_full' if full else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if win or full else None)


def apply(state,action):
    if action['type']!='place': fail('Unknown action')
    fields(action['params'],{'cell':{'type':'integer','minimum':0,'maximum':8}},'/params')
    cell=int(action['params']['cell']); data=state['data']
    if data['board'][cell]!=-1: fail('Occupied square')
    if action.get('actor') is not None and action['actor']!=state['players'][int(data['turn'])]['id']: fail('Wrong actor')
    board=list(data['board']); board[cell]=data['turn']
    return dict(board=board,turn=1-data['turn'])


def legal(state):
    return [dict(type='place',params={'cell':i}) for i,v in enumerate(state['data']['board']) if v==-1]
