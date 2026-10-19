"""Xiangqi local legal moves; repeated-position disputes use explicit adjudication."""
from copy import deepcopy
from functools import lru_cache
from ..values import fields,fail
# Positive red moves toward increasing rows; negative black toward decreasing rows.
# Piece types: general 1, advisor 2, elephant 3, horse 4, chariot 5, cannon 6, soldier 7.
def side(piece):return 0 if piece>0 else 1 if piece<0 else None
def palace(p,x,y):return 3<=x<=5 and (0<=y<=2 if p==0 else 7<=y<=9)
def inside(x,y):return 0<=x<9 and 0<=y<10
def targets(b,i):
    piece=int(b[i]);p=side(piece);kind=abs(piece);x=i%9;y=i//9;out=[]
    def add(a,c):
        if inside(a,c) and side(b[c*9+a])!=p:out.append(c*9+a)
    if kind==1:
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            if palace(p,x+dx,y+dy):add(x+dx,y+dy)
        dy=1 if p==0 else -1;row=y+dy
        while inside(x,row):
            j=row*9+x
            if b[j]:
                if b[j]==-piece:out.append(j)
                break
            row+=dy
    elif kind==2:
        for dx,dy in ((1,1),(1,-1),(-1,1),(-1,-1)):
            if palace(p,x+dx,y+dy):add(x+dx,y+dy)
    elif kind==3:
        for dx,dy in ((2,2),(2,-2),(-2,2),(-2,-2)):
            a=x+dx;c=y+dy
            if inside(a,c) and (c<=4 if p==0 else c>=5) and not b[(y+dy//2)*9+x+dx//2]:add(a,c)
    elif kind==4:
        for dx,dy in ((2,1),(2,-1),(-2,1),(-2,-1),(1,2),(-1,2),(1,-2),(-1,-2)):
            lx=x+(dx//2 if abs(dx)==2 else 0);ly=y+(dy//2 if abs(dy)==2 else 0)
            if inside(lx,ly) and not b[ly*9+lx]:add(x+dx,y+dy)
    elif kind in (5,6):
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            a=x+dx;c=y+dy;screen=False
            while inside(a,c):
                j=c*9+a
                if kind==5:
                    if side(b[j])!=p:out.append(j)
                    if b[j]:break
                elif not screen:
                    if b[j]:screen=True
                    else:out.append(j)
                elif b[j]:
                    if side(b[j])!=p:out.append(j)
                    break
                a+=dx;c+=dy
    elif kind==7:
        add(x,y+(1 if p==0 else -1))
        if (y>=5 if p==0 else y<=4):add(x-1,y);add(x+1,y)
    return out

def in_check(b,p):
    king=1 if p==0 else -1
    if king not in b:return True
    k=b.index(king)
    return any(k in targets(b,i) for i,c in enumerate(b) if c and side(c)!=p)
def moves(d):return cached_moves(tuple(d['board']),int(d['turn']))
@lru_cache(maxsize=128)
def cached_moves(board,p):
    b=list(board);out=[]
    for i,c in enumerate(b):
        if not c or side(c)!=p:continue
        for j in targets(b,i):
            if abs(b[j])==1:continue
            trial=b[:];trial[j]=trial[i];trial[i]=0
            if not in_check(trial,p):out.append((i,j))
    return tuple(out)

def key(d):return ''.join(chr(int(c)+104) for c in d['board'])+str(int(d['turn']))
def repetition(d):return d['history'].count(key(d))>=3

def validate(d):
    b=d['board']
    for p in (0,1):
        sign=1 if p==0 else -1
        for kind,limit in ((1,1),(2,2),(3,2),(4,2),(5,2),(6,2),(7,5)):
            n=b.count(sign*kind)
            if n>limit or (kind==1 and n!=1):fail('Invalid army composition',code='INVALID_STATE')
        for i,c in enumerate(b):
            if c==0 or side(c)!=p:continue
            x=i%9;y=i//9;k=abs(c)
            if k in (1,2) and not palace(p,x,y):fail('General and advisors must stay in their palace',code='INVALID_STATE')
            if k==2 and (x+y)%2!=(1 if p==0 else 0):fail('Advisor is off its diagonal palace points',code='INVALID_STATE')
            allowed={(2,0),(6,0),(0,2),(4,2),(8,2),(2,4),(6,4)}
            if k==3 and (x,y if p==0 else 9-y) not in allowed:fail('Elephant is off its reachable own-side points',code='INVALID_STATE')
            if k==7 and ((p==0 and y<3) or (p==1 and y>6) or ((y<5 if p==0 else y>4) and x%2!=0)):fail('Soldier is behind its starting rank or sideways before crossing',code='INVALID_STATE')
    if in_check(b,1-int(d['turn'])):fail('The nonmoving general cannot be left in check',code='INVALID_STATE')
    if not d['history'] or d['history'][-1]!=key(d):fail('History must end at the current position',code='INVALID_STATE')
    if any(len(h)!=91 or any(c not in 'abcdefghijklmno' for c in h[:90]) or h[-1] not in '01' for h in d['history']):fail('Invalid position history encoding',code='INVALID_STATE')
    if d['decision'] is not None and ((d['decision']['reason']=='mutual_repetition')!=(d['decision']['offender'] is None)):fail('Repetition decision and offender disagree',code='INVALID_STATE')
    if d['decision'] is not None and not repetition(d):fail('Repetition adjudication requires a third occurrence',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type'];t=int(d['turn'])
    if k=='adjudicate_repetition':
        fields(p,dict(offender=dict(type='integer',minimum=0,maximum=1,nullable=True),reason=dict(type='string',enum=['perpetual_check','perpetual_chase','mutual_repetition'])),'/params')
        if not repetition(d):fail('No repeated-position dispute is pending')
        if (p['reason']=='mutual_repetition')!=(p['offender'] is None):fail('Mutual repetition draws; a one-sided offence must name the offender')
        d['decision']=deepcopy(p);return d
    if k!='move':fail('Unknown action')
    fields(p,dict(source=dict(type='integer',minimum=0,maximum=89),destination=dict(type='integer',minimum=0,maximum=89)),'/params');i=int(p['source']);j=int(p['destination'])
    if repetition(d):fail('Resolve repeated-position adjudication before further play')
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if (i,j) not in moves(d):fail('Move must obey piece restrictions and leave the moving general safe')
    captured=d['board'][j]!=0;d['board'][j]=d['board'][i];d['board'][i]=0;d['turn']=1-t
    if captured:d['history']=[]
    d['history'].append(key(d));return d

def legal(state):
    d=state['data']
    if repetition(d):return dict(mode='event_types',actions=[],action_types=[dict(type='adjudicate_repetition',params_schema=dict(offender=dict(type='integer',minimum=0,maximum=1,nullable=True),reason=dict(type='string',enum=['perpetual_check','perpetual_chase','mutual_repetition'])),preconditions=['An official adjudicator resolves repeated-position responsibility; null offender only for a mutual draw.'],external_observations=['Perpetual check/chase classification and responsibility.'])],constraints={},completeness=False,reason='repetition_requires_adjudication')
    return [dict(type='move',params=dict(source=i,destination=j)) for i,j in moves(d)]
def outcome(state,pack):
    d=state['data'];decision=d['decision'];available=moves(d);done=decision is not None or not available;pending=not done and repetition(d);w=(None if decision['offender'] is None else 1-int(decision['offender'])) if decision else 1-int(d['turn']) if done else None
    return dict(status='terminal' if done else 'awaiting_adjudication' if pending else 'ongoing',result_kind=('draw' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason=decision['reason'] if decision else ('checkmate' if in_check(d['board'],int(d['turn'])) else 'stalemate_loss') if done else 'repeated_position' if pending else 'ongoing',evidence_required=['Official repeated-position adjudication.'] if pending else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
