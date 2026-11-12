# easy-lang

An interpreter for Easy, the teaching notation in Evangel P. Quiwa, *Data Structures* (Manila: Electronics Hobbyists Publishing House, 2007). Quiwa traces that notation to SPARKS, in Ellis Horowitz and Sartaj Sahni, *Fundamentals of Data Structures* (Computer Science Press, 1976), pp. 8–15, and to the data-structures course Oscar Ibarra taught at the University of the Philippines in the mid-1970s.

This program runs those statement forms. It does not contain the textbook. The examples in `examples/` were written for this interpreter.

The interpreter is [jjuliano/easy-lang](https://github.com/jjuliano/easy-lang). It is MIT, copyright Joel Bryan Juliano. Procedures for the fifteen sessions live in [jjuliano/datastructures](https://github.com/jjuliano/datastructures), in each session's `easy/` folder. The examples in this repository are smaller checks.

## Install

Install once. Homebrew's Python refuses this line and reports `externally-managed-environment`:

```
python3 -m pip install --user git+https://github.com/jjuliano/easy-lang.git
```

Do not pass `--break-system-packages`. Use the installer instead. It builds a private environment at `~/.easy-lang` and links Easy onto this `python3`. Homebrew's packages stay as they are.

```
curl -fsSL -A easy-lang https://raw.githubusercontent.com/jjuliano/easy-lang/main/install.py | python3
```

If the command on your machine is `python` and not `python3`, pipe that installer into `python`.

## Run

After the install, run a file or a link from any directory. A GitHub blob link is the file page. The interpreter reads the file itself.

```
python3 -m easy insertion.easy
python3 -m easy https://github.com/jjuliano/datastructures/blob/main/session03-algorithms/easy/insertion.easy
python3 -m easy https://github.com/jjuliano/datastructures/blob/main/session03-algorithms/easy/search.easy
```

The insertion program prints `1 2 2 3`. The search program prints `3`, then `0`. If you skip the install, `python3 -m easy` stops with `No module named easy`.

## See each step

Put `--explain` before the file or the link. `-x` is the same flag. Leave it off when you only want the program's lines.

```
python3 -m easy --explain https://github.com/jjuliano/datastructures/blob/main/session03-algorithms/easy/search.easy
python3 -m easy -x insertion.easy
```

The steps come first, on standard error. Each one starts with `+`. A step inside a procedure is indented under that procedure's name. `←` stores a value. `→` is the value that step just produced. `while` and `case` end in `→ true` or `→ false`. The program's own lines follow, on standard output.

```
+ procedure MAIN
+   procedure Find(a=array, n=5, key=7)
+     lo ← 1
+     hi ← n → 5
+     while (lo ≤ hi) → true
+     mid ← floor(((lo + hi) / 2)) → 3
+     case (key = a(mid)) → true
+     return 3
+   output Find(row, 5, 7) → 3
3
0
```

The last two lines are the program. The step above `3` says `return 3`. If the command prints `usage:` and stops, run the installer again.

## Explain it for an interview

`--interview` does not run the program. It prints a short bullet list you can give in an interview:

- What it is
- Key steps (with a sub-bullet for each step, when the steps are already separate sentences)
- Time and space
- Watch for

```
python3 -m easy --interview examples/stack.easy
python3 -m easy --interview examples/paths.easy
python3 -m easy --interview https://github.com/jjuliano/datastructures/blob/main/session04-stacks/easy/pile.easy
```

The tool looks the program up in a catalog of the examples in this repository and of the session listings in the data-structures book. A program may also carry its own explainer in comments that start with `¤ Interview:`.


From a clone of this repository, the same command works without installing, if you run it in the clone:

```
python3 -m easy examples/gcd.easy
python3 -m unittest tests.test_easy
```

If standard input is not a terminal, `input` reads its whitespace-separated tokens. From Python, `easy.run(source, inputs=["2", "oak"], explain=True)` does the same. `.output` is the program's lines, `.trace` is the steps, `.value` is what `MAIN` returned, and `.globals` holds the global cells.

## Notation

A program is one or more procedures. Execution starts at `MAIN`. The print form and the typewriter form are the same language.

```
middle ← floor((lower + upper) / 2)
```

`<-` is the same arrow as `←`. `*`, `<=`, `>=`, `<>`, `/=`, and `!=` are the typewriter spellings of `×`, `≤`, `≥`, and `≠`. A comment runs from `¤` to the end of the line. `nil`, `lambda`, and `Λ` are the null address.

`/` is real division. Integer work uses `mod` and `floor` (also `⌊ ⌋`, `ceil`, `⌈ ⌉`, and `log2`). `^` is power and groups to the right, so `2^3^2` is 512. A leading minus applies to a whole power, so `-2^2` is −4. `not` binds tighter than `=`. `and` and `or` stop early and bind looser than relations. Relations do not chain.

```
if cond then S1
else S2
```

`S1` and `S2` are one statement, or several statements inside `[` and `]`. The `else` belongs to the nearest `if`. There is no `endif`.

```
case
: cond1: S1
: cond2: S2
: else: S3
endcase
```

```
while cond do
  S
endwhile

repeat
  S
until cond

loop
  S
forever

for i ← start to finish by step do
  S
endfor
```

`by` defaults to 1 and may be negative. `start`, `finish`, and `step` are read once, on entry. A positive step runs while the variable is less than or equal to `finish`. `exit` leaves the innermost loop. `go to label` jumps to `label:` in the same procedure. `stop` ends the program. Reaching `end` without `return` yields nil.

`output` prints one line. Items are separated by spaces or commas, and strings are printed without quotes. `input` reads the next tokens into variables. `input row(1:m)` fills that slice after the earlier names in the same statement have been read.

```
array row(1:n), grid(1:n, 1:m)
```

A bare upper bound means the lower bound is 1, so `array a(n)` is `a(1:n)`. An unset cell is nil. An index outside the bounds is an error. A declaration of a parameter that is already an array documents that array; it does not allocate a second one.

```
node(info, link)
call GETNODE(p)
info(p) ← "oak"
link(p) ← nil
call RETNODE(p)
```

`field(address)` is the cell in that node. Addresses are integers starting at 1. The pool holds 1024 nodes unless the program says `pool N`. A failed `GETNODE` stops the program. A procedure of the same name, if the program defines one, is used instead of the built-in.

Parameters are passed by reference. `call Swap(x, y)` shares the caller's cells. `call Move(n - 1, src, dst, spare)` copies the expression `n - 1` into a temporary cell, so the caller's `n` is unchanged. Assignment to a new name creates a global. A parameter, an opened structure field, or an array declared in the procedure hides a global of the same name.

The book's structure `S = [S(1:n), top]` is written here as a declaration and a variable:

```
structure Pile(n) = [slot(1:n), top]
Pile pile(4)
call Push(pile, x)
```

Passing `pile` opens `slot`, `top`, and `n` in the callee. From the outside, `top(pile)` is the scalar field. A structure with one array can be indexed directly. The linked form is:

```
structure Chain = [(info, link), head]
```

The parenthesized names are the node layout.

Procedure names may contain spaces (`end Add One`). Keywords are not case-sensitive. A program that never defines `MAIN` is rejected.
