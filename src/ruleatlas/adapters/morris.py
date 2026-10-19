"""Nine Men's Morris: placement, mills, protected captures, flying and draws."""
from copy import deepcopy
import re
from ..values import fields,fail
MILLS=[[o+i for i in line] for o in (0,8,16) for line in ((0,1,2),(2,3,4),(4,5,6),(6,7,0))]+[[i,i+8,i+16] for i in (1,3,5,7)]
ADJ={i:{i//8*8+(i+1)%8,i//8*8+(i-1)%8} for i in range(24)}
for i in (1,3,5,7):
    ADJ[i].add(i+8);ADJ[i+8].update((i,i+16));ADJ[i+16].add(i+8)
def key(d):return ''.join(str(int(v)) if v>=0 else '2' for v in d['board'])+'|'+str(int(d['turn']))+'|'+str(int(d['placed'][0]))+'|'+str(int(d['placed'][1]))
def in_mill(board,i):return any(i in line and all(board[j]==board[i] for j in line) for line in MILLS)
def captures(d):
    opponent=[i for i,v in enumerate(d['board']) if v==1-d['turn']];unprotected=[i for i in opponent if not in_mill(d['board'],i)]
    return unprotected or opponent
def ordinary(d):
    b=d['board'];p=int(d['turn']);empty=[i for i,v in enumerate(b) if v==-1]
    if sum(d['placed'])<18:return [dict(type='place',params=dict(cell=i)) for i in empty]
    return [dict(type='move',params=dict(source=i,target=j)) for i,v in enumerate(b) if v==p for j in empty if b.count(p)==3 or j in ADJ[i]]
def result(d):
    if d['pending']:return None,None
    for p in (0,1):
        if d['board'].count(p)+9-d['placed'][p]<3:return 1-p,'fewer_than_three_stones'
    if sum(d['placed'])==18 and not ordinary(d):return 1-int(d['turn']),'no_legal_move'
    if d['history'].count(key(d))>=3:return -1,'threefold_repetition'
    if d['quiet_turns']>=100:return -1,'fifty_moves_each_without_capture'
    return None,None
def validate(d):
    b=d['board'];p=int(d['turn']);a,c=d['placed']
    if any(b.count(t)>d['placed'][t] for t in (0,1)):fail('Board contains unplaced stones',code='INVALID_STATE')
    if a not in (c,c+1):fail('Invalid placement counts',code='INVALID_STATE')
    if a+c<18 and p!=((1 if a==c else 0) if d['pending'] else (0 if a==c else 1)):fail('Placement turn mismatch',code='INVALID_STATE')
    if d['pending'] and (not any(v==p and in_mill(b,i) for i,v in enumerate(b)) or not captures(d)):fail('Capture requires a mill and an opposing stone',code='INVALID_STATE')
    if any(not re.fullmatch(r'[012]{24}\|[01]\|[0-9]\|[0-9]', item) for item in d['history']):fail('Malformed repetition position',code='INVALID_STATE')
    if not d['history'] or len(d['history'])!=d['quiet_turns']+1:fail('Repetition history and quiet count mismatch',code='INVALID_STATE')
    if not d['pending'] and d['history'][-1]!=key(d):fail('History does not end at the current position',code='INVALID_STATE')
    if a+c<18 and d['quiet_turns']!=0:fail('Placement resets the quiet counter',code='INVALID_STATE')
    wins=[t for t in (0,1) if b.count(t)+9-d['placed'][t]<3]
    if len(wins)>1 or wins and (d['pending'] or wins[0]!=p):fail('Impossible material result',code='INVALID_STATE')
def finish(d,reset):
    d['turn']=1-d['turn'];d['pending']=False
    if reset:d['quiet_turns']=0;d['history']=[key(d)]
    else:d['quiet_turns']+=1;d['history'].append(key(d))
    return d
def apply(state,action):
    d=deepcopy(state['data']);p=int(d['turn']);params=action['params'];kind=action['type']
    if action.get('actor') is not None and action['actor']!=state['players'][p]['id']:fail('Wrong actor')
    if d['pending']:
        if kind!='capture':fail('Capture an opposing stone first')
        fields(params,dict(cell=dict(type='integer',minimum=0,maximum=23)),'/params');i=int(params['cell'])
        if i not in captures(d):fail('Stone cannot be captured while an unprotected stone exists')
        d['board'][i]=-1;return finish(d,True)
    placing=sum(d['placed'])<18
    expected='place' if placing else 'move'
    if kind!=expected:fail('Action is not permitted in this phase')
    fields(params,{k:dict(type='integer',minimum=0,maximum=23) for k in (['cell'] if placing else ['source','target'])},'/params')
    if dict(type=kind,params=params) not in ordinary(d):fail('Illegal placement or movement')
    i=int(params['cell'] if placing else params['target'])
    if placing:d['placed'][p]+=1
    else:d['board'][int(params['source'])]=-1
    d['board'][i]=p
    if in_mill(d['board'],i):d['pending']=True;return d
    return finish(d,placing)
def legal(state):
    d=state['data']
    return [dict(type='capture',params=dict(cell=i)) for i in captures(d)] if d['pending'] else ordinary(d)
def outcome(state,pack):
    w,reason=result(state['data']);terminal=w is not None
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('draw' if w==-1 else 'win') if terminal else 'none',winners=[state['players'][w]['id']] if terminal and w>=0 else [],losers=[state['players'][1-w]['id']] if terminal and w>=0 else [],placements=[],reason=reason or 'awaiting_capture' if state['data']['pending'] else reason or 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
