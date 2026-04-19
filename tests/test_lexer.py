import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lexer import RBACLexer


def format_tokens(tokens):
    return "\n".join(
        str(
            {
                "type": token.type,
                "value": token.value,
                "line": token.lineno,
                "position": token.lexpos,
            }
        )
        for token in tokens
    )


def test_lexer():
    l = RBACLexer()
    l.build()

    toks = l.tokenize("role User { permissions: read }")
    print("Lexer tokens for role definition:")
    print(format_tokens(toks))
    assert any(t.type == "ROLE" for t in toks)
    assert any(t.value == "User" for t in toks)

    toks = l.tokenize("role Admin inherits User")
    print("Lexer tokens for inheritance:")
    print(format_tokens(toks))
    assert any(t.type == "INHERITS" for t in toks)


if __name__ == "__main__":
    test_lexer()
