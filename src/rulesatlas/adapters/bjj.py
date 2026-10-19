"""Adult black-belt ten-minute BJJ scoring with advantages and escalating penalties."""
from copy import deepcopy
from ..values import fields,fail
PLAYER=dict(type='integer',minimum=0,maximum=1)
POINTS={'takedown':2,'sweep':2,'knee_on_belly':2,'guard_pass':3,'mount':4,'back_control':4}
PLAYERS=dict(type='array',minItems=1,maxItems=2,items=PLAYER)
def leaders(d):
    values=[(d['points'][p],d['advantages'][p],-d['penalties'][p]) for p in (0,1)]
    return [p for p in (0,1) if values[p]==max(values)]
def finish(d,w,reason,excluded=None):
    d['phase']='finished';d['running']=False;d['winner']=w;d['reason']=reason;d['excluded']=excluded or [];return d
def validate(d):
    if len(set(d['excluded']))!=len(d['excluded']):fail('Excluded players must be distinct',code='INVALID_STATE')
    if d['phase']=='ready':
        if d['remaining_ms']!=600000 or any(d['points']+d['advantages']+d['penalties']) or d['running'] or d['winner'] is not None or d['reason'] is not None or d['excluded']:fail('Ready contest must contain no play or awards',code='INVALID_STATE')
        return
    for p,n in enumerate(d['penalties']):
        if (n>=2 and d['advantages'][1-p]<1) or (n>=3 and d['points'][1-p]<2):fail('Penalty ladder must include its opposing advantage and point awards',code='INVALID_STATE')
    if d['phase']=='fighting' and d['remaining_ms']==0:fail('Expired contest requires result review',code='INVALID_STATE')
    if d['phase']=='review' and (d['remaining_ms'] or d['running']):fail('Result review requires an expired stopped clock',code='INVALID_STATE')
    if d['phase']=='finished':
        if d['running'] or d['reason'] is None:fail('Finished contest requires a reason and stopped clock',code='INVALID_STATE')
        if d['reason']=='disqualification':
            if not d['excluded'] or d['winner']!=(None if len(d['excluded'])==2 else 1-d['excluded'][0]):fail('Disqualification outcome must exclude the losing participants',code='INVALID_STATE')
        elif d['winner'] is None or d['excluded']:fail('Ordinary result requires one winner and no disqualification list',code='INVALID_STATE')
        if d['reason']=='walkover' and (d['remaining_ms']!=600000 or any(d['points']+d['advantages']+d['penalties'])):fail('Walkover requires no elapsed play or awards',code='INVALID_STATE')
        if d['reason']=='score' and (d['remaining_ms'] or leaders(d)!=[d['winner']]):fail('Score result must follow expired time and the ranking criteria',code='INVALID_STATE')
        if d['reason']=='referee_decision' and (d['remaining_ms'] or len(leaders(d))!=2):fail('Referee tie decision requires equal points, advantages and penalties at time',code='INVALID_STATE')
        if any(v==4 and p not in d['excluded'] for p,v in enumerate(d['penalties'])):fail('Fourth penalty requires disqualification',code='INVALID_STATE')
    elif d['winner'] is not None or d['reason'] is not None or d['excluded'] or max(d['penalties'])==4:fail('Unresolved contest cannot retain a final decision',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);k=action['type'];p=action['params']
    if k=='end_contest':
        fields(p,dict(loser=PLAYER,reason=dict(type='string',enum=['submission','retirement','walkover'])),'/params')
        if (p['reason']=='walkover' and d['phase']!='ready') or (p['reason']=='submission' and d['phase']=='ready'):fail('Walkover precedes play; submission requires a started contest')
        return finish(d,1-p['loser'],p['reason'])
    if k=='disqualify':
        fields(p,dict(players=PLAYERS),'/params')
        if len(set(p['players']))!=len(p['players']):fail('Disqualify distinct players')
        ex=sorted(p['players']);return finish(d,None if len(ex)==2 else 1-ex[0],'disqualification',ex)
    if k=='resume':
        fields(p,{},'/params')
        if d['running'] or d['phase'] not in ('ready','fighting'):fail('Resume only an unexpired stopped contest')
        d['phase']='fighting';d['running']=True;return d
    if d['phase']=='ready':fail('Start the contest before recording play events')
    if k=='pause':
        fields(p,{},'/params')
        if not d['running']:fail('Clock already stopped')
        d['running']=False;return d
    if k=='advance_clock':
        fields(p,dict(elapsed_ms=dict(type='integer',minimum=1,maximum=600000)),'/params')
        if not d['running'] or p['elapsed_ms']>d['remaining_ms']:fail('Advance only active contest time up to expiry')
        d['remaining_ms']-=p['elapsed_ms']
        if d['remaining_ms']==0:d['running']=False;d['phase']='review'
        return d
    if k=='award_points':
        fields(p,dict(player=PLAYER,technique=dict(type='string',enum=list(POINTS))),'/params');d['points'][p['player']]+=POINTS[p['technique']];return d
    if k=='award_advantage':
        fields(p,dict(player=PLAYER),'/params');d['advantages'][p['player']]+=1;return d
    if k=='penalize':
        fields(p,dict(players=PLAYERS),'/params')
        if len(set(p['players']))!=len(p['players']):fail('Penalize distinct players once each')
        excluded=[]
        for q in p['players']:
            d['penalties'][q]+=1
            if d['penalties'][q]==2:d['advantages'][1-q]+=1
            elif d['penalties'][q]==3:d['points'][1-q]+=2
            elif d['penalties'][q]==4:excluded.append(q)
        if excluded:
            excluded.sort();return finish(d,None if len(excluded)==2 else 1-excluded[0],'disqualification',excluded)
        return d
    if k=='confirm_result':
        fields(p,{},'/params')
        if d['phase']!='review' or len(leaders(d))!=1:fail('Confirm an expired contest with a winner by points, advantages or fewer penalties')
        return finish(d,leaders(d)[0],'score')
    if k=='referee_decision':
        fields(p,dict(winner=PLAYER),'/params')
        if d['phase']!='review' or len(leaders(d))!=2:fail('Referee decides only an expired complete statistical tie')
        return finish(d,p['winner'],'referee_decision')
    fail('Unknown action')
