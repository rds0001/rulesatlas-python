"""Fanorona on 9x5 intersections, approach/withdrawal captures and optional sequences."""
from copy import deepcopy
from ..values import fields,fail
DIRS=[(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
def at(r,c):return r*9+c if 0<=r<5 and 0<=c<9 else None
def ray(b,r,c,dr,dc,enemy):
    result=[];i=at(r,c)
    while i is not None and b[i]==enemy:result.append(i);r+=dr;c+=dc;i=at(r,c)
    return result

def options(d,captures_only=False):
    b=d['board'];t=d['turn'];captures=[];quiet=[];pending=d['pending']
    for i,v in enumerate(b):
        if v!=t or pending is not None and i!=pending:continue
        r,c=divmod(i,9)
        for direction,(dr,dc) in enumerate(DIRS):
            if direction>=4 and (r+c)%2 or direction==d['last_direction']:continue
            j=at(r+dr,c+dc)
            if j is None or b[j]!=-1 or j in d['visited']:continue
            approach=ray(b,r+2*dr,c+2*dc,dr,dc,1-t);withdraw=ray(b,r-dr,c-dc,-dr,-dc,1-t)
            if approach:captures.append((i,j,'approach',direction,approach))
            if withdraw:captures.append((i,j,'withdrawal',direction,withdraw))
            if not approach and not withdraw:quiet.append((i,j,'move',direction,[]))
    return captures if captures or pending is not None or captures_only else quiet

def key(d):return ''.join(str(int(v)+1) for v in d['board'])+str(int(d['turn']))
def end_turn(d,captured):
    d['pending']=None;d['visited']=[];d['last_direction']=None;d['turn']=1-d['turn']
    if captured:d['history']=[key(d)]
    else:d['history'].append(key(d))
    return d

def validate(d):
    if all(v==-1 for v in d['board']) or any(d['board'].count(p)>22 for p in (0,1)):fail('More than twenty-two stones for one side',code='INVALID_STATE')
    if d['pending'] is None:
        if d['visited'] or d['last_direction'] is not None or not d['history'] or d['history'][-1]!=key(d):fail('Completed turn has stale capture sequence or history',code='INVALID_STATE')
    else:
        path=d['visited']
        if any(d['board'][int(i)]!=-1 for i in path[:-1]) or len(path)<2 or len(set(path))!=len(path) or path[-1]!=d['pending'] or d['board'][int(d['pending'])]!=d['turn'] or d['last_direction'] is None or d['history'] or not options(d,True):fail('Invalid continuation of a capture sequence',code='INVALID_STATE')
        for a,b in zip(path,path[1:]):
            r,c=divmod(int(a),9);rr,cc=divmod(int(b),9);delta=(rr-r,cc-c)
            if delta not in DIRS or abs(delta[0])+abs(delta[1])==2 and (r+c)%2:fail('Capture path does not follow connected intersections',code='INVALID_STATE')
        a,b=map(int,path[-2:]);delta=(b//9-a//9,b%9-a%9)
        if DIRS[int(d['last_direction'])]!=delta:fail('Last capture direction mismatch',code='INVALID_STATE')
    if any(len(k)!=46 or set(k[:45])-set('012') or k[-1] not in '01' for k in d['history']):fail('Malformed repetition history',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];t=int(d['turn'])
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if action['type']=='end_turn':
        fields(p,{},'/params')
        if d['pending'] is None:fail('Only a started capture sequence may be stopped')
        return end_turn(d,True)
    if action['type']!='step':fail('Unknown action')
    fields(p,dict(start=dict(type='integer',minimum=0,maximum=44),end=dict(type='integer',minimum=0,maximum=44),mode=dict(type='string',enum=['move','approach','withdrawal'])),'/params')
    move=next((m for m in options(d) if m[:3]==(p['start'],p['end'],p['mode'])),None)
    if move is None:fail('Step violates capture priority, connected lines or capture-sequence restrictions')
    i,j,mode,direction,victims=move;d['board'][i]=-1;d['board'][j]=t
    if not victims:return end_turn(d,False)
    for k in victims:d['board'][k]=-1
    if d['pending'] is None:d['visited']=[i]
    d['visited'].append(j);d['pending']=j;d['last_direction']=direction;d['history']=[]
    return d if options(d,True) else end_turn(d,True)

def legal(state):
    d=state['data'];actions=[dict(type='step',params=dict(start=i,end=j,mode=mode)) for i,j,mode,_,_ in options(d)]
    if d['pending'] is not None:actions.append(dict(type='end_turn',params={}))
    return actions

def outcome(state,pack):
    d=state['data'];lost=not any(v==d['turn'] for v in d['board']) or d['pending'] is None and not options(d);other_lost=not any(v==1-d['turn'] for v in d['board']);draw=not lost and not other_lost and d['pending'] is None and d['history'].count(key(d))>=3;terminal=lost or other_lost or draw;winner=int(d['turn']) if other_lost else 1-int(d['turn'])
    return dict(status='terminal' if terminal else 'ongoing',result_kind='draw' if draw else 'win' if terminal else 'none',winners=[] if not terminal or draw else [state['players'][winner]['id']],losers=[] if not terminal or draw else [state['players'][1-winner]['id']],placements=[],reason='threefold_repetition' if draw else 'no_stones_or_moves' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
