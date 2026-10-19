"""Adult four-minute judo under the explicit two-waza-ari, no-yuko rule variant."""
from copy import deepcopy
from ..values import fields,fail
PLAYER=dict(type='integer',minimum=0,maximum=1)
def finish(d,w,reason):
    d['winner']=w;d['reason']=reason;d['phase']='finished';d['running']=False;d['hold']=None;return d
def time_end(d):
    if d['phase']=='regulation' and d['remaining_ms']==0 and d['hold'] is None:
        if d['waza'][0]!=d['waza'][1]:return finish(d,0 if d['waza'][0]>d['waza'][1] else 1,'regulation_score')
        d['phase']='golden';d['running']=False
    return d
def award(d,p):
    d['waza'][p]+=1
    if d['waza'][p]==2:return finish(d,p,'two_waza_ari')
    if d['phase']=='golden':return finish(d,p,'golden_score')
    return d
def validate(d):
    if d['phase']=='ready':
        if d['remaining_ms']!=240000 or d['golden_ms'] or any(d['waza']) or any(d['shido']) or d['hold'] is not None or d['running'] or d['winner'] is not None or d['reason'] is not None:fail('Ready contest must contain no elapsed play or scores',code='INVALID_STATE')
        return
    if d['phase']=='regulation' and (d['golden_ms'] or (d['remaining_ms']==0 and d['hold'] is None)):fail('Expired regulation must resolve or enter golden score',code='INVALID_STATE')
    if d['phase']=='golden' and (d['remaining_ms'] or d['waza'][0]!=d['waza'][1]):fail('Golden score requires tied regulation and zero remaining time',code='INVALID_STATE')
    if d['hold'] is not None:
        h=d['hold']
        if not d['running'] or h['elapsed_ms']>=20000 or h['awarded']!=(h['elapsed_ms']>=10000) or (h['awarded'] and not d['waza'][h['player']]):fail('Active hold requires running time and consistent ten-second credit',code='INVALID_STATE')
    if d['phase']=='golden' and d['hold'] is not None and d['hold']['awarded']:fail('A credited golden-score hold must finish the contest',code='INVALID_STATE')
    if d['phase']=='finished':
        if d['winner'] is None or d['reason'] is None or d['running'] or d['hold'] is not None:fail('Finished contest requires a winner and stopped clocks',code='INVALID_STATE')
        w=d['winner'];reason=d['reason']
        if reason=='two_waza_ari' and d['waza'][w]!=2:fail('Two-waza-ari finish requires two awards',code='INVALID_STATE')
        if reason=='third_shido' and d['shido'][1-w]!=3:fail('Third-shido finish requires three penalties against the loser',code='INVALID_STATE')
        if reason=='regulation_score' and (d['remaining_ms'] or d['waza'][w]<=d['waza'][1-w]):fail('Regulation winner must lead at time expiry',code='INVALID_STATE')
        if reason=='golden_score' and (d['remaining_ms'] or d['waza'][w]<=d['waza'][1-w]):fail('Golden-score winner must have the new scoring lead',code='INVALID_STATE')
        if reason=='walkover' and (d['remaining_ms']!=240000 or d['golden_ms'] or any(d['waza']) or any(d['shido'])):fail('Walkover requires no elapsed contest or scores',code='INVALID_STATE')
    elif d['winner'] is not None or d['reason'] is not None or max(d['waza'])>=2 or max(d['shido'])>=3:fail('Winning score or third shido must finish the contest',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);k=action['type'];p=action['params']
    if k=='end_contest':
        fields(p,dict(loser=PLAYER,reason=dict(type='string',enum=['direct_disqualification','retirement','walkover'])),'/params')
        if p['reason']=='walkover' and d['phase']!='ready':fail('Walkover only before the contest starts')
        return finish(d,1-p['loser'],p['reason'])
    if k=='resume':
        fields(p,{},'/params')
        if d['running']:fail('Clock already running')
        if d['phase']=='ready':d['phase']='regulation'
        d['running']=True;return d
    if d['phase']=='ready':fail('Start the contest before recording play events')
    if k=='pause':
        fields(p,{},'/params')
        if not d['running']:fail('Clock already stopped')
        d['running']=False;d['hold']=None;return time_end(d)
    if k=='advance_clock':
        fields(p,dict(elapsed_ms=dict(type='integer',minimum=1,maximum=1000000000)),'/params');n=p['elapsed_ms']
        if not d['running']:fail('Only running contest time may advance')
        h=d['hold']
        if h is None and d['phase']=='regulation' and n>d['remaining_ms']:fail('Regulation cannot advance beyond time expiry without an active hold')
        if h is not None:
            winning_at=10000 if not h['awarded'] and (d['waza'][h['player']]==1 or d['phase']=='golden') else 20000
            if h['elapsed_ms']+n>winning_at:fail('Clock update cannot pass the instant a hold wins the contest')
        if d['phase']=='regulation':d['remaining_ms']=max(0,d['remaining_ms']-n)
        else:d['golden_ms']+=n
        if h is not None:
            h['elapsed_ms']+=n
            if h['elapsed_ms']>=10000 and not h['awarded']:
                h['awarded']=True;d=award(d,h['player'])
                if d['phase']=='finished':return d
            if h['elapsed_ms']==20000:return finish(d,h['player'],'hold_ippon')
        return time_end(d)
    if k=='start_hold':
        fields(p,dict(player=PLAYER),'/params')
        if not d['running'] or d['hold'] is not None:fail('Start one adjudicated hold while the contest clock runs')
        d['hold']=dict(player=p['player'],elapsed_ms=0,awarded=False);return d
    if k=='end_hold':
        fields(p,{},'/params')
        if d['hold'] is None:fail('No active hold')
        d['hold']=None;return time_end(d)
    if k=='award_score':
        fields(p,dict(player=PLAYER,score=dict(type='string',enum=['waza_ari','ippon'])),'/params')
        if d['hold'] is not None:fail('Hold scores come from its clock; use submission for a separate submission decision')
        if p['score']=='ippon':return finish(d,p['player'],'ippon')
        return award(d,p['player'])
    if k=='submission':
        fields(p,dict(loser=PLAYER),'/params');return finish(d,1-p['loser'],'submission')
    if k=='shido':
        fields(p,dict(player=PLAYER),'/params');q=p['player'];d['shido'][q]+=1
        return finish(d,1-q,'third_shido') if d['shido'][q]==3 else d
    fail('Unknown action')
