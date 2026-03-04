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
    
    print("\nTesting inheritance loops...")
    ast = quick_parse("""
        role A inherits B { permissions: p }
        role B inherits A { permissions: p }
    """)
    print("AST:", ast)
    for n in ast.roles:
        print("Node:", n)
    errs = analyze_program(ast)
    print("\nDetected semantic errors:", errs)

    assert any("loop" in e.lower() for e in errs)
    
    print("Semantic tests passed.")

if __name__ == "__main__":
    test_semantic()
