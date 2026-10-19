"""Singles Crossminton: best of five, sixteen by two, three-serve blocks."""
from copy import deepcopy
from ..values import fields,fail

def wins(d):
    result=[0,0]
    for a,b in d['games']:
        if max(result)>=3 or max(a,b)<16 or max(a,b)==16 and min(a,b)>14 or max(a,b)>16 and abs(a-b)!=2:fail('Invalid completed game or continuation after match end',code='INVALID_STATE')
        result[0 if a>b else 1]+=1
    return result

def first(d):
    if not d['games']:return int(d['first_server'])
    a,b=d['games'][-1];return 0 if a<b else 1

def server(d):
    total=sum(d['points']);block=(total-30)%2 if min(d['points'])>=15 else (total//3)%2
    return (first(d)+block)%2

def validate(d):
    w=wins(d);decision=d['decision'];finished=max(w)==3 or decision is not None
    if (d['phase']=='finished')!=finished:fail('Match phase and result mismatch',code='INVALID_STATE')
    a,b=d['points']
    if max(a,b)>=16 and abs(a-b)>=2:fail('Completed current game must be closed',code='INVALID_STATE')
    if max(w)==3 and (d['points']!=[0,0] or decision is not None):fail('Finished match has stale points or duplicate decision',code='INVALID_STATE')
    if decision is not None and decision['kind']=='walkover' and (d['games'] or sum(d['points'])):fail('Walkover requires pre-play state',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if kind=='choose_first_server':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params')
        if d['games'] or sum(d['points']):fail('Initial service must be chosen before play')
        d['first_server']=p['player'];return d
    if kind=='end_match':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1),kind=dict(type='string',enum=['retirement','disqualification','walkover'])),'/params')
        if p['kind']=='walkover' and (d['games'] or sum(d['points'])):fail('Walkover requires pre-play state')
        d['decision']=deepcopy(p);d['phase']='finished';return d
    if kind=='replay':fields(p,{},'/params');return d
    if kind=='service_fault':fields(p,{},'/params');winner=1-server(d)
    elif kind=='rally':fields(p,dict(winner=dict(type='integer',minimum=0,maximum=1)),'/params');winner=int(p['winner'])
    else:fail('Unknown action')
    d['points'][winner]+=1
    if d['points'][winner]>=16 and d['points'][winner]-d['points'][1-winner]>=2:
        d['games'].append(d['points'][:]);d['points']=[0,0]
        if max(wins(d))==3:d['phase']='finished'
    return d

def legal(state):
    d=state['data'];actions=[dict(type='replay',params={}),dict(type='service_fault',params={})];kinds=['retirement','disqualification']
    if not d['games'] and not sum(d['points']):
        actions+=[dict(type='choose_first_server',params=dict(player=p)) for p in (0,1)];kinds.append('walkover')
    return dict(mode='event_types',actions=actions,action_types=[dict(type='rally',params_schema=dict(winner=dict(type='integer',minimum=0,maximum=1)),preconditions=['Rally is officially awarded to the indicated player.'],external_observations=['Observed rally result or adjudicated fault.']),dict(type='end_match',params_schema=dict(player=dict(type='integer',minimum=0,maximum=1),kind=dict(type='string',enum=kinds)),preconditions=['Official match-ending decision identifies the losing player.'],external_observations=['Retirement, disqualification or pre-play walkover.'])],constraints=dict(server=server(d),service_block_size=1 if min(d['points'])>=15 else 3,deciding_game_end_changes=sum(d['points'])//6 if len(d['games'])==4 else 0),completeness=False,reason='externally_adjudicated_rallies')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';decision=d['decision'];w=1-int(decision['player']) if decision else wins(d).index(3) if terminal else None
    return dict(status='terminal' if terminal else 'ongoing',result_kind=({'retirement':'technical','disqualification':'disqualification','walkover':'forfeit'}[decision['kind']] if decision else 'win') if terminal else 'none',winners=[state['players'][w]['id']] if terminal else [],losers=[state['players'][1-w]['id']] if terminal else [],placements=[],reason=decision['kind'] if decision else 'three_games_won' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
