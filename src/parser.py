import ply.yacc as yacc
from src.lexer import tokens

class ProgramNode:
    def __init__(self, roles):
        self.roles = roles

class RoleNode:
    def __init__(self, name, permissions, inherits=None, line=None):
        self.name = name
        self.permissions = permissions
        self.inherits = inherits
        self.line = line

class AssignmentNode:
    def __init__(self, role, user, line=None):
        self.role = role
        self.user = user
        self.line = line

class ConflictNode:
    def __init__(self, role1, role2, line=None):
        self.role1 = role1
        self.role2 = role2
        self.line = line

class RBACParser:
    tokens = tokens

    def __init__(self):
        self.parser = None
        self.errors = []

    def p_program(self, p):
        '''program : statements'''
        p[0] = ProgramNode(p[1])

    def p_statements_multiple(self, p):
        '''statements : statements statement'''
        statement_list = p[1]
        new_statement = p[2]
        statement_list.append(new_statement)
        p[0] = statement_list

    def p_statements_single(self, p):
        '''statements : statement'''
        first_statement = p[1]
        p[0] = [first_statement]

    def p_statement(self, p):
        '''statement : role_def
                     | assignment
                     | conflict_def'''
        p[0] = p[1]

    def p_role_def_base(self, p):
        '''role_def : ROLE IDENTIFIER LBRACE PERMISSIONS COLON perm_list RBRACE'''
        role_name = p[2]
        permissions = p[6]
        line_num = p.lineno(1)
        p[0] = RoleNode(role_name, permissions, inherits=None, line=line_num)

    def p_role_def_inherits(self, p):
        '''role_def : ROLE IDENTIFIER INHERITS IDENTIFIER LBRACE PERMISSIONS COLON perm_list RBRACE'''
        role_name = p[2]
        inherited_role = p[4]
        permissions = p[8]
        line_num = p.lineno(1)
        p[0] = RoleNode(role_name, permissions, inherits=inherited_role, line=line_num)

    def p_perm_list_multiple(self, p):
        '''perm_list : perm_list COMMA IDENTIFIER'''
        perm_list = p[1]
        new_perm = p[3]
        perm_list.append(new_perm)
        p[0] = perm_list

    def p_perm_list_single(self, p):
        '''perm_list : IDENTIFIER'''
        first_perm = p[1]
        p[0] = [first_perm]

    def p_assignment(self, p):
        '''assignment : ASSIGN IDENTIFIER TO IDENTIFIER'''
        role_name = p[2]
        user_name = p[4]
        line_num = p.lineno(1)
        p[0] = AssignmentNode(role_name, user_name, line=line_num)

    def p_conflict_def(self, p):
        '''conflict_def : CONFLICT IDENTIFIER COMMA IDENTIFIER'''
        role1_name = p[2]
        role2_name = p[4]
        line_num = p.lineno(1)
        p[0] = ConflictNode(role1_name, role2_name, line=line_num)

    def p_error(self, p):
        if p is not None:
            msg = f"Syntax error: '{p.value}' (line {p.lineno})"
        else:
            msg = "Unexpected end of file"
        self.errors.append(msg)
        print(f"[!] Parser: {msg}")

    def build(self):
        self.parser = yacc.yacc(module=self, write_tables=False, debug=False)
        return self.parser

    def parse(self, data, lexer):
        self.errors = []
        result = self.parser.parse(data, lexer=lexer)
        return result
