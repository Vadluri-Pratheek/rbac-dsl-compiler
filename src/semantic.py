from src.parser import RoleNode, AssignmentNode, ConflictNode
from src.security import get_effective_roles

_T_DUPLICATE_ROLE        = "DUPLICATE_ROLE"
_T_SELF_INHERIT          = "SELF_INHERIT"
_T_CYCLE_BROKEN          = "CYCLE_BROKEN"
_T_INHERITS_UNDEFINED    = "INHERITS_UNDEFINED"
_T_UNDEFINED_ROLE_ASSIGN = "UNDEFINED_ROLE_ASSIGN"
_T_REDUNDANT_ASSIGN      = "REDUNDANT_ASSIGN"
_T_CONFLICT_UNKNOWN      = "CONFLICT_UNKNOWN_ROLE"
_T_CONFLICT_VIOLATION    = "CONFLICT_VIOLATION"
_T_REDUNDANT_INH_PERM    = "REDUNDANT_INHERITED_PERM"

class SemanticAnalyzer:
    def __init__(self, ast):
        self.ast = ast
        self.roles = {}
        self.errors = []
        self.structured_errors = []
        self.reported_errors = set()
        self.cyclic_roles = set()

        for node in self.ast.roles:
            if isinstance(node, RoleNode):
                if node.name in self.roles:
                    self.report(
                        f"[Line {node.line}] Duplicate role definition: {node.name}",
                        itype   = _T_DUPLICATE_ROLE,
                        line    = node.line,
                        meta    = {"role": node.name},
                    )
                else:
                    self.roles[node.name] = node

    def report(self, message, *, itype=None, line=None, meta=None):
        if message not in self.reported_errors:
            self.errors.append(message)
            self.reported_errors.add(message)
            if itype is not None:
                self.structured_errors.append({
                    "type": itype,
                    "line": line,
                    "message": message,
                    "meta": meta or {},
                })

    def run_checks(self):
        visited = set()

        def check_cycle(role_name, path):
            if role_name in path:
                loop_start  = path.index(role_name)
                cycle_path  = path[loop_start:] + [role_name]
                path_str    = " -> ".join(cycle_path)

                for r in cycle_path[:-1]:
                    self.cyclic_roles.add(r)

                line_no = self.roles[role_name].line if role_name in self.roles else "?"

                if len(cycle_path) == 2:
                    self.report(
                        f"[Line {line_no}] Invalid inheritance: Role '{role_name}' cannot inherit itself",
                        itype = _T_SELF_INHERIT,
                        line  = line_no,
                        meta  = {"role": role_name},
                    )
                else:
                    closing_role = path[-1]
                    fix_line = (
                        self.roles[closing_role].line
                        if closing_role in self.roles else line_no
                    )
                    self.report(
                        f"[Line {line_no}] Inheritance cycle detected: {path_str}",
                        itype = _T_CYCLE_BROKEN,
                        line  = fix_line,
                        meta  = {
                            "role":       closing_role,
                            "parent":     role_name,
                            "cycle_path": path_str,
                        },
                    )
                return True

            if role_name in visited:
                return False

            visited.add(role_name)
            role_obj = self.roles.get(role_name)
            if role_obj and role_obj.inherits is not None:
                parent = role_obj.inherits
                if parent not in self.roles:
                    self.report(
                        f"[Line {role_obj.line}] Role '{role_name}' inherits from undefined '{parent}'",
                        itype = _T_INHERITS_UNDEFINED,
                        line  = role_obj.line,
                        meta  = {"role": role_name, "parent": parent},
                    )
                else:
                    check_cycle(parent, path + [role_name])
            return False

        for role_name in list(self.roles.keys()):
            check_cycle(role_name, [])

        assigns   = []
        conflicts = []

        for node in self.ast.roles:
            if isinstance(node, AssignmentNode):
                assigns.append(node)
            elif isinstance(node, ConflictNode):
                conflicts.append(node)

        seen_assignments = set()
        for a in assigns:
            line_no = a.line if hasattr(a, "line") else "?"
            if a.role not in self.roles:
                self.report(
                    f"[Line {line_no}] Undefined role: {a.role} assigned to {a.user}",
                    itype = _T_UNDEFINED_ROLE_ASSIGN,
                    line  = line_no,
                    meta  = {"role": a.role, "user": a.user},
                )
            else:
                key = (a.role, a.user)
                if key in seen_assignments:
                    self.report(
                        f"[Line {line_no}] Redundant role assignment: {a.role} to {a.user}",
                        itype = _T_REDUNDANT_ASSIGN,
                        line  = line_no,
                        meta  = {"role": a.role, "user": a.user},
                    )
                else:
                    seen_assignments.add(key)

        for c in conflicts:
            line_no = c.line if hasattr(c, "line") else "?"
            if c.role1 not in self.roles:
                self.report(
                    f"[Line {line_no}] Conflict rule for unknown role: {c.role1}",
                    itype = _T_CONFLICT_UNKNOWN,
                    line  = line_no,
                    meta  = {"unknown_role": c.role1},
                )
            if c.role2 not in self.roles:
                self.report(
                    f"[Line {line_no}] Conflict rule for unknown role: {c.role2}",
                    itype = _T_CONFLICT_UNKNOWN,
                    line  = line_no,
                    meta  = {"unknown_role": c.role2},
                )

        user_roles = {}
        for a in assigns:
            if a.role in self.roles and a.role not in self.cyclic_roles:
                user_roles.setdefault(a.user, set()).update(
                    get_effective_roles(a.role, self.roles)
                )

        reported_conflicts = set()
        for c in conflicts:
            if c.role1 in self.roles and c.role2 in self.roles:
                if c.role1 in self.cyclic_roles or c.role2 in self.cyclic_roles:
                    continue
                for user, roles in user_roles.items():
                    if c.role1 in roles and c.role2 in roles:
                        conflict_key = (user, tuple(sorted((c.role1, c.role2))))
                        if conflict_key in reported_conflicts:
                            continue
                        reported_conflicts.add(conflict_key)
                        line_no = c.line if hasattr(c, "line") else "?"
                        self.report(
                            f"[Line {line_no}] Conflict: User '{user}' has both '{c.role1}' and '{c.role2}'",
                            itype = _T_CONFLICT_VIOLATION,
                            line  = line_no,
                            meta  = {"user": user, "role1": c.role1, "role2": c.role2},
                        )

        for role_name, node in self.roles.items():
            if role_name in self.cyclic_roles:
                continue
            if node.inherits is not None and node.inherits in self.roles:
                parent_perms  = set()
                curr          = node.inherits
                visited_path  = set()

                while (
                    curr in self.roles
                    and curr not in visited_path
                    and curr not in self.cyclic_roles
                ):
                    visited_path.add(curr)
                    curr_node = self.roles[curr]
                    if curr_node.permissions is not None:
                        for p in curr_node.permissions:
                            parent_perms.add(p)
                    curr = curr_node.inherits

                if node.permissions is not None:
                    seen_redundant = set()
                    for perm in node.permissions:
                        if perm in parent_perms and perm not in seen_redundant:
                            seen_redundant.add(perm)
                            line_no = node.line if hasattr(node, "line") else "?"
                            self.report(
                                f"[Line {line_no}] Redundant inherited permission '{perm}' in role '{role_name}'",
                                itype = _T_REDUNDANT_INH_PERM,
                                line  = line_no,
                                meta  = {"role": role_name, "perm": perm, "parent": node.inherits},
                            )

        return self.errors

def analyze_program(ast) -> list:
    analyzer = SemanticAnalyzer(ast)
    analyzer.run_checks()
    return analyzer.errors

def get_structured_errors(ast) -> list:
    analyzer = SemanticAnalyzer(ast)
    analyzer.run_checks()
    return analyzer.structured_errors
