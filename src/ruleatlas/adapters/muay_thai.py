"""WMC 2020 bout-state variant: counted knockdowns, warnings and ring-out clocks."""
from copy import deepcopy
from ..values import fields,fail
from .judged_combat import JudgedCombat,finish as base_finish,PLAYER
CONFIG=dict(rounds=5,duration_ms=180000,minimum_score=7,counts=True,technical_after=5,rest_ms=120000)
BASE=JudgedCombat(CONFIG)
PLAYERS=dict(type='array',minItems=1,maxItems=2,items=PLAYER)
DRAWS=('double_count_out','simultaneous_count_limit','mutual_stoppage_draw')
def clean(d):
    if d['phase']=='finished':d.update(down=[],count_kind=None,count_paused=False,recent_counts=[None,None],recovery=None,warning_origin=None)
    return d
def finish(d,w,reason):return clean(base_finish(d,w,reason))
def end_count(d):
    d.update(count=None,down=[],count_kind=None,count_paused=False,phase='fighting' if d['remaining_ms'] else 'judging',running=d['remaining_ms']>0)
    if d['phase']=='judging':d['recent_counts']=[None,None]
    return d
def limit_players(d):return [p for p in (0,1) if any(row[p]>=3 for row in d['knockdowns']) or sum(row[p] for row in d['knockdowns'])>=5]
def warn(d,p):
    if d['phase'] not in ('fighting','judging','count') or d['running'] or (d['phase']=='count' and not d['count_paused']):fail('Formal warnings require stopped fighting or a paused count')
    d['warnings'][d['round']][p]+=1;d['deductions'][d['round']][p]+=1
    if sum(row[p] for row in d['warnings'])==3:d['warning_origin']=d['phase'];d['phase']='warning_decision'
    return d
