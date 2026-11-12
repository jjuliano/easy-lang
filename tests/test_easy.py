import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from easy import EasyError, run
from easy.interview import InterviewError, explain_interview, lookup
from easy.lex import lex


def lines(source, inputs=None, **kwargs):
    return run(source, inputs=inputs, **kwargs).output


class LexerTests(unittest.TestCase):
    def test_arrow_and_relations(self):
        kinds = [tok.kind for tok in lex("a <- b ≤ c ≠ d")]
        self.assertEqual(kinds, ["IDENT", "ARROW", "IDENT", "LE", "IDENT", "NE", "IDENT", "EOF"])

    def test_comment_keeps_the_newline(self):
        kinds = [tok.kind for tok in lex("a ← 1 ¤ note\nb ← 2")]
        self.assertIn("NL", kinds)
        self.assertNotIn("note", [tok.value for tok in lex("a ← 1 ¤ note\nb ← 2")])

    def test_newline_inside_parentheses_is_whitespace(self):
        kinds = [tok.kind for tok in lex("floor((1 +\n2))")]
        self.assertNotIn("NL", kinds)


class ExpressionTests(unittest.TestCase):
    def program(self, body):
        return f"procedure MAIN\n{body}\nend MAIN\n"

    def test_precedence_and_power(self):
        out = lines(self.program("output 1 + 2 * 3 ^ 2\noutput 2 ^ 3 ^ 2\noutput (2 ^ 3) ^ 2\noutput -2 ^ 2"))
        self.assertEqual(out, ["19", "512", "64", "-4"])

    def test_division_floor_mod_and_log(self):
        body = """
        output 7 / 2
        output floor(7 / 2)
        output ⌊7 / 2⌋
        output ceil(-0.5)
        output floor(-0.5)
        output log2(1024)
        output 10 mod 3
        output 10 + 3 mod 2
        """
        self.assertEqual(
            lines(self.program(body)),
            ["3.5", "3", "3", "0", "-1", "10", "1", "11"],
        )

    def test_not_binds_tighter_than_a_relation(self):
        out = lines(self.program("output not false = false\noutput not (1 = 2)"))
        self.assertEqual(out, ["false", "true"])

    def test_relations_do_not_chain(self):
        with self.assertRaises(EasyError):
            lines(self.program("output 1 < 2 < 3"))

    def test_strings_and_nil(self):
        out = lines(self.program("output \"oak\"\nx ← nil\noutput x\noutput \"a\" + \"b\""))
        self.assertEqual(out, ["oak", "nil", "ab"])


class ControlTests(unittest.TestCase):
    def test_dangling_else_binds_to_the_inner_if(self):
        src = """
        procedure MAIN
        if false then
          if true then output 1
        else output 3
        output 4
        end MAIN
        """
        self.assertEqual(lines(src), ["4"])

    def test_else_belongs_to_the_nearest_if(self):
        src = """
        procedure MAIN
        if true then
          if false then output 1
          else output 2
        end MAIN
        """
        self.assertEqual(lines(src), ["2"])

    def test_case_else_and_no_match(self):
        src = """
        procedure Show(n)
        case
        : n = 1: output "one"
        : n = 2: output "two"
        : else: output "other"
        endcase
        end Show
        procedure Silent(n)
        case
        : n = 1: output "one"
        endcase
        end Silent
        procedure MAIN
        call Show(2)
        call Show(9)
        call Silent(4)
        output "done"
        end MAIN
        """
        self.assertEqual(lines(src), ["two", "other", "done"])

    def test_repeat_runs_once_and_while_can_skip(self):
        src = """
        procedure MAIN
        i ← 3
        repeat
          i ← i + 1
        until i > 0
        output i
        n ← 0
        while n > 0 do
          output 9
        endwhile
        output n
        end MAIN
        """
        self.assertEqual(lines(src), ["4", "0"])

    def test_exit_leaves_only_the_inner_loop(self):
        src = """
        procedure MAIN
        i ← 0
        while i < 5 do
          i ← i + 1
          loop
            exit
          forever
          if i = 2 then exit
        endwhile
        output i
        end MAIN
        """
        self.assertEqual(lines(src), ["2"])

    def test_for_bounds_are_fixed_on_entry(self):
        src = """
        procedure MAIN
        n ← 3
        step ← 1
        for i ← 1 to n by step do
          n ← 1
          step ← 9
          output i
        endfor
        output i
        for j ← 5 to 1 do
          output 9
        endfor
        output j
        for k ← 3 to 1 by -1 do
          output k
        endfor
        end MAIN
        """
        self.assertEqual(lines(src), ["1", "2", "3", "4", "5", "3", "2", "1"])

    def test_for_step_zero_is_an_error(self):
        src = """
        procedure MAIN
        for i ← 1 to 2 by 0 do
          output i
        endfor
        end MAIN
        """
        with self.assertRaises(EasyError):
            lines(src)

    def test_goto_and_stop(self):
        src = """
        procedure MAIN
        i ← 1
        go to skip
        i ← 100
        skip: output i
        output 2
        stop
        output 3
        end MAIN
        """
        self.assertEqual(lines(src), ["1", "2"])

    def test_missing_label_and_exit_outside_a_loop(self):
        with self.assertRaises(EasyError):
            lines("procedure MAIN\ngo to missing\nend MAIN\n")
        with self.assertRaises(EasyError):
            lines("procedure MAIN\nexit\nend MAIN\n")


