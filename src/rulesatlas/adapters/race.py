"""Single-final race administration: starts, eligibility, results and ranking."""
from copy import deepcopy
from ..values import fields,fail
INDEX={'type':'integer','minimum':0,'maximum':7}
TIME={'type':'integer','minimum':1,'maximum':1000000000000,'nullable':True}
class Race:
    def __init__(self,config):self.config=config
    def controls(self,d):return d['route'] if self.config.get('route_configurable') else self.config.get('controls',[])
    def result_statuses(self):return ['finished','dns','dnf','dq']+(['mp','ot'] if self.config.get('route_configurable') else [])
    def validate(self,d):
        phase=d['phase'];runners=d['runners']
        controls=self.controls(d)
        if self.config.get('route_configurable'):
            if len(set(controls))!=len(controls):fail('Route controls must be unique',code='INVALID_STATE')
            if (phase=='racing' or any(r['status']=='finished' for r in runners)) and (not controls or not d['route_locked']):fail('Race route is not configured',code='INVALID_STATE')
        for r in runners:
            if (r['status']=='finished')!=(r['time_us'] is not None):fail('Finish status and time mismatch',code='INVALID_STATE')
            if self.config.get('controls') or self.config.get('route_configurable'):
                if r['status']=='ready' and r['checkpoints_completed']!=0:fail('Checkpoints exist before the start',code='INVALID_STATE')
                if r['checkpoints_completed']>len(controls) or (r['checkpoints_completed']==0)!=(r['last_checkpoint_time'] is None):fail('Checkpoint state mismatch',code='INVALID_STATE')
                if r['status']=='finished' and (r['checkpoints_completed']!=len(controls) or r['time_us']<r['last_checkpoint_time']):fail('Finish requires all checkpoints in order',code='INVALID_STATE')
            if self.config.get('route_configurable') and r['status']=='finished' and d['time_limit_us'] is not None and r['time_us']>d['time_limit_us']:fail('Finish exceeds the configured time limit',code='INVALID_STATE')
            if r['time_us'] is not None and r['time_us']%self.config['time_quantum_us']:fail('Time precision does not match the event',code='INVALID_STATE')
            if self.config.get('walking'):
                reds=r['red_cards'];yellows=r['yellow_paddles']
                if len({c['judge'] for c in reds})!=len(reds) or len({(c['judge'],c['offence']) for c in yellows})!=len(yellows):fail('Duplicate walking judge card or paddle',code='INVALID_STATE')
                if len(reds)>=3 and r['status']!='dq':fail('Three independent red cards require disqualification',code='INVALID_STATE')
                if r['status'] in ('ready','dns') and (reds or yellows):fail('Walking judgments require a started participant',code='INVALID_STATE')
            if r['warnings']==2 and r['status']!='dq':fail('Two warnings require disqualification',code='INVALID_STATE')
            if not self.config['conduct_warnings'] and r['warnings']:fail('Warning escalation is not part of this variant',code='INVALID_STATE')
        states=[r['status'] for r in runners]
        if ('ready' in states and phase!='ready') or ('running' in states and phase!='racing'):fail('Participant phase mismatch',code='INVALID_STATE')
        if phase=='ready' and ('finished' in states or 'dnf' in states):fail('Results exist before a valid start',code='INVALID_STATE')
        if phase in ('ready','racing') and not any(s in ('ready','running') for s in states):fail('Resolved race must enter review',code='INVALID_STATE')
        if phase in ('review','finished') and any(s in ('ready','running') for s in states):fail('Unresolved participant result',code='INVALID_STATE')
    def settle(self,d):
        if not any(r['status'] in ('ready','running') for r in d['runners']):d['phase']='review'
    def apply(self,state,action):
        INDEX=dict(type='integer',minimum=0,maximum=len(state['data']['runners'])-1)
        d=deepcopy(state['data']);p=action['params'];kind=action['type'];phase=d['phase']
        if kind in ('red_card','yellow_paddle','remove_red_card'):
            specs={'participant':INDEX,'judge':{'type':'integer','minimum':0,'maximum':8}}
            if kind!='remove_red_card':specs['offence']={'type':'string','enum':['loss_of_contact','bent_knee']}
            fields(p,specs,'/params')
            if not self.config.get('walking'):fail('Walking judgments are not part of this profile')
            r=d['runners'][int(p['participant'])]
            if kind=='remove_red_card':
                if phase!='review' or not any(c['judge']==p['judge'] for c in r['red_cards']):fail('Remove an existing red card only during official result review')
                r['red_cards']=[c for c in r['red_cards'] if c['judge']!=p['judge']]
            else:
                if phase not in ('racing','review') or r['status'] not in ('running','finished'):fail('Walking judgment requires an active or provisionally finished participant')
                card={k:p[k] for k in ('judge','offence')}
                if kind=='red_card':
                    if any(c['judge']==p['judge'] for c in r['red_cards']):fail('Each judge may issue only one red card per participant')
                    r['red_cards'].append(card)
                    if len(r['red_cards'])==3:r['status']='dq';r['time_us']=None
                else:
                    if card in r['yellow_paddles']:fail('A judge may show each offence paddle only once per participant')
                    r['yellow_paddles'].append(card)
                self.settle(d)
        elif kind=='configure_route':
            fields(p,{'controls':{'type':'array','items':{'type':'string','minLength':1,'maxLength':64},'minItems':1,'maxItems':128},'time_limit_us':TIME},'/params')
            if not self.config.get('route_configurable') or phase!='ready' or d['route_locked']:fail('Route cannot be configured now')
            d['route']=deepcopy(p['controls']);d['time_limit_us']=p['time_limit_us']
        elif kind=='visit_control':
            fields(p,{'participant':INDEX,'control':{'type':'string','minLength':1,'maxLength':64},'time_us':dict(TIME,nullable=False)},'/params');r=d['runners'][int(p['participant'])];controls=self.controls(d);index=int(r.get('checkpoints_completed',0))
            if phase!='racing' or r['status']!='running' or index>=len(controls) or p['control']!=controls[index]:fail('Control is not the next required checkpoint')
            if r['last_checkpoint_time'] is not None and p['time_us']<r['last_checkpoint_time']:fail('Checkpoint times must not go backwards')
            r['checkpoints_completed']+=1;r['last_checkpoint_time']=p['time_us']
        elif kind=='start':
            fields(p,{},'/params')
            if phase!='ready':fail('Race cannot start in this phase')
            if self.config.get('route_configurable'):
                if not d['route']:fail('Configure the route first')
                d['route_locked']=True
            for r in d['runners']:
                if r['status']=='ready':r['status']='running'
            d['phase']='racing'
        elif kind=='confirm_result':
            fields(p,{},'/params')
            if phase!='review':fail('Resolve all participant results first')
            d['phase']='finished'
        elif kind=='amend_result':
            fields(p,{'participant':INDEX,'status':{'type':'enum','values':self.result_statuses()},'time_us':TIME,'warnings':{'type':'integer','minimum':0,'maximum':2}},'/params')
            if phase!='review':fail('Amendments require result review')
            d['runners'][int(p['participant'])].update({k:p[k] for k in ('status','time_us','warnings')})
        elif kind=='record_finish':
            fields(p,{'participant':INDEX,'time_us':dict(TIME,nullable=False)},'/params');r=d['runners'][int(p['participant'])]
            if phase!='racing' or r['status']!='running':fail('Participant cannot finish now')
            controls=self.controls(d)
            if controls and r['last_checkpoint_time'] is not None and p['time_us']<r['last_checkpoint_time']:fail('Finish time precedes the last checkpoint')
            if controls and r['checkpoints_completed']!=len(controls):
                if not self.config.get('route_configurable'):fail('Complete all relay exchanges before finishing')
                r['status']='mp';r['time_us']=None
            elif self.config.get('route_configurable') and d['time_limit_us'] is not None and p['time_us']>d['time_limit_us']:
                r['status']='ot';r['time_us']=None
            else:
                if controls and p['time_us']<r['last_checkpoint_time']:fail('Finish time precedes the last checkpoint')
                r['status']='finished';r['time_us']=p['time_us']
            self.settle(d)
        elif kind in ('withdraw','disqualify','false_start','warn'):
            fields(p,{'participant':INDEX},'/params');r=d['runners'][int(p['participant'])]
            if kind=='withdraw':
                if phase not in ('ready','racing') or r['status'] not in ('ready','running'):fail('Participant cannot withdraw now')
                r['status']='dns' if phase=='ready' else 'dnf'
            elif kind=='disqualify':
                if r['status']=='dq':fail('Participant is already disqualified')
                r['status']='dq';r['time_us']=None
            elif kind=='warn':
                if not self.config['conduct_warnings'] or phase not in (('ready','racing') if self.config.get('race_warnings') else ('ready',)) or r['status'] not in ('ready','running'):fail('A conduct warning is unavailable')
                r['warnings']+=1
                if r['warnings']==2:r['status']='dq'
            else:
                if not self.config.get('false_start_disqualifies',True):fail('False-start disqualification is not part of this variant')
                if phase not in ('ready','racing') or r['status'] not in ('ready','running'):fail('False-start decision is unavailable')
                if self.config['recall'] and any(x['status']=='finished' or x.get('checkpoints_completed',0)>0 for x in d['runners']):fail('A completed finish cannot be recalled by this event')
                if self.config.get('shared_start_warning'):
                    if d['start_warning']:r['status']='dq'
                    else:d['start_warning']=True
                elif self.config.get('false_start_warning'):
                    r['warnings']+=1
                    if r['warnings']==2:r['status']='dq'
                else:r['status']='dq'
                r['time_us']=None
                if phase=='racing' and self.config['recall']:
                    for x in d['runners']:
                        if x['status']=='running':x['status']='ready'
                        elif x['status']=='dnf':x['status']='dns'
                    d['phase']='ready'
            self.settle(d)
        else:fail('Unknown action')
        return d
    def legal(self,state):
        INDEX=dict(type='integer',minimum=0,maximum=len(state['data']['runners'])-1)
        d=state['data'];phase=d['phase'];schemas={}
        if phase=='ready':
            schemas.update(start={},withdraw={'participant':INDEX},false_start={'participant':INDEX})
            if self.config.get('route_configurable') and not d['route_locked']:schemas['configure_route']={'controls':{'type':'array','items':{'type':'string','minLength':1,'maxLength':64},'minItems':1,'maxItems':128},'time_limit_us':TIME}
            if self.config['conduct_warnings']:schemas['warn']={'participant':INDEX}
        elif phase=='racing':schemas.update(record_finish={'participant':INDEX,'time_us':dict(TIME,nullable=False)},withdraw={'participant':INDEX},false_start={'participant':INDEX})
        elif phase=='review':schemas.update(confirm_result={},amend_result={'participant':INDEX,'status':{'type':'enum','values':self.result_statuses()},'time_us':TIME,'warnings':{'type':'integer','minimum':0,'maximum':2}})
        if self.config.get('route_configurable') and not d['route']:schemas.pop('start',None)
        if not self.config.get('false_start_disqualifies',True):schemas.pop('false_start',None)
        if phase=='racing' and self.config.get('race_warnings'):schemas['warn']={'participant':INDEX}
        if phase=='racing' and self.controls(d):schemas['visit_control']={'participant':INDEX,'control':{'type':'string','minLength':1,'maxLength':64},'time_us':dict(TIME,nullable=False)}
        if self.config.get('walking'):
            card={'participant':INDEX,'judge':{'type':'integer','minimum':0,'maximum':8},'offence':{'type':'string','enum':['loss_of_contact','bent_knee']}}
            if phase in ('racing','review'):schemas.update(red_card=card,yellow_paddle=card)
            if phase=='review':schemas['remove_red_card']={'participant':INDEX,'judge':{'type':'integer','minimum':0,'maximum':8}}
        schemas['disqualify']={'participant':INDEX}
        return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Participant status and race phase must permit this decision.'],external_observations=['Official start, eligibility, timing or result-review decision.']) for k,v in schemas.items()],constraints={'phase':phase,'time_quantum_us':self.config['time_quantum_us'],'statuses':[r['status'] for r in d['runners']]},completeness=False,reason='externally_adjudicated_race_events')
    def outcome(self,state,pack):
        d=state['data'];terminal=d['phase']=='finished';finishers=sorted((r['time_us'],i) for i,r in enumerate(d['runners']) if r['status']=='finished') if terminal else []
        winners=[state['players'][i]['id'] for t,i in finishers if t==finishers[0][0]] if finishers else []
        placements=[dict(player_id=state['players'][i]['id'],place=1+sum(t2<t for t2,_ in finishers),time_us=t) for t,i in finishers]
        return dict(status='terminal' if terminal else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if finishers else 'no_contest') if terminal else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=placements,reason='results_confirmed' if terminal else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official result confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
