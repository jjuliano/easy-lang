"""Lexer for Easy source text.

The print form uses ←, ≤, ≥, ≠, ×, and ¤. The ASCII spellings <-, <=, >=,
/=, *, and the same comment mark are accepted so a program can be typed.
"""

from easy.errors import EasyError

KEYWORDS = {
    "procedure",
    "end",
    "endwhile",
    "endfor",
    "endcase",
    "if",
    "then",
    "else",
    "while",
    "do",
    "repeat",
    "until",
    "loop",
    "forever",
    "for",
    "to",
    "by",
    "case",
    "call",
    "return",
    "stop",
    "go",
    "input",
    "output",
    "array",
    "node",
    "structure",
    "pool",
    "exit",
    "and",
    "or",
    "not",
    "mod",
    "true",
    "false",
    "nil",
    "lambda",
    "goto",
}

TWO_CHAR = {
    "<-": "ARROW",
    "<=": "LE",
    ">=": "GE",
    "<>": "NE",
    "/=": "NE",
    "!=": "NE",
}

ONE_CHAR = {
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
    "^": "CARET",
    "(": "LPAREN",
    ")": "RPAREN",
    "[": "LBRACK",
    "]": "RBRACK",
    ",": "COMMA",
    ":": "COLON",
    ";": "SEMI",
    "=": "EQ",
    "<": "LT",
    ">": "GT",
    "←": "ARROW",
    "≤": "LE",
    "≥": "GE",
    "≠": "NE",
    "×": "STAR",
    "ˆ": "CARET",
    "−": "MINUS",
    "Λ": "NIL",
    "⌊": "FLOOR_L",
    "⌋": "FLOOR_R",
    "⌈": "CEIL_L",
    "⌉": "CEIL_R",
}


class Token:
    def __init__(self, kind, value, line):
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, {self.line})"


def lex(source):
    tokens = []
    i = 0
    line = 1
    n = len(source)
    paren = 0

    def peek(offset=0):
        j = i + offset
        return source[j] if j < n else ""

    while i < n:
        ch = source[i]
        if ch in " \t":
            i += 1
            continue
        if ch == "\r":
            i += 1
            continue
        if ch == "¤":
            while i < n and source[i] not in "\n":
                i += 1
            continue
        if ch == "\n":
            if paren == 0:
                tokens.append(Token("NL", "\n", line))
            line += 1
            i += 1
            continue
        if ch in "'\"′‘’":
            quote = ch
            i += 1
            start = i
            while i < n and source[i] not in "'\"′‘’\n":
                i += 1
            if i >= n or source[i] == "\n":
                raise EasyError("unterminated string", line)
            tokens.append(Token("STRING", source[start:i], line))
            i += 1
            continue
        if ch.isdigit() or (ch == "." and peek(1).isdigit()):
            start = i
            has_dot = False
            while i < n and (source[i].isdigit() or (source[i] == "." and not has_dot)):
                if source[i] == ".":
                    has_dot = True
                i += 1
            text = source[start:i]
            value = float(text) if has_dot else int(text)
            tokens.append(Token("NUMBER", value, line))
            continue
        if ch.isalpha() or ch == "_" or ch in "αβγδεζηθικλμνξπρστυφχψωΑΒΓΔ":
            start = i
            i += 1
            while i < n and (source[i].isalnum() or source[i] == "_"):
                i += 1
            word = source[start:i]
            low = word.lower()
            if low == "nil" or low == "lambda":
                tokens.append(Token("NIL", None, line))
            elif low in KEYWORDS:
                tokens.append(Token(low.upper(), low, line))
            else:
                tokens.append(Token("IDENT", word, line))
            continue
        two = source[i : i + 2]
        if two in TWO_CHAR:
            tokens.append(Token(TWO_CHAR[two], two, line))
            i += 2
            continue
        if ch in ONE_CHAR:
            kind = ONE_CHAR[ch]
            if kind == "NIL":
                tokens.append(Token("NIL", None, line))
            else:
                tokens.append(Token(kind, ch, line))
            if ch == "(":
                paren += 1
            elif ch == ")" and paren:
                paren -= 1
            i += 1
            continue
        raise EasyError(f"unexpected character {ch!r}", line)
    tokens.append(Token("EOF", "", line))
    return tokens
