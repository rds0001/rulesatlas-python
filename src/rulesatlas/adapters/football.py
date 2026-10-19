"""Compact football match state: adjudicated events and their rule consequences."""
from copy import deepcopy
from ..values import fields, fail
TEAM={'type':'integer','minimum':0,'maximum':1}
SLOT={'type':'integer','minimum':0,'maximum':25}
BOOL={'type':'boolean'}
PLAY=('first_half','second_half','extra_first','extra_second')
BREAKS=('halftime','extra_break','extra_halftime')
EXTRA=('extra_break','extra_first','extra_halftime','extra_second')
RULES={'knockout':BOOL,'extra_time':BOOL,'substitution_limit':{'type':'integer','minimum':0,'maximum':5},'window_limit':{'type':'integer','minimum':0,'maximum':3},'extra_substitute':BOOL}

def active(team): return [i for i,s in enumerate(team['status']) if s=='active']
def penalty_winner(d):
    a=d['shootout_attempts'];g=d['shootout_goals']
    for t in (0,1):
        if max(a)<=5 and g[t]>g[1-t]+max(0,5-a[1-t]): return t
    if min(a)>=5 and a[0]==a[1] and g[0]!=g[1]:return 0 if g[0]>g[1] else 1
    return None

def validate(d):
    phase=d['phase'];r=d['rules'];shoot=phase in ('shootout_setup','shootout') or d['shootout_started']
    if r['extra_time'] and not r['knockout']:fail('Extra time requires knockout format',code='INVALID_STATE')
    if d['extra_started'] and not (r['knockout'] and r['extra_time']):fail('Extra time is disabled',code='INVALID_STATE')
    if phase in EXTRA and not d['extra_started']:fail('Extra-time phase mismatch',code='INVALID_STATE')
    if shoot and (not r['knockout'] or d['goals'][0]!=d['goals'][1]):fail('Shoot-out requires a tied knockout match',code='INVALID_STATE')
    if d['shootout_started'] != (phase in ('shootout','finished','abandoned') and shoot):fail('Shoot-out phase mismatch',code='INVALID_STATE')
    if d['extra_started'] and phase in ('pre_match','first_half','halftime','second_half'):fail('Extra time has not begun',code='INVALID_STATE')
    for t,team in enumerate(d['teams']):
        if len(team['yellow'])!=len(team['status']) or len(team['red'])!=len(team['status']):fail('Player vectors differ in length',code='INVALID_STATE')
        for y,red,status in zip(team['yellow'],team['red'],team['status']):
            if red!=(status=='dismissed') or (y==2 and not red):fail('Card and eligibility mismatch',code='INVALID_STATE')
        n=len(active(team))
        if n>11 or (phase in PLAY+BREAKS and n<7):fail('Invalid active player count',code='INVALID_STATE')
        if team['goalkeeper'] is not None and team['goalkeeper'] not in active(team):fail('Goalkeeper must be active',code='INVALID_STATE')
        bonus=int(d['extra_started'] and r['extra_substitute'])
        if team['substitutions']>r['substitution_limit']+bonus or team['windows']>r['window_limit']+bonus:fail('Substitution allowance exceeded',code='INVALID_STATE')
        if team['windows']>team['substitutions']:fail('Substitution windows exceed substitutions',code='INVALID_STATE')
        eligible=team['eligible'];taken=team['taken']
        if not shoot and (eligible or taken):fail('Kicker eligibility exists before shoot-out setup',code='INVALID_STATE')
        if d['shootout_started'] and team['goalkeeper'] is not None and team['goalkeeper'] not in eligible:fail('Shoot-out goalkeeper must be eligible',code='INVALID_STATE')
        if len(set(eligible))!=len(eligible) or any(i not in active(team) for i in eligible):fail('Invalid eligible kickers',code='INVALID_STATE')
        if len(set(taken))!=len(taken) or any(i not in eligible for i in taken):fail('Invalid kicker cycle',code='INVALID_STATE')
    a=d['shootout_attempts'];g=d['shootout_goals'];first=int(d['shootout_first'])
    if any(g[t]>a[t] for t in (0,1)) or a[first]-a[1-first] not in (0,1):fail('Invalid shoot-out counters',code='INVALID_STATE')
    if not d['shootout_started'] and (a!=[0,0] or g!=[0,0]):fail('Shoot-out has not started',code='INVALID_STATE')
    if phase=='shootout' and penalty_winner(d) is not None:fail('Shoot-out already decided',code='INVALID_STATE')
    if phase=='finished' and r['knockout'] and d['goals'][0]==d['goals'][1] and penalty_winner(d) is None:fail('Knockout winner is unresolved',code='INVALID_STATE')
    if d['pending_penalty'] is not None and phase not in PLAY:fail('Pending penalty requires a playing period',code='INVALID_STATE')
    if phase=='pre_match' and (d['goals']!=[0,0] or d['extra_started'] or d['shootout_started']):fail('Invalid pre-match counters',code='INVALID_STATE')

