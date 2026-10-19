"""Singles rally scoring with sport-specific game and service rules."""
from copy import deepcopy
from ..values import fail,fields
PLAYER={'type':'integer','minimum':0,'maximum':1}
DECISIONS=['retirement','disqualification','walkover']

def game_winner(score,sport):
    high,low=max(score),min(score)
    valid=(high==11 and low<=9) or (high>11 and high-low==2) if sport=='table_tennis' else ((high==21 and low<=19) or (22<=high<=29 and high-low==2) or (high==30 and low in (28,29)))
    if not valid: fail('Invalid completed game score',code='INVALID_STATE')
    return 0 if score[0]>score[1] else 1

def counts(data,sport):
    target=3 if sport=='table_tennis' else 2;wins=[0,0]
    for score in data['games']:
        if max(wins)==target: fail('Games continued after match end',code='INVALID_STATE')
        wins[game_winner(score,sport)]+=1
    return wins

def tt_server(data):
    total=sum(data['points']);base=len(data['games'])%2;exp=data['expedite']
    if exp is not None:
        if exp['game_index']==len(data['games']): return (exp['server']+total-exp['point_total'])%2
        return (base+total)%2
    return (base+(total//2 if min(data['points'])<10 else total))%2

def won(points,sport):
    high,low=max(points),min(points)
    return (high>=11 and high-low>=2) if sport=='table_tennis' else ((high>=21 and high-low>=2) or high==30)

def validate(data,sport):
    target=3 if sport=='table_tennis' else 2;wins=counts(data,sport);finished=max(wins)==target
    points=data['points'];decision=data['decision']
    if data['phase']!=('finished' if finished or decision is not None else 'game'): fail('Scoring phase mismatch',code='INVALID_STATE')
    if won(points,sport): fail('Unclosed completed game',code='INVALID_STATE')
    if finished and (decision is not None or points!=[0,0]): fail('Invalid completed match',code='INVALID_STATE')
    if decision is not None and decision['kind']=='walkover' and (data['games'] or points!=[0,0]): fail('Walkover requires pre-play state',code='INVALID_STATE')
    if sport=='table_tennis':
        exp=data['expedite']
        if exp is not None:
            index=int(exp['game_index'])
            if index>len(data['games']): fail('Expedite game index is in the future',code='INVALID_STATE')
            total=sum(points if index==len(data['games']) else data['games'][index])
            anchor=(index+exp['point_total']//2)%2 if exp['in_play'] or exp['point_total']==0 else (index+(exp['point_total']-1)//2+1)%2
            if exp['point_total']>total or exp['server']!=anchor: fail('Invalid expedite anchor',code='INVALID_STATE')
        if data['server']!=tt_server(data): fail('Incorrect service order',code='INVALID_STATE')
    elif sum(points)==0:
        expected=game_winner(data['games'][-1],sport) if data['games'] else 0
        if data['server']!=expected: fail('Incorrect opening server',code='INVALID_STATE')
    elif points[int(data['server'])]==0: fail('Server has not won a rally',code='INVALID_STATE')

def outcome(state,pack,sport):
    data=state['data'];target=3 if sport=='table_tennis' else 2;decision=data['decision'];terminal=data['phase']=='finished'
    w=1-int(decision['player']) if decision else counts(data,sport).index(target) if terminal else None
    kind={'retirement':'technical','disqualification':'disqualification','walkover':'forfeit'}[decision['kind']] if decision else 'win' if terminal else 'none'
    return dict(status='terminal' if terminal else 'ongoing',result_kind=kind,winners=[] if w is None else [state['players'][w]['id']],losers=[] if w is None else [state['players'][1-w]['id']],placements=[],reason=decision['kind'] if decision else 'required_games_won' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)

def apply(state,action,sport):
    data=deepcopy(state['data']);params=action['params']
    if action['type']=='end_match':
        fields(params,{'kind':{'type':'enum','values':DECISIONS},'player':PLAYER},'/params')
        data['decision']=deepcopy(params);data['phase']='finished';validate(data,sport);return data
    if action['type']=='start_expedite' and sport=='table_tennis':
        fields(params,{'mode':{'type':'enum','values':['timed','agreed']},'elapsed_seconds':{'type':'integer','minimum':0},'in_play':{'type':'boolean'}},'/params')
        if data['expedite'] is not None or sum(data['points'])>=18: fail('Expedite cannot start now')
        if params['mode']=='timed' and params['elapsed_seconds']<600: fail('Timed expedite requires ten minutes')
        total=sum(data['points']);anchor=data['server'] if params['in_play'] or total==0 else (len(data['games'])+(total-1)//2+1)%2
        data['expedite']=dict(game_index=len(data['games']),point_total=total,server=anchor,in_play=params['in_play']);data['server']=anchor;return data
    if action['type']!='award_point': fail('Unknown action')
    fields(params,{'player':PLAYER},'/params');p=int(params['player']);data['points'][p]+=1
    if sport=='badminton': data['server']=p
    if won(data['points'],sport):
        data['games'].append(list(data['points']));data['points']=[0,0]
        if max(counts(data,sport))==(3 if sport=='table_tennis' else 2): data['phase']='finished'
    if sport=='table_tennis': data['server']=tt_server(data)
    return data

def legal(state,sport):
    data=state['data'];kinds=DECISIONS if not data['games'] and data['points']==[0,0] else DECISIONS[:2]
    types=[dict(type='award_point',params_schema={'player':PLAYER},preconditions=['Match is ongoing.'],external_observations=['An adjudicator has awarded this rally point.']),dict(type='end_match',params_schema={'kind':{'type':'enum','values':kinds},'player':PLAYER},preconditions=['Walkover is allowed only before play.'],external_observations=['Official match-ending decision.'])]
    if sport=='table_tennis' and data['expedite'] is None and sum(data['points'])<18:
        types.append(dict(type='start_expedite',params_schema={'mode':{'type':'enum','values':['timed','agreed']},'elapsed_seconds':{'type':'integer','minimum':0},'in_play':{'type':'boolean'}},preconditions=['Timed mode requires at least 600 elapsed seconds; agreed mode requires both players to request it.'],external_observations=['Official elapsed playing time or mutual agreement.']))
    return dict(mode='event_types',actions=[],action_types=types,constraints={'server':data['server']},completeness=False,reason='externally_adjudicated_events')
