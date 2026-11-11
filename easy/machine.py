"""Runtime for Easy.

Parameters are passed by reference. An actual parameter that is a variable,
an array element, or a node field shares its cell with the callee. Any other
expression is copied into a temporary cell. Passing a structure opens its
fields in the callee, so the callee's assignment to `top` changes the caller's
structure.
"""

import math

from easy.errors import EasyError
from easy.parse import parse_source

MATH = {"floor", "ceil", "log2"}
NODE_OPS = {"getnode", "retnode"}


class StopProgram(Exception):
    pass


class Cell:
    def __init__(self, value):
        self.value = value


class Array:
    def __init__(self, bounds):
        self.bounds = bounds
        self.data = {}

    def cell_at(self, indexes, line):
        if len(indexes) != len(self.bounds):
            raise EasyError("wrong number of indexes", line)
        key = []
        for (low, high), index in zip(self.bounds, indexes):
            if index < low or index > high:
                raise EasyError("index out of range", line)
            key.append(index)
        key = tuple(key)
        if key not in self.data:
            self.data[key] = Cell(None)
        return self.data[key]


class Structure:
    def __init__(self, type_name, fields, bounds):
        self.type_name = type_name
        self.fields = fields
        self.bounds = bounds


class Node:
    def __init__(self, fields):
        self.fields = {name: Cell(None) for name in fields}
        self.alive = True


class Frame:
    def __init__(self):
        self.cells = {}
        self.params = set()


class Result:
    def __init__(self, output, value, globals_, trace=None):
        self.output = output
        self.value = value
        self.globals = globals_
        self.trace = trace or []


