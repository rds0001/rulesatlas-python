"""Standard shogi moves and drops, fourfold repetition and agreed 24-point impasse."""
from copy import deepcopy
from functools import lru_cache
from ..values import fields,fail
# Types: king, gold, silver, knight, lance, bishop, rook, pawn; promotion adds eight.
TOTAL={1:2,2:4,3:4,4:4,5:4,6:2,7:2,8:18}
def base(c):return abs(int(c))-8 if abs(c)>8 else abs(int(c))
def side(c):return 0 if c>0 else 1 if c<0 else None
def zone(p,row):return row>=6 if p==0 else row<=2
def inside(x,y):return 0<=x<9 and 0<=y<9
def targets(b,i):
    c=int(b[i]);p=side(c);k=abs(c);x=i%9;y=i//9;f=1 if p==0 else -1;out=[];steps=[];rays=[]
    if k==1:steps=[(a,b) for a in (-1,0,1) for b in (-1,0,1) if a or b]
    elif k in (2,11,12,13,16):steps=[(-1,f),(0,f),(1,f),(-1,0),(1,0),(0,-f)]
    elif k==3:steps=[(-1,f),(0,f),(1,f),(-1,-f),(1,-f)]
    elif k==4:steps=[(-1,2*f),(1,2*f)]
    elif k==5:rays=[(0,f)]
    elif k in (6,14):
        rays=[(-1,-1),(-1,1),(1,-1),(1,1)]
        if k==14:steps=[(-1,0),(1,0),(0,-1),(0,1)]
    elif k in (7,15):
        rays=[(-1,0),(1,0),(0,-1),(0,1)]
        if k==15:steps=[(-1,-1),(-1,1),(1,-1),(1,1)]
    elif k==8:steps=[(0,f)]
    for dx,dy in steps:
        a=x+dx;c=y+dy
        if inside(a,c) and side(b[c*9+a])!=p:out.append(c*9+a)
    for dx,dy in rays:
        a=x+dx;c=y+dy
        while inside(a,c):
            j=c*9+a
            if side(b[j])!=p:out.append(j)
            if b[j]:break
            a+=dx;c+=dy
    return out

def check(b,p):
    king=1 if p==0 else -1
    if king not in b:return True
    k=b.index(king)
    return any(k in targets(b,i) for i,c in enumerate(b) if c and side(c)!=p)
