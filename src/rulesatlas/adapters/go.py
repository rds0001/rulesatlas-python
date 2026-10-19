"""9x9 area-scoring Go, positional superko and agreed dead groups."""
from copy import deepcopy
from ..values import fields,fail

def neighbors(i):
    r,c=divmod(i,9)
    return [j for j,ok in ((i-9,r>0),(i+9,r<8),(i-1,c>0),(i+1,c<8)) if ok]
def group(b,i):
    seen={i};todo=[i]
    while todo:
        for j in neighbors(todo.pop()):
            if b[j]==b[i] and j not in seen:seen.add(j);todo.append(j)
    return seen
def liberties(b,g):return {j for i in g for j in neighbors(i) if b[j]==-1}
def key(b):return ''.join(str(int(v)+1) for v in b)
def place(d,i):
    b=d['board'][:];t=d['turn']
    if b[i]!=-1:fail('Intersection is occupied')
    b[i]=t
    for j in neighbors(i):
        if b[j]==1-t:
            g=group(b,j)
            if not liberties(b,g):
                for k in g:b[k]=-1
    if not liberties(b,group(b,i)):fail('Suicide is forbidden')
    if key(b) in d['history']:fail('Positional superko forbids repeating an earlier board')
    return b

def validate(d):
    b=d['board'];history=d['history']
    if not history or history[-1]!=key(b) or len(set(history))!=len(history) or any(len(x)!=81 or set(x)-set('012') for x in history):fail('Invalid positional superko history',code='INVALID_STATE')
    checked=set()
    for i,v in enumerate(b):
        if v!=-1 and i not in checked:
            g=group(b,i);checked|=g
            if not liberties(b,g):fail('A remaining group has no liberties',code='INVALID_STATE')
    if d['resigned'] is None and (d['phase'] in ('scoring','finished'))!=(d['passes']==2):fail('Two passes are required for area scoring',code='INVALID_STATE')
    if d['resigned'] is not None and (d['phase']!='finished' or d['proposal'] is not None):fail('Invalid resignation state',code='INVALID_STATE')
    proposal=d['proposal']
    if proposal is not None:
        dead=set(proposal['dead'])
        if d['phase'] not in ('scoring','finished') or len(dead)!=len(proposal['dead']) or any(b[int(i)]==-1 or not group(b,int(i))<=dead for i in dead):fail('Dead stones must comprise complete occupied groups',code='INVALID_STATE')
    if d['phase']=='finished' and d['resigned'] is None and proposal is None:fail('Scoring requires an agreed proposal',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type'];actor=action.get('actor');t=int(d['turn'])
    if kind in ('place','pass'):
        if d['phase']!='playing':fail('Play is suspended for scoring')
        if actor is not None and actor!=state['players'][t]['id']:fail('Wrong actor')
        if kind=='place':
            fields(p,dict(cell=dict(type='integer',minimum=0,maximum=80)),'/params');d['board']=place(d,int(p['cell']));d['history'].append(key(d['board']));d['passes']=0
        else:
            fields(p,{},'/params');d['passes']+=1
            if d['passes']==2:d['phase']='scoring'
        d['turn']=1-t;return d
    if kind not in ('propose_dead','accept_score','resume','resign'):fail('Unknown action')
    schema=dict(player=dict(type='integer',minimum=0,maximum=1))
    if kind=='propose_dead':schema['dead']=dict(type='array',minItems=0,maxItems=81,items=dict(type='integer',minimum=0,maximum=80))
    fields(p,schema,'/params');player=int(p['player'])
    if actor is not None and actor!=state['players'][player]['id']:fail('Wrong actor')
    if kind=='resign':d['resigned']=player;d['proposal']=None;d['phase']='finished';return d
    if d['phase']!='scoring':fail('Scoring decisions require two consecutive passes')
    if kind=='propose_dead':
        dead=set(p['dead'])
        if len(dead)!=len(p['dead']) or any(d['board'][int(i)]==-1 or not group(d['board'],int(i))<=dead for i in dead):fail('Propose whole occupied groups only')
        d['proposal']=dict(player=player,dead=sorted(dead));return d
    if kind=='resume':d['phase']='playing';d['passes']=0;d['proposal']=None;return d
    if d['proposal'] is None or d['proposal']['player']==player:fail('The opponent must accept the proposed dead groups')
    d['phase']='finished';return d

def area(d):
    b=d['board'][:]
    for i in d['proposal']['dead']:b[int(i)]=-1
    scores=[2*b.count(0),2*b.count(1)+15];seen=set()
    for i,v in enumerate(b):
        if v==-1 and i not in seen:
            g=group(b,i);seen|=g;owners={b[j] for k in g for j in neighbors(k) if b[j]!=-1}
            if len(owners)==1:scores[int(next(iter(owners)))]+=2*len(g)
    return scores

def legal(state):
    d=state['data']
    if d['phase']=='playing':
        actions=[dict(type='pass',params={})]+[dict(type='resign',params=dict(player=p)) for p in (0,1)]
        types=[dict(type='place',params_schema=dict(cell=dict(type='integer',minimum=0,maximum=80)),preconditions=['Empty intersection; capture adjacent opponent groups without liberties; own resulting group must have a liberty; resulting board must not occur in positional history.'],external_observations=[])]
    else:
        actions=[dict(type=k,params=dict(player=p)) for k in ('resume','resign') for p in (0,1)]
        if d['proposal'] is not None:actions.append(dict(type='accept_score',params=dict(player=1-d['proposal']['player'])))
        types=[dict(type='propose_dead',params_schema=dict(player=dict(type='integer',minimum=0,maximum=1),dead=dict(type='array',minItems=0,maxItems=81,items=dict(type='integer',minimum=0,maximum=80))),preconditions=['Distinct stones forming whole occupied groups; the opponent must accept before scoring.'],external_observations=['Players agree which groups are dead; disagreement resumes play.'])]
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(turn=d['turn']),completeness=False,reason='guarded_move_or_scoring_proposal')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';wins=[];scores=None
    if terminal:
        if d['resigned'] is not None:wins=[1-int(d['resigned'])]
        else:scores=area(d);wins=[p for p in (0,1) if scores[p]==max(scores)]
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if terminal else 'none',winners=[state['players'][p]['id'] for p in wins],losers=[state['players'][p]['id'] for p in (0,1) if p not in wins] if terminal else [],placements=[dict(player_id=state['players'][p]['id'],place=1+sum(v>scores[p] for v in scores),score=scores[p]) for p in (0,1)] if scores is not None else [],reason=('resignation' if d['resigned'] is not None else 'agreed_area_score') if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
