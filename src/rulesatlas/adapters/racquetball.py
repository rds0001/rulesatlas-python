"""Traditional singles racquetball: side-out games 15, 15, 11, two serves."""
from copy import deepcopy
from ..values import fields,fail

def wins(d):
    w=[0,0]
    for i,(a,b) in enumerate(d['games']):
        target=11 if i==2 else 15
        if max(w)>=2 or max(a,b)!=target or min(a,b)>=target:fail('Invalid completed game',code='INVALID_STATE')
        w[0 if a>b else 1]+=1
    return w

def game_server(d):
    n=len(d['games'])
    if n<2:return (int(d['first_server'])+n)%2
    totals=[sum(g[p] for g in d['games'][:2]) for p in (0,1)]
    return None if totals[0]==totals[1] else 0 if totals[0]>totals[1] else 1

def validate(d):
    w=wins(d);done=max(w)==2 or d['decision'] is not None
    if (d['phase']=='finished')!=done:fail('Match phase and outcome mismatch',code='INVALID_STATE')
    target=11 if len(d['games'])==2 else 15
    if max(d['points'])>=target:fail('Completed game must be closed',code='INVALID_STATE')
    if sum(sum(g) for g in d['games'])+sum(d['points'])>d['rallies']:fail('Points exceed completed rallies',code='INVALID_STATE')
    if not d['started'] and (d['rallies'] or d['faults'] or d['games'] or d['server']!=d['first_server']):fail('Invalid pre-play state',code='INVALID_STATE')
    if d['phase']=='choose_server' and (len(d['games'])!=2 or game_server(d) is not None or d['points']!=[0,0] or d['faults']):fail('Service choice is only for a tied aggregate before game three',code='INVALID_STATE')
    if max(w)==2 and (d['points']!=[0,0] or d['faults'] or d['decision'] is not None):fail('Completed match cannot retain current points, faults or a second decision',code='INVALID_STATE')
    if d['decision'] is not None and d['decision']['kind']=='walkover' and d['started']:fail('Walkover requires no play',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type']
    if k in ('choose_first_server','choose_tiebreak_server'):
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params')
        if k=='choose_first_server':
            if d['started']:fail('Choose the initial server before play')
            d['first_server']=p['player']
        elif d['phase']!='choose_server':fail('Tiebreak server choice requires equal aggregate points')
        d['server']=p['player'];d['phase']='playing';return d
    if k=='end_match':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1),kind=dict(type='string',enum=['retirement','disqualification','walkover'])),'/params')
        if p['kind']=='walkover' and d['started']:fail('Walkover requires no play')
        d['decision']=deepcopy(p);d['phase']='finished';return d
    if d['phase']!='playing':fail('Choose the tiebreak server before play')
    if k=='replay':fields(p,{},'/params');d['faults']=0;d['started']=True;return d
    if k=='service_fault':
        fields(p,{},'/params');d['started']=True
        if d['faults']==0:d['faults']=1;return d
        winner=1-int(d['server'])
    elif k=='out_serve':fields(p,{},'/params');winner=1-int(d['server'])
    elif k=='rally':fields(p,dict(winner=dict(type='integer',minimum=0,maximum=1)),'/params');winner=int(p['winner'])
    else:fail('Unknown action')
    d['started']=True;d['faults']=0;d['rallies']+=1
    if winner!=d['server']:d['server']=winner;return d
    d['points'][winner]+=1;target=11 if len(d['games'])==2 else 15
    if d['points'][winner]==target:
        d['games'].append(d['points'][:]);d['points']=[0,0]
        if max(wins(d))==2:d['phase']='finished'
        else:
            server=game_server(d)
            if server is None:d['phase']='choose_server'
            else:d['server']=server
    return d

def legal(state):
    d=state['data'];actions=[];types=[];kinds=['retirement','disqualification']
    if not d['started']:
        kinds.append('walkover');actions+=[dict(type='choose_first_server',params=dict(player=p)) for p in (0,1)]
    if d['phase']=='choose_server':actions+=[dict(type='choose_tiebreak_server',params=dict(player=p)) for p in (0,1)]
    else:
        actions += [dict(type=k,params={}) for k in ('service_fault','out_serve','replay')]
        types.append(dict(type='rally',params_schema=dict(winner=dict(type='integer',minimum=0,maximum=1)),preconditions=['Official rally winner; only the server scores.'],external_observations=['Adjudicated rally, including court, contact and avoidable-hinder decisions.']))
    types.append(dict(type='end_match',params_schema=dict(player=dict(type='integer',minimum=0,maximum=1),kind=dict(type='string',enum=kinds)),preconditions=['Official match-ending decision identifies the losing player.'],external_observations=['Retirement, disqualification or pre-play walkover.']))
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(server=d['server'],serve_attempt=1+d['faults'],target=11 if len(d['games'])==2 else 15),completeness=False,reason='externally_adjudicated_rallies_and_serve_faults')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';decision=d['decision'];w=1-int(decision['player']) if decision else wins(d).index(2) if done else None
    return dict(status='terminal' if done else 'ongoing',result_kind=({'retirement':'technical','disqualification':'disqualification','walkover':'forfeit'}[decision['kind']] if decision else 'win') if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[],reason=decision['kind'] if decision else 'two_games_won' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
