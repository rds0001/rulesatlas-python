"""Three-round assaut in a ring, using historical FIS double-category cards."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
P=I(0,1);B=dict(type='boolean')
PAIR=dict(type='array',minItems=2,maxItems=2,items=I(1,3))
CARD=dict(type='array',minItems=2,maxItems=2,items=PAIR,nullable=True)
CARDS=dict(type='array',minItems=3,maxItems=3,items=CARD)
APPROVAL=dict(type='array',minItems=3,maxItems=3,items=B)
def card_valid(card):return card is None or all(pair in ([2,2],[3,2],[2,3],[3,1],[1,3]) for pair in card)
def totals(d):return [[sum(sum(card[j][k][t] for k in (0,1)) for card in d['cards'] if card[j] is not None)-2*d['penalties'][t] for t in (0,1)] for j in range(3)]
def votes(d):
 s=totals(d)
 return ['non_decision' if all(card[j] is None for card in d['cards']) else 'draw' if s[j][0]==s[j][1] else str(int(s[j][1]>s[j][0])) for j in range(3)]
def majority(d):
 vv=votes(d)
 return next((v for v in ('0','1','draw','non_decision') if vv.count(v)>=2),None)
def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason,break_ms=0)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if any(not card_valid(card) for row in d['cards'] for card in row):bad('Each category must be tied, dominated or markedly dominated')
 n=len(d['cards']);r=d['round']
 if n>r or n<(r-1):bad('Cards must agree with the current round')
 if d['phase'] in ('ready','fighting','paused','judging') and n!=r-1:bad('Current round cannot already be scored')
 if d['phase'] in ('break','decision','delegate') and n!=r:bad('Completed-round phase requires its three cards')
 if d['phase']=='ready' and d['remaining_ms']!=120000:bad('Ready round requires its full clock')
 if d['phase'] in ('fighting','paused') and not d['remaining_ms']:bad('Expired round requires judging')
 if d['phase']=='judging' and d['remaining_ms'] and not d['technical_stop']:bad('Partial-round judging requires official stoppage')
 if d['phase']=='break' and (r==3 or not d['break_ms'] or d['remaining_ms'] or d['technical_stop']):bad('Rest follows a completed nonfinal round')
 if d['phase']!='break' and d['break_ms']:bad('Rest clock outside an interval')
 if d['phase'] in ('decision','delegate') and not(d['round']==3 or d['technical_stop']):bad('Final decision requires all rounds or official stoppage')
 if d['phase']=='finished':
  if d['reason'] is None or (d['winner'] is None)!=(d['reason'] in ('draw','non_decision','double_disqualification')):bad('Result must agree with winner presence')
  if d['reason']=='judges' and majority(d)!=str(d['winner']):bad('Judge victory must agree with adjusted cards')
  if d['reason']=='draw' and (not d['allow_draw'] or majority(d)!='draw'):bad('Draw requires a majority and permitted format')
 else:
  if d['winner'] is not None or d['reason'] is not None or max(d['penalties'])>=3:bad('A decided bout cannot continue')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='ready':
  s['start_round']={}
  if d['round']==1:s['configure']=dict(allow_draw=B)
 if ph in ('fighting','break'):s['elapse']=dict(milliseconds=I(1,120000))
 if ph=='fighting':s['pause']={}
 if ph=='paused':s['resume']={}
 if ph in ('fighting','paused'):s['medical_score_stop']={}
 if ph=='judging':s['submit_round']=dict(cards=CARDS)
 if ph=='decision':s.update(confirm_result={},correct_round=dict(round=I(1,len(d['cards'])),cards=CARDS))
 if ph=='delegate':s['delegate_decision']=dict(winner=P)
 if ph not in ('decision','delegate'):s['penalty_vote']=dict(player=P,approvals=APPROVAL)
 s.update(disqualify_vote=dict(player=P,approvals=APPROVAL),double_disqualification=dict(approvals=dict(type='array',minItems=2,maxItems=2,items=APPROVAL)),withdraw=dict(player=P),referee_stop=dict(winner=P),non_decision={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='configure':d['allow_draw']=p['allow_draw']
 elif k in ('start_round','resume'):d['phase']='fighting'
 elif k=='pause':d['phase']='paused'
 elif k=='elapse':
  f='break_ms' if d['phase']=='break' else 'remaining_ms'
  if p['milliseconds']>d[f]:fail('Elapsed time exceeds the current interval')
  d[f]-=p['milliseconds']
  if not d[f]:
   if f=='break_ms':d.update(phase='ready',round=d['round']+1,remaining_ms=120000)
   else:d['phase']='judging'
 elif k=='medical_score_stop':d.update(phase='judging',technical_stop=True)
 elif k in ('submit_round','correct_round'):
  if not all(card_valid(card) for card in p['cards']):fail('Each category must use an allowed scoring pair')
  if k=='correct_round':d['cards'][p['round']-1]=deepcopy(p['cards'])
  else:
   d['cards'].append(deepcopy(p['cards']))
   if d['round']==3 or d['technical_stop']:d['phase']='decision'
   else:d.update(phase='break',break_ms=60000)
 elif k=='penalty_vote':
  if sum(p['approvals'])>=2:
   d['penalties'][p['player']]+=1
   if d['penalties'][p['player']]==3:finish(d,1-p['player'],'disqualification')
  if d['phase']=='fighting':d['phase']='paused'
 elif k=='disqualify_vote':
  if sum(p['approvals'])>=2:finish(d,1-p['player'],'disqualification')
  elif d['phase']=='fighting':d['phase']='paused'
 elif k=='double_disqualification':
  if any(sum(v)<2 for v in p['approvals']):fail('Both exclusions require a separate judge majority')
  finish(d,None,'double_disqualification')
 elif k=='confirm_result':
  m=majority(d)
  if m in ('0','1'):finish(d,int(m),'judges')
  elif m=='non_decision':finish(d,None,'non_decision')
  elif m=='draw' and d['allow_draw']:finish(d,None,'draw')
  else:d['phase']='delegate'
 elif k=='delegate_decision':finish(d,p['winner'],'delegate')
 elif k=='withdraw':finish(d,1-p['player'],'withdrawal')
 elif k=='referee_stop':finish(d,p['winner'],'referee_stop')
 elif k=='non_decision':finish(d,None,'non_decision')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Round, judge approval, scorecard and penalty conditions must permit the event.'],external_observations=['Official paired category marks, accepted penalty votes and stoppage rulings.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],round=d['round'],remaining_ms=d['remaining_ms'],break_ms=d['break_ms'],penalties=d['penalties'],judge_totals=totals(d),judge_votes=votes(d)),completeness=False,reason='official_assaut_double_category_cards')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner'];review=d['phase'] in ('judging','decision','delegate')
 return dict(status='terminal' if done else 'awaiting_adjudication' if review else 'ongoing',result_kind=('no_contest' if d['reason']=='non_decision' else 'draw' if d['reason']=='draw' else 'disqualification' if d['reason']=='double_disqualification' else 'win') if done else 'none',winners=[state['players'][w]['id']] if w is not None else [],losers=([state['players'][1-w]['id']] if w is not None else [p['id'] for p in state['players']] if d['reason']=='double_disqualification' else []),placements=[],reason=d['reason'] if done else 'official_judging_required' if review else 'ongoing',evidence_required=['Official judge cards or delegate decision.'] if review else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
