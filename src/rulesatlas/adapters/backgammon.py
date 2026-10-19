"""Single-game backgammon, legal dice usage and a centered doubling cube."""
from copy import deepcopy
from functools import lru_cache
from ..values import fields,fail

def sign(p):return 1 if p==0 else -1
def candidates(board,bar,off,p,die):
    s=sign(p);sources=[-1] if bar[p] else [i for i,c in enumerate(board) if c*s>0];out=[]
    home=bar[p]==0 and all(c*s<=0 or (i>=18 if p==0 else i<=5) for i,c in enumerate(board))
    for i in sources:
        dest=(die-1 if p==0 else 24-die) if i==-1 else i+(die if p==0 else -die)
        if 0<=dest<24:
            if board[dest]*s>=-1:out.append((i,dest))
        elif i!=-1 and home:
            distance=24-i if p==0 else i+1
            farther=any(c*s>0 and (j<i if p==0 else j>i) for j,c in enumerate(board))
            if die==distance or (die>distance and not farther):out.append((i,24))
    return out

def step(board,bar,off,p,source,dest):
    b=list(board);bars=list(bar);offs=list(off);s=sign(p)
    if source==-1:bars[p]-=1
    else:b[source]-=s
    if dest==24:offs[p]+=1
    else:
        if b[dest]==-s:bars[1-p]+=1;b[dest]=0
        b[dest]+=s
    return tuple(b),tuple(bars),tuple(offs)
@lru_cache(maxsize=8192)
def max_uses(board,bar,off,p,dice):
    best=0
    for die in sorted(set(dice),reverse=True):
        rest=list(dice);rest.remove(die)
        for source,dest in candidates(board,bar,off,p,die):
            b,ba,o=step(board,bar,off,p,source,dest);best=max(best,1+max_uses(b,ba,o,p,tuple(rest)))
            if best==len(dice):return best
    return best

def allowed(d):
    board=tuple(d['board']);bar=tuple(d['bar']);off=tuple(d['off']);p=int(d['turn']);dice=tuple(sorted(d['dice']));scored=[]
    for die in sorted(set(dice),reverse=True):
        rest=list(dice);rest.remove(die)
        for source,dest in candidates(board,bar,off,p,die):
            b,ba,o=step(board,bar,off,p,source,dest);scored.append((1+max_uses(b,ba,o,p,tuple(rest)),source,dest,die))
    if not scored:return []
    best=max(x[0] for x in scored);keep=[x for x in scored if x[0]==best]
    if best==1 and len(dice)==2 and dice[0]!=dice[1]:keep=[x for x in keep if x[3]==max(q[3] for q in keep)]
    return [(source,dest,die) for _,source,dest,die in keep]

def end_turn(d):
    d['turn']=1-int(d['turn']);d['phase']='roll';d['dice']=[];d['rolled']=None;return d

