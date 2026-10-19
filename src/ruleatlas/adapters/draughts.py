"""English draughts: compulsory short captures, crowning and bounded draw counters."""
from copy import deepcopy
from ..values import fields,fail

def rc(i):return i//4,2*(i%4)+(1 if (i//4)%2==0 else 0)
def index(r,c):return r*4+c//2 if 0<=r<8 and 0<=c<8 and (r+c)%2==1 else None
def owner(v):return v%2 if v>=0 else -1
def moves(d,capture):
    b=d['board'];t=d['turn'];result=[]
    for i,v in enumerate(b):
        if owner(v)!=t or d['pending'] is not None and i!=d['pending']:continue
        r,c=rc(i)
        for dr in ((-1,1) if v>=2 else ((1,) if t==0 else (-1,))):
            for dc in (-1,1):
                j=index(r+dr,c+dc)
                if j is None:continue
                if capture:
                    k=index(r+2*dr,c+2*dc)
                    if owner(b[j])==1-t and k is not None and b[k]==-1:result.append((i,k,j))
                elif b[j]==-1:result.append((i,j,None))
    return result
def options(d):return moves(d,True) or ([] if d['pending'] is not None else moves(d,False))
def key(d):return ''.join(str(int(v)+1) for v in d['board'])+str(int(d['turn']))
def validate(d):
    b=d['board']
    if any(sum(owner(v)==p for v in b)>12 for p in (0,1)) or any(v==0 and i//4==7 or v==1 and i//4==0 for i,v in enumerate(b)):fail('Invalid piece counts or uncrowned back-rank man',code='INVALID_STATE')
    if d['pending'] is not None:
        if not moves(d,True) or d['quiet']!=0 or d['history']:fail('Pending multi-capture must have another jump and reset draw history',code='INVALID_STATE')
    else:
        if len(d['history'])!=d['quiet']+1 or not d['history'] or d['history'][-1]!=key(d):fail('Draw history and quiet counter mismatch',code='INVALID_STATE')
        if any(len(k)!=33 or set(k[:32])-set('01234') or k[-1] not in '01' for k in d['history']):fail('Malformed repetition key',code='INVALID_STATE')
def apply(state,action):
    if action['type']!='move':fail('Unknown action')
    p=action['params'];fields(p,dict(start=dict(type='integer',minimum=0,maximum=31),end=dict(type='integer',minimum=0,maximum=31)),'/params');d=deepcopy(state['data']);t=int(d['turn'])
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    match=next((m for m in options(d) if m[:2]==(p['start'],p['end'])),None)
    if match is None:fail('Illegal move: capture is compulsory and a capture sequence must continue with the same piece')
    i,j,captured=match;piece=d['board'][i];d['board'][i]=-1;d['board'][j]=piece
    crown=piece<2 and j//4==(7 if t==0 else 0)
    if crown:d['board'][j]+=2
    if captured is not None:
        d['board'][captured]=-1;d['pending']=j;d['quiet']=0;d['history']=[]
        if not crown and moves(d,True):return d
    d['pending']=None;d['turn']=1-t
    if captured is not None or piece<2:d['quiet']=0;d['history']=[key(d)]
    else:d['quiet']+=1;d['history'].append(key(d))
    return d

def legal(state):return [dict(type='move',params=dict(start=i,end=j)) for i,j,_ in options(state['data'])]
def outcome(state,pack):
    d=state['data'];blocked=d['pending'] is None and not options(d);draw=d['pending'] is None and not blocked and (d['quiet']>=80 or d['history'].count(key(d))>=3);terminal=blocked or draw;win=1-int(d['turn'])
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if blocked else 'draw' if draw else 'none',winners=[state['players'][win]['id']] if blocked else [],losers=[state['players'][int(d['turn'])]['id']] if blocked else [],placements=[],reason='no_legal_move' if blocked else 'quiet_or_threefold_draw' if draw else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
