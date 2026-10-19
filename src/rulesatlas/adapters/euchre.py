"""Four-player partnership Euchre with stick-the-dealer and optional lone maker."""
from copy import deepcopy
from ..values import fields,fail

def suit(c,trump):
    s=int(c)//6;r=int(c)%6
    return trump if r==2 and s==(trump^1) else s

def strength(c,trump):
    s=int(c)//6;r=int(c)%6
    if s==trump and r==2:return 8
    if s==(trump^1) and r==2:return 7
    return r

def active(d):return [p for p in range(4) if not d['alone'] or p!=(int(d['maker'])+2)%4]
def next_player(d,p):return next((p+i)%4 for i in range(1,5) if (p+i)%4 in active(d))
def playable(d):
    hand=d['hands'][int(d['turn'])]
    if not d['trick']:return hand
    lead=suit(d['trick'][0]['card'],int(d['trump']));follow=[c for c in hand if suit(c,int(d['trump']))==lead]
    return follow or hand

def validate(d):
    cards=sum(d['hands'],[])+d['stock']+sum(d['won'],[])+[x['card'] for x in d['trick']]+([] if d['upcard'] is None else [d['upcard']])
    if d['phase']=='setup':
        if cards or any(d['scores']) or d['trump'] is not None or d['maker'] is not None:fail('Setup must be empty',code='INVALID_STATE')
        return
    if sorted(cards)!=list(range(24)):fail('Every card must occur exactly once',code='INVALID_STATE')
    bidding=d['phase'] in ('bid_first','bid_second')
    if bidding:
        if d['trump'] is not None or d['maker'] is not None or d['alone'] or d['upcard'] is None or len(d['stock'])!=3 or any(len(h)!=5 for h in d['hands']) or any(d['won']) or d['trick'] or d['turn']!=(d['dealer']+1+d['passes'])%4:fail('Invalid bidding state',code='INVALID_STATE')
    else:
        if d['trump'] is None or d['maker'] is None:fail('Contract is missing',code='INVALID_STATE')
        if d['phase']=='discard':
            if d['turn']!=d['dealer'] or d['upcard'] is not None or len(d['stock'])!=3 or any(len(h)!=(6 if p==d['dealer'] else 5) for p,h in enumerate(d['hands'])) or any(d['won']) or d['trick']:fail('Dealer must discard one of six cards',code='INVALID_STATE')
        else:
            n=len(active(d));completed=sum(len(p) for p in d['won'])//n
            if len(d['stock'])!=4 or d['upcard'] is not None or any(len(p)%n for p in d['won']) or completed>5:fail('Invalid stock or trick piles',code='INVALID_STATE')
            actors=[x['player'] for x in d['trick']]
            if len(set(actors))!=len(actors) or len(actors)>=n or any(p not in active(d) for p in actors):fail('Invalid partial trick',code='INVALID_STATE')
            if actors and (any(actors[i]!=next_player(d,int(actors[i-1])) for i in range(1,len(actors))) or d['turn']!=next_player(d,int(actors[-1]))):fail('Incorrect trick order',code='INVALID_STATE')
            if any(len(d['hands'][p])!=(5-completed-(p in actors) if p in active(d) else 5) for p in range(4)):fail('Hand sizes do not match completed tricks',code='INVALID_STATE')
            if any(d['won'][p] for p in range(4) if p not in active(d)):fail('Sitting-out partner cannot win tricks',code='INVALID_STATE')
            if d['turn'] not in active(d) or (d['phase'] in ('round_end','finished'))!=(completed==5):fail('Round phase or active player mismatch',code='INVALID_STATE')
    if (d['phase']=='finished')!=(max(d['scores'])>=10):fail('Match target and phase mismatch',code='INVALID_STATE')

