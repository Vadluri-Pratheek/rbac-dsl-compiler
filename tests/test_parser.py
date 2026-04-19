import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lexer import RBACLexer
from src.parser import RBACParser, RoleNode, AssignmentNode


def serialize_ast(node):
    if isinstance(node, list):
        return [serialize_ast(item) for item in node]
    if hasattr(node, "__dict__"):
        data = {"type": type(node).__name__}
        for key, value in vars(node).items():
            data[key] = serialize_ast(value)
        return data
    return node


def test_parser():
    l = RBACLexer()
    l.build()
    p = RBACParser()
    p.build()

    ast = p.parse("role User { permissions: read }", l.lexer)
    print("AST for role definition:")
    print(json.dumps(serialize_ast(ast), indent=2))
    assert len(ast.roles) == 1
    assert isinstance(ast.roles[0], RoleNode)
    assert ast.roles[0].name == "User"

    ast = p.parse("assign Admin to alice", l.lexer)
    print("AST for assignment:")
    print(json.dumps(serialize_ast(ast), indent=2))
    assert isinstance(ast.roles[0], AssignmentNode)
    assert ast.roles[0].user == "alice"

if __name__ == "__main__":
    test_parser()
