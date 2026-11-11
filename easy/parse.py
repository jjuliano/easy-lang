"""Parser and compiler for Easy procedures.

A program is a list of procedures, plus optional pool, node, array, and
structure declarations. `go to` is compiled to a jump, so each procedure
becomes a flat list of instructions.
"""

from easy.errors import EasyError
from easy.lex import lex

REL = {"EQ": "=", "NE": "<>", "LT": "<", "GT": ">", "LE": "<=", "GE": ">="}


class StructType:
    def __init__(self, name, params, fields, layout):
        self.name = name
        self.params = params
        self.fields = fields
        self.layout = layout


class Proc:
    def __init__(self, name, params, code, line):
        self.name = name
        self.params = params
        self.code = code
        self.line = line


class Program:
    def __init__(self):
        self.procedures = {}
        self.structures = {}
        self.prelude = []


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0
        self.program = Program()

    def peek(self, k=0):
        j = self.i + k
        if j >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[j]

    def at(self, kind):
        return self.peek().kind == kind

    def take(self):
        tok = self.peek()
        if tok.kind != "EOF":
            self.i += 1
        return tok

    def expect(self, kind):
        tok = self.peek()
        if tok.kind != kind:
            raise EasyError(f"expected {kind.lower()} but found {tok.value or tok.kind}", tok.line)
        return self.take()

    def skip_sep(self):
        while self.at("NL") or self.at("SEMI"):
            self.take()

    def parse(self):
        self.skip_sep()
        while not self.at("EOF"):
            if self.at("PROCEDURE"):
                self.parse_procedure()
            elif self.at("STRUCTURE"):
                self.parse_structure()
            elif self.at("NODE"):
                names, line = self.parse_node()
                self.program.prelude.append(("node", [n.lower() for n in names], line))
            elif self.at("POOL"):
                self.parse_pool()
            elif self.at("ARRAY"):
                specs, line = self.parse_array()
                self.program.prelude.append(("array", specs, line))
            else:
                tok = self.peek()
                raise EasyError(
                    "expected a procedure, structure, node, array, or pool",
                    tok.line,
                )
            self.skip_sep()
        if "main" not in self.program.procedures:
            raise EasyError("program has no MAIN procedure")
        return self.program

    def parse_pool(self):
        tok = self.expect("POOL")
        num = self.expect("NUMBER")
        if not isinstance(num.value, int) or num.value < 1:
            raise EasyError("pool size must be a positive integer", num.line)
        self.program.prelude.append(("pool", num.value, tok.line))

    def parse_node(self):
        tok = self.expect("NODE")
        self.expect("LPAREN")
        names = [self.expect("IDENT").value]
        while self.at("COMMA"):
            self.take()
            names.append(self.expect("IDENT").value)
        self.expect("RPAREN")
        return names, tok.line

    def parse_structure(self):
        tok = self.expect("STRUCTURE")
        name = self.expect("IDENT").value
        params = []
        if self.at("LPAREN"):
            params = self.parse_names()
        self.skip_sep()
        self.expect("EQ")
        self.skip_sep()
        self.expect("LBRACK")
        self.skip_sep()
        fields = []
        layout = None
        seen = {p.lower() for p in params}
        while not self.at("RBRACK") and not self.at("EOF"):
            if self.at("LPAREN"):
                if layout is not None:
                    raise EasyError("a structure has one node layout", self.peek().line)
                node_names, _ = self._names_in_parens()
                layout = node_names
            else:
                field = self.expect("IDENT").value
                key = field.lower()
                if key in seen:
                    raise EasyError(f"duplicate name {field}", self.peek().line)
                seen.add(key)
                if self.at("LPAREN"):
                    dims = self.parse_dims()
                    fields.append(("array", field, dims))
                else:
                    fields.append(("scalar", field))
            self.skip_sep()
            if self.at("COMMA"):
                self.take()
                self.skip_sep()
        self.expect("RBRACK")
        key = name.lower()
        if key in self.program.structures:
            raise EasyError(f"duplicate structure {name}", tok.line)
        self.program.structures[key] = StructType(name, params, fields, layout)
        if layout:
            self.program.prelude.append(("node", [n.lower() for n in layout], tok.line))

    def _names_in_parens(self):
        self.expect("LPAREN")
        names = [self.expect("IDENT").value]
        while self.at("COMMA"):
            self.take()
            names.append(self.expect("IDENT").value)
        self.expect("RPAREN")
        return names, None

    def parse_names(self):
        self.expect("LPAREN")
        names = []
        if not self.at("RPAREN"):
            names.append(self.expect("IDENT").value)
            while self.at("COMMA"):
                self.take()
                names.append(self.expect("IDENT").value)
        self.expect("RPAREN")
        return names

    def parse_procedure(self):
        tok = self.expect("PROCEDURE")
        name = self.parse_proc_name(require_paren=False)
        params = []
        if self.at("LPAREN"):
            params = self.parse_names()
        self.skip_sep()
        body = self.parse_list({"END"})
        self.expect("END")
        end_name = []
        while self.at("IDENT"):
            end_name.append(self.take().value)
        if end_name and " ".join(end_name).lower() != name.lower():
            raise EasyError(f"end {name} does not match", tok.line)
        key = name.lower()
        if key in self.program.procedures:
            raise EasyError(f"duplicate procedure {name}", tok.line)
        code = compile_body(body, tok.line)
        self.program.procedures[key] = Proc(name, params, code, tok.line)

    def parse_proc_name(self, require_paren):
        parts = [self.expect("IDENT").value]
        while self.at("IDENT"):
            parts.append(self.take().value)
        if require_paren and not self.at("LPAREN"):
            raise EasyError("expected (", self.peek().line)
        return " ".join(parts)

    def parse_list(self, stop):
        stmts = []
        self.skip_sep()
        while self.peek().kind not in stop and not self.at("EOF"):
            before = self.i
            stmts.append(self.parse_statement())
            if self.i == before:
                raise EasyError("empty statement", self.peek().line)
            self.skip_sep()
        return stmts

    def parse_statement(self):
        line = self.peek().line
        if self.at("IDENT") and self.peek(1).kind == "COLON":
            name = self.take().value
            self.take()
            self.skip_sep()
            return ("labeled", name, self.parse_statement(), line)
        if self.at("IF"):
            return self.parse_if(line)
        if self.at("CASE"):
            return self.parse_case(line)
        if self.at("WHILE"):
            return self.parse_while(line)
        if self.at("REPEAT"):
            return self.parse_repeat(line)
        if self.at("LOOP"):
            return self.parse_loop(line)
        if self.at("FOR"):
            return self.parse_for(line)
        if self.at("GO"):
            self.take()
            self.expect("TO")
            return ("goto", self.expect("IDENT").value, line)
        if self.at("GOTO"):
            self.take()
            return ("goto", self.expect("IDENT").value, line)
        if self.at("EXIT"):
            self.take()
            return ("exit", line)
        if self.at("INPUT"):
            self.take()
            return ("input", self.parse_items(self.parse_target, juxtapose=False), line)
        if self.at("OUTPUT"):
            self.take()
            return ("output", self.parse_items(self.parse_expr, juxtapose=True), line)
        if self.at("ARRAY"):
            specs, _ = self.parse_array()
            return ("array", specs, line)
        if self.at("NODE"):
            names, _ = self.parse_node()
            return ("node", names, line)
        if self.at("CALL"):
            self.take()
            name = self.parse_proc_name(require_paren=False)
            args = self.parse_names_or_args()
            return ("call", name, args, line)
        if self.at("RETURN"):
            self.take()
            expr = None
            if self.at("LPAREN"):
                self.take()
                expr = self.parse_expr()
                self.expect("RPAREN")
            return ("return", expr, line)
        if self.at("STOP"):
            self.take()
            return ("stop", line)
        if self.at("LBRACK"):
            self.take()
            body = self.parse_list({"RBRACK"})
            self.expect("RBRACK")
            return ("block", body, line)
        if self.at("PROCEDURE"):
            raise EasyError("a procedure cannot contain another procedure", line)
        if self.at("IDENT") and self.peek(1).kind == "IDENT":
            type_name = self.take().value
            var_name = self.take().value
            args = []
            if self.at("LPAREN"):
                args = self.parse_arg_list()
            return ("new", type_name, var_name, args, line)
        if self.starts_expr():
            target = self.parse_expr()
            self.expect("ARROW")
            value = self.parse_expr()
            require_lvalue(target)
            return ("assign", target, value, line)
        tok = self.peek()
        raise EasyError(f"unexpected {tok.value or tok.kind}", tok.line)

    def parse_names_or_args(self):
        if self.at("LPAREN"):
            return self.parse_arg_list()
        return []

    def parse_if(self, line):
        self.expect("IF")
        cond = self.parse_expr()
        self.expect("THEN")
        self.skip_sep()
        then_s = self.parse_statement()
        self.skip_sep()
        else_s = None
        if self.at("ELSE"):
            self.take()
            self.skip_sep()
            else_s = self.parse_statement()
        return ("if", cond, then_s, else_s, line)

    def parse_case(self, line):
        self.expect("CASE")
        self.skip_sep()
        arms = []
        while not self.at("ENDCASE") and not self.at("EOF"):
            self.expect("COLON")
            if self.at("ELSE"):
                self.take()
                self.expect("COLON")
                self.skip_sep()
                arms.append(("else", self.parse_statement()))
            else:
                cond = self.parse_expr()
                self.expect("COLON")
                self.skip_sep()
                arms.append(("when", cond, self.parse_statement()))
            self.skip_sep()
        self.expect("ENDCASE")
        return ("case", arms, line)

    def parse_while(self, line):
        self.expect("WHILE")
        cond = self.parse_expr()
        self.expect("DO")
        body = self.parse_list({"ENDWHILE"})
        self.expect("ENDWHILE")
        return ("while", cond, body, line)

    def parse_repeat(self, line):
        self.expect("REPEAT")
        body = self.parse_list({"UNTIL"})
        self.expect("UNTIL")
        cond = self.parse_expr()
        return ("repeat", body, cond, line)

    def parse_loop(self, line):
        self.expect("LOOP")
        body = self.parse_list({"FOREVER"})
        self.expect("FOREVER")
        return ("loop", body, line)

    def parse_for(self, line):
        self.expect("FOR")
        var = self.expect("IDENT").value
        self.expect("ARROW")
        start = self.parse_expr()
        self.expect("TO")
        finish = self.parse_expr()
        if self.at("BY"):
            self.take()
            step = self.parse_expr()
        else:
            step = ("num", 1, line)
        self.expect("DO")
        body = self.parse_list({"ENDFOR"})
        self.expect("ENDFOR")
        return ("for", var, start, finish, step, body, line)

    def parse_array(self):
        tok = self.expect("ARRAY")
        specs = []
        while True:
            name = self.expect("IDENT").value
            dims = self.parse_dims()
            specs.append((name, dims))
            if not self.at("COMMA"):
                break
            self.take()
        return specs, tok.line

    def parse_dims(self):
        self.expect("LPAREN")
        dims = [self.parse_dim()]
        while self.at("COMMA"):
            self.take()
            dims.append(self.parse_dim())
        self.expect("RPAREN")
        return dims

    def parse_dim(self):
        first = self.parse_expr()
        if self.at("COLON"):
            self.take()
            return (first, self.parse_expr())
        return (None, first)

    def parse_items(self, parse_one, juxtapose):
        items = [parse_one()]
        while self.at("COMMA") or (juxtapose and self.starts_expr()) or (
            not juxtapose and self.at("IDENT")
        ):
            if self.at("COMMA"):
                self.take()
            items.append(parse_one())
        return items

    def parse_target(self):
        expr = self.parse_expr()
        if expr[0] not in ("var", "apply", "slice"):
            raise EasyError("input expects a variable", expr[-1])
        return expr

    def starts_expr(self):
        return self.peek().kind in {
            "NUMBER",
            "STRING",
            "IDENT",
            "NIL",
            "LPAREN",
            "NOT",
            "MINUS",
            "PLUS",
            "TRUE",
            "FALSE",
            "FLOOR_L",
            "CEIL_L",
        }

    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.at("OR"):
            line = self.take().line
            right = self.parse_and()
            left = ("binary", "or", left, right, line)
        return left

    def parse_and(self):
        left = self.parse_rel()
        while self.at("AND"):
            line = self.take().line
            right = self.parse_rel()
            left = ("binary", "and", left, right, line)
        return left

    def parse_rel(self):
        left = self.parse_sum()
        if self.peek().kind in REL:
            tok = self.take()
            right = self.parse_sum()
            if self.peek().kind in REL:
                raise EasyError("relations do not chain", self.peek().line)
            return ("binary", REL[tok.kind], left, right, tok.line)
        return left

    def parse_sum(self):
        left = self.parse_signed()
        while self.at("PLUS") or self.at("MINUS"):
            tok = self.take()
            op = "+" if tok.kind == "PLUS" else "-"
            right = self.parse_signed()
            left = ("binary", op, left, right, tok.line)
        return left

    def parse_signed(self):
        if self.at("PLUS") or self.at("MINUS"):
            tok = self.take()
            op = "+" if tok.kind == "PLUS" else "-"
            return ("unary", op, self.parse_signed(), tok.line)
        return self.parse_term()

    def parse_term(self):
        left = self.parse_power()
        while self.at("STAR") or self.at("SLASH") or self.at("MOD"):
            tok = self.take()
            op = {"STAR": "*", "SLASH": "/", "MOD": "mod"}[tok.kind]
            right = self.parse_power()
            left = ("binary", op, left, right, tok.line)
        return left

    def parse_power(self):
        left = self.parse_not()
        if self.at("CARET"):
            tok = self.take()
            right = self.parse_power()
            return ("binary", "^", left, right, tok.line)
        return left

    def parse_not(self):
        if self.at("NOT"):
            tok = self.take()
            return ("unary", "not", self.parse_not(), tok.line)
        return self.parse_primary()

    def parse_primary(self):
        tok = self.peek()
        if tok.kind == "NUMBER":
            self.take()
            return ("num", tok.value, tok.line)
        if tok.kind == "STRING":
            self.take()
            return ("str", tok.value, tok.line)
        if tok.kind == "NIL":
            self.take()
            return ("nil", tok.line)
        if tok.kind == "TRUE":
            self.take()
            return ("bool", True, tok.line)
        if tok.kind == "FALSE":
            self.take()
            return ("bool", False, tok.line)
        if tok.kind == "FLOOR_L":
            self.take()
            expr = self.parse_expr()
            self.expect("FLOOR_R")
            return ("floor", expr, tok.line)
        if tok.kind == "CEIL_L":
            self.take()
            expr = self.parse_expr()
            self.expect("CEIL_R")
            return ("ceil", expr, tok.line)
        if tok.kind == "LPAREN":
            self.take()
            expr = self.parse_expr()
            self.expect("RPAREN")
            return expr
        if tok.kind == "IDENT":
            return self.parse_name_expr()
        raise EasyError(f"expected an expression but found {tok.value or tok.kind}", tok.line)

    def parse_name_expr(self):
        # Several words are one procedure name when a "(" follows them.
        k = 1
        while self.peek(k).kind == "IDENT":
            k += 1
        if k > 1 and self.peek(k).kind == "LPAREN":
            parts = [self.take().value for _ in range(k)]
            name = " ".join(parts)
            line = self.peek().line
        else:
            tok = self.take()
            name = tok.value
            line = tok.line
        expr = ("var", name, line)
        while self.at("LPAREN"):
            expr = self.parse_suffix(expr)
        return expr

    def parse_suffix(self, base):
        line = self.peek().line
        self.expect("LPAREN")
        if self.at("RPAREN"):
            self.take()
            return ("apply", base, [], line)
        first = self.parse_expr()
        if self.at("COLON"):
            self.take()
            second = self.parse_expr()
            self.expect("RPAREN")
            return ("slice", base, first, second, line)
        args = [first]
        while self.at("COMMA"):
            self.take()
            args.append(self.parse_expr())
        self.expect("RPAREN")
        return ("apply", base, args, line)

    def parse_arg_list(self):
        self.expect("LPAREN")
        args = []
        if not self.at("RPAREN"):
            args.append(self.parse_expr())
            while self.at("COMMA"):
                self.take()
                args.append(self.parse_expr())
        self.expect("RPAREN")
        return args


