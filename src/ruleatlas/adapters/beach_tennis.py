"""Singles beach tennis: no-ad games and one service attempt per point."""
from copy import deepcopy
from ..values import fields,fail
from .tennis import counts,next_server,outcome as tennis_outcome
PLAYER=dict(type='integer',minimum=0,maximum=1)
def server(d):return (next_server(d)+d['first_server'])%2
def validate(d):
    wins=counts(d);finished=max(wins)==2;tie=d['games']==[6,6];p=d['points'];g=d['games'];decision=d['decision']
    if d['phase']!=('finished' if finished or decision is not None else 'tiebreak' if tie else 'game'):fail('Scoring phase mismatch',code='INVALID_STATE')
    if not tie and max(g)>=6 and abs(g[0]-g[1])>=2:fail('Unclosed completed set',code='INVALID_STATE')
    if tie:
        if max(p)>=7 and abs(p[0]-p[1])>=2:fail('Unclosed completed tiebreak',code='INVALID_STATE')
    elif max(p)>3:fail('No-ad games never retain an advantage point',code='INVALID_STATE')
    if d['server']!=server(d):fail('Incorrect service order',code='INVALID_STATE')
    if finished and (decision is not None or g!=[0,0] or p!=[0,0]):fail('Completed match must have reset current scores',code='INVALID_STATE')
    if not d['started'] and (d['sets'] or any(g) or any(p)):fail('Scored play requires a started match',code='INVALID_STATE')
    if decision is not None and decision['kind']=='walkover' and d['started']:fail('Walkover is unavailable after play starts',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type']
    if k=='choose_first_server':
        fields(p,dict(player=PLAYER),'/params')
        if d['started']:fail('Choose initial service before play')
        d['first_server']=p['player'];d['server']=p['player'];return d
    if k=='end_match':
        fields(p,dict(kind=dict(type='string',enum=['retirement','disqualification','walkover']),player=PLAYER),'/params')
        if p['kind']=='walkover' and d['started']:fail('Walkover is unavailable after play starts')
        d['decision']=p.copy();d['phase']='finished';return d
    if k=='replay':fields(p,{},'/params');d['started']=True;return d
    if k=='service_fault':fields(p,{},'/params');winner=1-d['server']
    elif k=='rally':fields(p,dict(winner=PLAYER),'/params');winner=p['winner']
    else:fail('Unknown action')
    d['started']=True;d['points'][winner]+=1
    if d['phase']=='tiebreak':
        if d['points'][winner]>=7 and d['points'][winner]-d['points'][1-winner]>=2:
            score=[6,6];score[winner]=7;d['sets'].append(score);d['games']=[0,0];d['points']=[0,0];d['phase']='game'
    elif d['points'][winner]==4:
        d['games'][winner]+=1;d['points']=[0,0]
        if d['games'][winner]>=6 and d['games'][winner]-d['games'][1-winner]>=2:d['sets'].append(d['games'][:]);d['games']=[0,0]
        elif d['games']==[6,6]:d['phase']='tiebreak'
    if max(counts(d))==2:d['phase']='finished'
    d['server']=server(d);return d
def legal(state):
    d=state['data'];types=[dict(type='rally',params_schema=dict(winner=PLAYER),preconditions=['Match is ongoing.'],external_observations=['Officially awarded rally winner.']),dict(type='service_fault',params_schema={},preconditions=['Only one service attempt per point; a fault awards the receiver the point.'],external_observations=['Adjudicated service fault; net contact alone on an otherwise valid service is not a fault.']),dict(type='replay',params_schema={},preconditions=['Official replay for external interference; no automatic service-net let.'],external_observations=['Official replay decision.']),dict(type='end_match',params_schema=dict(kind=dict(type='string',enum=['retirement','disqualification']+([] if d['started'] else ['walkover'])),player=PLAYER),preconditions=['Walkover only before play.'],external_observations=['Official match-ending decision.'])]
    if not d['started']:types.append(dict(type='choose_first_server',params_schema=dict(player=PLAYER),preconditions=['Before play begins.'],external_observations=['Initial service choice.']))
    played=sum(d['games'])
    return dict(mode='event_types',actions=[],action_types=types,constraints=dict(server=d['server'],service_attempts=1,deciding_point=d['phase']=='game' and d['points']==[3,3],current_set_end_changes=(played+1)//2+(sum(d['points'])//6 if d['phase']=='tiebreak' else 0)),completeness=False,reason='externally_adjudicated_rallies')
def outcome(state,pack):return tennis_outcome(state,pack)