def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';abandoned=d['phase']=='abandoned';w=None
    if terminal:w=penalty_winner(d) if d['shootout_started'] else (None if d['goals'][0]==d['goals'][1] else 0 if d['goals'][0]>d['goals'][1] else 1)
    return dict(status='terminal' if terminal else 'awaiting_adjudication' if abandoned else 'ongoing',result_kind=('draw' if w is None else 'win') if terminal else 'none',winners=[] if w is None else [state['players'][w]['id']],losers=[] if w is None else [state['players'][1-w]['id']],placements=[],reason='shootout_decided' if terminal and d['shootout_started'] else 'match_finished' if terminal else 'match_abandoned' if abandoned else 'ongoing',evidence_required=['Competition decision on abandoned match.'] if abandoned else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)

def transition_after_play(d):
    if d['phase']=='first_half':d['phase']='halftime'
    elif d['phase']=='extra_first':d['phase']='extra_halftime'
    elif d['goals'][0]!=d['goals'][1] or not d['rules']['knockout']:d['phase']='finished'
    elif d['phase']=='second_half' and d['rules']['extra_time']:
        d['phase']='extra_break';d['extra_started']=True
    else:
        d['phase']='shootout_setup'
        for team in d['teams']:
            team['yellow']=[0]*len(team['yellow']);team['eligible']=active(team);team['taken']=[]

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type'];phase=d['phase']
    if phase in ('finished','abandoned'):fail('Match is not open')
    if kind=='configure':
        if phase!='pre_match':fail('Rules are fixed after kick-off')
        fields(p,RULES,'/params');d['rules']=deepcopy(p)
    elif kind=='set_lineup':
        fields(p,SCHEMAS[kind],'/params')
        if phase!='pre_match':fail('Lineup is fixed after kick-off')
        t=d['teams'][int(p['team'])];n=int(p['roster_size']);starters=p['starters']
        if any(t['yellow']) or any(t['red']):fail('Lineup replacement cannot erase disciplinary records')
        if len(set(starters))!=len(starters) or max(starters)>=n or p['goalkeeper'] not in starters or n-len(starters)>15:fail('Invalid starting lineup')
        t.update(yellow=[0]*n,red=[False]*n,status=['active' if i in starters else 'bench' for i in range(n)],goalkeeper=p['goalkeeper'])
    elif kind=='start_period':
        fields(p,{},'/params');mapping={'pre_match':'first_half','halftime':'second_half','extra_break':'extra_first','extra_halftime':'extra_second'}
        if phase not in mapping:fail('No period can start now')
        if any(len(active(t))<7 or t['goalkeeper'] is None for t in d['teams']):fail('Each team needs seven players and a goalkeeper')
        d['phase']=mapping[phase]
    elif kind=='abandon_match':
        fields(p,{},'/params')
        if phase=='pre_match':fail('Match has not started')
        d['phase']='abandoned';d['pending_penalty']=None
    elif kind=='goal':
        fields(p,{'team':TEAM},'/params')
        if phase not in PLAY:fail('Goals require a playing period')
        if d['pending_penalty'] is not None or any(t['goalkeeper'] is None for t in d['teams']):fail('Resolve the pending restart or goalkeeper first')
        d['goals'][int(p['team'])]+=1
    elif kind=='end_period':
        fields(p,{},'/params')
        if phase not in PLAY:fail('No playing period to end')
        if d['pending_penalty'] is not None:fail('A pending penalty must be resolved before the period ends')
        transition_after_play(d)
    elif kind=='award_penalty':
        fields(p,{'team':TEAM},'/params')
        if phase not in PLAY or d['pending_penalty'] is not None:fail('Cannot award a penalty now')
        d['pending_penalty']=p['team']
    elif kind=='resolve_penalty':
        fields(p,{'scored':BOOL},'/params')
        if d['pending_penalty'] is None:fail('No penalty is pending')
        if any(t['goalkeeper'] is None for t in d['teams']):fail('A goalkeeper must be designated first')
        d['goals'][int(d['pending_penalty'])]+=int(p['scored']);d['pending_penalty']=None
    elif kind=='replace_before_start':
        fields(p,{'team':TEAM,'in':SLOT},'/params')
        if phase!='pre_match':fail('Match has already started')
        t=d['teams'][int(p['team'])];b=int(p['in'])
        if b>=len(t['status']) or t['status'][b]!='bench' or len(active(t))>=11:fail('Invalid pre-match replacement')
        t['status'][b]='active'
    elif kind=='card':
        fields(p,{'team':TEAM,'player':SLOT,'color':{'type':'enum','values':['yellow','red']}},'/params');t=d['teams'][int(p['team'])];i=int(p['player'])
        if i>=len(t['status']) or t['red'][i]:fail('Player is unavailable for a new card')
        if p['color']=='yellow':t['yellow'][i]+=1
        if p['color']=='red' or t['yellow'][i]==2:
            t['red'][i]=True;t['status'][i]='dismissed'
            if t['goalkeeper']==i:t['goalkeeper']=None
            t['eligible']=[x for x in t['eligible'] if x!=i];t['taken']=[x for x in t['taken'] if x!=i]
            if not d['shootout_started'] and phase!='shootout_setup' and phase!='pre_match' and len(active(t))<7:d['phase']='abandoned'
    elif kind=='set_goalkeeper':
        fields(p,{'team':TEAM,'player':SLOT},'/params');t=d['teams'][int(p['team'])];i=int(p['player'])
        if i not in active(t) or (d['shootout_started'] and i not in t['eligible']):fail('Goalkeeper must be active and eligible')
        t['goalkeeper']=i
    elif kind=='substitute':
        fields(p,{'team':TEAM,'out':{'type':'array','items':SLOT,'minItems':1,'maxItems':6},'in':{'type':'array','items':SLOT,'minItems':1,'maxItems':6}},'/params')
        if phase not in PLAY+BREAKS:fail('Substitution is unavailable in this phase')
        t=d['teams'][int(p['team'])];out=[int(i) for i in p['out']];inc=[int(i) for i in p['in']];bonus=int(d['extra_started'] and d['rules']['extra_substitute'])
        if len(out)!=len(inc) or len(set(out))!=len(out) or len(set(inc))!=len(inc):fail('Invalid substitution vectors')
        if any(i not in active(t) for i in out) or any(i>=len(t['status']) or t['status'][i]!='bench' for i in inc):fail('Only active players may leave and unused substitutes enter')
        window=int(phase in PLAY)
        if t['substitutions']+len(inc)>d['rules']['substitution_limit']+bonus or t['windows']+window>d['rules']['window_limit']+bonus:fail('Substitution allowance exhausted')
        for a,b in zip(out,inc):
            t['status'][a]='off';t['status'][b]='active'
            if t['goalkeeper']==a:t['goalkeeper']=b
        t['substitutions']+=len(inc);t['windows']+=window
    elif kind=='start_shootout':
        fields(p,{'first_team':TEAM,'excluded':{'type':'array','items':{'type':'array','items':SLOT,'maxItems':11},'minItems':2,'maxItems':2}},'/params')
        if phase!='shootout_setup':fail('Shoot-out is not ready')
        for team,excluded in zip(d['teams'],p['excluded']):
            if len(set(excluded))!=len(excluded) or any(i not in team['eligible'] for i in excluded) or team['goalkeeper'] in excluded:fail('Invalid shoot-out exclusions')
            team['eligible']=[i for i in team['eligible'] if i not in excluded]
        sizes=[len(t['eligible']) for t in d['teams']]
        if not sizes[0] or sizes[0]!=sizes[1] or any(t['goalkeeper'] is None for t in d['teams']):fail('Shoot-out teams must have equal eligible counts and goalkeepers')
        d['shootout_first']=int(p['first_team']);d['shootout_started']=True;d['phase']='shootout'
    elif kind=='replace_shootout_goalkeeper':
        fields(p,{'team':TEAM,'player':SLOT},'/params')
        if phase!='shootout':fail('Not in a shoot-out')
        t=d['teams'][int(p['team'])];i=int(p['player']);old=t['goalkeeper']
        if old is None or i>=len(t['status']) or i in t['eligible'] or t['status'][i] not in ('active','bench'):fail('Replacement must be an excluded player or unused substitute')
        if t['status'][i]=='bench':
            limit=d['rules']['substitution_limit']+int(d['extra_started'] and d['rules']['extra_substitute'])
            if t['substitutions']>=limit:fail('Substitution allowance exhausted')
            t['substitutions']+=1
        old=int(old)
        t['status'][old]='off';t['status'][i]='active';t['goalkeeper']=i
        t['eligible']=[i if x==old else x for x in t['eligible']];t['taken']=[i if x==old else x for x in t['taken']]
    elif kind=='exclude_kicker':
        fields(p,{'team':TEAM,'player':SLOT},'/params')
        if phase!='shootout':fail('Not in a shoot-out')
        team=d['teams'][int(p['team'])];other=d['teams'][1-int(p['team'])];i=int(p['player'])
        if len(team['eligible'])<=len(other['eligible']) or i not in team['eligible'] or i==team['goalkeeper']:fail('Exclusion must equalize eligible teams')
        team['eligible'].remove(i);team['taken']=[x for x in team['taken'] if x!=i]
    elif kind=='shootout_kick':
        fields(p,{'team':TEAM,'player':SLOT,'scored':BOOL},'/params')
        if phase!='shootout':fail('Not in a shoot-out')
        t=int(p['team']);i=int(p['player']);first=int(d['shootout_first']);a=d['shootout_attempts'];expected=first if a[0]==a[1] else 1-first;team=d['teams'][t]
        if t!=expected or any(x['goalkeeper'] is None for x in d['teams']) or len(team['eligible'])!=len(d['teams'][1-t]['eligible']):fail('Wrong turn or unresolved shoot-out eligibility')
        if set(team['taken'])==set(team['eligible']):team['taken']=[]
        if i not in team['eligible'] or i in team['taken']:fail('Kicker is ineligible or has already kicked this cycle')
        team['taken'].append(i);a[t]+=1;d['shootout_goals'][t]+=int(p['scored'])
        if penalty_winner(d) is not None:d['phase']='finished'
    else:fail('Unknown action')
    return d

