from src.parser import RoleNode, AssignmentNode, ConflictNode

def get_effective_roles(role_name, roles_map):
    """Recursively get all roles including inherited ones."""
    effective = {role_name}
    node = roles_map.get(role_name)
    if node and node.inherits:
        effective |= get_effective_roles(node.inherits, roles_map)
    return effective

def run_security_checks(ast):
    """Scan for conflict rule violations and redundant permissions."""
    roles_map = {n.name: n for n in ast.roles if isinstance(n, RoleNode)}
    assigns = [n for n in ast.roles if isinstance(n, AssignmentNode)]
    conflicts = [n for n in ast.roles if isinstance(n, ConflictNode)]
    
    warnings = []
    
    # 1. User Conflict Detection
    user_roles = {}
    for a in assigns:
        if a.role in roles_map:
            user_roles.setdefault(a.user, set()).update(get_effective_roles(a.role, roles_map))
            
    for c in conflicts:
        for user, roles in user_roles.items():
            if c.role1 in roles and c.role2 in roles:
                warnings.append(f"Security: User '{user}' has both {c.role1} and {c.role2} (conflict!)")
                
    # 2. Redundancy Check
    for name, node in roles_map.items():
        if node.inherits and node.inherits in roles_map:
            parent_perms = set()
            curr = node.inherits
            while curr in roles_map:
                parent_perms |= set(roles_map[curr].permissions)
                curr = roles_map[curr].inherits
            
            redundant = set(node.permissions) & parent_perms
            if redundant:
                warnings.append(f"Note: Role '{name}' redundantly defines {list(redundant)} (already in parent)")
                
    return warnings
