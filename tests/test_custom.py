from copy import deepcopy
import json
from pathlib import Path
import pytest
import rulesatlas as r

ROOT=Path(__file__).resolve().parents[1]
PACK=json.loads((ROOT/'examples/rulepacks/first_to_three.json').read_text())
GOLDEN=json.loads((ROOT/'examples/golden/first_to_three_cases.json').read_text())

@pytest.fixture(autouse=True)
def reset():
    from rulesatlas.core import _REGISTRY
    _REGISTRY.clear()
    r.register_rules(PACK)
    yield
    _REGISTRY.clear()

def state(): return r.new_state(PACK['game_id'],players=GOLDEN['players'])

@pytest.mark.parametrize('case',GOLDEN['cases'],ids=lambda c:c['id'])
def test_original_goldens(case):
    s=state(); s['data']=deepcopy(case['initial_data']); original=deepcopy(s)
    if 'expected_valid' in case: assert r.validate_state(s)['valid']==case['expected_valid']
    if 'expected_legal' in case: assert r.legal_actions(s)['actions']==case['expected_legal']
    if 'expected_outcome' in case:
        expected=deepcopy(case['expected_outcome'])
        if 'winners' in expected: expected['winners']=[s['players'][i]['id'] for i in expected['winners']]
        actual=r.outcome(s)
        assert all(actual[k]==v for k,v in expected.items())
    if 'action' in case:
        if 'expected_error' in case:
            with pytest.raises(r.RuleError) as e: r.apply_action(s,case['action'])
            assert e.value.code==case['expected_error']
        else: assert r.apply_action(s,case['action'])['data']==case['expected_data']
    assert s==original

@pytest.mark.parametrize('bad',[True,'0',None,-1,2,{},[]])
def test_invalid_parameters(bad):
    with pytest.raises(r.RuleError) as e: r.apply_action(state(),{'type':'score','params':{'player':bad}})
    assert e.value.code=='ILLEGAL_ACTION'

def test_conflicting_outcomes():
    s=state(); s['data']['scores']=[3,3]
    assert not r.validate_state(s)['valid']
    with pytest.raises(r.RuleError) as e: r.outcome(s)
    assert e.value.code=='INVALID_STATE'

def test_registry_isolation_and_versions():
    p=r.get_game(PACK['game_id']); p['state']['initial']['turn']=99
    assert state()['data']['turn']==0
    p=deepcopy(PACK); p['state']['initial']['turn']=1
    with pytest.raises(r.RuleError): r.register_rules(p,overwrite=True)
    p['ruleset_version']='2.0.0'; r.register_rules(p)
    with pytest.raises(r.RuleError) as e: state()
    assert e.value.code=='RULESET_CONFLICT'
    assert r.new_state(PACK['game_id'],players=GOLDEN['players'],ruleset_version='1.0.0')['data']['turn']==0

@pytest.mark.parametrize('mutate',[
 lambda p:p.update(game_id='G105'),
 lambda p:p['actions'][0].update(when={'op':'system','args':['touch x']}),
 lambda p:p['actions'][0]['effects'][0].update(path='/../x'),
 lambda p:p['actions'][0]['effects'].append(deepcopy(p['actions'][0]['effects'][0])),
 lambda p:p['state']['initial'].update(turn=True),
 lambda p:p['participants'].update(min=3,max=2),
])
def test_invalid_packs(mutate):
    p=deepcopy(PACK); mutate(p)
    assert not r.validate_rules(p)['valid']

def test_event_domain_and_postcondition():
    p=deepcopy(PACK); p['game_id']='user.event'; p['ruleset_id']='user.event.standard'
    p['actions'][0]['params']['player']={'type':'integer','minimum':0,'maximum':10000}
    p['actions'][0]['when']=True
    r.register_rules(p)
    s=r.new_state('user.event',players=GOLDEN['players'])
    legal=r.legal_actions(s)
    assert legal['mode']=='event_types' and not legal['completeness']
    with pytest.raises(r.RuleError): r.apply_action(s,{'type':'score','params':{'player':10000}})
    assert s['data']['scores']==[0,0]

def test_duplicate_json(tmp_path):
    path=tmp_path/'bad.json'; path.write_text('{"x":1,"x":2}')
    assert not r.validate_rules(path)['valid']

def test_terminal_and_input_isolation():
    s=state()
    for i in [0,1,0,1,0]:
        old=deepcopy(s); result=r.apply_action(s,{'type':'score','params':{'player':i}})
        assert old==s; s=result
    assert r.outcome(s)['winners']==['p0']
    assert r.legal_actions(s)['actions']==[]

def test_reduced_catalog_exactly_matches_registered_profiles():
    curated={g['id'] for g in json.loads((ROOT/'catalog/target_profiles.json').read_text())['entries']}
    assert len(curated)==212
    builtins={g['game_id'] for g in r.list_games() if not g['game_id'].startswith('user.')}
    assert builtins==curated
    assert {g['game_id'] for g in r.list_games(True)}=={g['game_id'] for g in r.list_games()}

def test_removed_profiles_are_unavailable():
    import importlib.util
    scope=json.loads((ROOT/'catalog/profile_scope.json').read_text())
    for game_id in scope['removed_ids']:
        for function in (r.get_game,r.get_capabilities,r.new_state):
            with pytest.raises(r.RuleError) as error:
                function(game_id)
            assert error.value.code=='UNKNOWN_GAME'
    for adapter in scope['removed_adapters']:
        assert importlib.util.find_spec('rulesatlas.adapters.'+adapter) is None


@pytest.mark.parametrize('case',json.loads((ROOT/'common/golden/security_packs.json').read_text()),ids=lambda c:c['id'])
def test_shared_security_packs(case):
    assert r.validate_rules(case['pack'])['valid']==case['valid']

def test_atomic_effect_types():
    r.register_rules(ROOT/'common/rulepacks/transactions.json')
    s=r.new_state('user.transactions',players=[{'id':'one'}]); original=deepcopy(s)
    assert r.apply_action(s,{'type':'swap','params':{}})['data']=={'x':2,'y':1,'items':[10,20]}
    assert r.apply_action(s,{'type':'append','params':{'value':30}})['data']['items']==[10,20,30]
    assert r.apply_action(s,{'type':'remove','params':{'index':0}})['data']['items']==[20]
    for action in [{'type':'fail_atomic','params':{}},{'type':'remove','params':{'index':2}}]:
        with pytest.raises(r.RuleError): r.apply_action(s,action)
        assert s==original
