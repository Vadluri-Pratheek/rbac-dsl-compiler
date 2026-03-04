from src.parser import RoleNode, AssignmentNode, ConflictNode

class SemanticAnalyzer:
    def __init__(self, ast):
        self.ast = ast
        self.roles = {n.name: n for n in ast.roles if isinstance(n, RoleNode)}
        self.errors = []

    def check_cycle(self, name, path=None):
        path = path or []
        node = self.roles.get(name)
        if not node or not node.inherits: return False
        if node.inherits in path: return True
        return self.check_cycle(node.inherits, path + [name])

    def run_checks(self):
        # 1. Undefined roles & cycles
        for name, node in self.roles.items():
            if node.inherits and node.inherits not in self.roles:
                self.errors.append(f"Role '{name}' inherits from undefined '{node.inherits}'")
            elif self.check_cycle(name):
                self.errors.append(f"Inheritance loop found in role '{name}'")

        # 2. Assign & Conflict basics
        assigns = [n for n in self.ast.roles if isinstance(n, AssignmentNode)]
        conflicts = [n for n in self.ast.roles if isinstance(n, ConflictNode)]

        for a in assigns:
            if a.role not in self.roles:
                self.errors.append(f"Can't assign unknown role '{a.role}' to {a.user}")

        for c in conflicts:
            if c.role1 not in self.roles: self.errors.append(f"Conflict rule for unknown role: {c.role1}")
            if c.role2 not in self.roles: self.errors.append(f"Conflict rule for unknown role: {c.role2}")

        return self.errors

def analyze_program(ast):
    analyzer = SemanticAnalyzer(ast)
    return analyzer.run_checks()