def legal(state):
    d=state['data'];actions=[];types=[]
    def event(k,params,condition,obs):types.append(dict(type=k,params_schema=params,preconditions=[condition],external_observations=[obs]))
    actions.append(dict(type='pause' if d['running'] else 'resume',params={}))
    event('end_contest',dict(loser=PLAYER,reason=dict(type='string',enum=['direct_disqualification','retirement']+(['walkover'] if d['phase']=='ready' else []))),'Walkover only before starting.','Official exclusion, withdrawal or pre-contest forfeit.')
    if d['phase']!='ready':
        event('shido',dict(player=PLAYER),'Third shido ends the contest; smaller penalty differences do not decide a tied contest.','Official minor-penalty award.')
        event('submission',dict(loser=PLAYER),'Contest is ongoing.','Official submission decision.')
        if d['hold'] is None:event('award_score',dict(player=PLAYER,score=dict(type='string',enum=['waza_ari','ippon'])),'Two waza-ari or one golden-score award wins.','Adjudicated non-hold score.')
        if d['running']:
            h=d['hold'];limit=d['remaining_ms'] if d['phase']=='regulation' and h is None else ((10000 if not h['awarded'] and (d['waza'][h['player']]==1 or d['phase']=='golden') else 20000)-h['elapsed_ms']) if h is not None else 1000000000
            event('advance_clock',dict(elapsed_ms=dict(type='integer',minimum=1,maximum=limit)),'Do not pass a winning hold threshold or unheld regulation expiry.','Official elapsed active contest milliseconds.')
            if h is None:event('start_hold',dict(player=PLAYER),'Only one active hold.','Referee announces a valid hold.')
            else:actions.append(dict(type='end_hold',params={}))
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(phase=d['phase'],remaining_ms=d['remaining_ms'],running=d['running']),completeness=False,reason='official_scores_penalties_and_clock_events')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';w=d['winner']
    return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
