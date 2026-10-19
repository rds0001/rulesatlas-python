"""Adjudicated sumo bout administration without physical-state modeling."""
from copy import deepcopy
from ..values import fields,fail
DECISION=dict(winner=dict(type='integer',minimum=0,maximum=1),reason=dict(type='string',enum=['out_of_ring','ground_contact','forbidden_action','forfeit']))
def validate(d):
    if (d['phase'] in ('provisional','review','finished'))!=(d['decision'] is not None):fail('Decision and bout phase mismatch',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type'];phase=d['phase']
    if kind in ('declare','overturn'):
        fields(p,DECISION,'/params')
        if kind=='overturn':
            if phase!='review':fail('Overturning requires an official review')
        elif phase not in ('ready','active','paused') or p['reason'] in ('out_of_ring','ground_contact') and phase!='active':fail('This decision is not permitted in the current bout phase')
        d['decision']=deepcopy(p);d['phase']='provisional' if kind=='declare' else 'review';return d
    fields(p,{},'/params')
    transitions=dict(start=('ready','active'),pause=('active','paused'),resume=('paused','active'),request_review=('provisional','review'))
    if kind in transitions:
        expected,target=transitions[kind]
        if phase!=expected:fail('Action is not permitted in this bout phase')
        d['phase']=target;return d
    if kind=='false_start':
        if phase!='active':fail('A false-start ruling requires an active start')
        d['false_starts']+=1;d['phase']='ready';return d
    if kind=='rematch':
        if phase!='review':fail('A rematch requires an official review')
        d['rematches']+=1;d['decision']=None;d['phase']='ready';return d
    if kind=='confirm':
        if phase not in ('provisional','review'):fail('There is no decision to confirm')
        d['phase']='finished';return d
    fail('Unknown action')
def legal(state):
    phase=state['data']['phase'];schemas={}
    if phase=='ready':schemas=dict(start={},declare=DECISION)
    elif phase=='active':schemas=dict(false_start={},pause={},declare=DECISION)
    elif phase=='paused':schemas=dict(resume={},declare=DECISION)
    elif phase=='provisional':schemas=dict(request_review={},confirm={})
    elif phase=='review':schemas=dict(overturn=DECISION,rematch={},confirm={})
    return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Physical winning observations require active play; review actions require a provisional decision.'],external_observations=['Official start, false start, interruption, winning ruling or judges’ review.']) for k,v in schemas.items()],constraints=dict(phase=phase),completeness=False,reason='externally_adjudicated_bout')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';w=int(d['decision']['winner']) if terminal else None;reason=d['decision']['reason'] if terminal else 'awaiting_confirmation' if d['phase'] in ('provisional','review') else 'ongoing'
    return dict(status='terminal' if terminal else 'ongoing',result_kind=({'forfeit':'forfeit','forbidden_action':'disqualification'}.get(reason,'win')) if terminal else 'none',winners=[state['players'][w]['id']] if terminal else [],losers=[state['players'][1-w]['id']] if terminal else [],placements=[],reason=reason,evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