def legal(state):
    d=state['data'];actions=[];types=[]
    def event(k,params,cond,obs):types.append(dict(type=k,params_schema=params,preconditions=[cond],external_observations=[obs]))
    if d['phase']!='review':actions.append(dict(type='pause' if d['running'] else 'resume',params={}))
    event('end_contest',dict(loser=PLAYER,reason=dict(type='string',enum=['retirement']+(['walkover'] if d['phase']=='ready' else ['submission']))),'Walkover only before play.','Official submission, withdrawal or pre-start forfeit.')
    event('disqualify',dict(players=PLAYERS),'Name distinct participants; simultaneous double exclusion has no winner.','Official serious-foul disqualification.')
    if d['phase']!='ready':
        event('award_points',dict(player=PLAYER,technique=dict(type='string',enum=list(POINTS))),'Use finalized technical awards, including any late award during review.','Referee has established the technique and required control or stabilization.')
        event('award_advantage',dict(player=PLAYER),'Contest or its result review is open.','Referee awards an advantage.')
        event('penalize',dict(players=PLAYERS),'Second penalty awards opposing advantage; third two points; fourth disqualifies.','Official escalating penalty, including simultaneous penalties.')
        if d['running']:event('advance_clock',dict(elapsed_ms=dict(type='integer',minimum=1,maximum=d['remaining_ms'])),'Only active time up to the limit.','Official active elapsed milliseconds.')
        if d['phase']=='review':
            if len(leaders(d))==1:actions.append(dict(type='confirm_result',params={}))
            else:event('referee_decision',dict(winner=PLAYER),'Points, advantages and penalties are tied after time.','Official referee selection of the winner.')
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(phase=d['phase'],remaining_ms=d['remaining_ms'],running=d['running']),completeness=False,reason='official_technical_awards_and_result_review')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';w=d['winner'];dq=d['reason']=='disqualification'
    return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('disqualification' if dq else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][p]['id'] for p in (0,1) if p!=w] if done else [],placements=[],reason=d['reason'] if done else 'review_required' if d['phase']=='review' else 'ongoing',evidence_required=['Result confirmation or referee tie decision.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
