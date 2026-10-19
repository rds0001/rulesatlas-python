"""Singles cornhole: alternating pitches, foul bags and cancellation scoring."""
from copy import deepcopy
from ..values import fields,fail
def validate(d):
    if d['fouls'][int(d['first'])]>(d['pitched']+1)//2 or d['fouls'][1-int(d['first'])]>d['pitched']//2:fail('Foul count exceeds pitched bags',code='INVALID_STATE')
    if sum(v>=21 for v in d['scores'])>1 or max(d['scores'])>=21 and d['pitched']!=0:fail('Invalid completed-game state',code='INVALID_STATE')
    if max(d['scores'])>=21 and d['scores'][int(d['first'])]<21:fail('Winner must lead the next inning',code='INVALID_STATE')
    if d['innings']==0 and any(d['scores']):fail('Scores require a completed inning',code='INVALID_STATE')
    if any(v>d['innings']*12 for v in d['scores']):fail('Score exceeds completed inning capacity',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if kind=='choose_first':
        if d['innings'] or d['pitched']:fail('Opening player is already fixed')
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params');d['first']=p['player'];return d
    if kind=='pitch':
        if d['pitched']==8:fail('Score the completed inning first')
        fields(p,dict(foul=dict(type='boolean')),'/params');t=(int(d['first'])+int(d['pitched']))%2
        if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        d['pitched']+=1;d['fouls'][t]+=int(p['foul']);return d
    if kind!='score_inning':fail('Unknown action')
    if d['pitched']!=8:fail('Both players must pitch all four bags')
    vector=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=0,maximum=4))
    fields(p,dict(board=vector,hole=vector),'/params')
    for t in range(2):
        if p['board'][t]+p['hole'][t]>4-d['fouls'][t]:fail('Scoring bags exceed eligible pitched bags')
    points=[p['board'][t]+3*p['hole'][t] for t in range(2)];delta=points[0]-points[1]
    if delta:d['first']=0 if delta>0 else 1;d['scores'][int(d['first'])]+=abs(delta)
    d['innings']+=1;d['pitched']=0;d['fouls']=[0,0];return d
def legal(state):
    d=state['data'];types=[];vector=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=0,maximum=4))
    if d['pitched']<8:types.append(dict(type='pitch',params_schema=dict(foul=dict(type='boolean')),preconditions=['The next player pitches exactly one bag.'],external_observations=['Official foul ruling.']))
    else:types.append(dict(type='score_inning',params_schema=dict(board=vector,hole=vector),preconditions=['Final scoring bags exclude foul bags and total at most four minus fouls per player.'],external_observations=['Final board and hole counts after all eight pitches; displaced bags are judged in their final position.']))
    if d['innings']==0 and d['pitched']==0:types.append(dict(type='choose_first',params_schema=dict(player=dict(type='integer',minimum=0,maximum=1)),preconditions=['No pitch has been made.'],external_observations=['Opening player determined externally.']))
    return dict(mode='event_types',actions=[],action_types=types,constraints=dict(player=(int(d['first'])+int(d['pitched']))%2 if d['pitched']<8 else None),completeness=False,reason='externally_adjudicated_bag_results')
def outcome(state,pack):
    d=state['data'];wins=[p for p,v in enumerate(d['scores']) if v>=21];w=wins[0] if wins else None
    return dict(status='terminal' if wins else 'ongoing',result_kind='win' if wins else 'none',winners=[state['players'][w]['id']] if wins else [],losers=[state['players'][1-w]['id']] if wins else [],placements=[],reason='twenty_one_reached' if wins else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if wins else None)
