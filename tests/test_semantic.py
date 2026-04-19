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


def print_semantic_errors(title, errors):
    print(title)
    if errors:
        for error in errors:
            print(f"  - {error}")
    else:
        print("  - No semantic errors")


def test_semantic():
    ast = quick_parse("role X inherits Y { permissions: z }")
    errs = analyze_program(ast)
    print_semantic_errors("Semantic errors for undefined inheritance:", errs)
    assert any("undefined" in e.lower() for e in errs)

    ast = quick_parse("""
        role A inherits B { permissions: p }
        role B { permissions: p }
        assign A to Alice
        assign A to Alice
    """)
    errs = analyze_program(ast)
    print_semantic_errors("Semantic errors for redundant assignment:", errs)
    assert any("redund" in e.lower() for e in errs)
    assert not any("loop" in e.lower() for e in errs)

    ast = quick_parse("""
        role A inherits B { permissions: p }
        role B inherits A { permissions: p }
    """)
    errs = analyze_program(ast)
    print_semantic_errors("Semantic errors for inheritance cycle:", errs)
    assert any("cycle" in e.lower() for e in errs)

    ast = quick_parse("""
        role A { permissions: read }
        role B inherits A { permissions: write }
        role C { permissions: delete }
        assign B to alice
        assign C to bob
        conflict A, C
    """)
    errs = analyze_program(ast)
    print_semantic_errors("Semantic errors for non-conflicting users:", errs)
    assert not any("Conflict:" in e for e in errs)

    ast = quick_parse("""
        role A { permissions: read }
        role B inherits A { permissions: write }
        role C { permissions: delete }
        assign B to alice
        assign C to alice
        conflict A, C
        conflict C, A
    """)
    errs = analyze_program(ast)
    print_semantic_errors("Semantic errors for actual conflict:", errs)
    conflict_errors = [e for e in errs if "Conflict:" in e]
    assert len(conflict_errors) == 1
    assert "alice" in conflict_errors[0]

if __name__ == "__main__":
    test_semantic()