def contract(d,trump,alone):
    d['trump']=trump;d['maker']=d['turn'];d['alone']=alone
    if d['phase']=='bid_first':
        d['hands'][int(d['dealer'])].append(d['upcard']);d['upcard']=None;d['turn']=d['dealer'];d['phase']='discard'
    else:
        d['stock'].append(d['upcard']);d['upcard']=None;d['turn']=next_player(d,int(d['dealer']));d['phase']='play'
    return d

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type'];t=int(d['turn'])
    if kind=='deal':
        fields(p,dict(deck=dict(type='array',minItems=24,maxItems=24,items=dict(type='integer',minimum=0,maximum=23))),'/params')
        if d['phase'] not in ('setup','round_end') or len(set(p['deck']))!=24:fail('Deal a complete deck only between rounds')
        if d['phase']=='round_end':d['dealer']=(d['dealer']+1)%4
        d['hands']=[[] for _ in range(4)];deck=p['deck']
        for i in range(20):d['hands'][(int(d['dealer'])+1+i)%4].append(deck[i])
        d['stock']=deck[21:];d['upcard']=deck[20];d['trump']=None;d['maker']=None;d['alone']=False;d['passes']=0;d['turn']=(d['dealer']+1)%4;d['won']=[[] for _ in range(4)];d['trick']=[];d['phase']='bid_first';return d
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if d['phase'] in ('bid_first','bid_second'):
        if kind=='pass':
            fields(p,{},'/params')
            if d['phase']=='bid_second' and d['passes']==3:fail('Dealer must choose a trump in the second bidding round')
            d['passes']+=1;d['turn']=(t+1)%4
            if d['passes']==4:d['passes']=0;d['phase']='bid_second'
            return d
        if kind!='call':fail('Pass or name trump')
        fields(p,dict(trump=dict(type='integer',minimum=0,maximum=3),alone=dict(type='boolean')),'/params');up=int(d['upcard'])//6
        if (p['trump']==up)!=(d['phase']=='bid_first'):fail('First round must order the upcard suit; second round must choose another suit')
        return contract(d,int(p['trump']),p['alone'])
    if d['phase']=='discard':
        if kind!='discard':fail('Dealer must discard')
        fields(p,dict(card=dict(type='integer',minimum=0,maximum=23)),'/params')
        if p['card'] not in d['hands'][t]:fail('Discard must be held')
        d['hands'][t].remove(p['card']);d['stock'].append(p['card']);d['turn']=next_player(d,int(d['dealer']));d['phase']='play';return d
    if kind!='play' or d['phase']!='play':fail('Play a card during a trick')
    fields(p,dict(card=dict(type='integer',minimum=0,maximum=23)),'/params');c=p['card']
    if c not in playable(d):fail('Card must be held and follow effective suit, including the left bower')
    d['hands'][t].remove(c);d['trick'].append(dict(player=t,card=c));d['turn']=next_player(d,t);n=len(active(d))
    if len(d['trick'])==n:
        trump=int(d['trump']);lead=suit(d['trick'][0]['card'],trump)
        winner=max(d['trick'],key=lambda x:(2 if suit(x['card'],trump)==trump else 1 if suit(x['card'],trump)==lead else 0,strength(x['card'],trump)))['player'];d['won'][int(winner)]+=[x['card'] for x in d['trick']];d['trick']=[];d['turn']=winner
        if sum(len(p) for p in d['won'])==5*n:
            team=int(d['maker'])%2;tricks=sum(len(d['won'][p])//n for p in range(4) if p%2==team)
            if tricks<3:d['scores'][1-team]+=2
            else:d['scores'][team]+=(4 if d['alone'] else 2) if tricks==5 else 1
            d['phase']='finished' if max(d['scores'])>=10 else 'round_end'
    return d

def legal(state):
    d=state['data'];phase=d['phase']
    if phase in ('setup','round_end'):return dict(mode='event_types',actions=[],action_types=[dict(type='deal',params_schema=dict(deck=dict(type='array',minItems=24,maxItems=24,items=dict(type='integer',minimum=0,maximum=23))),preconditions=['Permutation of all 24 cards, supplied between rounds.'],external_observations=['Externally shuffled deck.'])],constraints={},completeness=False,reason='external_deal')
    if phase in ('bid_first','bid_second'):
        up=int(d['upcard'])//6;suits=[up] if phase=='bid_first' else [s for s in range(4) if s!=up]
        actions=[dict(type='call',params=dict(trump=s,alone=a)) for s in suits for a in (False,True)]
        if phase!='bid_second' or d['passes']<3:actions.insert(0,dict(type='pass',params={}))
        return actions
    return [dict(type='discard' if phase=='discard' else 'play',params=dict(card=c)) for c in (d['hands'][int(d['turn'])] if phase=='discard' else playable(d))]
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';team=d['scores'].index(max(d['scores']));wins=[p for p in range(4) if p%2==team] if terminal else []
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if terminal else 'none',winners=[state['players'][p]['id'] for p in wins],losers=[state['players'][p]['id'] for p in range(4) if p not in wins] if terminal else [],placements=[],reason='team_reached_ten' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
