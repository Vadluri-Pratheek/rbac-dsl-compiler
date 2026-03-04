import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lexer import RBACLexer
from src.parser import RBACParser
from src.security import run_security_checks

def quick_parse(data):
    l = RBACLexer()
    l.build()
    p = RBACParser()
    p.build()
    return p.parse(data, l.lexer)

def test_security():
    print("Testing security conflicts...")
    ast = quick_parse("""
        role Admin { permissions: all }
        role Guest { permissions: none }
        conflict Admin, Guest
        assign Admin to bob
        assign Guest to bob
    """)
    warns = run_security_checks(ast)
    assert any("conflict" in w.lower() for w in warns)

    print("Testing redundancy...")
    ast = quick_parse("""
        role P { permissions: read }
        role C inherits P { permissions: read, write }
    """)
    warns = run_security_checks(ast)
    assert any("redundant" in w.lower() for w in warns)

    print("Security tests passed.")

if __name__ == "__main__":
    test_security()
