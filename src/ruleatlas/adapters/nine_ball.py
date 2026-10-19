"""Traditional single-rack nine-ball, adjudicated shot facts and no geometry."""
from copy import deepcopy
from ..values import fields,fail
BALL=dict(type='integer',minimum=1,maximum=9)
def validate(d):
    if sum(d['fouls'])>d['shots'] or (d['phase']!='break' and d['shots']==0) or (d['phase']=='push_choice' and d['shots']<2):fail('Shot count is inconsistent with play or fouls',code='INVALID_STATE')
    if len(set(d['remaining']))!=len(d['remaining']):fail('Remaining object balls must be distinct',code='INVALID_STATE')
    if d['phase']!='finished' and 9 not in d['remaining']:fail('The nine remains on the table until a legal winning shot',code='INVALID_STATE')
    if d['phase']=='break' and (sorted(d['remaining'])!=list(range(1,10)) or d['shots'] or any(d['fouls']) or any(d['warned']) or d['push_available'] or d['pusher'] is not None or not d['ball_in_hand']):fail('Invalid opening rack',code='INVALID_STATE')
    if any(d['warned'][p] and d['fouls'][p]!=2 for p in (0,1)):fail('Two-foul warning requires exactly two consecutive fouls',code='INVALID_STATE')
    if d['phase']=='push_choice':
        if d['pusher'] is None or d['turn']==d['pusher'] or d['push_available'] or d['ball_in_hand']:fail('Push-out choice belongs to the incoming player after a legal push',code='INVALID_STATE')
    elif d['pusher'] is not None:fail('A pending pusher is only retained for the push-out choice',code='INVALID_STATE')
    if d['push_available'] and (d['phase']!='play' or d['shots']!=1 or d['ball_in_hand']):fail('Push-out is available only immediately after a legal break',code='INVALID_STATE')
    if d['phase']=='finished':
        if d['winner'] is None or d['reason'] not in ('nine_pocketed','three_fouls'):fail('Finished rack needs a winner and reason',code='INVALID_STATE')
        if d['reason']=='nine_pocketed' and (9 in d['remaining'] or d['winner']!=d['turn']):fail('Winning shooter must have legally pocketed the nine',code='INVALID_STATE')
        if d['reason']=='three_fouls' and (d['fouls'][1-int(d['winner'])]!=3 or 9 not in d['remaining']):fail('Three-foul loss requires three consecutive warned fouls',code='INVALID_STATE')
    elif d['winner'] is not None or d['reason'] is not None or max(d['fouls'])>=3:fail('Terminal facts require a finished rack',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type'];t=int(d['turn'])
    if k=='warn_two_fouls':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params');q=int(p['player'])
        if d['fouls'][q]!=2 or d['warned'][q]:fail('Warn only an unwarned player on two consecutive fouls')
        d['warned'][q]=True;return d
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if k=='choose_push':
        fields(p,dict(take_shot=dict(type='boolean')),'/params')
        if d['phase']!='push_choice':fail('Choose only after a legal push-out')
        if not p['take_shot']:d['turn']=d['pusher']
        d['pusher']=None;d['phase']='play';return d
    if k not in ('shot','push'):fail('Unknown action')
    fields(p,dict(first_contact=dict(BALL,nullable=True),pocketed=dict(type='array',minItems=0,maxItems=9,items=BALL),off_table=dict(type='array',minItems=0,maxItems=9,items=BALL),rail_after_contact=dict(type='boolean'),break_rail_count=dict(type='integer',minimum=0,maximum=9),foul=dict(type='boolean')),'/params')
    if d['phase'] not in ('break','play'):fail('Resolve the push-out choice before shooting')
    if k=='push' and not d['push_available']:fail('Push-out is only available immediately after a legal break')
    removed=p['pocketed']+p['off_table']
    if len(set(removed))!=len(removed) or any(b not in d['remaining'] for b in removed) or (p['first_contact'] is not None and p['first_contact'] not in d['remaining']):fail('Shot balls must be distinct and present on the table')
    breaking=d['phase']=='break';pushing=k=='push'
    if not breaking and p['break_rail_count']!=0:fail('Break rail count applies only to the opening break')
    foul=p['foul'] or bool(p['off_table'])
    if not pushing:
        foul=foul or p['first_contact']!=min(d['remaining'])
        if breaking:foul=foul or (not p['pocketed'] and p['break_rail_count']<4)
        else:foul=foul or (not p['pocketed'] and not p['rail_after_contact'])
    d['shots']+=1;d['push_available']=False;d['ball_in_hand']=False;d['remaining']=[b for b in d['remaining'] if b not in removed];d['phase']='play'
    if 9 in removed and (foul or pushing):d['remaining']=sorted(d['remaining']+[9])
    if foul:
        if d['fouls'][t]==2 and d['warned'][t]:
            d['fouls'][t]=3;d['warned'][t]=False;d['winner']=1-t;d['reason']='three_fouls';d['phase']='finished'
        else:d['fouls'][t]=min(2,d['fouls'][t]+1);d['warned'][t]=False
        d['turn']=1-t;d['ball_in_hand']=True;return d
    d['fouls'][t]=0;d['warned'][t]=False
    if pushing:d['phase']='push_choice';d['pusher']=t;d['turn']=1-t
    elif 9 in p['pocketed']:d['phase']='finished';d['winner']=t;d['reason']='nine_pocketed'
    else:
        if not p['pocketed']:d['turn']=1-t
        d['push_available']=breaking
    return d

def legal(state):
    d=state['data'];actions=[dict(type='warn_two_fouls',params=dict(player=p)) for p in (0,1) if d['fouls'][p]==2 and not d['warned'][p]];types=[]
    if d['phase']=='push_choice':actions += [dict(type='choose_push',params=dict(take_shot=x)) for x in (True,False)]
    else:
        schema=dict(first_contact=dict(BALL,nullable=True),pocketed=dict(type='array',minItems=0,maxItems=9,items=BALL),off_table=dict(type='array',minItems=0,maxItems=9,items=BALL),rail_after_contact=dict(type='boolean'),break_rail_count=dict(type='integer',minimum=0,maximum=9),foul=dict(type='boolean'))
        types=[dict(type=k,params_schema=schema,preconditions=['Report distinct currently present balls. A normal shot must contact the lowest ball first and pocket a ball or reach a rail; an opening break instead pockets a ball or drives four object balls to rails.'],external_observations=['Official first object contact, pockets, object balls off table, rail facts and any additional foul.']) for k in (['shot','push'] if d['push_available'] else ['shot'])]
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(turn=d['turn'],lowest_ball=min(d['remaining']),ball_in_hand=d['ball_in_hand'],hand_region='behind_head_string' if d['phase']=='break' else 'anywhere',push_available=d['push_available']),completeness=False,reason='adjudicated_shot_facts_without_ball_motion')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';w=d['winner']
    return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][int(w)]['id']] if done else [],losers=[state['players'][1-int(w)]['id']] if done else [],placements=[],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
