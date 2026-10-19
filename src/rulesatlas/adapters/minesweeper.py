"""Fixed-layout 9-by-9 Minesweeper with ten mines, flags and chording."""
from copy import deepcopy
from ..values import fields,fail
CELL={'type':'integer','minimum':0,'maximum':80}
MINES={'type':'array','items':CELL,'minItems':10,'maxItems':10}
def neighbors(i):
    r,c=divmod(i,9)
    return [(r+dr)*9+c+dc for dr in (-1,0,1) for dc in (-1,0,1) if (dr or dc) and 0<=r+dr<9 and 0<=c+dc<9]
def count(d,i):return sum(j in d['mines'] for j in neighbors(i))
def validate(d):
    if any(a and b for a,b in zip(d['revealed'],d['flags'])):fail('A revealed cell cannot be flagged',code='INVALID_STATE')
    if d['mines'] is None:
        if any(d['revealed']) or any(d['flags']) or d['exploded'] is not None:fail('Layout is not configured',code='INVALID_STATE')
        return
    if len(set(d['mines']))!=10:fail('Mine positions must be distinct',code='INVALID_STATE')
    hit=[int(i) for i in d['mines'] if d['revealed'][int(i)]]
    if hit!=([] if d['exploded'] is None else [d['exploded']]):fail('Explosion state mismatch',code='INVALID_STATE')
def reveal(d,i):
    if i in d['mines']:d['revealed'][i]=True;d['exploded']=i;return
    todo=[i]
    while todo:
        j=todo.pop()
        if d['revealed'][j] or d['flags'][j]:continue
        d['revealed'][j]=True
        if count(d,j)==0:todo.extend(k for k in neighbors(j) if not d['revealed'][k] and not d['flags'][k])
def apply(state,action):
    d=deepcopy(state['data']);p=action['params']
    if d['mines'] is None:
        if action['type']!='set_mines':fail('Supply the mine layout first')
        fields(p,{'mines':MINES},'/params');d['mines']=sorted(int(i) for i in p['mines']);return d
    if action['type'] not in ('reveal','toggle_flag','chord'):fail('Unknown action')
    fields(p,{'cell':CELL},'/params');i=int(p['cell'])
    if action['type']=='toggle_flag':
        if d['revealed'][i]:fail('Revealed cells cannot be flagged')
        d['flags'][i]=not d['flags'][i]
    elif action['type']=='reveal':
        if d['revealed'][i] or d['flags'][i]:fail('Cell cannot be revealed')
        reveal(d,i)
    else:
        around=neighbors(i)
        if not d['revealed'][i] or count(d,i)==0 or sum(d['flags'][j] for j in around)!=count(d,i):fail('Chording requires a revealed number and matching flag count')
        targets=[j for j in around if not d['revealed'][j] and not d['flags'][j]]
        if not targets:fail('No hidden neighbors to chord')
        for j in targets:
            reveal(d,j)
            if d['exploded'] is not None:break
    return d
def legal(state):
    d=state['data']
    if d['mines'] is None:return dict(mode='event_types',actions=[],action_types=[dict(type='set_mines',params_schema={'mines':MINES},preconditions=['Ten distinct mine positions on the 9-by-9 board.'],external_observations=['A fixed externally supplied layout.'])],constraints={},completeness=False,reason='external_layout_required')
    result=[]
    for i in range(81):
        if not d['revealed'][i]:
            if not d['flags'][i]:result.append(dict(type='reveal',params={'cell':i}))
            result.append(dict(type='toggle_flag',params={'cell':i}))
        else:
            around=neighbors(i)
            if count(d,i)>0 and sum(d['flags'][j] for j in around)==count(d,i) and any(not d['revealed'][j] and not d['flags'][j] for j in around):result.append(dict(type='chord',params={'cell':i}))
    return result
def outcome(state,pack):
    d=state['data'];lost=d['exploded'] is not None;won=d['mines'] is not None and not lost and all(d['revealed'][i] or i in d['mines'] for i in range(81));terminal=lost or won
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if won else 'other' if lost else 'none',winners=[state['players'][0]['id']] if won else [],losers=[state['players'][0]['id']] if lost else [],placements=[],reason='mine_revealed' if lost else 'all_safe_cells_revealed' if won else 'awaiting_layout' if d['mines'] is None else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