def validate(d):
    if d['phase']=='warning_decision' and d['warning_origin'] not in ('fighting','judging','count'):fail('Warning decision requires a valid preceding phase',code='INVALID_STATE')
    copy=deepcopy(d)
    if d['phase']=='recovery':copy['phase']='fighting'
    if d['phase']=='warning_decision':copy['phase']=d['warning_origin']
    if copy['phase']=='count':copy['running']=copy['remaining_ms']>0
    if d['reason'] in DRAWS:copy['reason']='technical_draw'
    if d['reason'] in ('no_decision','cancelled'):copy['reason']='no_contest'
    BASE.validate(copy)
    if not d['started'] and (any(any(row) for row in d['knockdowns']+d['cautions']) or any(x is not None for x in d['recent_counts'])):fail('Count and caution history requires a started bout',code='INVALID_STATE')
    if d['technical']:fail('This WMC variant does not use partial technical scorecards',code='INVALID_STATE')
    if d['warnings']!=d['deductions']:fail('Every formal warning deducts exactly one point',code='INVALID_STATE')
    if any(any(row) for row in d['knockdowns'][d['round']+1:]+d['warnings'][d['round']+1:]):fail('Future rounds cannot contain counts or warnings',code='INVALID_STATE')
    for card,kds in zip(d['cards'],d['knockdowns']):
        for scores in card:
            if scores[0]!=scores[1]:
                loser=0 if scores[0]<scores[1] else 1
                if (kds[loser]==1 and scores[loser]>8) or (kds[loser]==2 and scores[loser]!=7):fail('Losing-round scores must reflect one or two counts before warning deductions',code='INVALID_STATE')
    limited=limit_players(d)
    if limited and (d['phase']!='finished' or d['reason']!=('simultaneous_count_limit' if len(limited)==2 else 'count_limit_tko') or d['winner']!=(None if len(limited)==2 else 1-limited[0])):fail('Three round counts or five bout counts immediately stop the bout',code='INVALID_STATE')
    warned=[p for p in (0,1) if sum(row[p] for row in d['warnings'])>=3]
    if len(warned)>1 or any(sum(row[p] for row in d['warnings'])>3 for p in (0,1)):fail('A third formal warning requires immediate resolution',code='INVALID_STATE')
    if warned and not (d['phase']=='warning_decision' or d['phase']=='finished' and (d['reason']=='no_decision' or d['reason']=='disqualification' and d['winner']==1-warned[0])):fail('Third warning must resolve as exclusion or no decision',code='INVALID_STATE')
    if d['phase']=='warning_decision':
        if not warned or d['warning_origin'] not in ('fighting','judging','count') or d['running']:fail('Warning decision requires a stopped third-warning event',code='INVALID_STATE')
    elif d['warning_origin'] is not None:fail('Warning origin outside its decision phase',code='INVALID_STATE')
    count_phase=d['phase']=='count' or d['phase']=='warning_decision' and d['warning_origin']=='count'
    if count_phase:
        if not d['down'] or len(set(d['down']))!=len(d['down']) or d['count']['player']!=d['down'][0] or d['count_kind'] is None or d['count']['number']>=(20 if d['count_kind']=='ring_out' else 10):fail('Active count requires its distinct counted players, kind and unfinished number',code='INVALID_STATE')
    elif d['down'] or d['count_kind'] is not None or d['count_paused']:fail('Count metadata outside an active count',code='INVALID_STATE')
    if d['phase']=='recovery':
        if d['recovery'] is None or d['running'] or d['remaining_ms']==0:fail('Recovery interval requires a stopped unexpired contest',code='INVALID_STATE')
    elif d['recovery'] is not None:fail('Recovery timer outside its phase',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);k=action['type'];p=action['params']
    if d['phase']=='warning_decision':
        if k!='resolve_warning':fail('Resolve the third warning before continuing')
        fields(p,dict(result=dict(type='string',enum=['disqualification','no_decision'])),'/params');loser=next(q for q in (0,1) if sum(row[q] for row in d['warnings'])==3)
        return finish(d,1-loser if p['result']=='disqualification' else None,p['result'])
    if k=='official_result':
        fields(p,dict(result=dict(type='string',enum=['no_decision','cancelled','mutual_stoppage_draw'])),'/params')
        if not d['started'] and p['result']=='mutual_stoppage_draw':fail('Mutual stoppage requires a started contest')
        return finish(d,None,p['result'])
    if k=='warn':
        fields(p,dict(player=PLAYER),'/params');return warn(d,p['player'])
    if k=='caution':
        fields(p,dict(player=PLAYER,kind=dict(type='string',enum=['leg_push','fake_fall'])),'/params');q=p['player'];i=0 if p['kind']=='leg_push' else 1
        if d['phase']!='fighting' or d['running']:fail('Record cautions during a referee stoppage')
        if d['cautions'][q][i]==2:return warn(d,q)
        d['cautions'][q][i]+=1;return d
    if k in ('deduct_points','technical_stop','knockdown','fighter_ready'):fail('Use the WMC warning and count events for this profile')
    if k=='start_count':
        fields(p,dict(players=PLAYERS,kind=dict(type='string',enum=['knockdown','ring_out'])),'/params')
        if not d['started'] or d['phase'] not in ('fighting','ready') or (d['phase']=='fighting' and not d['running']) or len(set(p['players']))!=len(p['players']):fail('Begin a count for distinct participants during active fighting or after a completed break')
        down=sorted(p['players']);d['recent_counts']=[None,None]
        if p['kind']=='knockdown':
            for q in down:d['knockdowns'][d['round']][q]+=1
            limited=limit_players(d)
            if limited:return finish(d,None if len(limited)==2 else 1-limited[0],'simultaneous_count_limit' if len(limited)==2 else 'count_limit_tko')
        d.update(phase='count',running=True,count=dict(player=down[0],number=0),down=down,count_kind=p['kind'],count_paused=False);return d
    if k in ('pause_count','resume_count'):
        fields(p,{},'/params')
        if d['phase']!='count' or d['count_paused']==(k=='pause_count'):fail('Count pause state does not permit this event')
        d['count_paused']=k=='pause_count';return d
    if k=='pause' and d['phase']=='count':
        fields(p,{},'/params')
        if not d['running']:fail('Clock already stopped')
        d['running']=False;d['count_paused']=True;return d
    if k=='resume' and d['phase']=='count':
        fields(p,{},'/params')
        if d['running'] or d['remaining_ms']==0:fail('Resume only a stopped unexpired count clock')
        d['running']=True;return d
    if k=='advance_count':
        fields(p,dict(number=dict(type='integer',minimum=1,maximum=20)),'/params')
        if d['phase']!='count' or d['count_paused'] or p['number']!=d['count']['number']+1:fail('An unpaused referee count advances one number at a time')
        limit=20 if d['count_kind']=='ring_out' else 10
        if p['number']==limit:return finish(d,None if len(d['down'])==2 else 1-d['down'][0],'double_count_out' if len(d['down'])==2 else 'tko' if limit==20 else 'knockout')
        d['count']['number']=p['number'];return d
    if k=='counted_fighter_ready':
        fields(p,dict(player=PLAYER),'/params');q=p['player']
        if d['phase']!='count' or d['count_kind']!='knockdown' or d['count_paused'] or q not in d['down'] or d['count']['number']<8:fail('A counted boxer must be ready at or after eight before ten')
        d['recent_counts'][q]=d['count']['number'];d['down'].remove(q)
        if not d['down']:return end_count(d)
        d['count']['player']=d['down'][0];return d
    if k=='return_to_ring':
        fields(p,dict(players=PLAYERS),'/params')
        if d['phase']!='count' or d['count_kind']!='ring_out' or d['count_paused'] or len(set(p['players']))!=len(p['players']) or any(q not in d['down'] for q in p['players']):fail('Return distinct currently counted boxers before twenty')
        if len(d['down'])==2 and len(p['players'])==1:return finish(d,p['players'][0],'ring_return_win')
        return end_count(d)
    if k=='recollapse':
        fields(p,dict(player=PLAYER),'/params');q=p['player']
        if d['phase']!='fighting' or not d['running'] or d['recent_counts'][q] is None:fail('Resume a prior count only after a recorded return and without a new blow')
        d.update(phase='count',count=dict(player=q,number=d['recent_counts'][q]),down=[q],count_kind='knockdown',count_paused=False);return d
    if k=='new_exchange':
        fields(p,{},'/params')
        if d['phase']!='fighting' or not d['running']:fail('New exchange requires active fighting')
        d['recent_counts']=[None,None];return d
    if k=='start_recovery':
        fields(p,dict(player=PLAYER),'/params')
        if d['phase']!='fighting':fail('A recovery interval requires an ongoing round')
        d.update(phase='recovery',running=False,recovery=dict(player=p['player'],remaining_ms=300000));return d
    if d['phase']=='recovery':
        if k=='advance_recovery':
            fields(p,dict(elapsed_ms=dict(type='integer',minimum=1,maximum=300000)),'/params')
            if p['elapsed_ms']>d['recovery']['remaining_ms']:fail('Recovery cannot exceed five minutes')
            d['recovery']['remaining_ms']-=p['elapsed_ms'];return d
        if k=='recovered':fields(p,{},'/params');d.update(phase='fighting',running=False,recovery=None);return d
        if k=='recovery_failure':
            fields(p,dict(result=dict(type='string',enum=['loss','no_decision'])),'/params');q=d['recovery']['player'];return finish(d,1-q if p['result']=='loss' else None,'tko' if p['result']=='loss' else 'no_decision')
        if k!='stop':fail('Resolve or time the recovery interval before continuing')
    oldround=d['round'];result=BASE.apply(dict(state,data=d),action)
    if result['round']!=oldround or result['phase'] in ('break','judging'):result['recent_counts']=[None,None]
    return clean(result)
