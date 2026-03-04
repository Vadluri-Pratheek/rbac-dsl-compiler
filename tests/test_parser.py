import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lexer import RBACLexer
from src.parser import RBACParser, RoleNode, AssignmentNode

def test_parser():
    l = RBACLexer()
    l.build()
    p = RBACParser()
    p.build()
    
    print("Testing basic role parsing...")
    ast = p.parse("role User { permissions: read }", l.lexer)
    assert len(ast.roles) == 1
    assert isinstance(ast.roles[0], RoleNode)
    assert ast.roles[0].name == "User"
    
    print("Testing user assignments...")
    ast = p.parse("assign Admin to alice", l.lexer)
    assert isinstance(ast.roles[0], AssignmentNode)
    assert ast.roles[0].user == "alice"
    
    print("Parser tests passed.")

if __name__ == "__main__":
    test_parser()