class ProcedureTests(unittest.TestCase):
    def test_reference_and_expression_temporaries(self):
        src = """
        procedure Inc(a)
        a ← a + 1
        end Inc
        procedure Swap(a, b)
        t ← a
        a ← b
        b ← t
        end Swap
        procedure MAIN
        n ← 10
        call Inc(n)
        output n
        call Inc(n - 1)
        output n
        x ← 1
        y ← 2
        call Swap(x, y)
        output x y
        end MAIN
        """
        self.assertEqual(lines(src), ["11", "11", "2 1"])

    def test_recursion_and_a_later_procedure(self):
        src = """
        procedure MAIN
        output Fact(5)
        output Later(3)
        end MAIN
        procedure Fact(n)
        if n = 0 then return(1)
        else return(n * Fact(n - 1))
        end Fact
        procedure Later(n)
        return(n + 1)
        end Later
        """
        self.assertEqual(lines(src), ["120", "4"])

    def test_multiword_name_and_return_value(self):
        src = """
        procedure Add One(n)
        return(n + 1)
        end Add One
        procedure MAIN
        output Add One(10)
        return(7)
        end MAIN
        """
        result = run(src)
        self.assertEqual(result.output, ["11"])
        self.assertEqual(result.value, 7)

    def test_short_circuit(self):
        src = """
        procedure Touch(flag)
        flag ← true
        return(true)
        end Touch
        procedure MAIN
        flag ← false
        cond ← false and Touch(flag)
        output flag
        cond ← true or Touch(flag)
        output flag
        cond ← false or Touch(flag)
        output flag
        output cond
        end MAIN
        """
        self.assertEqual(lines(src), ["false", "false", "true", "true"])

    def test_global_assignment_and_unknown_name(self):
        src = """
        procedure Set
        g ← 5
        end Set
        procedure MAIN
        call Set
        output g
        end MAIN
        """
        self.assertEqual(lines(src), ["5"])
        with self.assertRaises(EasyError):
            lines("procedure MAIN\noutput missing\nend MAIN\n")

    def test_no_main(self):
        with self.assertRaises(EasyError):
            lines("procedure Other\noutput 1\nend Other\n")


class ArrayTests(unittest.TestCase):
    def test_bounds_nil_and_parameters(self):
        src = """
        procedure Sum(a, n)
        array a(1:n)
        s ← 0
        for i ← 1 to n do
          s ← s + a(i)
        endfor
        return(s)
        end Sum
        procedure Zero(a)
        array a(1:1)
        a(1) ← 0
        end Zero
        procedure MAIN
        array row(1:3), grid(2, 2)
        row(1) ← 4
        row(2) ← 5
        row(3) ← 6
        output Sum(row, 3)
        output row(2)
        call Zero(row)
        output row(1)
        grid(2, 1) ← 9
        output grid(2, 1)
        output grid(1, 1)
        end MAIN
        """
        self.assertEqual(lines(src), ["15", "5", "0", "9", "nil"])

    def test_index_errors(self):
        src = """
        procedure MAIN
        array a(1:2)
        output a(0)
        end MAIN
        """
        with self.assertRaises(EasyError):
            lines(src)


class NodeTests(unittest.TestCase):
    def test_chain_and_reuse(self):
        src = """
        node(info, link)
        procedure MAIN
        call GETNODE(a)
        call GETNODE(b)
        info(a) ← "oak"
        link(a) ← b
        info(b) ← "ash"
        link(b) ← nil
        output info(link(a))
        call RETNODE(b)
        call GETNODE(c)
        output c
        end MAIN
        """
        self.assertEqual(lines(src), ["ash", "2"])

    def test_pool_exhaustion(self):
        src = """
        pool 1
        node(info, link)
        procedure MAIN
        call GETNODE(a)
        call GETNODE(b)
        end MAIN
        """
        with self.assertRaises(EasyError) as caught:
            lines(src)
        self.assertIn("GETNODE", str(caught.exception))

    def test_structure_supplies_the_node_layout(self):
        src = """
        structure Chain = [(info, link), head]
        procedure MAIN
        Chain chain
        head(chain) ← nil
        call GETNODE(p)
        info(p) ← 7
        link(p) ← nil
        head(chain) ← p
        output info(head(chain))
        end MAIN
        """
        self.assertEqual(lines(src), ["7"])


