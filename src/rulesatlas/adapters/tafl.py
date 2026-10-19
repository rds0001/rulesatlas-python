"""Seven-by-seven Brandubh-style tafl, weak king except at or beside the throne."""
from copy import deepcopy
from ..values import fields,fail
CORNERS={0,6,42,48};THRONE=24
DIRECTIONS=((1,0),(-1,0),(0,1),(0,-1))
def neighbor(i,dx,dy):
    x=int(i)%7+dx;y=int(i)//7+dy
    return y*7+x if 0<=x<7 and 0<=y<7 else None

def team(piece):return 0 if piece==1 else 1 if piece in (2,3) else None
def moves(d):
    b=d['board'];t=int(d['turn']);out=[]
    for i,p in enumerate(b):
        if team(p)!=t:continue
        for dx,dy in DIRECTIONS:
            j=neighbor(i,dx,dy)
            while j is not None and b[j]==0:
                if p==3 or j not in CORNERS|{THRONE}:out.append((i,j))
                j=neighbor(j,dx,dy)
    return out

def key(d):return ''.join(str(int(c)) for c in d['board'])+str(int(d['turn']))
def royal_captured(b,k,dest):
    adjacent=[neighbor(k,dx,dy) for dx,dy in DIRECTIONS]
    if dest not in adjacent:return False
    if k==THRONE:return all(j is not None and b[j]==1 for j in adjacent)
    if THRONE in adjacent:return all(j==THRONE or (j is not None and b[j]==1) for j in adjacent)
    for dx,dy in ((1,0),(0,1)):
        a=neighbor(k,dx,dy);c=neighbor(k,-dx,-dy)
        if dest in (a,c) and a is not None and c is not None and (b[a]==1 or a in CORNERS) and (b[c]==1 or c in CORNERS):return True
    return False

def result(d):
    b=d['board']
    if 3 not in b:return 0,'king_captured'
    if b.index(3) in CORNERS:return 1,'king_escaped'
    if not moves(d):return 1-int(d['turn']),'no_legal_move'
    if d['history'].count(key(d))>=3:return None,'threefold_repetition'
    return None,None

def validate(d):
    b=d['board']
    if b.count(1)>8 or b.count(2)>4 or b.count(3)>1:fail('Piece counts exceed the starting armies',code='INVALID_STATE')
    if any(b[i] in (1,2) for i in CORNERS|{THRONE}):fail('Only the king may occupy corners or throne',code='INVALID_STATE')
    if not d['history'] or d['history'][-1]!=key(d):fail('History must end at the current board and turn',code='INVALID_STATE')
    if any(len(h)!=50 or any(c not in '0123' for c in h[:49]) or h[-1] not in '01' for h in d['history']):fail('Invalid position history encoding',code='INVALID_STATE')
    if b.count(3)==0 and d['turn']!=1:fail('A king capture must follow an attacker move',code='INVALID_STATE')
    if b.count(3)==1 and b.index(3) in CORNERS and d['turn']!=0:fail('A king escape must follow a defender move',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];t=int(d['turn'])
    if action['type']!='move':fail('Unknown action')
    fields(p,dict(source=dict(type='integer',minimum=0,maximum=48),destination=dict(type='integer',minimum=0,maximum=48)),'/params');i=int(p['source']);j=int(p['destination'])
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if (i,j) not in moves(d):fail('Move an owned piece orthogonally through empty squares; only the king may stop on a restricted square')
    b=d['board'];b[j]=b[i];b[i]=0;captured=[]
    for dx,dy in DIRECTIONS:
        q=neighbor(j,dx,dy)
        if q is None or b[q] not in (1,2) or team(b[q])==t:continue
        behind=neighbor(q,dx,dy)
        if behind is not None and (team(b[behind])==t or (b[behind]==0 and behind in CORNERS|{THRONE})):captured.append(q)
    for q in captured:b[q]=0
    if t==0 and 3 in b and royal_captured(b,b.index(3),j):captured.append(b.index(3));b[b.index(3)]=0
    d['turn']=1-t
    if captured:d['history']=[]
    d['history'].append(key(d));return d

def legal(state):return [dict(type='move',params=dict(source=i,destination=j)) for i,j in moves(state['data'])]
def outcome(state,pack):
    w,reason=result(state['data']);done=reason is not None
    return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason=reason if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
