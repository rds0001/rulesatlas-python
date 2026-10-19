"""Orthodox chess with local king-safety checks and explicit draw adjudication."""
from copy import deepcopy
import re
from ..values import fields,fail
ORTH=[(1,0),(-1,0),(0,1),(0,-1)];DIAG=[(1,1),(1,-1),(-1,1),(-1,-1)];KNIGHT=[(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]
def at(r,c):return r*8+c if 0<=r<8 and 0<=c<8 else None
def sign(p):return 1 if p==0 else -1
def attacked(b,square,by):
    r,c=divmod(square,8);s=sign(by)
    for dc in (-1,1):
        j=at(r-s,c+dc)
        if j is not None and b[j]==s:return True
    for dr,dc in KNIGHT:
        j=at(r+dr,c+dc)
        if j is not None and b[j]==2*s:return True
    for dr,dc in ORTH+DIAG:
        rr,cc=r+dr,c+dc;j=at(rr,cc);distance=1
        while j is not None:
            v=b[j]
            if v:
                if v*s>0 and (abs(v)==6 and distance==1 or abs(v)==5 or abs(v)==(4 if (dr,dc) in ORTH else 3)):return True
                break
            rr+=dr;cc+=dc;j=at(rr,cc);distance+=1
    return False

def raw(d,i,j,promotion=None):
    x=deepcopy(d);b=x['board'];piece=b[i];captured=b[j];p=int(d['turn']);s=sign(p);b[i]=0;b[j]=piece
    if abs(piece)==1 and j==d['ep'] and captured==0 and i%8!=j%8:captured=b[j-8*s];b[j-8*s]=0
    if promotion is not None:b[j]=s*int(promotion)
    if abs(piece)==6:
        x['rights'][2*p:2*p+2]=[False,False]
        if abs(j-i)==2:
            rook_from=i+3 if j>i else i-4;rook_to=i+1 if j>i else i-1;b[rook_to]=b[rook_from];b[rook_from]=0
    for k,home in enumerate([7,0,63,56]):
        if i==home or j==home:x['rights'][k]=False
    x['ep']=(i+j)//2 if abs(piece)==1 and abs(j-i)==16 else None;x['halfmove']=0 if abs(piece)==1 or captured else d['halfmove']+1;x['turn']=1-p
    return x

def safe(d,i,j,promotion=None):
    x=raw(d,i,j,promotion);p=int(d['turn']);return not attacked(x['board'],x['board'].index(6*sign(p)),1-p)
def moves(d):
    b=d['board'];p=int(d['turn']);s=sign(p);result=[]
    for i,v in enumerate(b):
        if v*s<=0:continue
        r,c=divmod(i,8);dest=[];piece=abs(v)
        if piece==1:
            j=at(r+s,c)
            if j is not None and b[j]==0:
                dest.append(j);jj=at(r+2*s,c)
                if r==(1 if p==0 else 6) and b[jj]==0:dest.append(jj)
            for dc in (-1,1):
                j=at(r+s,c+dc)
                if j is not None and (b[j]*s<0 and abs(b[j])!=6 or j==d['ep']):dest.append(j)
        elif piece in (2,6):
            for dr,dc in KNIGHT if piece==2 else ORTH+DIAG:
                j=at(r+dr,c+dc)
                if j is not None and b[j]*s<=0 and abs(b[j])!=6:dest.append(j)
            home=4 if p==0 else 60
            if piece==6 and i==home and not attacked(b,i,1-p):
                for offset,k,empty,path in [(2,2*p,[1,2],[1,2]),(-2,2*p+1,[-1,-2,-3],[-1,-2])]:
                    if d['rights'][k] and all(b[i+o]==0 for o in empty) and all(not attacked(b,i+o,1-p) for o in path):dest.append(i+offset)
        else:
            dirs=ORTH if piece==4 else DIAG if piece==3 else ORTH+DIAG
            for dr,dc in dirs:
                rr,cc=r+dr,c+dc;j=at(rr,cc)
                while j is not None:
                    if b[j]*s>0 or abs(b[j])==6:break
                    dest.append(j)
                    if b[j]:break
                    rr+=dr;cc+=dc;j=at(rr,cc)
        for j in dest:
            for promotion in (2,3,4,5) if piece==1 and j//8 in (0,7) else (None,):
                if safe(d,i,j,promotion):result.append((i,j,promotion))
    return result

def key(d):
    ep=None;p=int(d['turn']);s=sign(p)
    if d['ep'] is not None:
        j=int(d['ep']);r,c=divmod(j,8)
        for dc in (-1,1):
            i=at(r-s,c+dc)
            if i is not None and d['board'][i]==s and safe(d,i,j):ep=j
    return ''.join(chr(103+int(v)) for v in d['board'])+'|'+str(p)+'|'+''.join('1' if x else '0' for x in d['rights'])+'|'+('-' if ep is None else str(ep))
def transition(d,i,j,promotion):
    x=raw(d,i,j,promotion);x['history']=[key(x)] if x['halfmove']==0 else d['history']+[key(x)]
    if d['offer'] is not None and d['offer']!=d['turn']:x['offer']=None
    return x

def dead(d):
    pieces=[(i,v) for i,v in enumerate(d['board']) if v and abs(v)!=6]
    if not pieces:return True
    if any(abs(v) in (1,4,5) for i,v in pieces):return False
    if len(pieces)==1:return True
    return all(abs(v)==3 for i,v in pieces) and len({(i//8+i%8)%2 for i,v in pieces})==1

def validate(d):
    b=d['board'];p=int(d['turn'])
    if d['decision'] is not None and ((d['decision']['kind']=='draw')!=(d['decision']['winner'] is None)):fail('Draw and winner decision mismatch',code='INVALID_STATE')
    if b.count(6)!=1 or b.count(-6)!=1 or any(abs(b[i])==1 for i in list(range(8))+list(range(56,64))):fail('Exactly one king per side and no back-rank pawns are required',code='INVALID_STATE')
    for q in (0,1):
        s=sign(q);owned=[(i,abs(v)) for i,v in enumerate(b) if v*s>0];pawns=sum(v==1 for i,v in owned)
        promotions=sum(max(0,sum(v==piece for i,v in owned)-n) for piece,n in [(2,2),(4,2),(5,1)])+sum(max(0,sum(v==3 and (i//8+i%8)%2==c for i,v in owned)-1) for c in (0,1))
        if len(owned)>16 or pawns>8 or promotions>8-pawns:fail('Material requires more promotions than missing pawns allow',code='INVALID_STATE')
    if attacked(b,b.index(6*sign(1-p)),p):fail('The side that just moved cannot leave its king in check',code='INVALID_STATE')
    for k,(king,rook,s) in enumerate([(4,7,1),(4,0,1),(60,63,-1),(60,56,-1)]):
        if d['rights'][k] and (b[king]!=6*s or b[rook]!=4*s):fail('Castling right requires the king and rook on their original squares',code='INVALID_STATE')
    if d['ep'] is not None:
        j=int(d['ep']);s=sign(p)
        if j//8!=(5 if p==0 else 2) or b[j]!=0 or b[j-8*s]!=-s or b[j+8*s]!=0 or d['halfmove']!=0:fail('Invalid en-passant target after a double pawn step',code='INVALID_STATE')
    if len(d['history'])!=d['halfmove']+1 or not d['history'] or d['history'][-1]!=key(d) or any(not re.fullmatch(r'[a-m]{64}\|[01]\|[01]{4}\|(?:-|[0-9]{1,2})',h) for h in d['history']):fail('Invalid repetition history or halfmove count',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type'];t=int(d['turn'])
    if kind in ('resign','time_forfeit'):
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params');loser=int(p['player']);other=1-loser
        no_mate=dead(d) or not any(v*sign(other)>0 and abs(v)!=6 for v in d['board']);d['decision']=dict(kind='draw' if no_mate else kind,winner=None if no_mate else other);return d
    if kind=='adjudicate_dead_position':
        fields(p,{},'/params');d['decision']=dict(kind='draw',winner=None);return d
    if kind=='accept_draw':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params');player=int(p['player'])
        if d['offer'] is None or d['offer']==player:fail('Only the opponent may accept an outstanding offer')
        if action.get('actor') is not None and action['actor']!=state['players'][player]['id']:fail('Wrong actor')
        d['decision']=dict(kind='draw',winner=None);return d
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if kind=='offer_draw':fields(p,{},'/params');d['offer']=t;return d
    move_schema=dict(start=dict(type='integer',minimum=0,maximum=63),end=dict(type='integer',minimum=0,maximum=63),promotion=dict(type='integer',minimum=2,maximum=5,nullable=True))
    if kind=='claim_draw':
        fields(p,dict(reason=dict(type='string',enum=['threefold','fifty_moves']),move=dict(type='object',properties=move_schema,required=list(move_schema),nullable=True)),'/params');x=d
        if p['move'] is not None:
            m=p['move'];triple=(m['start'],m['end'],m['promotion'])
            if triple not in moves(d):fail('The intended move must be legal')
            x=transition(d,*triple)
        if (x['history'].count(key(x))<3 if p['reason']=='threefold' else x['halfmove']<100):fail('Requested draw condition is not met')
        d['decision']=dict(kind='draw',winner=None);return d
    if kind!='move':fail('Unknown action')
    fields(p,move_schema,'/params');triple=(p['start'],p['end'],p['promotion'])
    if triple not in moves(d):fail('Move is illegal or leaves the moving king in check')
    return transition(d,*triple)

def result(d):
    if d['decision'] is not None:return d['decision']['kind'],d['decision']['winner']
    legal=moves(d)
    if not legal:
        return ('checkmate',1-int(d['turn'])) if attacked(d['board'],d['board'].index(6*sign(d['turn'])),1-d['turn']) else ('stalemate',None)
    if dead(d):return 'dead_material',None
    if d['halfmove']>=150:return 'seventy_five_moves',None
    if d['history'].count(key(d))>=5:return 'fivefold_repetition',None
    return None,None

def legal(state):
    d=state['data'];actions=[dict(type='move',params=dict(start=i,end=j,promotion=p)) for i,j,p in moves(d)]+[dict(type='offer_draw',params={})]
    if d['offer'] is not None:actions.append(dict(type='accept_draw',params=dict(player=1-d['offer'])))
    for reason,ok in [('threefold',d['history'].count(key(d))>=3),('fifty_moves',d['halfmove']>=100)]:
        if ok:actions.append(dict(type='claim_draw',params=dict(reason=reason,move=None)))
    ms=dict(start=dict(type='integer',minimum=0,maximum=63),end=dict(type='integer',minimum=0,maximum=63),promotion=dict(type='integer',minimum=2,maximum=5,nullable=True))
    types=[dict(type='claim_draw',params_schema=dict(reason=dict(type='string',enum=['threefold','fifty_moves']),move=dict(type='object',properties=ms,required=list(ms),nullable=True)),preconditions=['Current or indicated legal next position satisfies the claimed condition.'],external_observations=[])]
    types += [dict(type=k,params_schema=dict(player=dict(type='integer',minimum=0,maximum=1)),preconditions=['Losing player identified; draw if the opponent cannot mate under the supported material checks.'],external_observations=['Official resignation or time-forfeit decision.']) for k in ('resign','time_forfeit')]
    types.append(dict(type='adjudicate_dead_position',params_schema={},preconditions=['An adjudicator establishes that no legal continuation permits checkmate.'],external_observations=['Dead-position ruling beyond elementary material cases.']))
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(turn=d['turn'],in_check=attacked(d['board'],d['board'].index(6*sign(d['turn'])),1-d['turn'])),completeness=False,reason='legal_moves_and_adjudication')
def outcome(state,pack):
    kind,winner=result(state['data']);done=kind is not None
    return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if winner is None else 'forfeit' if kind=='time_forfeit' else 'win') if done else 'none',winners=[state['players'][int(winner)]['id']] if winner is not None else [],losers=[state['players'][1-int(winner)]['id']] if winner is not None else [],placements=[],reason=kind or 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
