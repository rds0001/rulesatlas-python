"""One duplicate bridge board: auction, legal card play and contract scoring."""
from copy import deepcopy
from ..values import fields,fail
CARD=dict(type='integer',minimum=0,maximum=51)
def auction(d):
    high=None;bidder=None;double=0;passes=0;first={};done=False
    for i,c in enumerate(d['auction']):
        p=(d['dealer']+i)%4
        if done:fail('Auction continued after closing',code='INVALID_STATE')
        if c==0:passes+=1
        elif c==1:
            if high is None or double or p%2==bidder%2:fail('Double requires an opposing undoubled contract',code='INVALID_STATE')
            double=1;passes=0
        elif c==2:
            if high is None or double!=1 or p%2!=bidder%2:fail('Redouble requires own side’s doubled contract',code='INVALID_STATE')
            double=2;passes=0
        else:
            if high is not None and c<=high:fail('Bids must increase by level and denomination',code='INVALID_STATE')
            high=c;bidder=p;double=0;passes=0;first.setdefault((p%2,(c-3)%5),p)
        done=passes>=(4 if high is None else 3)
    contract=None if high is None else dict(level=(high-3)//5+1,strain=(high-3)%5,declarer=first[(bidder%2,(high-3)%5)],double=double)
    return done,contract

def trick_winner(cards,leader,strain):
    led=cards[0]//13;trump=strain if strain<4 else -1
    i=max(range(4),key=lambda i:(2 if cards[i]//13==trump else 1 if cards[i]//13==led else 0,cards[i]%13))
    return (leader+i)%4

def playable(d):
    hand=d['hands'][d['turn']]
    if not d['trick']:return hand
    follow=[c for c in hand if c//13==d['trick'][0]//13]
    return follow or hand

def validate(d):
    if d['phase']=='deal':
        if any(d['hands']) or any(d['won']) or d['trick'] or d['auction'] or d['claim'] is not None:fail('Undealt board must contain no cards or calls',code='INVALID_STATE')
        return
    if sorted(sum(d['hands'],[])+sum(d['won'],[])+d['trick'])!=list(range(52)) or any(len(w)%4 for w in d['won']):fail('Conserve all fifty-two cards and complete captured tricks',code='INVALID_STATE')
    closed,contract=auction(d);completed=sum(len(w)//4 for w in d['won'])
    if not closed:
        if d['phase']!='auction' or completed or d['trick'] or any(len(h)!=13 for h in d['hands']) or d['turn']!=(d['dealer']+len(d['auction']))%4 or d['claim'] is not None:fail('Active auction must retain full hands and correct caller',code='INVALID_STATE')
        return
    if contract is None:
        if d['phase']!='finished' or completed or d['trick'] or d['claim'] is not None or any(len(h)!=13 for h in d['hands']):fail('Four opening passes finish an unplayed board',code='INVALID_STATE')
        return
    for p,h in enumerate(d['hands']):
        played=(p-d['leader'])%4<len(d['trick'])
        if len(h)!=13-completed-int(played):fail('Hand sizes disagree with completed and current tricks',code='INVALID_STATE')
    if d['turn']!=(d['leader']+len(d['trick']))%4:fail('Current trick and player turn disagree',code='INVALID_STATE')
    if completed==0 and d['leader']!=(contract['declarer']+1)%4:fail('Opening lead belongs to declarer’s left-hand opponent',code='INVALID_STATE')
    if d['claim'] is not None:
        if d['claim']>13-completed or completed==13 or d['phase']!='finished':fail('Adjudicated claim must allocate remaining tricks and finish play',code='INVALID_STATE')
    elif d['phase']!=('finished' if completed==13 else 'play'):fail('Thirteen completed tricks finish the board',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type']
    if k=='deal':
        fields(p,dict(order=dict(type='array',minItems=52,maxItems=52,items=CARD),dealer=dict(type='integer',minimum=0,maximum=3),vulnerable=dict(type='array',minItems=2,maxItems=2,items=dict(type='boolean'))),'/params')
        if d['phase']!='deal' or len(set(p['order']))!=52:fail('Supply a complete unique deck for an undealt board')
        d['dealer']=p['dealer'];d['vulnerable']=p['vulnerable'][:];d['turn']=p['dealer'];d['hands']=[p['order'][i::4] for i in range(4)];d['phase']='auction';return d
    if k=='call':
        fields(p,dict(call=dict(type='integer',minimum=0,maximum=37)),'/params')
        if d['phase']!='auction':fail('Calls are allowed only in an open auction')
        if action.get('actor') is not None and action['actor']!=state['players'][d['turn']]['id']:fail('Wrong actor')
        d['auction'].append(p['call']);closed,contract=auction(d);d['turn']=(d['turn']+1)%4
        if closed:
            if contract is None:d['phase']='finished'
            else:d['phase']='play';d['leader']=(contract['declarer']+1)%4;d['turn']=d['leader']
        return d
    if k=='settle_claim':
        fields(p,dict(ns_remaining=dict(type='integer',minimum=0,maximum=13)),'/params')
        if d['phase']!='play' or p['ns_remaining']>13-sum(len(w)//4 for w in d['won']):fail('Allocate only the remaining tricks by agreement or official adjudication')
        d['claim']=p['ns_remaining'];d['phase']='finished';return d
    if k!='play':fail('Unknown action')
    fields(p,dict(card=CARD),'/params')
    if d['phase']!='play':fail('Card play requires a completed non-passed-out auction')
    contract=auction(d)[1];controller=contract['declarer'] if d['turn']==(contract['declarer']+2)%4 else d['turn']
    if action.get('actor') is not None and action['actor']!=state['players'][controller]['id']:fail('The declarer controls dummy; other players control their own hands')
    if p['card'] not in playable(d):fail('Play a held card and follow the led suit when possible')
    d['hands'][d['turn']].remove(p['card']);d['trick'].append(p['card'])
    if len(d['trick'])==4:
        w=trick_winner(d['trick'],d['leader'],contract['strain']);d['won'][w]+=d['trick'];d['trick']=[];d['leader']=w;d['turn']=w
        if not any(d['hands']):d['phase']='finished'
    else:d['turn']=(d['turn']+1)%4
    return d

def contract_score(c,tricks,vulnerable):
    need=6+c['level'];made=tricks-need;double=c['double'];factor=2**double;strain=c['strain']
    if made<0:
        down=-made
        if not double:return -down*(100 if vulnerable else 50)
        penalty=(200+300*(down-1)) if vulnerable else (100+200*min(2,down-1)+300*max(0,down-3))
        return -penalty*(2 if double==2 else 1)
    base=(20*c['level'] if strain<2 else 30*c['level']+(10 if strain==4 else 0))*factor
    bonus=(500 if vulnerable else 300) if base>=100 else 50
    if c['level']==6:bonus+=750 if vulnerable else 500
    if c['level']==7:bonus+=1500 if vulnerable else 1000
    insult=50*(factor//2) if double else 0
    over=made*((200 if vulnerable else 100)*(2 if double==2 else 1) if double else 20 if strain<2 else 30)
    return base+bonus+insult+over

def legal(state):
    d=state['data'];actions=[];types=[];constraints=dict(turn=d['turn'])
    if d['phase']=='deal':types=[dict(type='deal',params_schema=dict(order=dict(type='array',minItems=52,maxItems=52,items=CARD),dealer=dict(type='integer',minimum=0,maximum=3),vulnerable=dict(type='array',minItems=2,maxItems=2,items=dict(type='boolean'))),preconditions=['Every physical card exactly once.'],external_observations=['External card allocation, board dealer and NS/EW vulnerability.'])]
    elif d['phase']=='auction':
        c=auction(d)[1];bids=[x for x in d['auction'] if x>=3];high=max(bids) if bids else 2
        calls=[0]+list(range(high+1,38))
        if c is not None:
            if d['turn']%2!=c['declarer']%2 and c['double']==0:calls.append(1)
            if d['turn']%2==c['declarer']%2 and c['double']==1:calls.append(2)
        actions=[dict(type='call',params=dict(call=c)) for c in sorted(calls)]
    else:
        c=auction(d)[1];actions=[dict(type='play',params=dict(card=x)) for x in sorted(playable(d))];dummy=(c['declarer']+2)%4
        constraints.update(declarer=c['declarer'],dummy=dummy,dummy_exposed=bool(d['trick'] or any(d['won'])),controller=c['declarer'] if d['turn']==dummy else d['turn'])
        types=[dict(type='settle_claim',params_schema=dict(ns_remaining=dict(type='integer',minimum=0,maximum=13-sum(len(w)//4 for w in d['won']))),preconditions=['Agreement by the opponents or official adjudication fixes all remaining tricks.'],external_observations=['Agreed or adjudicated number of remaining tricks awarded to North-South.'])]
    return dict(mode='event_types',actions=actions,action_types=types,constraints=constraints,completeness=False,reason='enumerated_calls_and_cards_with_external_deal_or_claim')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';c=auction(d)[1] if d['phase']!='deal' else None;score=0;declarer_tricks=None
    if done and c is not None:
        completed=sum(len(w)//4 for w in d['won']);ns=sum(len(d['won'][p])//4 for p in (0,2))+(d['claim'] if d['claim'] is not None else 0)
        declarer_tricks=ns if c['declarer']%2==0 else 13-ns;score=contract_score(c,declarer_tricks,d['vulnerable'][c['declarer']%2])*(1 if c['declarer']%2==0 else -1)
    side=0 if score>0 else 1;winners=[state['players'][p]['id'] for p in range(4) if p%2==side] if done and score else []
    return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if not score else 'win') if done else 'none',winners=winners,losers=[state['players'][p]['id'] for p in range(4) if p%2!=side] if done and score else [],placements=[dict(side='NS',score=score),dict(side='EW',score=-score)] if done else [],reason='passed_out' if done and c is None else 'contract_scored' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
