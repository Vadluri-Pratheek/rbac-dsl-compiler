"""
Token definitions and Lexer for RBAC DSL
"""
import ply.lex as lex

tokens = (
    "ROLE",
    "INHERITS",
    "PERMISSIONS",
    "CONFLICT",
    "ASSIGN",
    "TO",
    "IDENTIFIER",
    "LBRACE",
    "RBRACE",
    "COLON",
    "COMMA",
)

reserved = {
    "role": "ROLE",
    "inherits": "INHERITS",
    "permissions": "PERMISSIONS",
    "conflict": "CONFLICT",
    "assign": "ASSIGN",
    "to": "TO",
}


class RBACLexer:
    tokens = tokens

    t_LBRACE = r"\{"
    t_RBRACE = r"\}"
    t_COLON = r":"
    t_COMMA = r","
    t_ignore = " \t"

    def __init__(self):
        self.lexer = None
        self.errors = []

    def t_IDENTIFIER(self, t):
        r"[a-zA-Z_][a-zA-Z_0-9]*"
        t.type = reserved.get(t.value, "IDENTIFIER")
        return t

    def t_newline(self, t):
        r"\n+"
        t.lexer.lineno += len(t.value)

    def t_COMMENT(self, t):
        r"//.*"
        pass

    def t_error(self, t):
        msg = f"Illegal character '{t.value[0]}' at line {t.lineno}"
        self.errors.append(msg)
        print(f"Lexer error: {msg}")
        t.lexer.skip(1)

    def build(self):
        self.lexer = lex.lex(module=self)
        return self.lexer

    def tokenize(self, data):
        self.lexer.input(data)
        self.errors = []
        result = []

        while True:
            tok = self.lexer.token()
            if not tok:
                break
            result.append(tok)

        return result

    def print_tokens(self, data):
        toks = self.tokenize(data)

        print("Token list:")
        for tok in toks:
            print(f"- {tok.type}: {tok.value}")
        print(f"Total tokens: {len(toks)}")

        if self.errors:
            for e in self.errors:
                print(f"- {e}")
        else:
            print("No lexer errors.")

        return toks


if __name__ == "__main__":
    lexer = RBACLexer()
    lexer.build()
    test = """role Admin inherits User {
                    permissions: read, write
            }
            role User {
                    permissions: krekkfk  read
            }
            conflict Admin, User
            assign Admin to Alice
            """


    print(test)
    lexer.print_tokens(test)
