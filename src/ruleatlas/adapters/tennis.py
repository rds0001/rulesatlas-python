"""Externally adjudicated singles points, advantage games and tiebreak sets."""
from copy import deepcopy
from ..values import fail,fields


def set_winner(score):
    a,b=score
    if (max(a,b)==6 and min(a,b)<=4) or (max(a,b)==7 and min(a,b) in (5,6)):
        return 0 if a>b else 1
    fail('Invalid completed set score',code='INVALID_STATE')


def counts(data):
    wins=[0,0]
    for score in data['sets']:
        if max(wins)==2: fail('Sets continued after match end',code='INVALID_STATE')
        wins[set_winner(score)]+=1
    return wins


def next_server(data):
    first=(sum(sum(score) for score in data['sets'])+sum(data['games']))%2
    if data['games']==[6,6]:
        total=sum(data['points'])
        return (first+(0 if total==0 else ((total+1)//2)%2))%2
    return first


def validate(data):
    wins=counts(data); games=data['games']; points=data['points']; decision=data['decision']
    finished=max(wins)==2
    tie=games==[6,6]
    expected='finished' if finished or decision is not None else 'tiebreak' if tie else 'game'
    if data['phase']!=expected: fail('Scoring phase mismatch',code='INVALID_STATE')
    if not tie and max(games)>=6 and abs(games[0]-games[1])>=2: fail('Unclosed completed set',code='INVALID_STATE')
    if tie:
        if max(points)>=7 and abs(points[0]-points[1])>=2: fail('Unclosed completed tiebreak',code='INVALID_STATE')
    elif max(points)>4 or (max(points)==4 and sorted(points)!=[3,4]): fail('Invalid advantage score',code='INVALID_STATE')
    if data['server']!=next_server(data): fail('Incorrect service order',code='INVALID_STATE')
    if finished and (decision is not None or games!=[0,0] or points!=[0,0]): fail('Invalid completed match',code='INVALID_STATE')
    if decision is not None and decision['kind']=='walkover' and (data['sets'] or games!=[0,0] or points!=[0,0]): fail('Walkover requires pre-play state',code='INVALID_STATE')


def outcome(state,pack):
    data=state['data']; wins=counts(data); decision=data['decision']; terminal=data['phase']=='finished'
    w=(1-int(decision['player'])) if decision else wins.index(2) if terminal else None
    kind={'retirement':'technical','disqualification':'disqualification','walkover':'forfeit'}[decision['kind']] if decision else 'win' if terminal else 'none'
    return dict(status='terminal' if terminal else 'ongoing',result_kind=kind,winners=[] if w is None else [state['players'][w]['id']],losers=[] if w is None else [state['players'][1-w]['id']],placements=[],reason=decision['kind'] if decision else 'two_sets_won' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)


def apply(state,action):
    data=deepcopy(state['data']); params=action['params']
    if action['type']=='end_match':
        fields(params,{'kind':{'type':'enum','values':['retirement','disqualification','walkover']},'player':{'type':'integer','minimum':0,'maximum':1}},'/params')
        data['decision']=deepcopy(params); data['phase']='finished'
        validate(data); return data
    if action['type']!='award_point': fail('Unknown action')
    fields(params,{'player':{'type':'integer','minimum':0,'maximum':1}},'/params')
    player=int(params['player']); points=data['points']; points[player]+=1
    if data['phase']=='tiebreak':
        if points[player]>=7 and points[player]-points[1-player]>=2:
            score=[6,6]; score[player]=7; data['sets'].append(score)
            data['games']=[0,0]; data['points']=[0,0]; data['phase']='game'
    elif points[player]>=4 and points[player]-points[1-player]>=2:
        data['games'][player]+=1; data['points']=[0,0]
        games=data['games']
        if games[player]>=6 and games[player]-games[1-player]>=2:
            data['sets'].append(list(games)); data['games']=[0,0]
        elif games==[6,6]: data['phase']='tiebreak'
    elif points==[4,4]: data['points']=[3,3]
    if max(counts(data))==2: data['phase']='finished'
    data['server']=next_server(data)
    return data


def legal(state):
    data=state['data']; kinds=['retirement','disqualification']
    if not data['sets'] and data['games']==[0,0] and data['points']==[0,0]: kinds.append('walkover')
    return dict(mode='event_types',actions=[],action_types=[
        dict(type='award_point',params_schema={'player':{'type':'integer','minimum':0,'maximum':1}},preconditions=['Match is ongoing.'],external_observations=['An adjudicator has awarded this point to the specified participant.']),
        dict(type='end_match',params_schema={'kind':{'type':'enum','values':kinds},'player':{'type':'integer','minimum':0,'maximum':1}},preconditions=['Match is ongoing; walkover is permitted only before play.'],external_observations=['An official match-ending decision identifies the losing participant.'])],constraints={'server':data['server'],'phase':data['phase']},completeness=False,reason='externally_adjudicated_events')