def legal(state):
    d=state['data'];types=[];actions=[]
    def event(k,params,cond,obs):types.append(dict(type=k,params_schema=params,preconditions=[cond],external_observations=[obs]))
    if d['phase']=='warning_decision':event('resolve_warning',dict(result=dict(type='string',enum=['disqualification','no_decision'])),'Third warning requires a final disposition.','Referee chooses disqualification or no decision.')
    else:
        base=BASE.legal(state);types=[x for x in base['action_types'] if x['type'] not in ('deduct_points','technical_stop','knockdown')];actions=base['actions']
        event('official_result',dict(result=dict(type='string',enum=['no_decision','cancelled']+(['mutual_stoppage_draw'] if d['started'] else []))),'Use the stated official disposition.','Chairman or referee declares no decision, cancellation or mutual inability to continue.')
        if d['phase'] in ('fighting','judging','count') and not d['running'] and (d['phase']!='count' or d['count_paused']):event('warn',dict(player=PLAYER),'Deduct one point; the third warning requires a final decision.','Formal referee warning, not a mere caution.')
        if d['phase']=='fighting':
            event('start_recovery',dict(player=PLAYER),'At most five minutes; contest time is stopped.','Referee grants the specific foul-recovery interval.')
            if not d['running']:event('caution',dict(player=PLAYER,kind=dict(type='string',enum=['leg_push','fake_fall'])),'Two recorded cautions of the named category precede subsequent formal warnings.','Referee identifies the repeatable caution category.')
            elif any(n is not None for n in d['recent_counts']):
                actions.append(dict(type='new_exchange',params={}))
                actions += [dict(type='recollapse',params=dict(player=p)) for p in (0,1) if d['recent_counts'][p] is not None]
        if d['started'] and (d['phase']=='ready' or d['phase']=='fighting' and d['running']):event('start_count',dict(players=PLAYERS,kind=dict(type='string',enum=['knockdown','ring_out'])),'Count distinct players; knockdown limits are three per round or five in the bout.','Referee identifies the counted player or simultaneous counted players and count kind.')
        if d['phase']=='count':
            actions=[dict(type='resume_count' if d['count_paused'] else 'pause_count',params={})]
            if d['remaining_ms']>0:actions.append(dict(type='pause' if d['running'] else 'resume',params={}))
            if not d['count_paused']:
                actions.append(dict(type='advance_count',params=dict(number=d['count']['number']+1)))
                if d['count_kind']=='knockdown' and d['count']['number']>=8:actions += [dict(type='counted_fighter_ready',params=dict(player=p)) for p in d['down']]
                if d['count_kind']=='ring_out':event('return_to_ring',dict(players=PLAYERS),'Return counted players before twenty.','Referee reports the returning player or both simultaneous returnees.')
        if d['phase']=='recovery':
            actions=[dict(type='recovered',params={})]
            if d['recovery']['remaining_ms']:event('advance_recovery',dict(elapsed_ms=dict(type='integer',minimum=1,maximum=d['recovery']['remaining_ms'])),'No more than the remaining recovery interval.','Official elapsed recovery milliseconds.')
            event('recovery_failure',dict(result=dict(type='string',enum=['loss','no_decision'])),'Referee resolves refusal or inability to continue.','Official loss or no-decision ruling.')
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(phase=d['phase'],round=d['round']+1,remaining_ms=d['remaining_ms'],break_ms=d['break_ms'],count_paused=d['count_paused']),completeness=False,reason='wmc_counts_warnings_clocks_and_judged_rounds')
def outcome(state,pack):
    result=BASE.outcome(state,pack);d=state['data']
    if d['phase']=='warning_decision':result.update(status='awaiting_adjudication',reason='third_warning_disposition',evidence_required=['Disqualification or no-decision ruling.'])
    if d['reason']=='no_decision':result['result_kind']='other'
    if d['reason']=='cancelled':result['result_kind']='no_contest'
    if d['reason'] in (*DRAWS,'no_decision','cancelled'):result['placements']=[]
    return result
