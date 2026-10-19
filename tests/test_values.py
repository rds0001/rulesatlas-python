from copy import deepcopy
import pytest
from rulesatlas.values import expression, check_expr, RuleError, typed, bounded

@pytest.mark.parametrize('op,args,expected',[
 ('eq',[1,1],True),('ne',[1,2],True),('lt',[1,2],True),('lte',[2,2],True),
 ('gt',[3,2],True),('gte',[2,2],True),('and',[True,False],False),
 ('or',[False,True],True),('not',[False],True),('add',[2,3],5),
 ('sub',[2,3],-1),('mul',[2,3],6),('mod',[-5,3],1),('len',['ä🙂'],2),
 ('in',[2,{'ref':'state.values'}],True)])
def test_operator_oracles(op,args,expected):
    ast={'op':op,'args':args}; check_expr(ast)
    assert expression(ast,{'values':[1,2]}, {})==expected

@pytest.mark.parametrize('ast',[
 {'op':'eq','args':[True,1]}, {'op':'add','args':['1','2']},
 {'op':'mod','args':[1,0]}, {'op':'mod','args':[1.5,2]},
 {'op':'and','args':[True,1]}, {'op':'lt','args':['a','b']},
 {'op':'add','args':[9007199254740991,1]}, {'ref':'state.missing'}])
def test_bad_evaluation(ast):
    check_expr(ast)
    with pytest.raises(RuleError): expression(ast,{}, {})

@pytest.mark.parametrize('ast',[{'op':'eval','args':['x']},{'op':'not','args':[True,False]}, {'ref':'state...x'},[1,2]])
def test_bad_ast(ast):
    with pytest.raises(RuleError): check_expr(ast)

def test_depth():
    ast=True
    for _ in range(34): ast={'op':'not','args':[ast]}
    with pytest.raises(RuleError,match='limit'): check_expr(ast)

@pytest.mark.parametrize('v',[True,'1',None,[],{}])
def test_no_integer_coercion(v):
    with pytest.raises(RuleError): typed(v,{'type':'integer'})

@pytest.mark.parametrize('v',[float('nan'),float('inf'),2**53])
def test_numeric_limits(v):
    with pytest.raises(RuleError): bounded(v)


def test_native_enum_constraint_preserves_base_type():
    from rulesatlas.values import typed, RuleError
    import pytest
    typed('clear', {'type': 'string', 'enum': ['clear', 'fail', 'pass']})
    with pytest.raises(RuleError):
        typed('unknown', {'type': 'string', 'enum': ['clear', 'fail', 'pass']})
    with pytest.raises(RuleError):
        typed(1, {'type': 'string', 'enum': [1]})
    typed('clear', {'type': 'enum', 'values': ['clear', 'fail']})
