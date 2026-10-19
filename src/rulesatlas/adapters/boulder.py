"""Five-problem qualification-style bouldering: attempts, zones, tops and ranks."""
from copy import deepcopy
from ..values import fields,fail

def cell(d):return d['results'][int(d['current'])%2][int(d['current'])//2]
def advance(d):
    while d['current']<10:
        c=cell(d)
        if d['disqualified'][int(d['current'])%2]:c['closed']=True;c['active']=False
        if not c['closed']:break
        d['current']+=1

def validate(d):
    for player,row in enumerate(d['results']):
        for problem,c in enumerate(row):
            index=problem*2+player
            if c['closed']!=(index<d['current']):fail('Problem order mismatch',code='INVALID_STATE')
            if c['active'] and (index!=d['current'] or c['attempts']==0):fail('Invalid active attempt',code='INVALID_STATE')
            for key in ('zone_attempt','top_attempt'):
                if c[key] is not None and not 1<=c[key]<=c['attempts']:fail('Scoring attempt is outside the attempt count',code='INVALID_STATE')
            if c['top_attempt'] is not None and (not c['closed'] or c['zone_attempt'] is None or c['zone_attempt']>c['top_attempt']):fail('Top and zone state mismatch',code='INVALID_STATE')
            if index>d['current'] and (c['attempts'] or c['zone_attempt'] is not None or c['top_attempt'] is not None):fail('Future problem has attempts',code='INVALID_STATE')
    if d['current']<10 and d['disqualified'][int(d['current'])%2]:fail('Disqualified climber must be skipped',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if kind=='disqualify':
        fields(p,{'player':{'type':'integer','minimum':0,'maximum':1}},'/params');t=int(p['player'])
        if d['disqualified'][t]:fail('Climber is already disqualified')
        d['disqualified'][t]=True;advance(d);return d
    fields(p,{},'/params');c=cell(d);t=int(d['current'])%2
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if kind=='start_attempt':
        if c['active']:fail('An attempt is already active')
        c['attempts']+=1;c['active']=True
    elif kind in ('record_zone','record_top','fail_attempt'):
        if not c['active']:fail('An active attempt is required')
        if kind=='record_zone':
            if c['zone_attempt'] is not None:fail('Zone has already been recorded')
            c['zone_attempt']=c['attempts']
        elif kind=='record_top':
            if c['zone_attempt'] is None:c['zone_attempt']=c['attempts']
            c['top_attempt']=c['attempts'];c['closed']=True;c['active']=False
        else:c['active']=False
    elif kind=='end_problem':c['closed']=True;c['active']=False
    else:fail('Unknown action')
    advance(d);return d

def score(row):
    tops=sum(c['top_attempt'] is not None for c in row);zones=sum(c['zone_attempt'] is not None for c in row)
    ta=sum(c['top_attempt'] or 0 for c in row);za=sum(c['zone_attempt'] or 0 for c in row)
    return (-tops,-zones,ta,za)
def legal(state):
    d=state['data'];c=cell(d);kinds=['end_problem']
    if c['active']:
        kinds+=['fail_attempt','record_top']
        if c['zone_attempt'] is None:kinds+=['record_zone']
    else:kinds+=['start_attempt']
    types=[dict(type=k,params_schema={},preconditions=['The current attempt and problem must permit the event.'],external_observations=['Official attempt, controlled hold, failure or end of climbing period.']) for k in kinds]
    types.append(dict(type='disqualify',params_schema={'player':{'type':'integer','minimum':0,'maximum':1}},preconditions=['Climber is not already disqualified.'],external_observations=['Official disciplinary decision.']))
    return dict(mode='event_types',actions=[],action_types=types,constraints={'player':int(d['current'])%2,'problem':int(d['current'])//2},completeness=False,reason='externally_adjudicated_climbing_events')
def outcome(state,pack):
    d=state['data'];terminal=d['current']==10;eligible=sorted((score(row),i) for i,row in enumerate(d['results']) if not d['disqualified'][i]) if terminal else []
    winners=[state['players'][i]['id'] for s,i in eligible if s==eligible[0][0]] if eligible else []
    places=[dict(player_id=state['players'][i]['id'],place=1+sum(other<s for other,_ in eligible),tops=-s[0],zones=-s[1],top_attempts=s[2],zone_attempts=s[3]) for s,i in eligible]
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('ranking' if eligible else 'no_contest') if terminal else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=places,reason='qualification_round_completed' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
