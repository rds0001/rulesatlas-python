"""Independent handwritten board/turn/outcome examples, plus reachability audit."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
import rulesatlas as r
ROOT=Path(__file__).resolve().parents[1]
GOLDEN=json.loads((ROOT/'common/golden/G105/standard.json').read_text())

def new(): return r.new_state('G105',players=GOLDEN['players'],ruleset_version='1.0.0')

@pytest.mark.parametrize('case',GOLDEN['cases'],ids=lambda c:c['id'])
def test_golden(case):
    state=new()
    for cell in case['moves']:
        original=deepcopy(state)
        state=r.apply_action(state,{'type':'place','params':{'cell':cell}})
        assert original['data']['board'][cell]==-1
    assert state['data']==dict(board=case['expected_board'],turn=case['expected_turn'])
    assert r.validate_state(state)['valid']
    outcome=r.outcome(state)
    assert outcome['status']==case['expected_status']
    assert outcome['winners']==case['expected_winners']
    if 'expected_kind' in case: assert outcome['result_kind']==case['expected_kind']
    legal=r.legal_actions(state)
    assert legal['completeness'] and legal['mode']=='enumerated'
    assert [a['params']['cell'] for a in legal['actions']]==case['expected_legal_cells']
    if outcome['status']=='terminal':
        with pytest.raises(r.RuleError) as e: r.apply_action(state,{'type':'place','params':{'cell':8}})
        assert e.value.code=='ILLEGAL_ACTION'

@pytest.mark.parametrize('data',GOLDEN['invalid_data'])
def test_invalid_positions(data):
    state=new(); state['data']=data
    assert not r.validate_state(state)['valid']
    with pytest.raises(r.RuleError): r.legal_actions(state)

@pytest.mark.parametrize('cell',[True,None,'1',-1,9,1.5])
def test_bad_cell(cell):
    with pytest.raises(r.RuleError) as e: r.apply_action(new(),{'type':'place','params':{'cell':cell}})
    assert e.value.code=='ILLEGAL_ACTION'

def test_occupied_square_and_actor():
    state=r.apply_action(new(),{'type':'place','params':{'cell':0}})
    with pytest.raises(r.RuleError): r.apply_action(state,{'type':'place','params':{'cell':0}})
    with pytest.raises(r.RuleError): r.apply_action(state,{'type':'place','params':{'cell':1},'actor':'alice'})
    assert r.apply_action(state,{'type':'place','params':{'cell':1},'actor':'bob'})['data']['turn']==0

def test_builtin_protection():
    with pytest.raises(r.RuleError): r.unregister_rules('G105')
    assert r.get_game('G105')['profile_id']=='G105'
    assert r.get_capabilities('G105')['legal_actions']=='enumerated'
