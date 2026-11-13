import ast
def policy(source):
    if len(source)>12000: raise ValueError('source length limit')
    tree=ast.parse(source)
    allowed=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.If,ast.Return,ast.Assign,ast.Name,ast.Load,ast.Store,ast.Constant,ast.Subscript,ast.Dict,ast.List,ast.Tuple,ast.Compare,ast.BoolOp,ast.UnaryOp,ast.Not,ast.And,ast.Or,ast.Eq,ast.NotEq,ast.In,ast.NotIn,ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.BinOp,ast.Add,ast.Sub,ast.Mult,ast.Call,ast.Attribute,ast.keyword,ast.Expr,ast.Pass,ast.IfExp,ast.USub)
    if len(list(ast.walk(tree)))>600: raise ValueError('AST size limit')
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef): raise ValueError('exactly one function required')
    f=tree.body[0]
    if f.name!='next_commands' or [x.arg for x in f.args.args]!=['event','order'] or f.decorator_list or f.args.defaults or f.args.vararg or f.args.kwarg or f.args.kwonlyargs or f.args.posonlyargs or f.returns or any(a.annotation for a in f.args.args): raise ValueError('expected next_commands(event, order), no decorators/annotations/defaults')
    for n in ast.walk(tree):
        if not isinstance(n,allowed): raise ValueError('unsupported syntax: '+type(n).__name__)
        if isinstance(n,ast.Name) and (n.id.startswith('_') or n.id not in {'event','order'} and isinstance(n.ctx,ast.Load) and n.id=='next_commands'): raise ValueError('forbidden name')
        if isinstance(n,ast.Assign) and any(not isinstance(t,ast.Name) or t.id in ('event','order') for t in n.targets): raise ValueError('only local-name assignments allowed')
        if isinstance(n,ast.Call):
            if not (isinstance(n.func,ast.Attribute) and n.func.attr=='get' and isinstance(n.func.value,ast.Name) and n.func.value.id in ('event','order')): raise ValueError('only event.get/order.get calls allowed')
        if isinstance(n,ast.Attribute) and not (n.attr=='get' and isinstance(n.value,ast.Name) and n.value.id in ('event','order')): raise ValueError('forbidden attribute')
        if isinstance(n,ast.Constant) and (isinstance(n.value,str) and len(n.value)>1000 or isinstance(n.value,int) and abs(n.value)>1000000): raise ValueError('constant limit')
    scope={'__builtins__':{}};exec(compile(tree,'candidate','exec'),scope);return scope['next_commands']
