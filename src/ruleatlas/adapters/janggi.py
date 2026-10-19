"""Casual Janggi, layout choices, palace diagonals, bikjang and passing."""
from copy import deepcopy
from functools import lru_cache
from ..values import fields,fail
from .xiangqi import side,inside,palace,targets as xq_targets,key
PALACE_LINES=[(3,13,23),(5,13,21),(66,76,86),(68,76,84)]
def diagonal_rays(i):
    out=[]
    for line in PALACE_LINES:
        if i in line:
            n=line.index(i)
            if n<2:out.append(list(line[n+1:]))
            if n>0:out.append(list(reversed(line[:n])))
    return out

def initial_board(layouts):
    b=[0]*90
    for p in (0,1):
        row=[5,3,4,2,0,2,4,3,5];layout=int(layouts[p] or 0)
        if layout&1:row[1],row[2]=row[2],row[1]
        if layout&2:row[6],row[7]=row[7],row[6]
        offset=0 if p==0 else 81;sgn=1 if p==0 else -1
        b[offset:offset+9]=[c*sgn for c in row];b[13 if p==0 else 76]=sgn
        for i in ((19,25) if p==0 else (64,70)):b[i]=6*sgn
        for i in ((27,29,31,33,35) if p==0 else (54,56,58,60,62)):b[i]=7*sgn
    return b

