import re

_T_REDUNDANT_PERM_LOCAL = "REDUNDANT_PERM_LOCAL"
_T_NO_PERMISSIONS       = "NO_PERMISSIONS"
_T_PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"

from src.parser import RoleNode, AssignmentNode

DANGEROUS_PERMISSION_TOKENS = {
    "assign",
    "elevate",
    "escalate",
    "everything",
    "grant",
    "impersonate",
    "owner",
    "promote",
    "root",
    "sudo",
    "superuser",
}

DANGEROUS_PERMISSION_PHRASES = {
    "all_access",
    "full_access",
    "manage_roles",
}

HIGH_PRIVILEGE_ROLE_MARKERS = (
    "admin",
    "owner",
    "root",
    "superuser",
)

def build_tables(ast):
    roles_map = {}
    assigns = []
    for node in ast.roles:
        if isinstance(node, RoleNode):
            roles_map[node.name] = node
        elif isinstance(node, AssignmentNode):
            assigns.append(node)
    return roles_map, assigns

def find_cyclic_roles(roles_map):
    cyclic_roles = set()
    state = {}
    path = []

    def visit(role_name):
        if role_name not in roles_map:
            return

        current_state = state.get(role_name, 0)
        if current_state == 1:
            if role_name in path:
                loop_start = path.index(role_name)
                cyclic_roles.update(path[loop_start:])
            return
        if current_state == 2:
            return

        state[role_name] = 1
        path.append(role_name)

        parent = roles_map[role_name].inherits
        if parent in roles_map:
            visit(parent)

        path.pop()
        state[role_name] = 2

    for role_name in roles_map:
        visit(role_name)

    return cyclic_roles

def get_effective_roles(role_name, roles_map, seen=None):
    if seen is None:
        seen = set()

    if role_name in seen:
        return set()

    seen.add(role_name)
    effective = set()
    effective.add(role_name)
    node = roles_map.get(role_name)
    if node is not None and node.inherits is not None:
        inherited_roles = get_effective_roles(node.inherits, roles_map, seen)
        for r in inherited_roles:
            effective.add(r)
    return effective

def get_effective_permissions(role_name, roles_map, cyclic_roles=None, seen=None):
    if cyclic_roles is None:
        cyclic_roles = set()
    if seen is None:
        seen = set()

    if role_name in seen or role_name in cyclic_roles:
        return set()

    seen.add(role_name)

    role_obj = roles_map.get(role_name)
    if role_obj is None:
        return set()

    permissions = set(role_obj.permissions or [])
    if role_obj.inherits is not None:
        permissions.update(get_effective_permissions(role_obj.inherits, roles_map, cyclic_roles, seen))

    return permissions

def enforce_least_privilege(roles_map, cyclic_roles=None):
    if cyclic_roles is None:
        cyclic_roles = set()

    results  = []
    reported = set()

    for role_name, role_obj in roles_map.items():
        if role_name in cyclic_roles:
            continue

        if role_obj.permissions:
            seen_local = set()
            for p in role_obj.permissions:
                if p in seen_local:
                    msg = f"[Line {role_obj.line}] Redundant permission '{p}' in role '{role_name}'"
                    if msg not in reported:
                        results.append(msg)
                        reported.add(msg)
                else:
                    seen_local.add(p)

        effective_permissions = get_effective_permissions(role_name, roles_map, cyclic_roles)
        if not effective_permissions:
            line_no = role_obj.line if hasattr(role_obj, "line") else "?"
            msg = f"[Line {line_no}] Least privilege warning: Role '{role_name}' has no effective permissions"
            if msg not in reported:
                results.append(msg)
                reported.add(msg)

    return results

def enforce_least_privilege_structured(roles_map, cyclic_roles=None):
    if cyclic_roles is None:
        cyclic_roles = set()

    results  = []
    reported = set()

    for role_name, role_obj in roles_map.items():
        if role_name in cyclic_roles:
            continue

        if role_obj.permissions:
            seen_local = set()
            for p in role_obj.permissions:
                if p in seen_local:
                    key = (role_name, p)
                    if key not in reported:
                        reported.add(key)
                        results.append({
                            "type": _T_REDUNDANT_PERM_LOCAL,
                            "line": role_obj.line,
                            "message": f"[Line {role_obj.line}] Redundant permission '{p}' in role '{role_name}'",
                            "meta":  {"role": role_name, "perm": p},
                        })
                else:
                    seen_local.add(p)

        effective_permissions = get_effective_permissions(role_name, roles_map, cyclic_roles)
        if not effective_permissions:
            line_no = role_obj.line if hasattr(role_obj, "line") else None
            key = ("NO_PERM", role_name)
            if key not in reported:
                reported.add(key)
                results.append({
                    "type": _T_NO_PERMISSIONS,
                    "line": line_no,
                    "message": f"[Line {line_no}] Least privilege warning: Role '{role_name}' has no effective permissions",
                    "meta":  {"role": role_name},
                })

    return results

