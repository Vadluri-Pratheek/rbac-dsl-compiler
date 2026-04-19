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


def print_security_issues(title, warnings):
    print(title)
    if warnings:
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("  - No security issues")


def test_security():
    ast = quick_parse("""
        role P { permissions: read, read, write }
    """)
    warns = run_security_checks(ast)
    print_security_issues("Security issues for redundant permissions:", warns)
    assert any("redundant" in w.lower() for w in warns)

    ast = quick_parse("""
        role User { permissions: read }
        role Moderator inherits User { permissions: write, promote_user }
        role Admin inherits Moderator { permissions: delete }
        assign Moderator to aswin
    """)
    warns = run_security_checks(ast)
    print_security_issues("Security issues for privilege escalation:", warns)
    assert any("escalation" in w.lower() for w in warns)

    ast = quick_parse("""
        role Top { permissions: root }
        role Low inherits Top { permissions: browse }
    """)
    warns = run_security_checks(ast)
    print_security_issues("Security issues for high-privilege inheritance:", warns)
    assert any("inherits high-privilege role 'Top'" in w for w in warns)
    assert not any("can potentially escalate" in w for w in warns)

    ast = quick_parse("""
        role Admin inherits Moderator { permissions: delete }
        role Moderator inherits Admin { permissions: manage_roles }
    """)
    warns = run_security_checks(ast)
    print_security_issues("Security issues for cyclic inheritance:", warns)
    assert warns == []

    ast = quick_parse("""
        role Root { permissions: root }
        role Layer1 inherits Root { permissions: browse }
        role Layer2 inherits Layer1 { permissions: write }
        assign Root to eve
    """)
    warns = run_security_checks(ast)
    print_security_issues("Security issues for layered escalation:", warns)
    escalation_warnings = [w for w in warns if "Privilege Escalation" in w]
    assert len(escalation_warnings) == 1
    assert "Layer1" in escalation_warnings[0]
    assert "eve" not in escalation_warnings[0]

if __name__ == "__main__":
    test_security()
