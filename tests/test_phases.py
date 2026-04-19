import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lexer import RBACLexer
from src.parser import RBACParser
from src.semantic import analyze_program
from src.security import run_security_checks


def read_test_case():
    return """
role Viewer {
    permissions: read
}
role Editor inherits Viewer {
    permissions: write
}
assign Editor to Alice
"""


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


def serialize_ast(node):
    if isinstance(node, list):
        return [serialize_ast(item) for item in node]
    if hasattr(node, "__dict__"):
        data = {"type": type(node).__name__}
        for key, value in vars(node).items():
            data[key] = serialize_ast(value)
        return data
    return node


def print_semantic_errors(title, errors):
    print(title)
    if errors:
        for error in errors:
            print(f"  - {error}")
    else:
        print("  - No semantic errors")


def print_security_issues(title, warnings):
    print(title)
    if warnings:
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("  - No security issues")


def test_phases():
    data = read_test_case()

    lexer = RBACLexer()
    lexer.build()
    tokens = lexer.tokenize(data)
    print("Lexer tokens for valid_policy.rbac:")
    print(format_tokens(tokens))

    parser = RBACParser()
    parser.build()
    ast = parser.parse(data, lexer.lexer)
    print("Parser AST for valid_policy.rbac:")
    print(json.dumps(serialize_ast(ast), indent=2))

    semantic_errors = analyze_program(ast)
    print_semantic_errors("Semantic errors for valid_policy.rbac:", semantic_errors)

    security_warnings = run_security_checks(ast)
    print_security_issues("Security issues for valid_policy.rbac:", security_warnings)

    assert tokens
    assert ast is not None


if __name__ == "__main__":
    test_phases()