def dead_rank(p,k,y):return (k in (5,8) and y==(8 if p==0 else 0)) or (k==4 and (y>=7 if p==0 else y<=1))
def board_moves(b,p):
    out=[]
    for i,c in enumerate(b):
        if not c or side(c)!=p:continue
        k=abs(int(c))
        for j in targets(b,i):
            if abs(b[j])==1:continue
            eligible=k in (3,4,5,6,7,8) and (zone(p,i//9) or zone(p,j//9));forced=dead_rank(p,k,j//9)
            for promotion in ([True] if forced else [False,True] if eligible else [False]):
                trial=b[:];trial[j]=c+(8 if p==0 else -8) if promotion else c;trial[i]=0
                if not check(trial,p):out.append((i,j,promotion))
    return out

def legal_parts(d):return cached_legal(tuple(d['board']),tuple(d['hands'][0]),tuple(d['hands'][1]),int(d['turn']))
@lru_cache(maxsize=64)
def cached_legal(board,h0,h1,p):
    b=list(board);moves=board_moves(b,p);drops=[];hand=(h0,h1)[p]
    for kind in range(2,9):
        if not hand[kind-2]:continue
        for j,c in enumerate(b):
            if c or dead_rank(p,kind,j//9):continue
            if kind==8 and any(b[y*9+j%9]==(8 if p==0 else -8) for y in range(9)):continue
            trial=b[:];trial[j]=kind if p==0 else -kind
            if check(trial,p):continue
            if kind==8 and check(trial,1-p) and not board_moves(trial,1-p):continue
            drops.append((kind,j))
    return tuple(moves),tuple(drops)

def key(d):return ''.join(chr(int(c)+81) for c in d['board'])+'|'+str(int(d['turn']))+'|'+','.join(str(int(n)) for h in d['hands'] for n in h)
def repeated(d):return d['history'].count(key(d))>=4

def repetition_result(d):
    positions=[i for i,k in enumerate(d['history']) if k==key(d)]
    if len(positions)<4:return None,None
    start=positions[-4];checkers=[]
    for p in (0,1):
        relevant=[d['checks'][i] for i in range(start+1,len(d['history'])) if int(d['history'][i].split('|')[1])==1-p]
        if relevant and all(relevant):checkers.append(p)
    return (1-checkers[0],'perpetual_check') if len(checkers)==1 else (None,'fourfold_repetition')
def impasse_points(d,p):return sum(5 if base(c) in (6,7) else 1 for c in d['board'] if c and side(c)==p and base(c)!=1)+sum(n*(5 if k in (6,7) else 1) for k,n in enumerate(d['hands'][p],2))
def impasse_possible(d):return all(zone(p,d['board'].index(1 if p==0 else -1)//9) and not check(d['board'],p) for p in (0,1))

def validate(d):
    b=d['board'];allowed={0,1,2,3,4,5,6,7,8,11,12,13,14,15,16}
    if any(abs(c) not in allowed for c in b):fail('Unknown or impossible promoted piece type',code='INVALID_STATE')
    for kind,total in TOTAL.items():
        actual=sum(base(c)==kind for c in b if c)+ (sum(h[kind-2] for h in d['hands']) if kind>=2 else 0)
        if actual!=total:fail('Board and hands must conserve all forty original pieces',code='INVALID_STATE')
    for p in (0,1):
        if b.count(1 if p==0 else -1)!=1:fail('Each side requires exactly one king',code='INVALID_STATE')
        for x in range(9):
            if sum(b[y*9+x]==(8 if p==0 else -8) for y in range(9))>1:fail('Two unpromoted pawns on one file are forbidden',code='INVALID_STATE')
        if any(c and side(c)==p and dead_rank(p,abs(int(c)),i//9) for i,c in enumerate(b)):fail('An immobile pawn, lance or knight must be promoted',code='INVALID_STATE')
    if check(b,1-int(d['turn'])):fail('The nonmoving king cannot remain in check',code='INVALID_STATE')
    if not d['history'] or d['history'][-1]!=key(d) or len(d['history'])!=len(d['checks']) or d['checks'][-1]!=check(b,int(d['turn'])):fail('Position and check history mismatch',code='INVALID_STATE')
    for h in d['history']:
        parts=h.split('|')
        if len(parts)!=3 or len(parts[0])!=81 or any(not 65<=ord(c)<=97 for c in parts[0]) or parts[1] not in ('0','1') or len(parts[2].split(','))!=14 or any(not c.isdigit() or int(c)>18 for c in parts[2].split(',')):fail('Malformed position history',code='INVALID_STATE')
    if d['decision'] is not None and d['decision']['kind']=='impasse' and not impasse_possible(d):fail('Agreed impasse requires both kings safely in enemy camps',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type'];t=int(d['turn'])
    if k in ('resign','offer_impasse','accept_impasse'):
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params');q=int(p['player'])
        if action.get('actor') is not None and action['actor']!=state['players'][q]['id']:fail('Wrong actor')
        if k=='resign':d['decision']=dict(kind='resign',player=q);return d
        if not impasse_possible(d):fail('Both kings must be safely in enemy camps for agreed impasse')
        if k=='offer_impasse':d['impasse_offer']=q
        else:
            if d['impasse_offer'] is None or d['impasse_offer']==q:fail('Only the opponent may accept an impasse offer')
            d['decision']=dict(kind='impasse',player=q)
        return d
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    moves,drops=legal_parts(d)
    if k=='move':
        fields(p,dict(source=dict(type='integer',minimum=0,maximum=80),destination=dict(type='integer',minimum=0,maximum=80),promote=dict(type='boolean')),'/params');i=int(p['source']);j=int(p['destination'])
        if (i,j,p['promote']) not in moves:fail('Illegal piece move, promotion choice or king exposure')
        captured=d['board'][j]
        if captured:d['hands'][t][base(captured)-2]+=1
        c=d['board'][i];d['board'][j]=c+(8 if t==0 else -8) if p['promote'] else c;d['board'][i]=0
    elif k=='drop':
        fields(p,dict(piece=dict(type='integer',minimum=2,maximum=8),destination=dict(type='integer',minimum=0,maximum=80)),'/params');kind=int(p['piece']);j=int(p['destination'])
        if (kind,j) not in drops:fail('Drop requires a held piece, a legal empty square, no doubled pawn and no immediate pawn-drop mate')
        d['hands'][t][kind-2]-=1;d['board'][j]=kind if t==0 else -kind
    else:fail('Unknown action')
    d['turn']=1-t;d['history'].append(key(d));d['checks'].append(check(d['board'],1-t));d['impasse_offer']=None;return d

def legal(state):
    d=state['data'];moves,drops=legal_parts(d);actions=[dict(type='move',params=dict(source=i,destination=j,promote=p)) for i,j,p in moves]+[dict(type='drop',params=dict(piece=k,destination=j)) for k,j in drops]+[dict(type='resign',params=dict(player=p)) for p in (0,1)]
    if impasse_possible(d):
        actions += [dict(type='offer_impasse',params=dict(player=p)) for p in (0,1)]
        if d['impasse_offer'] is not None:actions.append(dict(type='accept_impasse',params=dict(player=1-d['impasse_offer'])))
    return actions

def outcome(state,pack):
    d=state['data'];decision=d['decision'];w=None;reason=None
    if decision:
        if decision['kind']=='resign':w=1-int(decision['player']);reason='resignation'
        else:
            points=[impasse_points(d,p) for p in (0,1)];w=None if min(points)>=24 else 0 if points[0]>points[1] else 1;reason='agreed_twenty_four_point_impasse'
    else:
        moves,drops=legal_parts(d)
        if not moves and not drops:w=1-int(d['turn']);reason='no_legal_move'
        else:w,reason=repetition_result(d)
    done=reason is not None
    return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason=reason if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