SCHEMAS={'configure':RULES,'start_period':{},'end_period':{},'goal':{'team':TEAM},'card':{'team':TEAM,'player':SLOT,'color':{'type':'enum','values':['yellow','red']}},'set_goalkeeper':{'team':TEAM,'player':SLOT},'substitute':{'team':TEAM,'out':{'type':'array','items':SLOT,'minItems':1,'maxItems':6},'in':{'type':'array','items':SLOT,'minItems':1,'maxItems':6}},'start_shootout':{'first_team':TEAM,'excluded':{'type':'array','items':{'type':'array','items':SLOT,'maxItems':11},'minItems':2,'maxItems':2}},'exclude_kicker':{'team':TEAM,'player':SLOT},'shootout_kick':{'team':TEAM,'player':SLOT,'scored':BOOL}}
SCHEMAS.update(abandon_match={},set_lineup={'team':TEAM,'roster_size':{'type':'integer','minimum':7,'maximum':26},'starters':{'type':'array','items':SLOT,'minItems':7,'maxItems':11},'goalkeeper':SLOT},award_penalty={'team':TEAM},resolve_penalty={'scored':BOOL},replace_before_start={'team':TEAM,'in':SLOT},replace_shootout_goalkeeper={'team':TEAM,'player':SLOT})
def legal(state):
    phase=state['data']['phase'];kinds=[]
    if phase not in ('finished','abandoned'):kinds=['card','set_goalkeeper']
    if phase not in ('pre_match','finished','abandoned'):kinds+=['abandon_match']
    if phase=='pre_match':kinds+=['configure','set_lineup','start_period','replace_before_start']
    if phase in BREAKS:kinds+=['start_period','substitute']
    if phase in PLAY:
        kinds+=['substitute']
        kinds+=['resolve_penalty'] if state['data']['pending_penalty'] is not None else ['goal','end_period','award_penalty']
    if phase=='shootout_setup':kinds+=['start_shootout']
    if phase=='shootout':kinds+=['exclude_kicker','shootout_kick','replace_shootout_goalkeeper']
    if phase in PLAY and any(t['goalkeeper'] is None for t in state['data']['teams']):
        kinds=[k for k in kinds if k not in ('goal','resolve_penalty')]
    d=state['data'];bonus=int(d['extra_started'] and d['rules']['extra_substitute'])
    constraints={'phase':phase,'teams':[]}
    for t in d['teams']:
        remaining=d['rules']['substitution_limit']+bonus-t['substitutions'];windows=d['rules']['window_limit']+bonus-t['windows']
        kickers=[i for i in t['eligible'] if i not in t['taken']] or list(t['eligible'])
        constraints['teams'].append(dict(active=active(t),bench=[i for i,x in enumerate(t['status']) if x=='bench'],substitutions_remaining=remaining,windows_remaining=windows,next_kickers=kickers))
    if phase=='shootout':constraints['next_team']=d['shootout_first'] if d['shootout_attempts'][0]==d['shootout_attempts'][1] else 1-d['shootout_first']
    if 'substitute' in kinds and not any(t['substitutions_remaining']>0 and t['bench'] and (phase in BREAKS or t['windows_remaining']>0) for t in constraints['teams']):kinds.remove('substitute')
    return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Player eligibility, phase and allowances must permit the event.'],external_observations=['Referee-confirmed event; period ends include all required added time.']) for k in kinds],constraints=constraints,completeness=False,reason='externally_adjudicated_events')
