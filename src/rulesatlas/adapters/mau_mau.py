"""Explicit two-player 32-card Mau-Mau variant, no random dealing."""
from copy import deepcopy
from ..values import fields,fail
CARD=dict(type='integer',minimum=0,maximum=31)
def rank(c):return int(c)%8
def suit(c):return int(c)//8
def playable(d,c):
    if d['penalty']:return rank(c)==0
    if rank(c)==4:return rank(d['discard'][-1])!=4
    return suit(c)==d['suit'] or rank(c)==rank(d['discard'][-1])
def validate(d):
    if d['phase']=='setup':
        if any(d['hands']) or d['stock'] or d['discard'] or d['penalty'] or d['winner'] is not None or d['agreed_draw']:fail('Setup must be empty',code='INVALID_STATE')
        return
    if sorted(sum(d['hands'],[])+d['stock']+d['discard'])!=list(range(32)) or not d['discard']:fail('Every card must occur once and a top discard is required',code='INVALID_STATE')
    top=d['discard'][-1]
    if rank(top)!=4 and d['suit']!=suit(top):fail('Active suit must match the top card except for a jack',code='INVALID_STATE')
    if d['penalty'] and (rank(top)!=0 or d['penalty']%2):fail('Only sevens carry even draw penalties',code='INVALID_STATE')
    if d['phase']=='finished':
        if d['agreed_draw']:
            if d['winner'] is not None:fail('An agreed draw has no winner',code='INVALID_STATE')
        elif d['winner'] is None or d['hands'][int(d['winner'])] or d['winner']!=d['turn']:fail('Winner must have emptied the current hand',code='INVALID_STATE')
    elif d['winner'] is not None or d['agreed_draw'] or any(not h for h in d['hands']):fail('An empty hand ends the game',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type'];t=int(d['turn'])
    if k=='deal':
        fields(p,dict(deck=dict(type='array',minItems=32,maxItems=32,items=CARD)),'/params')
        if d['phase']!='setup' or len(set(p['deck']))!=32 or rank(p['deck'][10])==4:fail('Deal the complete deck with a non-jack opening discard')
        d['hands']=[p['deck'][:10:2],p['deck'][1:10:2]];d['discard']=[p['deck'][10]];d['stock']=p['deck'][11:];d['suit']=suit(d['discard'][0]);d['penalty']=2 if rank(d['discard'][0])==0 else 0;d['turn']=1 if rank(d['discard'][0])==1 else 0;d['phase']='play';return d
    if d['phase']!='play':fail('Deal before playing')
    if k in ('offer_draw','accept_draw'):
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)),'/params');q=int(p['player'])
        if action.get('actor') is not None and action['actor']!=state['players'][q]['id']:fail('Wrong actor')
        if k=='offer_draw':d['offer']=q
        else:
            if d['offer'] is None or d['offer']==q:fail('Only the opponent may accept a draw offer')
            d['agreed_draw']=True;d['phase']='finished'
        return d
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if k=='recycle':
        fields(p,dict(order=dict(type='array',minItems=1,maxItems=31,items=CARD)),'/params')
        if len(d['stock'])>=max(1,d['penalty']) or len(d['discard'])<2 or sorted(p['order'])!=sorted(d['discard'][:-1]):fail('Recycle all older discards only when the stock cannot satisfy the draw')
        d['stock']+=p['order'];d['discard']=d['discard'][-1:];return d
    if k=='play':
        fields(p,dict(card=CARD,suit=dict(type='integer',minimum=0,maximum=3)),'/params');c=p['card']
        if c not in d['hands'][t] or not playable(d,c) or (rank(c)!=4 and p['suit']!=suit(c)):fail('Play a matching held card, or a jack on a non-jack; respond to sevens only with sevens')
        d['hands'][t].remove(c);d['discard'].append(c);d['suit']=p['suit'];d['penalty']=d['penalty']+2 if rank(c)==0 else 0
        if not d['hands'][t]:d['winner']=t;d['phase']='finished'
        elif rank(c)!=1:d['turn']=1-t
    elif k=='draw':
        fields(p,{},'/params');n=max(1,d['penalty'])
        if len(d['stock'])<n and len(d['discard'])>1:fail('Recycle available discards before drawing')
        n=min(n,len(d['stock']));d['hands'][t]+=d['stock'][:n];d['stock']=d['stock'][n:];d['penalty']=0;d['turn']=1-t
    else:fail('Unknown action')
    if d['offer'] is not None and d['offer']!=t:d['offer']=None
    return d

def legal(state):
    d=state['data'];t=int(d['turn']);types=[];actions=[]
    if d['phase']=='setup':types=[dict(type='deal',params_schema=dict(deck=dict(type='array',minItems=32,maxItems=32,items=CARD)),preconditions=['Every card once; card ten (zero-based) must not be a jack.'],external_observations=['External deck order.'])]
    else:
        actions=[dict(type='offer_draw',params=dict(player=p)) for p in (0,1)]
        if d['offer'] is not None:actions.append(dict(type='accept_draw',params=dict(player=1-d['offer'])))
        actions += [dict(type='play',params=dict(card=c,suit=s)) for c in d['hands'][t] if playable(d,c) for s in (range(4) if rank(c)==4 else [suit(c)])]
        if len(d['stock'])>=max(1,d['penalty']) or len(d['discard'])==1:actions.append(dict(type='draw',params={}))
        else:types=[dict(type='recycle',params_schema=dict(order=dict(type='array',minItems=1,maxItems=31,items=CARD)),preconditions=['Permutation of all discards except the top; existing stock stays first.'],external_observations=['External reshuffle order.'])]
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(turn=t,penalty=d['penalty']),completeness=False,reason='card_actions_and_external_deck_order')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';w=d['winner']
    return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if d['agreed_draw'] else 'win') if done else 'none',winners=[state['players'][int(w)]['id']] if done and w is not None else [],losers=[state['players'][1-int(w)]['id']] if done and w is not None else [],placements=[],reason='agreed_draw' if done and d['agreed_draw'] else 'hand_emptied' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