def targets(b,i):
    c=int(b[i]);p=side(c);k=abs(c);x=i%9;y=i//9;out=[]
    def add(a,v):
        if inside(a,v) and side(b[v*9+a])!=p:out.append(v*9+a)
    if k in (1,2):
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            if palace(p,x+dx,y+dy):add(x+dx,y+dy)
        for ray in diagonal_rays(i):
            j=ray[0]
            if palace(p,j%9,j//9):add(j%9,j//9)
    elif k==3:
        for dx,dy in ((2,3),(2,-3),(-2,3),(-2,-3),(3,2),(3,-2),(-3,2),(-3,-2)):
            a=x+dx;v=y+dy;sx=1 if dx>0 else -1;sy=1 if dy>0 else -1
            legs=[(x,y+sy),(x+sx,y+2*sy)] if abs(dy)==3 else [(x+sx,y),(x+2*sx,y+sy)]
            if inside(a,v) and all(not b[ly*9+lx] for lx,ly in legs):add(a,v)
    elif k==4:return xq_targets(b,i)
    elif k in (5,6):
        rays=diagonal_rays(i)
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            ray=[];a=x+dx;v=y+dy
            while inside(a,v):ray.append(v*9+a);a+=dx;v+=dy
            rays.append(ray)
        for ray in rays:
            screen=False
            for j in ray:
                if k==5:
                    if side(b[j])!=p:out.append(j)
                    if b[j]:break
                elif not screen:
                    if b[j]:
                        if abs(b[j])==6:break
                        screen=True
                else:
                    if side(b[j])!=p and abs(b[j])!=6:out.append(j)
                    if b[j]:break
    elif k==7:
        f=1 if p==0 else -1;add(x,y+f);add(x-1,y);add(x+1,y)
        for ray in diagonal_rays(i):
            j=ray[0]
            if j//9-y==f:add(j%9,j//9)
    return out

def check(b,p):
    king=1 if p==0 else -1
    if king not in b:return True
    k=b.index(king)
    return any(k in targets(b,i) for i,c in enumerate(b) if c and side(c)!=p)
def facing(b):
    a=b.index(1);z=b.index(-1)
    return a%9==z%9 and all(b[i]==0 for i in range(min(a,z)+9,max(a,z),9))
def moves(d):return cached_moves(tuple(d['board']),int(d['turn']))
@lru_cache(maxsize=128)
def cached_moves(board,p):
    b=list(board);must_break=facing(b);out=[]
    for i,c in enumerate(b):
        if not c or side(c)!=p:continue
        for j in targets(b,i):
            if abs(b[j])==1:continue
            trial=b[:];trial[j]=trial[i];trial[i]=0
            if not check(trial,p) and (not must_break or not facing(trial)):out.append((i,j))
    return tuple(out)
def repeated(d):return d['history'].count(key(d))>=3

def validate(d):
    b=d['board']
    if d['phase']=='setup':
        expected_turn=1 if d['layouts'][1] is None else 0
        if d['layouts'][0] is not None or d['turn']!=expected_turn or b!=initial_board(d['layouts']) or d['history'] or d['passes'] or d['decision'] is not None:fail('Han chooses its layout before Cho, then play begins',code='INVALID_STATE')
        return
    if any(x is None for x in d['layouts']):fail('Both initial layouts must be selected',code='INVALID_STATE')
    for p in (0,1):
        s=1 if p==0 else -1
        for k,limit in ((1,1),(2,2),(3,2),(4,2),(5,2),(6,2),(7,5)):
            n=b.count(s*k)
            if n>limit or (k==1 and n!=1):fail('Invalid army composition',code='INVALID_STATE')
        for i,c in enumerate(b):
            if c and side(c)==p:
                if abs(c) in (1,2) and not palace(p,i%9,i//9):fail('General and guards must stay in their palace',code='INVALID_STATE')
                if abs(c)==7 and ((p==0 and i//9<3) or (p==1 and i//9>6)):fail('Soldier cannot retreat behind its initial rank',code='INVALID_STATE')
    if check(b,1-int(d['turn'])):fail('The nonmoving general cannot remain in check',code='INVALID_STATE')
    if not d['history'] or d['history'][-1]!=key(d) or any(len(h)!=91 or any(c not in 'abcdefghijklmno' for c in h[:90]) or h[-1] not in '01' for h in d['history']):fail('Invalid position history',code='INVALID_STATE')
    if d['passes'] and (check(b,int(d['turn'])) or facing(b)):fail('Passing cannot leave check or an unresolved bikjang',code='INVALID_STATE')
    if d['decision'] is not None:
        dec=d['decision'];r=dec['reason']
        if (r in ('bikjang','mutual_repetition'))!=(dec['offender'] is None):fail('Decision and offender disagree',code='INVALID_STATE')
        if r=='bikjang' and (not facing(b) or check(b,int(d['turn']))):fail('Bikjang acceptance requires facing generals without check',code='INVALID_STATE')
        if r in ('perpetual_check','perpetual_chase','mutual_repetition') and not repeated(d):fail('Repetition decision requires a third occurrence',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type'];t=int(d['turn'])
    if k=='choose_layout':
        fields(p,dict(layout=dict(type='integer',minimum=0,maximum=3)),'/params')
        if d['phase']!='setup':fail('Layouts are fixed once play begins')
        if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        d['layouts'][t]=p['layout'];d['board']=initial_board(d['layouts'])
        if t==1:d['turn']=0
        else:d['phase']='play';d['history']=[key(d)]
        return d
    if d['phase']!='play':fail('Choose both initial layouts first')
    if k=='resign':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params');q=int(p['player'])
        if action.get('actor') is not None and action['actor']!=state['players'][q]['id']:fail('Wrong actor')
        d['decision']=dict(reason='resignation',offender=q);return d
    if k=='adjudicate_repetition':
        fields(p,dict(offender=dict(type='integer',minimum=0,maximum=1,nullable=True),reason=dict(type='string',enum=['perpetual_check','perpetual_chase','mutual_repetition'])),'/params')
        if not repeated(d) or (p['reason']=='mutual_repetition')!=(p['offender'] is None):fail('Resolve an actual repetition with a consistent official decision')
        d['decision']=deepcopy(p);return d
    if repeated(d):fail('Resolve repetition before continuing')
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if k=='accept_bikjang':
        fields(p,{},'/params')
        if not facing(d['board']) or check(d['board'],t):fail('Accept bikjang only with facing generals and no check')
        d['decision']=dict(reason='bikjang',offender=None);return d
    if k=='pass':
        fields(p,{},'/params')
        if check(d['board'],t) or facing(d['board']):fail('Cannot pass while checked or facing bikjang')
        d['passes']+=1
    elif k=='move':
        fields(p,dict(source=dict(type='integer',minimum=0,maximum=89),destination=dict(type='integer',minimum=0,maximum=89)),'/params');i=int(p['source']);j=int(p['destination'])
        if (i,j) not in moves(d):fail('Illegal piece move, general exposure or failure to break bikjang')
        captured=d['board'][j]!=0;d['board'][j]=d['board'][i];d['board'][i]=0;d['passes']=0
        if captured:d['history']=[]
    else:fail('Unknown action')
    d['turn']=1-t;d['history'].append(key(d));return d

def legal(state):
    d=state['data']
    if d['phase']=='setup':return [dict(type='choose_layout',params=dict(layout=x)) for x in range(4)]
    if repeated(d):return dict(mode='event_types',actions=[],action_types=[dict(type='adjudicate_repetition',params_schema=dict(offender=dict(type='integer',minimum=0,maximum=1,nullable=True),reason=dict(type='string',enum=['perpetual_check','perpetual_chase','mutual_repetition'])),preconditions=['Third occurrence requires an official responsibility decision.'],external_observations=['Perpetual-check/chase or mutual-repetition decision.'])],constraints={},completeness=False,reason='repetition_requires_adjudication')
    actions=[dict(type='move',params=dict(source=i,destination=j)) for i,j in moves(d)]+[dict(type='resign',params=dict(player=p)) for p in (0,1)]
    if not check(d['board'],int(d['turn'])):actions.append(dict(type='accept_bikjang' if facing(d['board']) else 'pass',params={}))
    return actions

def outcome(state,pack):
    d=state['data'];reason=None;w=None;pending=False
    if d['phase']=='play':
        if d['decision'] is not None:
            reason=d['decision']['reason'];w=None if d['decision']['offender'] is None else 1-int(d['decision']['offender'])
        elif check(d['board'],int(d['turn'])) and not moves(d):reason='checkmate';w=1-int(d['turn'])
        elif d['passes']==2:reason='two_consecutive_passes'
        else:pending=repeated(d)
    done=reason is not None
    return dict(status='terminal' if done else 'awaiting_adjudication' if pending else 'ongoing',result_kind=('draw' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason=reason if done else 'repeated_position' if pending else 'ongoing',evidence_required=['Official repeated-position adjudication.'] if pending else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
