"""Single-class comparison final with five independent placement ballots."""
from copy import deepcopy
from ..values import fields,fail
INDEX=dict(type='integer',minimum=0,maximum=7)
RANKINGS=dict(type='array',minItems=5,maxItems=5,items=dict(type='array',minItems=8,maxItems=8,items=dict(type='integer',minimum=1,maximum=8,nullable=True)))
SCHEMAS=dict(start_comparison={},complete_comparison={},submit_rankings=dict(rankings=RANKINGS),correct_rankings=dict(rankings=RANKINGS),withdraw=dict(participant=INDEX),disqualify=dict(participant=INDEX),confirm_result={})
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if (d['phase'] in ('review','finished'))!=(d['rankings'] is not None):bad('Complete judge ballots are required for result review')
 if d['phase']=='ready' and 'dnf' in d['status']:bad('A pre-comparison withdrawal is DNS')
 if d['rankings'] is not None:
  eligible=[i for i,s in enumerate(d['status']) if s=='entered']
  for row in d['rankings']:
   if any((row[i] is not None)!=(i in eligible) for i in range(8)) or sorted(row[i] for i in eligible)!=list(range(1,len(eligible)+1)):bad('Every judge must rank each eligible entrant once without ties')
def exclude(d,i,status):
 d['status'][i]=status
 if d['rankings'] is not None:
  for row in d['rankings']:
   old=row[i];row[i]=None
   if old is not None:
    for j,v in enumerate(row):
     if v is not None and v>old:row[j]-=1
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase']
 if k not in SCHEMAS:fail('Unknown comparison-final event')
 fields(p,SCHEMAS[k],'/params')
 if k=='start_comparison':
  if phase!='ready':fail('Comparison has already started')
  d['phase']='comparing'
 elif k=='complete_comparison':
  if phase!='comparing':fail('No comparison is active')
  d['phase']='judging'
 elif k in ('submit_rankings','correct_rankings'):
  if phase!=('judging' if k=='submit_rankings' else 'review'):fail('Judge ballots require the proper scoring or review phase')
  d['rankings']=deepcopy(p['rankings']);d['phase']='review'
 elif k=='withdraw':
  i=p['participant']
  if phase not in ('ready','comparing') or d['status'][i]!='entered':fail('Withdrawal requires an unresolved entrant')
  exclude(d,i,'dns' if phase=='ready' else 'dnf')
 elif k=='disqualify':
  i=p['participant']
  if d['status'][i]=='dq':fail('Entrant is already disqualified')
  exclude(d,i,'dq')
 elif k=='confirm_result':
  if phase!='review':fail('Complete and review all judge ballots first')
  d['phase']='finished'
 return d
def total(d,i):return sum(sorted(row[i] for row in d['rankings'])[1:-1])
def legal(state):
 d=state['data'];names={'ready':['start_comparison','withdraw'],'comparing':['complete_comparison','withdraw'],'judging':['submit_rankings'],'review':['correct_rankings','confirm_result']}.get(d['phase'],[])
 if d['phase']!='finished':names+=['disqualify']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Comparison completion, eligibility and complete judge permutations must permit the event.'],external_observations=['Five final official placement ballots or an eligibility ruling.']) for k in names],constraints=dict(phase=d['phase'],eligible=[i for i,s in enumerate(d['status']) if s=='entered'],trim_each_end=1),completeness=False,reason='official_comparison_judgments')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';ranked=sorted((total(d,i),i) for i,s in enumerate(d['status']) if s=='entered') if done else [];winners=[state['players'][i]['id'] for score,i in ranked if score==ranked[0][0]] if ranked else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other<score for other,_ in ranked),judge_place_sum=score) for score,i in ranked],reason='comparison_final_confirmed' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
