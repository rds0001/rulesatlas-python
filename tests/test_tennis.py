"""Independently calculated tennis scores and adjudication boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
import rulesatlas as r
ROOT=Path(__file__).resolve().parents[1]
GOLDEN=json.loads((ROOT/'common/golden/S029/standard.json').read_text())
def new(): return r.new_state('S029',players=GOLDEN['players'],ruleset_version='1.0.0')

@pytest.mark.parametrize('case',GOLDEN['cases'],ids=lambda c:c['id'])
def test_golden(case):
    s=new();s['data']=deepcopy(case['data']);original=deepcopy(s)
    assert r.validate_state(s)['valid']
    legal=r.legal_actions(s)
    assert legal['mode']=='event_types' and not legal['completeness']
    if 'status' in case: assert r.outcome(s)['status']==case['status']
    if 'winners' in case: assert r.outcome(s)['winners']==case['winners']
    if 'action' in case:
        if 'error' in case:
            with pytest.raises(r.RuleError) as e: r.apply_action(s,case['action'])
            assert e.value.code==case['error']
        else:
            result=r.apply_action(s,case['action']); assert result['data']==case['expected_data']
            if 'after_status' in case:
                assert r.outcome(result)['status']==case['after_status']
                assert r.outcome(result)['winners']==case['after_winners']
                assert not r.legal_actions(result)['actions'] and not r.legal_actions(result)['action_types']
                with pytest.raises(r.RuleError): r.apply_action(result,{'type':'award_point','params':{'player':0}})
    assert s==original

@pytest.mark.parametrize('data',GOLDEN['invalid_data'])
def test_invalid(data):
    s=new();s['data']=data
    assert not r.validate_state(s)['valid']

@pytest.mark.parametrize('player',[True,None,'0',-1,2,0.5])
def test_invalid_player(player):
    with pytest.raises(r.RuleError): r.apply_action(new(),{'type':'award_point','params':{'player':player}})

def test_complete_straight_sets_and_disqualification():
    s=new()
    for _ in range(48): s=r.apply_action(s,{'type':'award_point','params':{'player':0}})
    assert s['data']['sets']==[[6,0],[6,0]]
    assert r.outcome(s)['winners']==['alice']
    d=r.apply_action(new(),{'type':'end_match','params':{'kind':'disqualification','player':1}})
    assert r.outcome(d)['result_kind']=='disqualification'
    assert r.outcome(d)['winners']==['alice']
