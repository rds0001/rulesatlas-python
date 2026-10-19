"""Singles squash, best of five games to eleven, with serve-box state."""
from copy import deepcopy
from ..values import fields,fail
PLAYER={'type':'integer','minimum':0,'maximum':1}
BOX={'type':'enum','values':['left','right']}

def validate(d):
    points=d['points'];games=d['games_won'];finished=d['decision'] is not None or 3 in games
    if games==[3,3]:fail('Both players cannot win the match',code='INVALID_STATE')
    if max(points)>=11 and abs(points[0]-points[1])>=2:fail('Completed game must be closed',code='INVALID_STATE')
    if d['finished']!=finished:fail('Match phase mismatch',code='INVALID_STATE')
    if 3 in games and (points!=[0,0] or d['decision'] is not None):fail('Invalid completed match',code='INVALID_STATE')
    if not d['started'] and (points!=[0,0] or games!=[0,0] or d['serve_box']!='choose'):fail('Invalid pre-play state',code='INVALID_STATE')
    if d['serve_box']=='choose' and sum(points)>0 and points[int(d['server'])]==0:fail('Receiver has not won service',code='INVALID_STATE')
def close_game(d,w):
    d['games_won'][w]+=1;d['points']=[0,0];d['server']=w;d['serve_box']='choose';d['started']=True
    d['finished']=d['games_won'][w]==3

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if kind=='choose_first_server':
        fields(p,{'player':PLAYER},'/params')
        if d['started']:fail('First server is already fixed')
        d['server']=p['player']
    elif kind=='choose_box':
        fields(p,{'box':BOX},'/params')
        if d['serve_box']!='choose':fail('Serve box is already determined')
        if action.get('actor') is not None and action['actor']!=state['players'][int(d['server'])]['id']:fail('Only the server chooses a box')
        d['serve_box']=p['box'];d['started']=True
    elif kind=='let':
        fields(p,{},'/params')
        if d['serve_box']=='choose':fail('Choose a serve box first')
    elif kind=='award_rally':
        fields(p,{'player':PLAYER},'/params')
        if d['serve_box']=='choose':fail('Choose a serve box first')
        w=int(p['player']);previous=int(d['server']);d['points'][w]+=1
        if max(d['points'])>=11 and abs(d['points'][0]-d['points'][1])>=2:close_game(d,w)
        else:
            d['server']=w;d['serve_box']=('right' if d['serve_box']=='left' else 'left') if w==previous else 'choose'
    elif kind=='award_game':
        fields(p,{'player':PLAYER},'/params');close_game(d,int(p['player']))
    elif kind=='end_match':
        fields(p,{'player':PLAYER,'kind':{'type':'enum','values':['retirement','disqualification','conduct_match','walkover']}},'/params')
        if p['kind']=='walkover' and d['started']:fail('Walkover requires pre-play state')
        d['decision']=deepcopy(p);d['finished']=True
    else:fail('Unknown action')
    return d

def legal(state):
    d=state['data'];schemas={}
    if not d['started']:schemas['choose_first_server']={'player':PLAYER}
    if d['serve_box']=='choose':schemas['choose_box']={'box':BOX}
    else:schemas.update(award_rally={'player':PLAYER},let={})
    schemas['award_game']={'player':PLAYER}
    kinds=['retirement','disqualification','conduct_match']+([] if d['started'] else ['walkover'])
    schemas['end_match']={'player':PLAYER,'kind':{'type':'enum','values':kinds}}
    return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['The game phase and service state must permit the event.'],external_observations=['An adjudicated rally, let or formal conduct/game/match decision.']) for k,v in schemas.items()],constraints={'server':d['server'],'serve_box':d['serve_box']},completeness=False,reason='externally_adjudicated_events')

def outcome(state,pack):
    d=state['data'];terminal=d['finished'];decision=d['decision'];w=1-int(decision['player']) if decision else d['games_won'].index(3) if terminal else None
    kind={'retirement':'technical','disqualification':'disqualification','conduct_match':'technical','walkover':'forfeit'}[decision['kind']] if decision else 'win' if terminal else 'none'
    return dict(status='terminal' if terminal else 'ongoing',result_kind=kind,winners=[] if w is None else [state['players'][w]['id']],losers=[] if w is None else [state['players'][1-w]['id']],placements=[],reason=decision['kind'] if decision else 'three_games_won' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
