
from pycket                 import values
from pycket                 import values_parameter
from pycket.argument_parser import ArgParser, EndOfInput
from pycket.arity           import Arity
from pycket.base            import W_Object
from pycket.error           import SchemeException
from pycket.prims.expose    import expose, expose_val, default, procedure
from rpython.rlib           import jit

@expose("make-parameter",
        [values.W_Object, default(values.W_Object, values.w_false)])
def make_parameter(init, guard):
    return values_parameter.W_Parameter(init, guard)

@expose("make-derived-parameter",
        [values_parameter.W_BaseParameter, procedure, procedure])
def make_derived_parameter(param, guard, wrap):
    return values_parameter.W_DerivedParameter(param, guard, wrap)

@expose("extend-parameterization", arity=Arity.geq(1))
@jit.unroll_safe
def scheme_extend_parameterization(args):
    if len(args) == 0:
        raise SchemeException("extend-parameterization: expected 1 or more arguments")

    config = args[0]
    argc = len(args)

    if argc < 2 or not isinstance(config, values_parameter.W_Parameterization) or argc % 2 != 1:
        return config

    parser = ArgParser("extend-parameterization", args, start_at=1)
    while parser.has_more():
        param  = parser.parameter()
        key    = parser.object()
        config = config.extend([param], [key])

    return config

def call_with_parameterization(f, args, paramz, env, cont):
    cont.update_cm(values.parameterization_key, paramz)
    return f.call(args, env, cont)

@expose("call-with-parameterization",
        [values.W_Object, values_parameter.W_Parameterization], simple=False)
def call_w_paramz(f, paramz, env, cont):
    return call_with_parameterization(f, [], paramz, env, cont)

def call_with_extended_paramz(f, args, keys, vals, env, cont):
    from pycket.values import parameterization_key
    # XXX seems untested?
    paramz = cont.get_mark_first(parameterization_key)
    assert isinstance(paramz, values_parameter.W_Parameterization) # XXX is this always right?
    paramz_new = paramz.extend(keys, vals)
    return call_with_parameterization(f, args, paramz_new, env, cont)

expose_val("parameterization-key", values.parameterization_key)
expose_val("print-mpair-curly-braces", values_parameter.W_Parameter(values.w_false))
expose_val("print-pair-curly-braces", values_parameter.W_Parameter(values.w_false))

READ_PARAMS = """
read-square-bracket-as-paren
read-curly-brace-as-paren
read-square-bracket-with-tag
read-curly-brace-with-tag
read-accept-box
read-accept-compiled
read-accept-bar-quote
read-accept-graph
read-decimal-as-inexact
read-accept-dot
read-accept-infix-dot
read-cdot
read-accept-quasiquote
read-accept-reader
read-accept-lang
"""

for name in READ_PARAMS.split():
    expose_val(name, values_parameter.W_Parameter(values.w_false))