def validate(d):
    for p in (0,1):
        if sum(max(0,c*sign(p)) for c in d['board'])+d['bar'][p]+d['off'][p]!=15:fail('Each player must own fifteen checkers across board, bar and off',code='INVALID_STATE')
    if d['cube'] & (d['cube']-1):fail('Cube must be a power of two',code='INVALID_STATE')
    if (d['cube']==1)!=(d['cube_owner'] is None):fail('Only an undoubled cube is centered',code='INVALID_STATE')
    opening=[0]*24
    for i,n in {0:2,11:5,16:3,18:5,23:-2,12:-5,7:-3,5:-5}.items():opening[i]=n
    if d['phase']=='opening' and (d['board']!=opening or any(d['bar']) or any(d['off']) or d['turn']!=0):fail('Opening requires the standard checker layout',code='INVALID_STATE')
    if d['phase']=='opening' and (d['cube']!=1 or d['dice'] or d['rolled'] is not None or d['winner'] is not None):fail('Opening roll requires a centered cube and no pending dice',code='INVALID_STATE')
    phase=d['resume'] if d['phase']=='resign_offer' else d['phase']
    if phase in ('roll','double_offer') and (d['dice'] or d['rolled'] is not None):fail('Roll phase cannot retain previous dice',code='INVALID_STATE')
    if phase=='move':
        if d['rolled'] is None:fail('Moves require a recorded roll',code='INVALID_STATE')
        original=d['rolled']*2 if d['rolled'][0]==d['rolled'][1] else d['rolled']
        if not d['dice'] or any(d['dice'].count(x)>original.count(x) for x in set(d['dice'])) or not allowed(d):fail('Remaining dice must belong to the roll and permit a move',code='INVALID_STATE')
    if d['phase']=='double_offer' and (d['cube']>=64 or d['cube_owner'] not in (None,d['turn'])):fail('Only the cube owner may offer a permitted redouble',code='INVALID_STATE')
    if d['phase']=='resign_offer':
        if d['resume'] not in ('roll','move') or d['resign_value'] is None:fail('Resignation must retain its prior phase and proposed value',code='INVALID_STATE')
    elif d['resume'] is not None or d['resign_value'] is not None:fail('Stale resignation offer',code='INVALID_STATE')
    if d['phase']=='finished':
        if d['winner'] is None or d['reason'] is None or d['multiplier'] is None or d['dice']:fail('A finished game needs a settled result',code='INVALID_STATE')
        if d['reason']=='borne_off':
            w=int(d['winner']);loser=1-w;backgammon=d['bar'][loser]>0 or any(c*sign(loser)>0 and (i>=18 if w==0 else i<=5) for i,c in enumerate(d['board']));expected=1 if d['off'][loser] else 3 if backgammon else 2
            if d['off'][w]!=15 or w!=d['turn'] or d['multiplier']!=expected:fail('Bearing-off result and gammon multiplier disagree',code='INVALID_STATE')
        if d['reason']=='double_declined' and (d['winner']!=d['turn'] or d['multiplier']!=1):fail('A declined double settles at the old cube',code='INVALID_STATE')
        if d['reason']=='resignation' and d['winner']==d['turn']:fail('The resigning player cannot win',code='INVALID_STATE')
    elif d['winner'] is not None or d['reason'] is not None or d['multiplier'] is not None or 15 in d['off']:fail('A completed game must be terminal',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type'];t=int(d['turn'])
    actor=1-t if d['phase'] in ('double_offer','resign_offer') else t
    if k!='roll' and action.get('actor') is not None and action['actor']!=state['players'][actor]['id']:fail('Wrong actor')
    if k=='roll':
        fields(p,dict(dice=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=1,maximum=6))),'/params')
        if d['phase'] not in ('opening','roll'):fail('A roll is unavailable while a move or offer is pending')
        a,b=p['dice']
        if d['phase']=='opening':
            if a==b:return d
            d['turn']=0 if a>b else 1
        d['rolled']=p['dice'][:];d['dice']=p['dice']*2 if a==b else p['dice'][:];d['phase']='move'
        return d if allowed(d) else end_turn(d)
    if k=='move':
        fields(p,dict(source=dict(type='integer',minimum=-1,maximum=23),die=dict(type='integer',minimum=1,maximum=6)),'/params')
        if d['phase']!='move':fail('Roll before moving')
        options=[m for m in allowed(d) if m[0]==p['source'] and m[2]==p['die']]
        if not options:fail('Move must obey bar priority, blocking, bearing off and maximum dice usage')
        source,dest,die=options[0];board,bar,off=step(d['board'],d['bar'],d['off'],t,source,dest);d['board']=list(board);d['bar']=list(bar);d['off']=list(off);d['dice'].remove(die)
        if d['off'][t]==15:
            loser=1-t;backgammon=d['bar'][loser]>0 or any(c*sign(loser)>0 and (i>=18 if t==0 else i<=5) for i,c in enumerate(d['board']));d['multiplier']=1 if d['off'][loser] else 3 if backgammon else 2;d['winner']=t;d['reason']='borne_off';d['phase']='finished';d['dice']=[];return d
        return d if d['dice'] and allowed(d) else end_turn(d)
    if k=='double':
        fields(p,{},'/params')
        if d['phase']!='roll' or d['cube_owner'] not in (None,t) or d['cube']>=64:fail('Double before rolling, with cube ownership and below the table limit')
        d['phase']='double_offer';return d
    if k=='respond_double':
        fields(p,dict(accept=dict(type='boolean')),'/params')
        if d['phase']!='double_offer':fail('No double is pending')
        if p['accept']:d['cube']*=2;d['cube_owner']=1-t;d['phase']='roll'
        else:d['winner']=t;d['multiplier']=1;d['reason']='double_declined';d['phase']='finished'
        return d
    if k=='offer_resignation':
        fields(p,dict(value=dict(type='integer',minimum=1,maximum=3)),'/params')
        if d['phase'] not in ('roll','move'):fail('Offer resignation only during your own normal turn')
        d['resume']=d['phase'];d['resign_value']=p['value'];d['phase']='resign_offer';return d
    if k=='respond_resignation':
        fields(p,dict(accept=dict(type='boolean')),'/params')
        if d['phase']!='resign_offer':fail('No resignation is pending')
        if p['accept']:d['winner']=1-t;d['multiplier']=d['resign_value'];d['reason']='resignation';d['phase']='finished';d['dice']=[]
        else:d['phase']=d['resume']
        d['resume']=None;d['resign_value']=None;return d
    fail('Unknown action')

def legal(state):
    d=state['data'];actions=[];types=[]
    if d['phase'] in ('opening','roll'):types=[dict(type='roll',params_schema=dict(dice=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=1,maximum=6))),preconditions=['Opening dice are one per player; ties are rerolled, higher player uses both. Later doubles give four moves.'],external_observations=['Actual dice.'])]
    if d['phase']=='move':actions=[dict(type='move',params=dict(source=i,die=die)) for i,j,die in allowed(d)]
    if d['phase']=='double_offer':actions=[dict(type='respond_double',params=dict(accept=x)) for x in (True,False)]
    elif d['phase']=='resign_offer':actions=[dict(type='respond_resignation',params=dict(accept=x)) for x in (True,False)]
    else:
        if d['phase']=='roll' and d['cube_owner'] in (None,d['turn']) and d['cube']<64:actions.append(dict(type='double',params={}))
        if d['phase'] in ('roll','move'):actions += [dict(type='offer_resignation',params=dict(value=x)) for x in (1,2,3)]
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(turn=d['turn'],dice=d['dice'],cube=d['cube'],cube_owner=d['cube_owner']),completeness=False,reason='legal_current_roll_moves_and_external_dice')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';w=d['winner']
    return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][int(w)]['id']] if done else [],losers=[state['players'][1-int(w)]['id']] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p==w else 2,points=d['cube']*d['multiplier']*(1 if p==w else -1)) for p in (0,1)] if done else [],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
