"""Six-player vanilla Mafia: host-resolved night choice and majority daytime vote."""
from copy import deepcopy
from ..values import fields,fail
def faction(d):
    if not d['roles']:return None
    mafia=sum(alive and role=='mafia' for alive,role in zip(d['alive'],d['roles']));town=sum(alive and role=='town' for alive,role in zip(d['alive'],d['roles']))
    return 'town' if mafia==0 else 'mafia' if mafia>=town else None
def validate(d):
    if d['phase']=='setup':
        if d['roles'] or not all(d['alive']) or d['day']!=0 or any(v!=-2 for v in d['votes']):fail('Unconfigured game contains play',code='INVALID_STATE')
        return
    if len(d['roles'])!=6 or d['roles'].count('mafia')!=2 or d['day']<1:fail('Six players require two mafia and four townspeople',code='INVALID_STATE')
    if (d['phase']=='finished')!=(faction(d) is not None):fail('Faction result and phase mismatch',code='INVALID_STATE')
    if d['phase']!='vote':
        if any(v!=-2 for v in d['votes']):fail('Votes remain outside the voting phase',code='INVALID_STATE')
    else:
        for p,v in enumerate(d['votes']):
            if not d['alive'][p] and v!=-2 or v>=0 and not d['alive'][int(v)]:fail('A dead participant cannot vote or receive a vote',code='INVALID_STATE')
        if all(v!=-2 for p,v in enumerate(d['votes']) if d['alive'][p]):fail('Completed votes must resolve',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if d['phase']=='setup':
        if kind!='assign_roles':fail('Assign roles first')
        fields(p,dict(roles=dict(type='array',minItems=6,maxItems=6,items=dict(type='string',enum=['mafia','town']))),'/params')
        if p['roles'].count('mafia')!=2:fail('Exactly two mafia members are required')
        d['roles']=deepcopy(p['roles']);d['phase']='night';d['day']=1;return d
    if d['phase']=='night':
        if kind!='night_choice':fail('Resolve the night choice first')
        fields(p,dict(target=dict(type='integer',minimum=0,maximum=5,nullable=True)),'/params');target=p['target']
        if action.get('actor') is not None and not any(player['id']==action['actor'] and d['alive'][i] and d['roles'][i]=='mafia' for i,player in enumerate(state['players'])):fail('Only living mafia can submit the night choice')
        if target is not None:
            target=int(target)
            if not d['alive'][target] or d['roles'][target]=='mafia':fail('Night target must be a living townsperson')
            d['alive'][target]=False
        d['phase']='finished' if faction(d) else 'vote';return d
    if kind!='vote':fail('Submit daytime votes')
    fields(p,dict(player=dict(type='integer',minimum=0,maximum=5),target=dict(type='integer',minimum=-1,maximum=5)),'/params');t=int(p['player']);target=int(p['target'])
    if not d['alive'][t] or d['votes'][t]!=-2:fail('Voter is dead or already voted')
    if target>=0 and not d['alive'][target]:fail('Vote target must be alive')
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    d['votes'][t]=target
    if all(v!=-2 for i,v in enumerate(d['votes']) if d['alive'][i]):
        living=sum(d['alive']);counts=[d['votes'].count(i) for i in range(6)];target=next((i for i,n in enumerate(counts) if n>living/2),None)
        if target is not None:d['alive'][target]=False
        d['votes']=[-2]*6
        if faction(d):d['phase']='finished'
        else:d['day']+=1;d['phase']='night'
    return d
def legal(state):
    d=state['data']
    if d['phase']=='setup':return dict(mode='event_types',actions=[],action_types=[dict(type='assign_roles',params_schema=dict(roles=dict(type='array',minItems=6,maxItems=6,items=dict(type='string',enum=['mafia','town']))),preconditions=['Exactly two mafia and four townspeople.'],external_observations=['Supplied secret roles.'])],constraints={},completeness=False,reason='external_role_assignment')
    if d['phase']=='night':return [dict(type='night_choice',params=dict(target=t)) for t in [None]+[i for i in range(6) if d['alive'][i] and d['roles'][i]=='town']]
    return [dict(type='vote',params=dict(player=p,target=t)) for p in range(6) if d['alive'][p] and d['votes'][p]==-2 for t in [-1]+[i for i in range(6) if d['alive'][i]]]
def outcome(state,pack):
    d=state['data'];winner=faction(d);terminal=winner is not None
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if terminal else 'none',winners=[state['players'][i]['id'] for i,r in enumerate(d['roles']) if r==winner] if terminal else [],losers=[state['players'][i]['id'] for i,r in enumerate(d['roles']) if r!=winner] if terminal else [],placements=[],reason='mafia_eliminated' if winner=='town' else 'mafia_reached_parity' if winner=='mafia' else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
