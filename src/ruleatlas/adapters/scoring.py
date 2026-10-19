"""Bounded adjudicated scoring segments, with fixed sport-specific awards."""
from copy import deepcopy
from ..values import fields, fail

class Scoring:
    def __init__(self, awards):
        self.awards = awards

    def validate(self, data):
        if any(0 < score < min(self.awards.values()) for score in data["scores"]):
            fail("Score is below the smallest scoring award", code="INVALID_STATE")

    def legal(self, state):
        return dict(mode='event_types', actions=[], action_types=[
            dict(type='award', params_schema={'player': {'type':'integer','minimum':0,'maximum':1}, 'kind': {'type':'enum','values':list(self.awards)}}, preconditions=['Scoring segment is open.'], external_observations=['An official has adjudicated this scoring event, including any prerequisites.']),
            dict(type='close_segment', params_schema={}, preconditions=['Scoring segment is open.'], external_observations=['The supplied scoring segment has ended.'])
        ], constraints={}, completeness=False, reason='externally_adjudicated_events')

    def apply(self, state, action):
        data=deepcopy(state['data'])
        if action['type']=='close_segment':
            fields(action['params'], {}, '/params');data['closed']=True
        elif action['type']=='award':
            fields(action['params'], {'player':{'type':'integer','minimum':0,'maximum':1}, 'kind':{'type':'enum','values':list(self.awards)}}, '/params')
            data['scores'][int(action['params']['player'])]+=self.awards[action['params']['kind']]
            if max(data['scores'])>1000000: fail('Score exceeds supported bound')
        else: fail('Unknown action')
        return data

    def outcome(self, state, pack):
        d=state['data'];terminal=d['closed'];tie=d['scores'][0]==d['scores'][1]
        w=None if not terminal or tie else (0 if d['scores'][0]>d['scores'][1] else 1)
        return dict(status='terminal' if terminal else 'ongoing', result_kind=('draw' if tie else 'win') if terminal else 'none', winners=[] if w is None else [state['players'][w]['id']], losers=[] if w is None else [state['players'][1-w]['id']], placements=[], reason='scoring_segment_closed' if terminal else 'ongoing', evidence_required=[], rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
