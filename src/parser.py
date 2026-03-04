import ply.yacc as yacc
from src.lexer import tokens

class ProgramNode:
    def __init__(self, roles): self.roles = roles
    def __repr__(self):
        lines = ["Program Node:"]
        for i, role in enumerate(self.roles, start=1):
            lines.append(f"  role{i}:")
            role_lines = str(role).splitlines()
            for line in role_lines:
                lines.append(f"    {line}")
        return "\n".join(lines)

class RoleNode:
    def __init__(self, name, permissions, inherits=None, line=None):
        self.name, self.permissions, self.inherits, self.line = name, permissions, inherits, line
    def __repr__(self):
        lines = [f"name: {self.name}"]
        lines.append(f"inherits: {self.inherits if self.inherits else 'none'}")
        lines.append("permissions:")
        if self.permissions:
            for p in self.permissions:
                lines.append(f"  - {p}")
        else:
            lines.append("  - none")
        return "\n".join(lines)

class AssignmentNode:
    def __init__(self, role, user, line=None):
        self.role, self.user, self.line = role, user, line
    def __repr__(self):
        return f"assignment: role={self.role}, user={self.user}"

class ConflictNode:
    def __init__(self, role1, role2, line=None):
        self.role1, self.role2, self.line = role1, role2, line
    def __repr__(self):
        return f"conflict: {self.role1} vs {self.role2}"

class RBACParser:
    tokens = tokens

    def __init__(self):
        self.parser = None
        self.errors = []

    def p_program(self, p):
        '''program : statements'''
        p[0] = ProgramNode(p[1])

    def p_statements(self, p):
        '''statements : statements statement
                      | statement'''
        p[0] = (p[1] + [p[2]]) if len(p) == 3 else [p[1]]

    def p_statement(self, p):
        '''statement : role_def
                    | assignment
                    | conflict_def'''
        p[0] = p[1]

    def p_role_def(self, p):
        '''role_def : ROLE IDENTIFIER LBRACE PERMISSIONS COLON perm_list RBRACE
                    | ROLE IDENTIFIER INHERITS IDENTIFIER LBRACE PERMISSIONS COLON perm_list RBRACE'''
        if len(p) == 8:
            p[0] = RoleNode(p[2], p[6], line=p.lineno(1))
        else:
            p[0] = RoleNode(p[2], p[8], inherits=p[4], line=p.lineno(1))

    def p_perm_list(self, p):
        '''perm_list : perm_list COMMA IDENTIFIER
                     | IDENTIFIER'''
        p[0] = (p[1] + [p[3]]) if len(p) == 4 else [p[1]]

    def p_assignment(self, p):
        '''assignment : ASSIGN IDENTIFIER TO IDENTIFIER'''
        p[0] = AssignmentNode(p[2], p[4], line=p.lineno(1))

    def p_conflict_def(self, p):
        '''conflict_def : CONFLICT IDENTIFIER COMMA IDENTIFIER'''
        p[0] = ConflictNode(p[2], p[4], line=p.lineno(1))

    def p_error(self, p):
        msg = f"Syntax error: '{p.value}' (line {p.lineno})" if p else "Unexpected end of file"
        self.errors.append(msg)
        print(f"[!] Parser: {msg}")

    def build(self):
        self.parser = yacc.yacc(module=self, write_tables=False, debug=False)
        return self.parser

    def parse(self, data, lexer):
        self.errors = []
        return self.parser.parse(data, lexer=lexer)