class StructureTests(unittest.TestCase):
    def test_opened_fields_and_the_matching_array_name(self):
        src = """
        structure Pair(n) = [box(1:n), other(1:n), top]
        procedure Push(box, x)
        top ← top + 1
        box(top) ← x
        end Push
        procedure MAIN
        Pair pair(2)
        top(pair) ← 0
        call Push(pair, 8)
        output box(pair)(1)
        output other(pair)(1)
        output top(pair)
        end MAIN
        """
        self.assertEqual(lines(src), ["8", "nil", "1"])

    def test_one_array_structure_indexes_directly(self):
        src = """
        structure Box(n) = [box(1:n), top]
        procedure Push(box, x)
        if top = n then stop
        top ← top + 1
        box(top) ← x
        end Push
        procedure MAIN
        Box box(2)
        top(box) ← 0
        call Push(box, 4)
        call Push(box, 5)
        output box(1)
        output box(2)
        output top(box)
        end MAIN
        """
        self.assertEqual(lines(src), ["4", "5", "2"])


class InputTests(unittest.TestCase):
    def test_tokens_and_a_slice(self):
        src = """
        procedure MAIN
        array a(1:5)
        input m, name, a(1:m)
        output name
        output a(1)
        output a(2)
        output m + 1
        end MAIN
        """
        self.assertEqual(lines(src, ["2", "oak", "10", "20"]), ["oak", "10", "20", "3"])

    def test_input_exhausted(self):
        with self.assertRaises(EasyError):
            lines("procedure MAIN\ninput x\nend MAIN\n", [])


class LimitTests(unittest.TestCase):
    def test_step_limit(self):
        src = """
        procedure MAIN
        while true do
          x ← 1
        endwhile
        end MAIN
        """
        with self.assertRaises(EasyError):
            lines(src, max_steps=40)