def require_lvalue(expr):
    if expr[0] == "var" and " " not in expr[1]:
        return
    if expr[0] == "apply":
        return
    raise EasyError("expected a variable", expr[-1])


def compile_body(body, line):
    code = []
    loops = []
    labels = {}
    gotos = []
    for stmt in body:
        compile_stmt(stmt, code, loops, labels, gotos)
    for inst in gotos:
        key = inst[3].lower()
        if key not in labels:
            raise EasyError(f"unknown label {inst[3]}", inst[4])
        inst[1] = labels[key]
    return code


def emit(code, inst):
    code.append(inst)
    return len(code) - 1


def compile_stmt(stmt, code, loops, labels, gotos):
    kind = stmt[0]
    if kind == "labeled":
        key = stmt[1].lower()
        if key in labels:
            raise EasyError(f"duplicate label {stmt[1]}", stmt[3])
        labels[key] = len(code)
        emit(code, ["label", stmt[1]])
        compile_stmt(stmt[2], code, loops, labels, gotos)
    elif kind == "block":
        for inner in stmt[1]:
            compile_stmt(inner, code, loops, labels, gotos)
    elif kind == "assign":
        emit(code, ["assign", stmt[1], stmt[2], stmt[3]])
    elif kind == "if":
        jf = emit(code, ["jf", stmt[1], None, "if"])
        compile_stmt(stmt[2], code, loops, labels, gotos)
        if stmt[3] is None:
            code[jf][2] = len(code)
        else:
            jump = emit(code, ["jump", None])
            code[jf][2] = len(code)
            compile_stmt(stmt[3], code, loops, labels, gotos)
            code[jump][1] = len(code)
    elif kind == "case":
        end_jumps = []
        for arm in stmt[1]:
            if arm[0] == "when":
                jf = emit(code, ["jf", arm[1], None, "case"])
                compile_stmt(arm[2], code, loops, labels, gotos)
                end_jumps.append(emit(code, ["jump", None]))
                code[jf][2] = len(code)
            else:
                compile_stmt(arm[1], code, loops, labels, gotos)
                end_jumps.append(emit(code, ["jump", None]))
        end = len(code)
        for index in end_jumps:
            code[index][1] = end
    elif kind == "while":
        loops.append([])
        start = len(code)
        jf = emit(code, ["jf", stmt[1], None, "while"])
        for inner in stmt[2]:
            compile_stmt(inner, code, loops, labels, gotos)
        emit(code, ["jump", start])
        end = len(code)
        code[jf][2] = end
        for index in loops.pop():
            code[index][1] = end
    elif kind == "repeat":
        loops.append([])
        start = len(code)
        for inner in stmt[1]:
            compile_stmt(inner, code, loops, labels, gotos)
        # until cond: leave when cond is true, so jump back when it is false
        emit(code, ["jf", stmt[2], start, "until"])
        end = len(code)
        for index in loops.pop():
            code[index][1] = end
    elif kind == "loop":
        loops.append([])
        start = len(code)
        for inner in stmt[1]:
            compile_stmt(inner, code, loops, labels, gotos)
        emit(code, ["jump", start])
        end = len(code)
        for index in loops.pop():
            code[index][1] = end
    elif kind == "for":
        slot = len(code)
        emit(code, ["for_init", stmt[1], stmt[2], stmt[3], stmt[4], slot, stmt[6]])
        test = emit(code, ["for_test", stmt[1], slot, None, stmt[6]])
        loops.append([])
        for inner in stmt[5]:
            compile_stmt(inner, code, loops, labels, gotos)
        emit(code, ["for_inc", stmt[1], slot, stmt[6]])
        emit(code, ["jump", test])
        end = len(code)
        code[test][3] = end
        for index in loops.pop():
            code[index][1] = end
    elif kind == "goto":
        inst = ["jump", None, "goto", stmt[1], stmt[2]]
        gotos.append(inst)
        emit(code, inst)
    elif kind == "exit":
        if not loops:
            raise EasyError("exit is outside a loop", stmt[1])
        loops[-1].append(emit(code, ["jump", None, "exit"]))
    elif kind == "input":
        emit(code, ["input", stmt[1], stmt[2]])
    elif kind == "output":
        emit(code, ["output", stmt[1], stmt[2]])
    elif kind == "array":
        emit(code, ["array", stmt[1], stmt[2]])
    elif kind == "node":
        emit(code, ["node", [n.lower() for n in stmt[1]], stmt[2]])
    elif kind == "call":
        emit(code, ["call", stmt[1], stmt[2], stmt[3]])
    elif kind == "return":
        emit(code, ["return", stmt[1], stmt[2]])
    elif kind == "stop":
        emit(code, ["stop", stmt[1]])
    elif kind == "new":
        emit(code, ["new", stmt[1], stmt[2], stmt[3], stmt[4]])
    else:
        raise EasyError(f"cannot compile {kind}")


def parse_source(source):
    return Parser(lex(source)).parse()
