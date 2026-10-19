"""Two-player 121-point cribbage with pegging and exact automatic show scoring."""
from copy import deepcopy
from itertools import combinations
from ..values import fields,fail
CARD=dict(type='integer',minimum=0,maximum=51)
def rank(c):return int(c)%13+1
def value(c):return min(10,rank(c))
def show_score(hand,starter,crib=False):
    cards=hand+[starter];points=sum(2 for n in range(2,6) for cs in combinations(cards,n) if sum(value(c) for c in cs)==15)
    points+=sum(2 for a,b in combinations(cards,2) if rank(a)==rank(b))
    for n in (5,4,3):
        runs=sum(1 for cs in combinations(cards,n) if len({rank(c) for c in cs})==n and max(rank(c) for c in cs)-min(rank(c) for c in cs)==n-1)
        if runs:points+=n*runs;break
    same=len({c//13 for c in hand})==1
    if same and (not crib or hand[0]//13==starter//13):points+=4+int(hand[0]//13==starter//13)
    points+=sum(1 for c in hand if rank(c)==11 and c//13==starter//13)
    return points
def peg_score(sequence):
    total=sum(value(c) for c in sequence);points=2 if total in (15,31) else 0;n=1
    for c in reversed(sequence[:-1]):
        if rank(c)!=rank(sequence[-1]):break
        n+=1
    if n>=2:points+=n*(n-1)
    for k in range(len(sequence),2,-1):
        ranks=[rank(c) for c in sequence[-k:]]
        if len(set(ranks))==k and max(ranks)-min(ranks)==k-1:points+=k;break
    return points
def legal_cards(d,p):return [c for c in d['hands'][p] if sum(value(x) for x in d['sequence'])+value(c)<=31]
def award(d,p,n):
    d['scores'][p]+=n
    if d['scores'][p]>=121:d['phase']='finished';d['winner']=p
    return d
def reset_sequence(d,last):
    d['sequence']=[];d['go']=[False,False];d['last']=None
    if not any(d['hands']):d['phase']='show';d['show_index']=0
    else:d['turn']=1-last if d['hands'][1-last] else last
    return d
def close_sequence(d):
    last=d['last']
    if last is not None:
        award(d,last,1)
        if d['phase']=='finished':return d
    return reset_sequence(d,last if last is not None else d['turn'])
def validate(d):
    if d['phase']=='deal':
        if any(d['hands']) or any(d['played']) or d['crib'] or d['deck'] or d['starter'] is not None or d['sequence'] or any(d['discarded']) or any(d['go']) or d['last'] is not None or d['winner'] is not None:fail('Awaiting deal must have no cards or pending pegging',code='INVALID_STATE')
        if max(d['scores'])>=121:fail('A winning score must finish the match',code='INVALID_STATE')
        return
    if d['hand_number']<1:fail('A dealt hand requires a positive hand number',code='INVALID_STATE')
    if d['phase'] in ('discard','cut','peg') and d['show_index']!=0:fail('Counting index must be zero before the show',code='INVALID_STATE')
    if d['phase'] in ('discard','cut') and any(d['go']):fail('Go declarations require pegging play',code='INVALID_STATE')
    cards=sum(d['hands'],[])+sum(d['played'],[])+d['crib']+d['deck']+([] if d['starter'] is None else [d['starter']])
    if sorted(cards)!=list(range(52)):fail('Each physical card must occur exactly once',code='INVALID_STATE')
    if d['phase']=='discard':
        if d['starter'] is not None or len(d['deck'])!=40 or len(d['crib'])!=2*sum(d['discarded']) or any(d['played']) or any(len(d['hands'][p])!=(4 if d['discarded'][p] else 6) for p in (0,1)) or all(d['discarded']):fail('Discard phase requires six cards before and four after each pair is set aside',code='INVALID_STATE')
    else:
        if not all(d['discarded']) or len(d['crib'])!=4 or any(len(d['hands'][p])+len(d['played'][p])!=4 for p in (0,1)):fail('Both retained hands contain four original cards and the crib four',code='INVALID_STATE')
        if d['phase']=='cut':
            if d['starter'] is not None or len(d['deck'])!=40 or any(d['played']):fail('Cut follows both discards before any pegging',code='INVALID_STATE')
        elif d['starter'] is None or len(d['deck'])!=39:fail('Pegging and counting require a starter and remaining thirty-nine-card stock',code='INVALID_STATE')
    if len(set(d['sequence']))!=len(d['sequence']) or any(c not in sum(d['played'],[]) for c in d['sequence']) or sum(value(c) for c in d['sequence'])>31:fail('Current pegging sequence must contain distinct played cards totaling at most thirty-one',code='INVALID_STATE')
    if d['sequence']:
        if d['last'] is None or d['sequence'][-1] not in d['played'][d['last']]:fail('Last-card owner must agree with the pegging sequence',code='INVALID_STATE')
    elif d['last'] is not None:fail('Empty pegging sequence has no last-card owner',code='INVALID_STATE')
    if d['phase']=='peg':
        if not d['hands'][d['turn']] or d['go'][d['turn']] or sum(value(c) for c in d['sequence'])==31:fail('Pegging turn requires a player who still acts; thirty-one resets the count',code='INVALID_STATE')
        if any(d['go'][p] and legal_cards(d,p) for p in (0,1)):fail('A player may say go only when unable to play within thirty-one',code='INVALID_STATE')
    if d['phase']=='show' and (any(d['hands']) or d['sequence'] or any(d['go'])):fail('Count hands only after all pegging cards have been played and reset',code='INVALID_STATE')
    if d['phase']=='finished':
        if d['winner'] is None or d['scores'][d['winner']]<121 or d['scores'][1-d['winner']]>=121:fail('First player reaching one hundred twenty-one wins immediately',code='INVALID_STATE')
    elif d['winner'] is not None or max(d['scores'])>=121:fail('A winning score must finish the match',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type']
    if k=='deal':
        fields(p,dict(order=dict(type='array',minItems=52,maxItems=52,items=CARD)),'/params')
        if d['phase']!='deal' or len(set(p['order']))!=52:fail('Deal every physical card once at a hand boundary')
        fore=1-d['dealer'];d['hands'][fore]=p['order'][:12:2];d['hands'][d['dealer']]=p['order'][1:12:2];d['deck']=p['order'][12:];d['phase']='discard';d['hand_number']+=1;return d
    if k=='discard_to_crib':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1),cards=dict(type='array',minItems=2,maxItems=2,items=CARD)),'/params');q=p['player']
        if action.get('actor') is not None and action['actor']!=state['players'][q]['id']:fail('Wrong actor')
        if d['phase']!='discard' or d['discarded'][q] or len(set(p['cards']))!=2 or any(c not in d['hands'][q] for c in p['cards']):fail('Each player sets aside two distinct held cards once')
        d['hands'][q]=[c for c in d['hands'][q] if c not in p['cards']];d['crib']+=p['cards'];d['discarded'][q]=True
        if all(d['discarded']):d['phase']='cut'
        return d
    if k=='cut':
        fields(p,dict(index=dict(type='integer',minimum=0,maximum=39)),'/params')
        if d['phase']!='cut':fail('Cut after both players discard')
        d['starter']=d['deck'].pop(p['index']);d['phase']='peg';d['turn']=1-d['dealer']
        if rank(d['starter'])==11:award(d,d['dealer'],2)
        return d
    if k in ('play','go'):
        if d['phase']!='peg':fail('No pegging action is available')
        t=d['turn']
        if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        if k=='go':
            fields(p,{},'/params')
            if legal_cards(d,t):fail('Say go only when no held card fits within thirty-one')
            d['go'][t]=True
            if d['hands'][1-t] and not d['go'][1-t]:d['turn']=1-t;return d
            return close_sequence(d)
        fields(p,dict(card=CARD),'/params');c=p['card']
        if c not in legal_cards(d,t):fail('Play a held card without passing thirty-one')
        d['hands'][t].remove(c);d['played'][t].append(c);d['sequence'].append(c);d['last']=t;award(d,t,peg_score(d['sequence']))
        if d['phase']=='finished':return d
        if sum(value(c) for c in d['sequence'])==31:return reset_sequence(d,t)
        if not any(d['hands']):return close_sequence(d)
        if d['hands'][1-t] and not d['go'][1-t]:d['turn']=1-t
        elif d['hands'][t]:d['turn']=t
        else:return close_sequence(d)
        return d
    if k=='count_show':
        fields(p,{},'/params')
        if d['phase']!='show':fail('Complete pegging before counting the hands')
        index=d['show_index'];q=1-d['dealer'] if index==0 else d['dealer']
        if action.get('actor') is not None and action['actor']!=state['players'][q]['id']:fail('Wrong counting actor')
        award(d,q,show_score(d['crib'] if index==2 else d['played'][q],d['starter'],index==2))
        if d['phase']=='finished':return d
        if index<2:d['show_index']+=1;return d
        d.update(phase='deal',dealer=1-d['dealer'],turn=0,hands=[[],[]],played=[[],[]],crib=[],deck=[],starter=None,discarded=[False,False],sequence=[],go=[False,False],last=None,show_index=0);return d
    fail('Unknown action')
def legal(state):
    d=state['data'];actions=[];types=[]
    def event(k,params,cond,obs):types.append(dict(type=k,params_schema=params,preconditions=[cond],external_observations=[obs]))
    if d['phase']=='deal':event('deal',dict(order=dict(type='array',minItems=52,maxItems=52,items=CARD)),'Deal six alternating cards starting with nondealer.','External complete deck order.')
    elif d['phase']=='discard':
        for p in (0,1):
            if not d['discarded'][p]:actions += [dict(type='discard_to_crib',params=dict(player=p,cards=list(cs))) for cs in combinations(sorted(d['hands'][p]),2)]
    elif d['phase']=='cut':event('cut',dict(index=dict(type='integer',minimum=0,maximum=39)),'Both players have discarded.','External cut position selecting the starter.')
    elif d['phase']=='peg':
        cards=legal_cards(d,d['turn']);actions=[dict(type='play',params=dict(card=c)) for c in sorted(cards)] if cards else [dict(type='go',params={})]
    elif d['phase']=='show':actions=[dict(type='count_show',params={})]
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(turn=d['turn'],phase=d['phase'],pegging_total=sum(value(c) for c in d['sequence']),show_index=d['show_index']),completeness=False,reason='card_choices_with_external_deal_and_cut')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';w=d['winner']
    return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p==w else 2,score=d['scores'][p]) for p in (0,1)] if done else [],reason='first_to_121' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