class ExampleTests(unittest.TestCase):
    def test_examples(self):
        expected = {
            "gcd.easy": ["6", "21"],
            "stack.easy": ["13", "8", "5"],
            "links.easy": ["oak", "ash", "elm"],
            "search.easy": ["3", "0", "3", "0"],
            "hanoi.easy": ["A B", "A C", "B C", "A B", "C A", "C B", "A B"],
        }
        for name, want in expected.items():
            source = (ROOT / "examples" / name).read_text(encoding="utf-8")
            self.assertEqual(lines(source), want, name)

    def test_cli(self):
        proc = subprocess.run(
            [sys.executable, "-m", "easy", "examples/gcd.easy"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "6\n21\n")

    def test_explain_shows_each_step(self):
        from easy import run

        source = (ROOT / "examples" / "gcd.easy").read_text(encoding="utf-8")
        result = run(source, explain=True)
        self.assertEqual(result.output, ["6", "21"])
        text = "\n".join(result.trace)
        self.assertIn("+ procedure MAIN", text)
        self.assertIn("procedure GCD(a=48, b=18)", text)
        self.assertIn("r ← (a mod b) → 12", text)
        self.assertIn("while (b ≠ 0) → false", text)
        self.assertIn("return 6", text)
        self.assertIn("output GCD(48, 18) → 6", text)
        self.assertEqual(run(source).trace, [])

    def test_cli_explain(self):
        proc = subprocess.run(
            [sys.executable, "-m", "easy", "--explain", "examples/gcd.easy"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "6\n21\n")
        self.assertIn("procedure GCD(a=48, b=18)", proc.stderr)
        dashed = subprocess.run(
            [sys.executable, "-m", "easy", "-x", "examples/gcd.easy"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(dashed.returncode, 0, dashed.stderr)
        self.assertEqual(dashed.stdout, "6\n21\n")
        self.assertIn("+ procedure MAIN", dashed.stderr)

    def test_github_blob_link_names_the_raw_file(self):
        from easy.__main__ import as_fetch_url

        blob = (
            "https://github.com/jjuliano/datastructures/blob/main/"
            "session03-algorithms/easy/insertion.easy"
        )
        self.assertEqual(
            as_fetch_url(blob),
            "https://raw.githubusercontent.com/jjuliano/datastructures/main/"
            "session03-algorithms/easy/insertion.easy",
        )
        self.assertIsNone(as_fetch_url("insertion.easy"))

    def test_cli_fetches_a_url(self):
        import threading
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

        server = ThreadingHTTPServer(("127.0.0.1", 0), SimpleHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "easy", f"http://{host}:{port}/examples/gcd.easy"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "6\n21\n")

    def test_cli_stdin_and_error(self):
        program = ROOT / "examples" / "_stdin.easy"
        program.write_text(
            "procedure MAIN\ninput x\noutput x + 1\nend MAIN\n",
            encoding="utf-8",
        )
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "easy", str(program)],
                cwd=ROOT,
                input="41\n",
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "42\n")
            bad = subprocess.run(
                [sys.executable, "-m", "easy", str(program)],
                cwd=ROOT,
                input="",
                capture_output=True,
                text=True,
            )
            self.assertEqual(bad.returncode, 1)
            self.assertIn("easy:", bad.stderr)
        finally:
            program.unlink(missing_ok=True)


    def test_interview_covers_every_example(self):
        missing = []
        for path in sorted((ROOT / "examples").glob("*.easy")):
            source = path.read_text(encoding="utf-8")
            matches = lookup(source, name=path.name)
            if not matches:
                missing.append(path.name)
        self.assertEqual(missing, [])
        search = lookup(
            (ROOT / "examples" / "search.easy").read_text(encoding="utf-8"),
            name="search.easy",
        )
        self.assertEqual([e.id for e in search], ["linear", "binary"])
        bst = lookup(
            (ROOT / "examples" / "bst.easy").read_text(encoding="utf-8"),
            name="bst.easy",
        )
        self.assertEqual([e.id for e in bst], ["bst", "height"])

    def test_interview_stack_and_paths(self):
        stack = (ROOT / "examples" / "stack.easy").read_text(encoding="utf-8")
        text = explain_interview(stack, name="stack.easy")
        self.assertIn("How to explain it in an interview: An array stack", text)
        self.assertIn("- What it is: A stack is last in, first out", text)
        self.assertIn("- Key steps:", text)
        self.assertIn("  - To push,", text)
        self.assertIn("  - To pop,", text)
        self.assertIn("- Time and space:", text)
        self.assertIn("O(1)", text)
        self.assertIn("- Watch for:", text)
        self.assertIn("overflow", text.lower())
        self.assertIn("underflow", text.lower())
        pile = (ROOT / "examples" / "pile.easy").read_text(encoding="utf-8")
        self.assertEqual(
            [e.id for e in lookup(pile, name="pile.easy")],
            ["stack"],
        )
        paths = (ROOT / "examples" / "paths.easy").read_text(encoding="utf-8")
        text = explain_interview(paths, name="paths.easy")
        self.assertIn("Dijkstra", text)
        self.assertIn("O(n^2)", text)
        self.assertIn("negative", text.lower())
        self.assertIn("Kruskal", text)
        self.assertIn("O(m log m)", text)
        self.assertLess(text.index("Dijkstra"), text.index("Kruskal"))

    def test_interview_comment_overrides_catalog(self):
        source = (
            "\N{CURRENCY SIGN} Interview: This toy just prints a number.\n"
            "\N{CURRENCY SIGN} Key steps: Store 1, then print it.\n"
            "\N{CURRENCY SIGN} Cost: O(1) time and space.\n"
            "\N{CURRENCY SIGN} Watch: Nothing much, it is a toy.\n"
            "\n"
            "procedure MAIN\n"
            "output 1\n"
            "end MAIN\n"
        )
        text = explain_interview(source, name="unused.easy")
        self.assertIn("- What it is: This toy just prints a number.", text)
        self.assertIn("- Key steps: Store 1, then print it.", text)
        self.assertIn("- Time and space: O(1) time and space.", text)
        self.assertIn("- Watch for: Nothing much, it is a toy.", text)

    def test_interview_unknown_program(self):
        source = "procedure MAIN\noutput 1\nend MAIN\n"
        with self.assertRaises(InterviewError):
            explain_interview(source, name="mystery.easy")

    def test_cli_interview(self):
        proc = subprocess.run(
            [sys.executable, "-m", "easy", "--interview", "examples/stack.easy"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("How to explain it in an interview: An array stack", proc.stdout)
        self.assertIn("- What it is:", proc.stdout)
        self.assertIn("- Key steps:", proc.stdout)
        self.assertNotIn("13", proc.stdout)
        self.assertEqual(proc.stderr, "")
        paths = subprocess.run(
            [sys.executable, "-m", "easy", "--interview", "examples/paths.easy"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(paths.returncode, 0, paths.stderr)
        self.assertIn("Dijkstra", paths.stdout)
        self.assertIn("Kruskal", paths.stdout)
        missing = subprocess.run(
            [sys.executable, "-m", "easy", "--interview", "examples/_none.easy"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(missing.returncode, 1)
        self.assertIn("easy:", missing.stderr)



if __name__ == "__main__":
    unittest.main()