def run_security_checks(ast) -> list:
    if ast is None:
        return []

    roles_map, _ = build_tables(ast)
    cyclic_roles  = find_cyclic_roles(roles_map)

    report = []
    report.extend(enforce_least_privilege(roles_map, cyclic_roles))
    report.extend(detect_privilege_escalation(roles_map, cyclic_roles))

    unique_report = []
    seen = set()
    for msg in report:
        if msg not in seen:
            unique_report.append(msg)
            seen.add(msg)

    return unique_report

def get_structured_warnings(ast) -> list:
    if ast is None:
        return []

    roles_map, _ = build_tables(ast)
    cyclic_roles  = find_cyclic_roles(roles_map)

    structured = []
    structured.extend(enforce_least_privilege_structured(roles_map, cyclic_roles))
    structured.extend(detect_privilege_escalation_structured(roles_map, cyclic_roles))

    seen     = set()
    deduped  = []
    for item in structured:
        key = (item["type"], item["line"], str(item["meta"]))
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped

def is_high_privilege_role_name(role_name):
    lowered_name = role_name.lower()
    return any(marker in lowered_name for marker in HIGH_PRIVILEGE_ROLE_MARKERS)

def has_dangerous_permission(perms):
    for permission in perms:
        lowered = permission.lower()
        tokens = {token for token in re.split(r"[^a-z0-9]+", lowered) if token}

        if tokens.intersection(DANGEROUS_PERMISSION_TOKENS):
            return True
        if any(phrase in lowered for phrase in DANGEROUS_PERMISSION_PHRASES):
            return True

    return False

def detect_privilege_escalation(roles_map, cyclic_roles=None):
    if cyclic_roles is None:
        cyclic_roles = set()

    results  = []
    reported = set()

    role_to_permissions = {}
    for role_name, node in roles_map.items():
        perms = set()
        if node.permissions:
            for p in node.permissions:
                perms.add(p.lower())
        role_to_permissions[role_name] = perms

    high_privilege_roles = {
        role_name
        for role_name, perms in role_to_permissions.items()
        if role_name not in cyclic_roles and (
            has_dangerous_permission(perms) or is_high_privilege_role_name(role_name)
        )
    }

    for role_name, node in roles_map.items():
        if role_name in cyclic_roles or not node.inherits:
            continue

        parent_role = node.inherits
        if parent_role in cyclic_roles or parent_role not in high_privilege_roles:
            continue

        line_no = node.line if hasattr(node, "line") else "?"
        msg = f"[Line {line_no}] Privilege Escalation: '{role_name}' inherits high-privilege role '{parent_role}'"
        if msg not in reported:
            results.append(msg)
            reported.add(msg)

    return results

def detect_privilege_escalation_structured(roles_map, cyclic_roles=None):
    if cyclic_roles is None:
        cyclic_roles = set()

    results  = []
    reported = set()

    role_to_permissions = {}
    for role_name, node in roles_map.items():
        perms = set()
        if node.permissions:
            for p in node.permissions:
                perms.add(p.lower())
        role_to_permissions[role_name] = perms

    high_privilege_roles = {
        role_name
        for role_name, perms in role_to_permissions.items()
        if role_name not in cyclic_roles and (
            has_dangerous_permission(perms) or is_high_privilege_role_name(role_name)
        )
    }

    for role_name, node in roles_map.items():
        if role_name in cyclic_roles or not node.inherits:
            continue

        parent_role = node.inherits
        if parent_role in cyclic_roles or parent_role not in high_privilege_roles:
            continue

        line_no = node.line if hasattr(node, "line") else None
        key = (role_name, parent_role)
        if key not in reported:
            reported.add(key)
            results.append({
                "type": _T_PRIVILEGE_ESCALATION,
                "line": line_no,
                "message": f"[Line {line_no}] Privilege Escalation: '{role_name}' inherits high-privilege role '{parent_role}'",
                "meta":  {"role": role_name, "parent": parent_role},
            })

    return results
