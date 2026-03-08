from src.parser import RoleNode, AssignmentNode, ConflictNode

class SemanticAnalyzer:
    def __init__(self, ast):
        self.ast = ast
        self.roles = {}
        self.errors = []
        
        for node in self.ast.roles:
            if isinstance(node, RoleNode):
                self.roles[node.name] = node

    def run_checks(self):
        visited = set()
        stack = set()
        
        def check_cycle(role_name):
            if role_name in stack:
                self.errors.append(f"Inheritance loop found in role '{role_name}'")
                return True
                
            if role_name in visited:
                return False
                
            visited.add(role_name)
            stack.add(role_name)
            
            role_obj = self.roles.get(role_name)
            if role_obj and role_obj.inherits is not None:
                parent = role_obj.inherits
                if parent not in self.roles:
                    self.errors.append(f"Role '{role_name}' inherits from undefined '{parent}'")
                else:
                    check_cycle(parent)
                    
            stack.remove(role_name)
            return False

        for role_name in self.roles:
            check_cycle(role_name)

        assigns = []
        conflicts = []
        
        for node in self.ast.roles:
            if isinstance(node, AssignmentNode):
                assigns.append(node)
            elif isinstance(node, ConflictNode):
                conflicts.append(node)

        seen_assignments = set()
        for a in assigns:
            if a.role not in self.roles:
                self.errors.append(f"Can't assign unknown role '{a.role}' to {a.user}")
            else:
                key = (a.role, a.user)
                if key in seen_assignments:
                    self.errors.append(f"Redundant assignment of role '{a.role}' to user '{a.user}'")
                else:
                    seen_assignments.add(key)

        for c in conflicts:
            if c.role1 not in self.roles:
                self.errors.append(f"Conflict rule for unknown role: {c.role1}")
            if c.role2 not in self.roles:
                self.errors.append(f"Conflict rule for unknown role: {c.role2}")

        return self.errors

def analyze_program(ast):
    analyzer = SemanticAnalyzer(ast)
    errors = analyzer.run_checks()
    return errors