class Machine:
    def __init__(self, program, inputs, max_steps, explain=False):
        self.program = program
        self.procs = program.procedures
        self.structures = program.structures
        self.inputs = list(inputs)
        self.max_steps = max_steps
        self.explain = explain
        self.trace = []
        self.steps = 0
        self.output = []
        self.globals = {}
        self.spelling = {}
        self.frames = []
        self.layout = None
        self.pool_size = 1024
        self.nodes = {}
        self.free = []
        self.next_addr = 1
        self.result_value = None

    def start(self):
        for action in self.program.prelude:
            kind = action[0]
            if kind == "pool":
                self.pool_size = action[1]
            elif kind == "node":
                self.layout = list(action[1])
                self.note("node(" + ", ".join(action[1]) + ")")
            elif kind == "array":
                self.declare_arrays(action[1], action[2], top_level=True)
        try:
            proc = self.procs["main"]
            self.result_value = self.call_user(proc, [], proc.line)
        except StopProgram:
            self.result_value = None

    def result(self):
        exported = {}
        for key, cell in self.globals.items():
            exported[self.spelling.get(key, key)] = cell.value
        return Result(self.output, self.result_value, exported, self.trace)

    def note(self, text):
        if not self.explain:
            return
        depth = len(self.frames)
        self.trace.append("+ " + ("  " * depth) + text)

    def note_store(self, target, expr, value):
        got = self.show(value)
        if expr == got:
            self.note(f"{target} ← {got}")
        else:
            self.note(f"{target} ← {expr} → {got}")

    def render_dims(self, dims):
        parts = []
        for low, high in dims:
            if low is None:
                parts.append(self.render(high))
            else:
                parts.append(f"{self.render(low)}:{self.render(high)}")
        return ", ".join(parts)

    def render(self, expr):
        kind = expr[0]
        if kind == "num":
            value = expr[1]
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        if kind == "str":
            return '"' + expr[1] + '"'
        if kind == "nil":
            return "nil"
        if kind == "bool":
            return "true" if expr[1] else "false"
        if kind == "var":
            return expr[1]
        if kind == "unary":
            op = expr[1]
            inner = self.render(expr[2])
            if op == "not":
                return f"not {inner}"
            if op == "-":
                return f"−{inner}"
            return f"+{inner}"
        if kind == "binary":
            symbol = {"<>": "≠", "<=": "≤", ">=": "≥", "*": "×", "-": "−"}.get(expr[1], expr[1])
            return f"({self.render(expr[2])} {symbol} {self.render(expr[3])})"
        if kind in ("floor", "ceil"):
            return f"{kind}({self.render(expr[1])})"
        if kind == "apply":
            args = ", ".join(self.render(arg) for arg in expr[2])
            return f"{self.render(expr[1])}({args})"
        if kind == "slice":
            return f"{self.render(expr[1])}({self.render(expr[2])}:{self.render(expr[3])})"
        return kind

    def tick(self):
        self.steps += 1
        if self.steps > self.max_steps:
            raise EasyError("step limit exceeded")

    def execute(self, code):
        pc = 0
        temps = {}
        while pc < len(code):
            self.tick()
            ins = code[pc]
            op = ins[0]
            if op == "label":
                pc += 1
                continue
            if op == "jump":
                if len(ins) > 2 and ins[2] == "goto":
                    self.note(f"go to {ins[3]}")
                elif len(ins) > 2 and ins[2] == "exit":
                    self.note("exit")
                pc = ins[1]
                continue
            if op == "jf":
                cond = self.eval(ins[1])
                passed = self.truth(cond, ins[1][-1])
                kind = ins[3] if len(ins) > 3 else "if"
                self.note(f"{kind} {self.render(ins[1])} → {self.show(cond)}")
                if not passed:
                    pc = ins[2]
                    continue
                pc += 1
                continue
            if op == "assign":
                value = self.eval(ins[2])
                self.place(ins[1]).value = value
                self.note_store(self.render(ins[1]), self.render(ins[2]), value)
            elif op == "call":
                cells = self.cells_for(ins[1], ins[2], ins[3])
                self.call_named(ins[1], cells, ins[3])
            elif op == "return":
                if ins[1] is None:
                    self.note("return")
                    return None
                value = self.eval(ins[1])
                self.note(f"return {self.show(value)}")
                return value
            elif op == "stop":
                self.note("stop")
                raise StopProgram()
            elif op == "output":
                rendered = " ".join(self.render(item) for item in ins[1])
                parts = [self.show(self.eval(item)) for item in ins[1]]
                line = " ".join(parts)
                self.output.append(line)
                if rendered == line:
                    self.note(f"output {line}")
                else:
                    self.note(f"output {rendered} → {line}")
            elif op == "input":
                self.do_input(ins[1], ins[2])
            elif op == "array":
                self.declare_arrays(ins[1], ins[2], top_level=False)
            elif op == "node":
                self.layout = list(ins[1])
                self.note("node(" + ", ".join(ins[1]) + ")")
            elif op == "new":
                self.instantiate(ins[1], ins[2], ins[3], ins[4])
            elif op == "for_init":
                self.for_init(ins, temps)
            elif op == "for_test":
                if not self.for_continues(ins, temps):
                    self.note(f"for {ins[1]} ends")
                    pc = ins[3]
                    continue
                self.note(f"for {ins[1]} = {self.show(self.lookup(ins[1], False, ins[4]).value)}")
            elif op == "for_inc":
                self.for_inc(ins, temps)
            else:
                raise EasyError(f"bad instruction {op}")
            pc += 1
        return None

    def for_init(self, ins, temps):
        var, start_e, finish_e, step_e, slot, line = (
            ins[1],
            ins[2],
            ins[3],
            ins[4],
            ins[5],
            ins[6],
        )
        start = self.as_number(self.eval(start_e), line)
        finish = self.as_number(self.eval(finish_e), line)
        step = self.as_number(self.eval(step_e), line)
        if step == 0:
            raise EasyError("for step is 0", line)
        temps[slot] = (finish, step)
        self.place(("var", var, line)).value = start
        span = f"for {var} ← {self.show(start)} to {self.show(finish)}"
        if step != 1:
            span += f" by {self.show(step)}"
        self.note(span)

    def for_continues(self, ins, temps):
        var, slot, line = ins[1], ins[2], ins[4]
        finish, step = temps[slot]
        value = self.as_number(self.lookup(var, False, line).value, line)
        if step > 0:
            return value <= finish
        return value >= finish

    def for_inc(self, ins, temps):
        var, slot, line = ins[1], ins[2], ins[3]
        _finish, step = temps[slot]
        cell = self.lookup(var, False, line)
        cell.value = self.as_number(cell.value, line) + step
        self.note(f"{var} ← {self.show(cell.value)}")

    def call_named(self, name, cells, line):
        self.tick()
        key = name.lower()
        if key in self.procs:
            return self.call_user(self.procs[key], cells, line)
        if key == "getnode":
            self.getnode(cells, line)
            return None
        if key == "retnode":
            self.retnode(cells, line)
            return None
        raise EasyError(f"unknown procedure {name}", line)

    def call_user(self, proc, cells, line):
        if len(cells) != len(proc.params):
            raise EasyError(
                f"{proc.name} expects {len(proc.params)} arguments",
                line,
            )
        frame = Frame()
        originals = []
        for param, cell in zip(proc.params, cells):
            frame.cells[param.lower()] = cell
            frame.params.add(param.lower())
            originals.append(cell)
        for cell in originals:
            self.open_structure(frame, cell)
        shown = []
        for param, cell in zip(proc.params, cells):
            shown.append(f"{param}={self.show(cell.value)}")
        if shown:
            self.note(f"procedure {proc.name}({', '.join(shown)})")
        else:
            self.note(f"procedure {proc.name}")
        self.frames.append(frame)
        try:
            return self.execute(proc.code)
        finally:
            self.frames.pop()

    def open_structure(self, frame, cell):
        value = cell.value
        if not isinstance(value, Structure):
            return
        for key, field in value.fields.items():
            frame.cells[key] = field
        for key, bound in value.bounds.items():
            frame.cells[key] = bound

    def cells_for(self, name, args, line):
        key = name.lower()
        if key == "getnode" and key not in self.procs:
            if len(args) != 1:
                raise EasyError("GETNODE expects one variable", line)
            kind, payload = self.classify(args[0], create_var=True)
            if kind != "cell":
                raise EasyError("GETNODE expects a variable", line)
            return [payload]
        return self.bind_args(args)

    def bind_args(self, args):
        cells = []
        for arg in args:
            kind, payload = self.classify(arg, create_var=True)
            if kind == "cell":
                cells.append(payload)
            else:
                cells.append(Cell(payload))
        return cells

    def getnode(self, cells, line):
        if len(cells) != 1:
            raise EasyError("GETNODE expects one variable", line)
        if not self.layout:
            raise EasyError("node layout is not set", line)
        if self.free:
            addr = min(self.free)
            self.free.remove(addr)
        elif self.next_addr <= self.pool_size:
            addr = self.next_addr
            self.next_addr += 1
        else:
            raise EasyError("GETNODE: unsuccessful allocation", line)
        self.nodes[addr] = Node(self.layout)
        cells[0].value = addr
        self.note(f"GETNODE → {addr}")

    def retnode(self, cells, line):
        if len(cells) != 1:
            raise EasyError("RETNODE expects one address", line)
        addr = cells[0].value
        node = self.nodes.get(addr)
        if not isinstance(addr, int) or node is None or not node.alive:
            raise EasyError("RETNODE: not a live node", line)
        node.alive = False
        self.free.append(addr)
        self.note(f"RETNODE {addr}")

    def instantiate(self, type_name, var_name, arg_exprs, line):
        stype = self.structures.get(type_name.lower())
        if stype is None:
            raise EasyError(f"unknown structure {type_name}", line)
        if len(arg_exprs) != len(stype.params):
            raise EasyError(
                f"{stype.name} expects {len(stype.params)} arguments",
                line,
            )
        values = [self.eval(arg) for arg in arg_exprs]
        bounds = {}
        for param, value in zip(stype.params, values):
            bounds[param.lower()] = Cell(value)
        scratch = Frame()
        scratch.cells.update(bounds)
        self.frames.append(scratch)
        try:
            fields = {}
            for field in stype.fields:
                if field[0] == "scalar":
                    fields[field[1].lower()] = Cell(None)
                else:
                    fields[field[1].lower()] = Cell(self.make_array(field[2], line))
        finally:
            self.frames.pop()
        struct = Structure(stype.name, fields, bounds)
        cell = Cell(struct)
        key = var_name.lower()
        self.spelling[key] = var_name
        if self.frames:
            self.frames[-1].cells[key] = cell
        else:
            self.globals[key] = cell
        self.note(f"{stype.name} {var_name}")

    def declare_arrays(self, specs, line, top_level):
        for name, dims in specs:
            key = name.lower()
            frame = self.frames[-1] if self.frames else None
            if frame is not None and key in frame.params:
                if not isinstance(frame.cells[key].value, Array):
                    raise EasyError(f"{name} is not an array", line)
                self.make_array(dims, line)
                self.note(f"array {name}({self.render_dims(dims)})")
                continue
            array = self.make_array(dims, line)
            cell = Cell(array)
            self.spelling[key] = name
            if top_level or frame is None:
                self.globals[key] = cell
            else:
                frame.cells[key] = cell
            self.note(f"array {name}({self.render_dims(dims)})")

    def make_array(self, dims, line):
        bounds = []
        for low_e, high_e in dims:
            low = 1 if low_e is None else self.as_index(self.eval(low_e), line)
            high = self.as_index(self.eval(high_e), line)
            if low > high:
                raise EasyError("array lower bound exceeds upper bound", line)
            bounds.append((low, high))
        return Array(bounds)

    def do_input(self, targets, line):
        for target in targets:
            if target[0] == "slice":
                self.read_slice(target)
            else:
                token = self.next_input(target[-1])
                self.place(target).value = token
                self.note(f"{self.render(target)} ← {self.show(token)}")

    def read_slice(self, expr):
        base, low_e, high_e, line = expr[1], expr[2], expr[3], expr[4]
        value = self.eval(base)
        if not isinstance(value, Array) or len(value.bounds) != 1:
            raise EasyError("input slice expects a one-dimensional array", line)
        low = self.as_index(self.eval(low_e), line)
        high = self.as_index(self.eval(high_e), line)
        for index in range(low, high + 1):
            token = self.next_input(line)
            value.cell_at([index], line).value = token
            self.note(f"{self.render(base)}({index}) ← {self.show(token)}")

    def next_input(self, line):
        if not self.inputs:
            raise EasyError("input exhausted", line)
        token = self.inputs.pop(0)
        if not isinstance(token, str):
            return token
        text = token.strip()
        lowered = text.lower()
        if lowered in ("nil", "lambda"):
            return None
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        try:
            return int(text, 10)
        except ValueError:
            pass
        try:
            return float(text)
        except ValueError:
            return token

    def place(self, expr):
        kind, payload = self.classify(expr, create_var=True)
        if kind != "cell":
            raise EasyError("expected a variable", expr[-1])
        return payload

    def eval(self, expr):
        kind, payload = self.classify(expr, create_var=False)
        if kind == "cell":
            return payload.value
        return payload

    def classify(self, expr, create_var):
        kind = expr[0]
        line = expr[-1]
        if kind == "num":
            return ("value", expr[1])
        if kind == "str":
            return ("value", expr[1])
        if kind == "bool":
            return ("value", expr[1])
        if kind == "nil":
            return ("value", None)
        if kind == "var":
            if " " in expr[1]:
                raise EasyError(f"unknown name {expr[1]}", line)
            return ("cell", self.lookup(expr[1], create_var, line))
        if kind == "unary":
            return ("value", self.eval_unary(expr))
        if kind == "binary":
            return ("value", self.eval_binary(expr))
        if kind == "floor":
            return ("value", self.math_fn("floor", self.eval(expr[1]), line))
        if kind == "ceil":
            return ("value", self.math_fn("ceil", self.eval(expr[1]), line))
        if kind == "apply":
            return self.classify_apply(expr)
        if kind == "slice":
            raise EasyError("a slice is only valid in input", line)
        raise EasyError("bad expression", line)

    def classify_apply(self, expr):
        base, args, line = expr[1], expr[2], expr[3]
        if base[0] == "var" and " " not in base[1] and self.is_bound(base[1]):
            value = self.lookup(base[1], False, line).value
            indexed = self.try_index(value, args, line)
            if indexed is None:
                raise EasyError(f"{base[1]} is not an array", line)
            return ("cell", indexed)
        if base[0] == "var":
            return self.classify_free_name(base[1], args, line)
        kind, payload = self.classify(base, create_var=False)
        value = payload.value if kind == "cell" else payload
        indexed = self.try_index(value, args, line)
        if indexed is None:
            raise EasyError("not an array", line)
        return ("cell", indexed)

    def classify_free_name(self, name, args, line):
        key = name.lower()
        if key in MATH and key not in self.procs:
            if len(args) != 1:
                raise EasyError(f"{name} expects one argument", line)
            return ("value", self.math_fn(key, self.eval(args[0]), line))
        if key in self.procs or key in NODE_OPS:
            return ("value", self.call_named(name, self.cells_for(name, args, line), line))
        if len(args) != 1:
            raise EasyError(f"unknown name {name}", line)
        return ("cell", self.field_cell(name, self.eval(args[0]), line))

    def try_index(self, value, args, line):
        array = None
        if isinstance(value, Array):
            array = value
        elif isinstance(value, Structure):
            arrays = [
                cell.value
                for cell in value.fields.values()
                if isinstance(cell.value, Array)
            ]
            if len(arrays) == 1 and len(args) == len(arrays[0].bounds):
                array = arrays[0]
        if array is None:
            return None
        indexes = [self.as_index(self.eval(arg), line) for arg in args]
        return array.cell_at(indexes, line)

    def field_cell(self, name, target, line):
        key = name.lower()
        if isinstance(target, Structure):
            if key in target.fields:
                return target.fields[key]
            if key in target.bounds:
                return target.bounds[key]
            raise EasyError(f"no field {name}", line)
        if target is None:
            raise EasyError("nil has no fields", line)
        node = self.nodes.get(target) if isinstance(target, int) else None
        if node is None or not node.alive:
            raise EasyError("not a node", line)
        if key not in node.fields:
            raise EasyError(f"no field {name}", line)
        return node.fields[key]

    def eval_unary(self, expr):
        op, inner, line = expr[1], expr[2], expr[3]
        if op == "not":
            return not self.truth(self.eval(inner), line)
        value = self.as_number(self.eval(inner), line)
        if op == "-":
            return -value
        return +value

    def eval_binary(self, expr):
        op, left_e, right_e, line = expr[1], expr[2], expr[3], expr[4]
        if op == "and":
            if not self.truth(self.eval(left_e), line):
                return False
            return self.truth(self.eval(right_e), line)
        if op == "or":
            if self.truth(self.eval(left_e), line):
                return True
            return self.truth(self.eval(right_e), line)
        left = self.eval(left_e)
        right = self.eval(right_e)
        if op == "+" and isinstance(left, str) and isinstance(right, str):
            return left + right
        if op in ("+", "-", "*", "/", "mod", "^"):
            return self.arith(op, left, right, line)
        if op in ("=", "<>", "<", ">", "<=", ">="):
            return self.relate(op, left, right, line)
        raise EasyError(f"unknown operator {op}", line)

    def arith(self, op, left, right, line):
        left = self.as_number(left, line)
        right = self.as_number(right, line)
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise EasyError("division by zero", line)
            quot = left / right
            if isinstance(quot, float) and quot.is_integer():
                return int(quot)
            return quot
        if op == "mod":
            if right == 0:
                raise EasyError("mod by zero", line)
            return left % right
        result = left ** right
        if isinstance(result, complex):
            raise EasyError("complex power", line)
        if isinstance(result, float) and result.is_integer():
            return int(result)
        return result

    def relate(self, op, left, right, line):
        if op in ("=", "<>"):
            same = self.same(left, right)
            return same if op == "=" else (not same)
        if isinstance(left, str) and isinstance(right, str):
            return {"<": left < right, ">": left > right, "<=": left <= right, ">=": left >= right}[op]
        left = self.as_number(left, line)
        right = self.as_number(right, line)
        return {"<": left < right, ">": left > right, "<=": left <= right, ">=": left >= right}[op]

    def same(self, left, right):
        if isinstance(left, bool) or isinstance(right, bool):
            return isinstance(left, bool) and isinstance(right, bool) and left == right
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left == right
        return left == right

    def math_fn(self, name, value, line):
        number = self.as_number(value, line)
        if name == "floor":
            return int(math.floor(number))
        if name == "ceil":
            return int(math.ceil(number))
        if number <= 0:
            raise EasyError("log2 of a non-positive number", line)
        result = math.log2(number)
        nearest = round(result)
        if math.isclose(result, nearest, rel_tol=0.0, abs_tol=1e-9):
            return int(nearest)
        return result

    def truth(self, value, line):
        if isinstance(value, bool):
            return value
        raise EasyError("condition is not true or false", line)

    def as_number(self, value, line):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EasyError("number expected", line)
        return value

    def as_index(self, value, line):
        if isinstance(value, bool):
            raise EasyError("index must be an integer", line)
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, int):
            return value
        raise EasyError("index must be an integer", line)

    def lookup(self, name, create, line):
        key = name.lower()
        if self.frames and key in self.frames[-1].cells:
            return self.frames[-1].cells[key]
        if key in self.globals:
            return self.globals[key]
        if create:
            cell = Cell(None)
            self.globals[key] = cell
            self.spelling[key] = name
            return cell
        raise EasyError(f"unknown name {name}", line)

    def is_bound(self, name):
        key = name.lower()
        if self.frames and key in self.frames[-1].cells:
            return True
        return key in self.globals

    def show(self, value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "nil"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return format(value, ".12g")
        if isinstance(value, str):
            return value
        if isinstance(value, Array):
            return "array"
        if isinstance(value, Structure):
            return value.type_name
        return str(value)


def run(source, inputs=None, max_steps=1_000_000, explain=False):
    machine = Machine(parse_source(source), inputs or [], max_steps, explain=explain)
    machine.start()
    return machine.result()
