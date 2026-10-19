"""Disc-golf scorecards and deadline rules over shared stroke-round mechanics."""
from copy import deepcopy
from . import golf
from ..values import fields,fail
I=golf.I
CARD=dict(player=golf.PLAYER,scores=dict(type='array',minItems=18,maxItems=18,items=I(1,1000,nullable=True)),total=I(1,18000,nullable=True))
ADJUST=dict(player=golf.PLAYER,delta=I(-1000,1000))
ELAPSE=dict(milliseconds=I(1,1800001))
def group_done(d):return all(r['status'] in ('card','returned','dns','dnf','dq') for r in d['golfers'])
def validate(d):
 golf.validate(d)
 if group_done(d)!=(d['card_elapsed_ms'] is not None):fail('Scorecard clock starts when the whole group finishes',code='INVALID_STATE')
 for r in d['golfers']:
  if r['status']=='returned' and (r['card']!=r['holes'] or sum(r['card'])+r['round_adjustment']+2*(r['card_error']+r['late_card'])<0):fail('Disc golf uses the corrected card plus explicit round penalties',code='INVALID_STATE')
  if r['card_error'] and r['card'] is None:fail('Card error exists before a card was submitted',code='INVALID_STATE')
  if r['late_card'] and (d['card_elapsed_ms'] is None or d['card_elapsed_ms']<=1800000):fail('Late-card penalty precedes the deadline',code='INVALID_STATE')
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k=='return_card':
  fields(p,CARD,'/params');r=d['golfers'][p['player']]
  if r['status']!='card' or not group_done(d):fail('Finish the group round before returning the independent scorecard')
  r['card_error']=p['scores']!=r['holes'] or p['total']!=sum(r['holes']);r['card']=r['holes'][:];r['status']='returned'
  d['phase']='review' if golf.settled(d) else 'round'
 elif k=='elapse_card_window':
  fields(p,ELAPSE,'/params')
  if d['card_elapsed_ms'] is None or d['card_elapsed_ms']+p['milliseconds']>1800001:fail('Advance the scorecard clock only up to the first expired millisecond')
  d['card_elapsed_ms']+=p['milliseconds']
  if d['card_elapsed_ms']>1800000:
   for r in d['golfers']:
    if r['status']=='card':r['late_card']=True
 elif k=='adjust_penalty':
  fields(p,ADJUST,'/params');r=d['golfers'][p['player']]
  if r['status']!='returned' or p['delta']==0:fail('Director adjustment requires a returned card and a nonzero correction')
  r['round_adjustment']+=p['delta']
  if abs(r['round_adjustment'])>1000 or sum(r['card'])+r['round_adjustment']+2*(r['card_error']+r['late_card'])<0:fail('Adjusted total is outside the supported score range')
 elif k=='unknown_penalty':fail('Use the director penalty adjustment for a returned disc-golf card')
 else:d=golf.apply(state,action)
 if group_done(d) and d['card_elapsed_ms'] is None:d['card_elapsed_ms']=0
 return d
def legal(state):
 d=state['data'];res=golf.legal(state);types=[]
 for item in res['action_types']:
  if item['type']=='unknown_penalty':continue
  if item['type']=='return_card':item['params_schema']=CARD
  types.append(item)
 if d['phase']!='finished':
  if d['card_elapsed_ms'] is not None and d['card_elapsed_ms']<1800001:types.append(dict(type='elapse_card_window',params_schema=ELAPSE,preconditions=['The group has completed its round.'],external_observations=['Elapsed time since group completion.']))
  if any(r['status']=='returned' for r in d['golfers']):types.append(dict(type='adjust_penalty',params_schema=ADJUST,preconditions=['An official adjustment applies to an already returned card.'],external_observations=['Tournament director penalty addition or removal.']))
 res['action_types']=types;res['constraints']['card_elapsed_ms']=d['card_elapsed_ms'];res['reason']='official_disc_golf_round';return res
def outcome(state,pack):
 d=state['data'];t=d['phase']=='finished';ranked=sorted((sum(r['card'])+r['round_adjustment']+2*(r['card_error']+r['late_card']),i) for i,r in enumerate(d['golfers']) if r['status']=='returned') if t else [];winners=[state['players'][i]['id'] for s,i in ranked if s==ranked[0][0]] if ranked else []
 return dict(status='terminal' if t else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if t else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other<s for other,_ in ranked),throws=s) for s,i in ranked],reason='round_confirmed' if t else 'scorecard_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official scorecard confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if t else None)
