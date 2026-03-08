import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lexer import RBACLexer
from src.parser import RBACParser
from src.semantic import analyze_program

def quick_parse(data):
    l = RBACLexer()
    l.build()
    p = RBACParser()
    p.build()
    return p.parse(data, l.lexer)

def test_semantic():
    print("\nTesting undefined role error...")
    ast = quick_parse("role X inherits Y { permissions: z }")
    print("AST:", ast)
    for n in ast.roles:
        print("Node:", n)
    errs = analyze_program(ast)
    print("\nDetected semantic errors:", errs)

    assert any("undefined" in e.lower() for e in errs)
    
    # ------------------------------------------------------------------
    print("\nTesting redundancy detection...")
    ast = quick_parse("""
        role A inherits B { permissions: p }
        role B { permissions: p }
        assign A to Alice
        assign A to Alice
    """)
    print("AST:", ast)
    for n in ast.roles:
        print("Node:", n)
    errs = analyze_program(ast)
    print("\nDetected semantic errors:", errs)

    # Should flag a redundant assignment but no inheritance loops.
    assert any("redund" in e.lower() for e in errs)
    assert not any("loop" in e.lower() for e in errs)

    # Now explicitly test a cycle scenario
    print("\nTesting inheritance loops...")
    ast = quick_parse("""
        role A inherits B { permissions: p }
        role B inherits A { permissions: p }
    """)
    errs = analyze_program(ast)
    print("Loop errors:", errs)
    assert any("loop" in e.lower() for e in errs)
    
    print("Semantic tests passed.")

if __name__ == "__main__":
    test_semantic()
