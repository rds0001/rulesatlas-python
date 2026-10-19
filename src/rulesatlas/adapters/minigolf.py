"""Recreational eighteen-hole minigolf: bounded attempts and sudden-death ties."""
from copy import deepcopy
from ..values import fields,fail
I=dict(type='integer',minimum=0,maximum=1)
def active(d):return [p for p in range(2) if d['status'][p]=='active']
def validate(d):
    for p in range(2):
        if len(d['scores'][p])>18 or len(d['scores'][p])>d['hole']+1:fail('Completed scorecards cannot exceed the current hole',code='INVALID_STATE')
    if d['phase']=='play':
        a=active(d)
        if len(a)!=2 or d['turn'] not in a or len(d['scores'][d['turn']])!=d['hole'] or any(len(d['scores'][p]) not in (d['hole'],d['hole']+1) for p in a):fail('The current player must still owe a score on this hole',code='INVALID_STATE')
    if d['phase']=='playoff':
        if len(active(d))!=2 or any(len(s)!=18 for s in d['scores']) or sum(d['scores'][0])!=sum(d['scores'][1]):fail('Playoffs require tied completed scorecards',code='INVALID_STATE')
        if d['playoff_scores'][d['turn']] is not None or sum(x is not None for x in d['playoff_scores'])>1:fail('The next playoff participant must not have completed this hole',code='INVALID_STATE')
    if d['phase']=='finished':
        if d['winner'] not in (0,1):fail('A finished game requires a winner',code='INVALID_STATE')
        w=d['winner']
        if 'withdrawn' in d['status']:
            if d['status'][w]!='active' or d['status'][1-w]!='withdrawn':fail('Withdrawal winner must be the remaining player',code='INVALID_STATE')
        else:
            if any(len(s)!=18 for s in d['scores']) or d['attempts'] or d['reset_required']:fail('Finish requires completed scorecards and no pending stroke',code='INVALID_STATE')
            totals=[sum(s) for s in d['scores']]
            if totals[0]==totals[1]:
                if any(s is None for s in d['playoff_scores']) or d['playoff_scores'][w]>=d['playoff_scores'][1-w]:fail('Tied totals require a winning playoff score',code='INVALID_STATE')
            elif totals[w]>=totals[1-w]:fail('Winner must have the lowest total',code='INVALID_STATE')
    elif d['winner'] is not None:fail('An ongoing game has no winner',code='INVALID_STATE')
    if d['phase']=='play' and (any(s is not None for s in d['playoff_scores']) or d['playoff_round']):fail('Playoff data requires completed tied regulation',code='INVALID_STATE')
    if not d['attempts'] and d['reset_required']:fail('Ball replacement follows an attempted stroke',code='INVALID_STATE')
def finish_hole(d,score):
    t=d['turn'];d['attempts']=0;d['reset_required']=False
    if d['phase']=='playoff':
        d['playoff_scores'][t]=score
        if d['playoff_scores'][1-t] is None:d['turn']=1-t
        elif d['playoff_scores'][0]!=d['playoff_scores'][1]:d['winner']=0 if d['playoff_scores'][0]<d['playoff_scores'][1] else 1;d['phase']='finished'
        else:d['playoff_round']+=1;d['playoff_scores']=[None,None];d['turn']=d['playoff_round']%2
        return d
    d['scores'][t].append(score)
    waiting=[p for p in active(d) if len(d['scores'][p])==d['hole']]
    if waiting:d['turn']=waiting[0]
    elif d['hole']<17:d['hole']+=1;d['turn']=d['hole']%2
    else:
        totals=[sum(s) for s in d['scores']]
        if totals[0]==totals[1]:d['phase']='playoff';d['turn']=0
        else:d['phase']='finished';d['winner']=0 if totals[0]<totals[1] else 1
    return d
def apply(state,action):
    d=deepcopy(state['data']);k=action['type'];p=action['params'];t=d['turn']
    if k=='withdraw':
        fields(p,dict(player=I),'/params');q=p['player']
        if action.get('actor') is not None and action['actor']!=state['players'][q]['id']:fail('Wrong actor')
        d['status'][q]='withdrawn';d['phase']='finished';d['winner']=1-q;return d
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if k=='replace_ball':
        fields(p,{},'/params')
        if not d['reset_required']:fail('Replace only a ball declared out of bounds')
        d['reset_required']=False;return d
    if k=='stroke':
        fields(p,dict(result=dict(type='string',enum=['holed','in_play','out_of_bounds'])),'/params')
        if d['reset_required']:fail('Replace an out-of-bounds ball before the next stroke')
        d['attempts']+=1
        if p['result']=='holed':return finish_hole(d,d['attempts'])
        if d['attempts']==6:return finish_hole(d,7)
        d['reset_required']=p['result']=='out_of_bounds';return d
    fail('Unknown action')
def legal(state):
    d=state['data'];actions=[dict(type='withdraw',params=dict(player=p)) for p in active(d)]
    if d['reset_required']:actions.append(dict(type='replace_ball',params={}))
    else:actions += [dict(type='stroke',params=dict(result=r)) for r in ('holed','in_play','out_of_bounds')]
    return dict(mode='enumerated',actions=actions,action_types=[],constraints=dict(turn=d['turn'],hole=d['hole']+1,attempts=d['attempts'],playoff_round=d['playoff_round']),completeness=True,reason='all_declared_stroke_results')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';w=d['winner']
    return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p==w else 2,strokes=sum(d['scores'][p]),holes_completed=len(d['scores'][p]),status=d['status'][p]) for p in range(2)] if done else [],reason=('withdrawal' if 'withdrawn' in d['status'] else 'sudden_death' if all(x is not None for x in d['playoff_scores']) else 'lowest_total') if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
