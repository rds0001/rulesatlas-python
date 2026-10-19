"""Bounded round, referee and three-judge scoring rules for declared combat formats."""
from copy import deepcopy
from ..values import fields,fail
PLAYER=dict(type='integer',minimum=0,maximum=1)
def totals(d):return [[sum(cards[j][p]-d['deductions'][r][p] for r,cards in enumerate(d['cards'])) for p in (0,1)] for j in range(3)]
def decision(d):
    votes=[0 if a==b else 1 if a>b else -1 for a,b in totals(d)];winner=0 if votes.count(1)>=2 else 1 if votes.count(-1)>=2 else None
    if winner is None:kind='unanimous_draw' if votes.count(0)==3 else 'majority_draw' if votes.count(0)==2 else 'split_draw'
    else:kind='unanimous_decision' if votes.count(1 if winner==0 else -1)==3 else 'majority_decision' if 0 in votes else 'split_decision'
    return winner,('technical_' if d['technical'] else '')+kind

def finish(d,w,reason):d.update(phase='finished',running=False,winner=w,reason=reason,break_ms=0,count=None);return d
class JudgedCombat:
    def __init__(self,config):self.c=config
    def validate(self,d):
        c=self.c;r=d['round'];n=len(d['cards'])
        if n>r+1:fail('Scorecards cannot extend beyond the current round',code='INVALID_STATE')
        for card in d['cards']:
            if any(max(s)!=10 or min(s)<c['minimum_score'] for s in card):fail('Each unadjusted judge score must obey the configured ten-point-must scale',code='INVALID_STATE')
        if any(any(v for v in d['deductions'][i]) for i in range(r+1,c['rounds'])):fail('Future rounds cannot contain deductions',code='INVALID_STATE')
        if not d['started'] and (r or n or d['remaining_ms']!=c['duration_ms'] or any(any(v for v in x) for x in d['deductions']) or d['count'] is not None):fail('Unstarted bout must contain no round activity',code='INVALID_STATE')
        if d['phase']!='finished':
            if d['winner'] is not None or d['reason'] is not None:fail('Ongoing bout cannot retain a final decision',code='INVALID_STATE')
            if n!=(r+1 if d['phase']=='break' else r):fail('Completed scorecards must agree with the current round',code='INVALID_STATE')
            if d['phase']=='break':
                if r==c['rounds']-1 or d['remaining_ms'] or not d['running'] or d['break_ms']==0:fail('Inter-round break requires a scored nonfinal round',code='INVALID_STATE')
            elif d['break_ms']:fail('Break time outside an inter-round break',code='INVALID_STATE')
            if d['phase']=='ready' and (d['remaining_ms']!=c['duration_ms'] or d['running']):fail('Ready round requires its full stopped clock',code='INVALID_STATE')
            if d['phase']=='fighting' and (not d['started'] or not d['remaining_ms']):fail('Active round must be started and unexpired',code='INVALID_STATE')
            if d['phase']=='judging' and (d['running'] or (d['remaining_ms'] and not d['technical'])):fail('Judge submission requires an expired or technically stopped round',code='INVALID_STATE')
        else:
            if d['running'] or d['break_ms'] or d['count'] is not None or d['reason'] is None:fail('Finished bout must have stopped clocks and a reason',code='INVALID_STATE')
            if 'decision' in d['reason'] or ('draw' in d['reason'] and d['reason']!='technical_draw'):
                if n!=r+1 or (not d['technical'] and (n!=c['rounds'] or d['remaining_ms']!=0)) or (d['winner'],d['reason'])!=decision(d):fail('Judged result must agree with complete submitted cards',code='INVALID_STATE')
            elif d['reason'] in ('no_contest','double_disqualification','technical_draw'):
                if d['winner'] is not None:fail('No-contest, technical draw or double exclusion has no winner',code='INVALID_STATE')
            elif d['winner'] is None:fail('A decisive stoppage requires its winning participant',code='INVALID_STATE')
            if d['reason']=='forfeit' and d['started']:fail('Pre-start forfeit cannot follow live action',code='INVALID_STATE')
        if d['technical'] and (r<c['technical_after'] or d['phase'] not in ('judging','finished')):fail('Technical score decision requires enough completed rounds and result submission',code='INVALID_STATE')
        if d['phase']=='count':
            if not c['counts'] or d['count'] is None or not d['started'] or d['running']!=(d['remaining_ms']>0):fail('Knockdown count requires the configured count format and clock state',code='INVALID_STATE')
        elif d['count'] is not None:fail('Knockdown-count data outside its phase',code='INVALID_STATE')
    def apply(self,state,action):
        d=deepcopy(state['data']);p=action['params'];k=action['type'];c=self.c
        if k=='stop':
            fields(p,dict(method=dict(type='string',enum=['knockout','tko','submission','disqualification','double_disqualification','no_contest','forfeit','technical_draw']),winner=dict(PLAYER,nullable=True)),'/params');method=p['method']
            if (p['winner'] is None)!=(method in ('no_contest','double_disqualification','technical_draw')):fail('Decisive stoppages require a winner; nondecisive results must not name one')
            if method=='forfeit' and d['started'] or method not in ('forfeit','no_contest','disqualification','double_disqualification') and not d['started']:fail('Stoppage method disagrees with whether the bout has started')
            if c['counts'] and method in ('knockout','submission'):fail('Count-format knockouts require the tenth count; submissions are outside this format')
            return finish(d,p['winner'],method)
        if k=='resume':
            fields(p,{},'/params')
            if d['phase'] not in ('ready','fighting') or d['running']:fail('Resume only a stopped ready or active round')
            d['phase']='fighting';d['running']=True;d['started']=True;return d
        if k=='pause':
            fields(p,{},'/params')
            if d['phase']!='fighting' or not d['running']:fail('Pause only an actively running round')
            d['running']=False;return d
        if k=='advance_clock':
            fields(p,dict(elapsed_ms=dict(type='integer',minimum=1,maximum=max(c['duration_ms'],c.get('rest_ms',60000)))),'/params');n=p['elapsed_ms']
            if not d['running'] or d['phase'] not in ('fighting','count','break'):fail('Only official running time may advance')
            field='break_ms' if d['phase']=='break' else 'remaining_ms'
            if n>d[field]:fail('Clock event cannot pass the current interval limit')
            d[field]-=n
            if d[field]==0:
                d['running']=False
                if d['phase']=='break':d['round']+=1;d['remaining_ms']=c['duration_ms'];d['phase']='ready'
                elif d['phase']!='count':d['phase']='judging'
            return d
        if k=='deduct_points':
            fields(p,dict(player=PLAYER,points=dict(type='integer',minimum=1,maximum=2)),'/params')
            if d['phase'] not in ('fighting','count','judging') or d['deductions'][d['round']][p['player']]+p['points']>10:fail('Record referee deductions in the current unscored round')
            d['deductions'][d['round']][p['player']]+=p['points'];return d
        if k=='technical_stop':
            fields(p,{},'/params')
            if d['phase']!='fighting' or d['round']<c['technical_after']:fail('Technical scoring requires enough completed rounds and an active partial round')
            d['technical']=True;d['phase']='judging';d['running']=False;return d
        if k=='submit_scores':
            fields(p,dict(scores=dict(type='array',minItems=3,maxItems=3,items=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=c['minimum_score'],maximum=10)))),'/params')
            if d['phase']!='judging' or any(max(s)!=10 for s in p['scores']):fail('Submit three unadjusted ten-point-must scores for the current round')
            d['cards'].append(deepcopy(p['scores']))
            if d['technical'] or d['round']==c['rounds']-1:return finish(d,*decision(d))
            d['phase']='break';d['break_ms']=c.get('rest_ms',60000);d['running']=True;return d
        if k=='knockdown':
            fields(p,dict(player=PLAYER),'/params')
            if not c['counts'] or d['phase']!='fighting' or not d['running']:fail('Record a knockdown only during active count-format fighting')
            d['count']=dict(player=p['player'],number=0);d['phase']='count';return d
        if k=='advance_count':
            fields(p,dict(number=dict(type='integer',minimum=1,maximum=10)),'/params')
            if d['phase']!='count' or p['number']!=d['count']['number']+1:fail('Referee knockdown counts advance one number at a time')
            if p['number']==10:return finish(d,1-d['count']['player'],'knockout')
            d['count']['number']=p['number'];return d
        if k=='fighter_ready':
            fields(p,{},'/params')
            if d['phase']!='count' or d['count']['number']<8:fail('A ready boxer may resume only after the mandatory eight count')
            d['count']=None;d['phase']='fighting' if d['remaining_ms'] else 'judging';return d
        fail('Unknown action')
    def legal(self,state):
        d=state['data'];c=self.c;actions=[];types=[]
        def event(k,params,cond,obs):types.append(dict(type=k,params_schema=params,preconditions=[cond],external_observations=[obs]))
        methods=['tko','disqualification','double_disqualification','no_contest','technical_draw']+([] if c['counts'] else ['knockout','submission']) if d['started'] else ['forfeit','disqualification','double_disqualification','no_contest']
        event('stop',dict(method=dict(type='string',enum=methods),winner=dict(PLAYER,nullable=True)),'Winning seat is required except no-contest, technical draw and double disqualification.','Officially adjudicated bout stoppage method and winner.')
        if d['phase'] in ('ready','fighting'):actions.append(dict(type='pause' if d['running'] else 'resume',params={}))
        if d['running'] and d['phase'] in ('fighting','count','break'):event('advance_clock',dict(elapsed_ms=dict(type='integer',minimum=1,maximum=d['break_ms'] if d['phase']=='break' else d['remaining_ms'])),'Do not exceed the current interval.','Official elapsed running milliseconds.')
        if d['phase'] in ('fighting','count','judging'):event('deduct_points',dict(player=PLAYER,points=dict(type='integer',minimum=1,maximum=2)),'Deduction applies equally to all judges in the current unscored round.','Official referee point deduction, separate from raw judge scores.')
        if d['phase']=='fighting' and d['round']>=c['technical_after']:event('technical_stop',{},'Score the partial round after the configured minimum completed rounds.','Official decision that a technical score result applies.')
        if d['phase']=='judging':event('submit_scores',dict(scores=dict(type='array',minItems=3,maxItems=3,items=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=c['minimum_score'],maximum=10)))),'Each judge gives at least one athlete ten before referee deductions.','Three finalized judge score pairs, excluding separately recorded deductions.')
        if c['counts'] and d['phase']=='fighting' and d['running']:event('knockdown',dict(player=PLAYER),'A physical knockdown has been adjudicated; no standing count.','Referee identifies the downed boxer.')
        if d['phase']=='count':
            actions.append(dict(type='advance_count',params=dict(number=d['count']['number']+1)))
            if d['count']['number']>=8:actions.append(dict(type='fighter_ready',params={}))
        return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(phase=d['phase'],round=d['round']+1,remaining_ms=d['remaining_ms'],break_ms=d['break_ms']),completeness=False,reason='official_clocks_referee_decisions_and_judge_cards')
    def outcome(self,state,pack):
        d=state['data'];done=d['phase']=='finished';w=d['winner'];reason=d['reason'];kind='none'
        if done:kind='no_contest' if reason=='no_contest' else 'disqualification' if reason in ('disqualification','double_disqualification') else 'forfeit' if reason=='forfeit' else 'draw' if w is None else 'technical' if d['technical'] else 'win'
        return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='judging' else 'ongoing',result_kind=kind,winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][p]['id'] for p in (0,1) if p!=w] if done and (w is not None or reason=='double_disqualification') else [],placements=[dict(judge=j,scores=s) for j,s in enumerate(totals(d))] if done and ('decision' in reason or ('draw' in reason and reason!='technical_draw')) else [],reason=reason if done else 'round_scores_required' if d['phase']=='judging' else 'ongoing',evidence_required=['Three finalized round score pairs.'] if d['phase']=='judging' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
