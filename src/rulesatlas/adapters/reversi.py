"""Standard 8-by-8 disc capture with mandatory passes."""
from ..values import fail,fields
DIRECTIONS=[(dr,dc) for dr in (-1,0,1) for dc in (-1,0,1) if (dr,dc)!=(0,0)]

def flips(board,cell,player):
    if board[cell]!=-1: return []
    row,col=divmod(cell,8);result=[]
    for dr,dc in DIRECTIONS:
        r,c=row+dr,col+dc;run=[]
        while 0<=r<8 and 0<=c<8 and board[r*8+c]==1-player:
            run.append(r*8+c);r+=dr;c+=dc
        if run and 0<=r<8 and 0<=c<8 and board[r*8+c]==player: result.extend(run)
    return result

def moves(board,player): return [i for i in range(64) if board[i]==-1 and flips(board,i,player)]

def validate(data):
    board=data['board']
    if any(board[i]==-1 for i in (27,28,35,36)): fail('Starting center discs cannot be empty',code='INVALID_STATE')

def outcome(state,pack):
    board=state['data']['board'];terminal=not moves(board,0) and not moves(board,1)
    counts=[board.count(0),board.count(1)];winner=None if not terminal or counts[0]==counts[1] else (0 if counts[0]>counts[1] else 1)
    return dict(status='terminal' if terminal else 'ongoing',result_kind='none' if not terminal else 'draw' if winner is None else 'win',winners=[] if winner is None else [state['players'][winner]['id']],losers=[] if winner is None else [state['players'][1-winner]['id']],placements=[],reason='no_legal_moves' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)

def apply(state,action):
    board=list(state['data']['board']);turn=int(state['data']['turn'])
    if action.get('actor') is not None and action['actor']!=state['players'][turn]['id']: fail('Wrong actor')
    if action['type']=='pass':
        fields(action['params'],{},'/params')
        if moves(board,turn) or not moves(board,1-turn): fail('Pass is not forced')
    elif action['type']=='place':
        fields(action['params'],{'cell':{'type':'integer','minimum':0,'maximum':63}},'/params')
        cell=int(action['params']['cell']);captured=flips(board,cell,turn)
        if not captured: fail('Move captures no discs')
        for i in [cell]+captured: board[i]=turn
    else: fail('Unknown action')
    return dict(board=board,turn=1-turn)

def legal(state):
    cells=moves(state['data']['board'],int(state['data']['turn']))
    return [dict(type='place',params={'cell':c}) for c in cells] if cells else [dict(type='pass',params={})]
