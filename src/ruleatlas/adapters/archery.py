"""Recurve individual set match with externally adjudicated arrow values."""
from copy import deepcopy
from ..values import fields,fail

def set_points(d):
    scores=[0,0]
    for a,b in d['ends']:
        if max(scores)>=6:fail('Sets continued after match end',code='INVALID_STATE')
        if a==b:scores=[v+1 for v in scores]
        else:scores[0 if a>b else 1]+=2
    return scores

def validate(d):
    scores=set_points(d);decision=d['decision'];phase=d['phase'];shot_sizes=[len(x) for x in d['arrows']]
    if decision is not None:
        if (len(d['ends'])<5 and shot_sizes==[3,3]) or (len(d['ends'])==5 and (max(shot_sizes)>1 or shot_sizes==[1,1] and d['arrows'][0]!=d['arrows'][1])):fail('Official decision follows an already completed end or shoot-off',code='INVALID_STATE')
        if phase!='finished':fail('Official decision must finish the match',code='INVALID_STATE')
        if decision['kind']=='walkover' and (d['ends'] or any(d['arrows'])):fail('Walkover requires pre-play state',code='INVALID_STATE')
        if max(scores)>=6 or d['winner'] is not None:fail('Duplicate match-ending decisions',code='INVALID_STATE')
    elif max(scores)>=6:
        if phase!='finished' or any(d['arrows']) or d['winner']!=scores.index(max(scores)):fail('Completed set match has invalid outcome',code='INVALID_STATE')
    elif len(d['ends'])==5:
        if scores!=[5,5] or phase not in ('shoot_off','judge','finished') or max(shot_sizes)>1:fail('Shoot-off requires five tied set points each',code='INVALID_STATE')
        if phase=='shoot_off' and (shot_sizes==[1,1] or d['winner'] is not None):fail('Completed shoot-off arrows require a decision',code='INVALID_STATE')
        if phase=='judge' and (shot_sizes!=[1,1] or d['arrows'][0]!=d['arrows'][1] or d['winner'] is not None):fail('Closest-arrow judgment requires equal arrow scores',code='INVALID_STATE')
        if phase=='finished':
            if shot_sizes!=[1,1] or d['winner'] is None:fail('Shoot-off result is missing',code='INVALID_STATE')
            a,b=d['arrows'][0][0],d['arrows'][1][0]
            if a!=b and d['winner']!=(0 if a>b else 1):fail('Higher shoot-off arrow must win',code='INVALID_STATE')
    elif phase!='set' or shot_sizes==[3,3] or d['winner'] is not None:fail('Invalid ongoing set state',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if kind=='end_match':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1),kind=dict(type='string',enum=['retirement','disqualification','walkover'])),'/params')
        if p['kind']=='walkover' and (d['ends'] or any(d['arrows'])):fail('Walkover requires pre-play state')
        d['decision']=deepcopy(p);d['phase']='finished';return d
    if kind=='closest':
        fields(p,dict(winner=dict(type='integer',minimum=0,maximum=1,nullable=True)),'/params')
        if d['phase']!='judge':fail('Closest-arrow decision is only needed after tied shoot-off arrows')
        if p['winner'] is None:d['arrows']=[[],[]];d['phase']='shoot_off'
        else:d['winner']=p['winner'];d['phase']='finished'
        return d
    if kind!='arrow':fail('Unknown action')
    fields(p,dict(player=dict(type='integer',minimum=0,maximum=1),score=dict(type='integer',minimum=0,maximum=10)),'/params');t=int(p['player'])
    if d['phase'] not in ('set','shoot_off'):fail('Arrow scoring is suspended')
    limit=3 if d['phase']=='set' else 1
    if len(d['arrows'][t])>=limit:fail('This player has already completed the current end')
    d['arrows'][t].append(p['score'])
    if all(len(a)==limit for a in d['arrows']):
        if d['phase']=='set':
            d['ends'].append([sum(a) for a in d['arrows']]);d['arrows']=[[],[]];scores=set_points(d)
            if max(scores)>=6:d['winner']=scores.index(max(scores));d['phase']='finished'
            elif len(d['ends'])==5:d['phase']='shoot_off'
        else:
            a,b=d['arrows'][0][0],d['arrows'][1][0]
            if a==b:d['phase']='judge'
            else:d['winner']=0 if a>b else 1;d['phase']='finished'
    return d

def legal(state):
    d=state['data'];types=[]
    if d['phase'] in ('set','shoot_off'):
        limit=3 if d['phase']=='set' else 1
        types.append(dict(type='arrow',params_schema=dict(player=dict(type='integer',enum=[p for p in (0,1) if len(d['arrows'][p])<limit]),score=dict(type='integer',minimum=0,maximum=10)),preconditions=['Record one officially credited arrow, including zero for a miss or invalidated arrow.'],external_observations=['Adjudicated arrow value after applicable shooting violations.']))
    else:types.append(dict(type='closest',params_schema=dict(winner=dict(type='integer',minimum=0,maximum=1,nullable=True)),preconditions=['Equal shoot-off arrow values; null means equally close and repeats the shoot-off.'],external_observations=['Judge identifies the arrow closer to the center.']))
    kinds=['retirement','disqualification']
    if not d['ends'] and not any(d['arrows']):kinds.append('walkover')
    types.append(dict(type='end_match',params_schema=dict(player=dict(type='integer',minimum=0,maximum=1),kind=dict(type='string',enum=kinds)),preconditions=['Official match-ending decision names the losing player.'],external_observations=['Official retirement, disqualification or pre-play walkover.']))
    return dict(mode='event_types',actions=[],action_types=types,constraints=dict(set_points=set_points(d),phase=d['phase']),completeness=False,reason='externally_adjudicated_arrows')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';decision=d['decision'];w=1-int(decision['player']) if decision else d['winner']
    return dict(status='terminal' if terminal else 'ongoing',result_kind=({'retirement':'technical','disqualification':'disqualification','walkover':'forfeit'}[decision['kind']] if decision else 'win') if terminal else 'none',winners=[state['players'][int(w)]['id']] if terminal else [],losers=[state['players'][1-int(w)]['id']] if terminal else [],placements=[],reason=(decision['kind'] if decision else 'set_match_or_shoot_off_won') if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
