import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lexer import RBACLexer


def test_lexer():
    l = RBACLexer()
    l.build()

    print("Testing basic tokens...")
    toks = l.print_tokens("role User { permissions: read }")
    assert any(t.type == "ROLE" for t in toks)
    assert any(t.value == "User" for t in toks)

    print("Testing inheritance keyword...")
    toks = l.print_tokens("role Admin inherits User")
    assert any(t.type == "INHERITS" for t in toks)

    print("Lexer tests passed.")


if __name__ == "__main__":
    test_lexer()
