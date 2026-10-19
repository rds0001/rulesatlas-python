"""Singles side-out pickleball, best of three games to eleven by two."""
from copy import deepcopy
from ..values import fields,fail

def wins(d):
    result=[0,0]
    for score in d['games']:
        a,b=score
        if max(result)>=2 or max(a,b)<11 or (max(a,b)==11 and min(a,b)>9) or (max(a,b)>11 and abs(a-b)!=2):fail('Invalid completed game or play after match end',code='INVALID_STATE')
        result[0 if a>b else 1]+=1
    return result

def validate(d):
    w=wins(d);done=max(w)==2 or d['decision'] is not None
    if (d['phase']=='finished')!=done:fail('Match phase and result mismatch',code='INVALID_STATE')
    a,b=d['points']
    if max(a,b)>=11 and abs(a-b)>=2:fail('Completed current game must be closed',code='INVALID_STATE')
    if sum(sum(g) for g in d['games'])+a+b>d['rallies']:fail('Scored points exceed completed rallies',code='INVALID_STATE')
    if d['rallies']==0 and (d['games'] or d['points']!=[0,0] or d['server']!=d['first_server']):fail('Invalid pre-play service state',code='INVALID_STATE')
    if max(w)==2 and (d['points']!=[0,0] or d['decision'] is not None):fail('Completed match has stale points or duplicate decision',code='INVALID_STATE')
    if d['decision'] is not None and d['decision']['kind']=='walkover' and d['rallies']!=0:fail('Walkover requires no completed rally',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if kind=='choose_first_server':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params')
        if d['rallies']!=0:fail('Initial service choice is fixed once play begins')
        d['first_server']=p['player'];d['server']=p['player'];return d
    if kind=='end_match':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1),kind=dict(type='string',enum=['retirement','disqualification','walkover'])),'/params')
        if p['kind']=='walkover' and d['rallies']!=0:fail('Walkover requires no completed rally')
        d['decision']=deepcopy(p);d['phase']='finished';return d
    if kind=='replay':fields(p,{},'/params');return d
    if kind=='service_fault':fields(p,{},'/params');winner=1-int(d['server'])
    elif kind=='rally':fields(p,dict(winner=dict(type='integer',minimum=0,maximum=1)),'/params');winner=int(p['winner'])
    else:fail('Unknown action')
    d['rallies']+=1
    if winner!=d['server']:d['server']=winner;return d
    d['points'][winner]+=1
    if d['points'][winner]>=11 and d['points'][winner]-d['points'][1-winner]>=2:
        d['games'].append(d['points'][:]);d['points']=[0,0];d['server']=(d['first_server']+len(d['games']))%2
        if max(wins(d))==2:d['phase']='finished'
    return d

def legal(state):
    d=state['data'];kinds=['retirement','disqualification'];actions=[dict(type='replay',params={}),dict(type='service_fault',params={})]
    if d['rallies']==0:
        kinds.append('walkover');actions+=[dict(type='choose_first_server',params=dict(player=p)) for p in (0,1)]
    return dict(mode='event_types',actions=actions,action_types=[dict(type='rally',params_schema=dict(winner=dict(type='integer',minimum=0,maximum=1)),preconditions=['Adjudicated rally winner; only the server scores, otherwise service changes.'],external_observations=['Official rally result, including faults under the two-bounce, non-volley-zone and service rules.']),dict(type='end_match',params_schema=dict(player=dict(type='integer',minimum=0,maximum=1),kind=dict(type='string',enum=kinds)),preconditions=['Official match-ending decision names the losing player.'],external_observations=['Retirement, disqualification or pre-play walkover.'])],constraints=dict(server=d['server'],service_court='right' if d['points'][int(d['server'])]%2==0 else 'left',points=d['points']),completeness=False,reason='externally_adjudicated_rallies')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';decision=d['decision'];w=1-int(decision['player']) if decision else wins(d).index(2) if terminal else None
    return dict(status='terminal' if terminal else 'ongoing',result_kind=({'retirement':'technical','disqualification':'disqualification','walkover':'forfeit'}[decision['kind']] if decision else 'win') if terminal else 'none',winners=[state['players'][w]['id']] if terminal else [],losers=[state['players'][1-w]['id']] if terminal else [],placements=[],reason=decision['kind'] if decision else 'two_games_won' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
