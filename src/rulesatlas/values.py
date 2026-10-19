"""Bounded, strict JSON values and whitelisted expression evaluation."""
import math
import re

MAX_INTEGER = 9007199254740991


class RuleError(Exception):
    """Portable error with a stable machine-readable code and JSON path."""
    def __init__(self, code, message, path=None):
        self.code, self.message, self.path = code, message, path
        super().__init__(message)


def fail(message, path=None, code='INVALID_RULEPACK'):
    raise RuleError(code, message, path)


def kind(x):
    if x is None: return 'null'
    if type(x) is bool: return 'boolean'
    if type(x) in (int, float): return 'number'
    if type(x) is str: return 'string'
    if type(x) is list: return 'array'
    if type(x) is dict: return 'object'
    fail('Not a JSON value')


def bounded(value, depth=0, budget=None):
    if budget is None: budget = [50000]
    budget[0] -= 1
    if depth > 32 or budget[0] < 0: fail('JSON resource limit', code='RESOURCE_LIMIT')
    k = kind(value)
    if k == 'number' and (abs(value) > MAX_INTEGER or not math.isfinite(value)):
        fail('Numeric value outside portable range')
    if k == 'string' and len(value.encode('utf-8')) > 1048576:
        fail('String resource limit', code='RESOURCE_LIMIT')
    if k in ('array', 'object'):
        if k == 'object' and any(type(key) is not str for key in value): fail('Object keys must be strings')
        for v in value.values() if k == 'object' else value: bounded(v, depth+1, budget)
    return value


def equal(a, b):
    if kind(a) != kind(b): return False
    if isinstance(a, dict): return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list): return len(a) == len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a == b


def typed(value, spec, path=''):
    if value is None and spec.get('nullable', False): return
    k, t = kind(value), spec['type']
    valid = k == t or (t == 'integer' and k == 'number' and value == int(value))
    if t == 'enum': valid = any(equal(value, x) for x in spec.get('values', []))
    if 'enum' in spec and not any(equal(value, x) for x in spec['enum']): valid = False
    if not valid: fail('Field type mismatch', path)
    if k == 'number':
        if value < spec.get('minimum', -MAX_INTEGER) or value > spec.get('maximum', MAX_INTEGER): fail('Numeric bound', path)
    if k in ('string', 'array'):
        suffix = 'Length' if k == 'string' else 'Items'
        if not spec.get('min'+suffix, 0) <= len(value) <= spec.get('max'+suffix, 1048576): fail('Length bound', path)
    if k == 'array':
        for i, v in enumerate(value): typed(v, spec.get('items', {}), f'{path}/{i}')
    if k == 'object':
        props = spec.get('properties', {})
        if set(value)-set(props) or set(spec.get('required', []))-set(value): fail('Object fields mismatch', path)
        for key,v in value.items(): typed(v, props[key], path+'/'+key)


def fields(value, specs, path=''):
    typed(value, {'type':'object','properties':specs,'required':list(specs)}, path)


OPS = {'eq':2,'ne':2,'lt':2,'lte':2,'gt':2,'gte':2,'not':1,'len':1,
       'add':2,'sub':2,'mul':2,'mod':2,'in':2,'and':None,'or':None}


def check_expr(expr, depth=0, budget=None):
    if budget is None: budget = [2000]
    budget[0] -= 1
    if depth > 32 or budget[0] < 0: fail('Expression resource limit', code='RESOURCE_LIMIT')
    if kind(expr) not in ('object','array'): bounded(expr); return
    if type(expr) is not dict: fail('Expression must be scalar or AST')
    if set(expr) == {'ref'}:
        if type(expr['ref']) is not str or not re.fullmatch(r'(state|params)\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*',expr['ref']): fail('Invalid reference')
        return
    if set(expr) != {'op','args'} or expr['op'] not in OPS or type(expr['args']) is not list: fail('Invalid operator')
    arity = OPS[expr['op']]
    if not 1 <= len(expr['args']) <= 32 or (arity and len(expr['args']) != arity): fail('Invalid operator arity')
    for arg in expr['args']: check_expr(arg, depth+1, budget)


def resolve(value, parts):
    for part in parts:
        if type(value) is dict and part in value: value = value[part]
        elif type(value) is list and re.fullmatch(r'0|[1-9][0-9]*',part) and int(part) < len(value): value = value[int(part)]
        else: fail('Unresolved reference')
    return value


def expression(expr, state, params, budget=None):
    if budget is None: budget = [50000]
    budget[0] -= 1
    if budget[0] < 0: fail('Evaluation resource limit', code='RESOURCE_LIMIT')
    if type(expr) is not dict: return expr
    if 'ref' in expr: return resolve({'state':state,'params':params}, expr['ref'].split('.'))
    op = expr['op']; args = [expression(a,state,params,budget) for a in expr['args']]
    if op in ('and','or','not'):
        if any(type(a) is not bool for a in args): fail('Boolean operands required')
        return all(args) if op == 'and' else any(args) if op == 'or' else not args[0]
    if op == 'len':
        if kind(args[0]) not in ('string','array','object'): fail('Collection required')
        return len(args[0])
    a,b = args
    if op == 'in':
        if type(b) is not list: fail('Array required')
        return any(equal(a,x) for x in b)
    if kind(a) != kind(b): fail('Matching operand types required')
    if op in ('eq','ne'): return equal(a,b) if op == 'eq' else not equal(a,b)
    if kind(a) != 'number': fail('Numeric operands required')
    if op == 'lt': return a < b
    if op == 'lte': return a <= b
    if op == 'gt': return a > b
    if op == 'gte': return a >= b
    if op == 'mod':
        if a != int(a) or b != int(b) or b <= 0: fail('Modulo requires integers and positive divisor')
        return a % b
    value = a+b if op == 'add' else a-b if op == 'sub' else a*b
    return bounded(value)
