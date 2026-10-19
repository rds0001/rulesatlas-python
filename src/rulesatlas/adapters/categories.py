"""Category-and-letter word rounds with explicit external answer adjudication."""
from copy import deepcopy
import re
from ..values import fields,fail
CATEGORIES=dict(type='array',minItems=1,maxItems=12,items=dict(type='string',minLength=1,maxLength=64))
LETTERS=dict(type='array',minItems=1,maxItems=26,items=dict(type='string',minLength=1,maxLength=1))
def finish_review(d):
    if d['phase']=='judging' and all(v!=-1 for row in d['rounds'][int(d['current'])]['judgments'] for v in row):
        d['current']+=1;d['phase']='finished' if d['current']==len(d['letters']) else 'writing'
    return d
def validate(d):
    if not d['configured']:
        if d['categories'] or d['letters'] or d['rounds'] or d['current'] or d['phase']!='writing':fail('Unconfigured game contains data',code='INVALID_STATE')
        return
    n=len(d['categories']);total=len(d['letters'])
    if not n or not total or len(set(d['categories']))!=n or len(set(d['letters']))!=total or any(not re.fullmatch('[A-Z]',v) for v in d['letters']):fail('Categories and letters must be distinct and valid',code='INVALID_STATE')
    if len(d['rounds'])!=total or d['current']>total or (d['phase']=='finished')!=(d['current']==total):fail('Round and phase mismatch',code='INVALID_STATE')
    for index,r in enumerate(d['rounds']):
        if any(len(row)!=n for row in r['answers']+r['judgments']):fail('Round category count mismatch',code='INVALID_STATE')
        for p in range(2):
            for c,word in enumerate(r['answers'][p]):
                judgment=r['judgments'][p][c]
                if word and (not re.fullmatch('[A-Z]+(?:[ -][A-Z]+)*',word) or word[0]!=d['letters'][index]):fail('Answer must start with the round letter',code='INVALID_STATE')
                if not word and judgment==1:fail('Empty answer cannot be valid',code='INVALID_STATE')
                if index<d['current'] and judgment==-1:fail('Completed round has an unjudged answer',code='INVALID_STATE')
                if index>d['current'] and word or (index>d['current'] or index==d['current'] and d['phase']=='writing') and judgment!=-1:fail('Future or open round contains adjudication',code='INVALID_STATE')
        if index==d['current'] and d['phase']=='judging' and all(v!=-1 for row in r['judgments'] for v in row):fail('Completed review must advance',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if not d['configured']:
        if kind!='configure':fail('Supply categories and round letters first')
        fields(p,dict(categories=CATEGORIES,letters=LETTERS),'/params');d.update(configured=True,categories=deepcopy(p['categories']),letters=deepcopy(p['letters']),rounds=[dict(answers=[['']*len(p['categories']) for _ in range(2)],judgments=[[-1]*len(p['categories']) for _ in range(2)]) for _ in p['letters']]);return d
    r=d['rounds'][int(d['current'])]
    if kind=='write':
        if d['phase']!='writing':fail('Writing has ended')
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1),category=dict(type='integer',minimum=0,maximum=len(d['categories'])-1),word=dict(type='string',minLength=0,maxLength=64)),'/params');t=int(p['player']);c=int(p['category']);word=p['word']
        if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        if word and (not re.fullmatch('[A-Z]+(?:[ -][A-Z]+)*',word) or word[0]!=d['letters'][int(d['current'])]):fail('Answer must start with the round letter')
        if r['answers'][t][c]==word:fail('Answer is unchanged')
        r['answers'][t][c]=word;return d
    if kind in ('stop','time_expired'):
        if d['phase']!='writing':fail('Writing has already ended')
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1)) if kind=='stop' else {},'/params')
        if kind=='stop':
            t=int(p['player'])
            if not all(r['answers'][t]):fail('Stopping player must fill every category')
            if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
        r['judgments']=[[-1 if w else 0 for w in row] for row in r['answers']];d['phase']='judging';return finish_review(d)
    if kind!='judge' or d['phase']!='judging':fail('Action is not permitted in this phase')
    fields(p,dict(player=dict(type='integer',minimum=0,maximum=1),category=dict(type='integer',minimum=0,maximum=len(d['categories'])-1),valid=dict(type='boolean')),'/params');t=int(p['player']);c=int(p['category'])
    if not r['answers'][t][c]:fail('Empty answer is already invalid')
    r['judgments'][t][c]=int(p['valid']);return finish_review(d)
def legal(state):
    d=state['data'];schemas={}
    if not d['configured']:schemas=dict(configure=dict(categories=CATEGORIES,letters=LETTERS))
    else:
        person=dict(player=dict(type='integer',minimum=0,maximum=1));cell=dict(**person,category=dict(type='integer',minimum=0,maximum=len(d['categories'])-1))
        if d['phase']=='writing':schemas=dict(write=dict(**cell,word=dict(type='string',minLength=0,maxLength=64)),stop=person,time_expired={})
        else:schemas=dict(judge=dict(**cell,valid=dict(type='boolean')))
    return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['The phase, category, starting letter and answer completeness must permit this action.'],external_observations=['Player answers, an agreed time limit or official category-validity judgments.']) for k,v in schemas.items()],constraints=dict(round=d['current']+1 if d['configured'] and d['phase']!='finished' else None,phase=d['phase']),completeness=False,reason='external_category_adjudication')
def totals(d):
    scores=[0,0]
    for r in d['rounds'][:int(d['current'])]:
        for c in range(len(d['categories'])):
            valid=[p for p in (0,1) if r['judgments'][p][c]==1]
            if len(valid)==1:scores[valid[0]]+=20
            elif len(valid)==2:
                points=5 if r['answers'][0][c]==r['answers'][1][c] else 10
                scores=[v+points for v in scores]
    return scores
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';scores=totals(d);winners=[state['players'][p]['id'] for p in (0,1) if scores[p]==max(scores)] if terminal else []
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('draw' if scores[0]==scores[1] else 'win') if terminal else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if terminal else [],placements=[dict(player_id=state['players'][p]['id'],place=1+sum(v>scores[p] for v in scores),score=scores[p]) for p in (0,1)] if terminal else [],reason='all_rounds_scored' if terminal else 'ongoing' if d['configured'] else 'awaiting_configuration',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
