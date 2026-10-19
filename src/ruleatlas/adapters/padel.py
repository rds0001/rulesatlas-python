"""Doubles padel with advantage scoring and fixed within-set service/receive order."""
from copy import deepcopy
from ..values import fields,fail
from . import tennis
PLAYER=dict(type='integer',minimum=0,maximum=1)
def service(d):
    first=(sum(sum(s) for s in d['sets'])+d['first_team'])%2
    n=sum(d['games'])+((sum(d['points'])+1)//2 if d['phase']=='tiebreak' else 0)
    team=(first+n)%2
    member=(d['first_members'][team]+n//2)%2
    receiver=(d['right_receivers'][1-team]+sum(d['points'])%2)%2
    return team,2*team+member,2*(1-team)+receiver

def validate(d):
    normalized=deepcopy(d);normalized['server']=tennis.next_server(d);tennis.validate(normalized)
    if d['server']!=service(d)[0]:fail('Incorrect serving team',code='INVALID_STATE')
    if not d['started'] and (d['sets'] or any(d['games']) or any(d['points']) or d['faults'] or d['set_started']):fail('Play data requires a started match',code='INVALID_STATE')
    if not d['set_started'] and (any(d['games']) or any(d['points']) or d['faults']):fail('Current-set play requires a started set',code='INVALID_STATE')
    if d['set_started'] and not all(d['configured']):fail('Both pairs must fix service and receiving order before play',code='INVALID_STATE')
    if d['decision'] is not None and d['decision']['kind']=='walkover' and d['started']:fail('Walkover is unavailable after play starts',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);k=action['type'];p=action['params']
    if k=='choose_first_team':
        fields(p,dict(team=PLAYER),'/params')
        if d['started']:fail('Choose initial serving team before play')
        d['first_team']=p['team'];d['server']=service(d)[0];return d
    if k=='configure_pair':
        fields(p,dict(team=PLAYER,first_server=PLAYER,right_receiver=PLAYER),'/params');t=p['team']
        if d['set_started'] or d['configured'][t]:fail('Each pair fixes its order once before the current set starts')
        d['first_members'][t]=p['first_server'];d['right_receivers'][t]=p['right_receiver'];d['configured'][t]=True;return d
    if k=='end_match':
        fields(p,dict(kind=dict(type='string',enum=['retirement','disqualification','walkover']),player=PLAYER),'/params')
        if p['kind']=='walkover' and d['started']:fail('Walkover is unavailable after play starts')
        d['decision']=p.copy();d['phase']='finished';return d
    if not all(d['configured']):fail('Both pairs must configure their order before play')
    d['started']=True;d['set_started']=True
    if k=='service_let':fields(p,{},'/params');return d
    if k=='replay':fields(p,{},'/params');d['faults']=0;return d
    if k=='service_fault':
        fields(p,{},'/params')
        if not d['faults']:d['faults']=1;return d
        winner=1-d['server']
    elif k=='rally':fields(p,dict(winner=PLAYER),'/params');winner=p['winner']
    else:fail('Unknown action')
    before=len(d['sets']);d=tennis.apply(dict(state,data=d),dict(type='award_point',params=dict(player=winner)));d['faults']=0
    if len(d['sets'])>before and d['phase']!='finished':d['set_started']=False;d['configured']=[False,False]
    d['server']=service(d)[0];return d

def legal(state):
    d=state['data'];types=[];empty={}
    if not d['started']:types.append(dict(type='choose_first_team',params_schema=dict(team=PLAYER),preconditions=['Before the match starts.'],external_observations=['Initial service choice.']))
    if not d['set_started']:
        types.append(dict(type='configure_pair',params_schema=dict(team=PLAYER,first_server=PLAYER,right_receiver=PLAYER),preconditions=['Each pair chooses once before each set. Member indices are zero or one within the pair.'],external_observations=['Pair service order and right-court receiver choice.']))
    if all(d['configured']):
        for kind,params,obs in [('rally',dict(winner=PLAYER),'Officially awarded rally winner.'),('service_fault',empty,'Adjudicated service fault; the second fault loses the point.'),('service_let',empty,'Official service let repeats that service attempt, preserving any first fault.'),('replay',empty,'Official replay of the whole point restores first service.')]:types.append(dict(type=kind,params_schema=params,preconditions=['Both pairs have configured the current set.'],external_observations=[obs]))
    types.append(dict(type='end_match',params_schema=dict(kind=dict(type='string',enum=['retirement','disqualification']+([] if d['started'] else ['walkover'])),player=PLAYER),preconditions=['Walkover only before play.'],external_observations=['Official match-ending decision.']))
    team,member,receiver=service(d)
    return dict(mode='event_types',actions=[],action_types=types,constraints=dict(serving_team=team,server_member=member,receiver_member=receiver,next_service_attempt=d['faults']+1,pairs_configured=d['configured'],service_court='right' if sum(d['points'])%2==0 else 'left',current_set_end_changes=(sum(d['games'])+1)//2+(sum(d['points'])//6 if d['phase']=='tiebreak' else 0)),completeness=False,reason='externally_adjudicated_rallies_and_pair_order')
def outcome(state,pack):return tennis.outcome(state,pack)
