from src.parser import RoleNode, AssignmentNode, ConflictNode

def build_tables(ast):
    roles_map = {}
    assigns = []
    conflicts = []
    
    for node in ast.roles:
        if isinstance(node, RoleNode):
            roles_map[node.name] = node
        elif isinstance(node, AssignmentNode):
            assigns.append(node)
        elif isinstance(node, ConflictNode):
            conflicts.append(node)
            
    return roles_map, assigns, conflicts

def get_effective_roles(role_name, roles_map):
    effective = set()
    effective.add(role_name)
    
    node = roles_map.get(role_name)
    if node is not None and node.inherits is not None:
        inherited_roles = get_effective_roles(node.inherits, roles_map)
        for r in inherited_roles:
            effective.add(r)
            
    return effective

def detect_role_conflicts(roles_map, assigns, conflicts):
    results = []
    
    user_roles = {}
    for a in assigns:
        user_name = a.user
        role_name = a.role
        
        if role_name in roles_map:
            if user_name not in user_roles:
                user_roles[user_name] = set()
            
            effective_roles = get_effective_roles(role_name, roles_map)
            for r in effective_roles:
                user_roles[user_name].add(r)
                
    for c in conflicts:
        role1 = c.role1
        role2 = c.role2
        
        for user, roles in user_roles.items():
            if role1 in roles and role2 in roles:
                results.append(
                    f"[SECURITY WARNING] User '{user}' has mutually exclusive roles '{role1}' and '{role2}'"
                )
                
    return results

def detect_redundant_permissions(roles_map):
    results = []
    
    for role_name, node in roles_map.items():
        if node.inherits is not None and node.inherits in roles_map:
            
            parent_perms = set()
            curr = node.inherits
            
            while curr in roles_map:
                curr_node = roles_map[curr]
                if curr_node.permissions is not None:
                    for p in curr_node.permissions:
                        parent_perms.add(p)
                curr = curr_node.inherits
                
            if node.permissions is not None:
                for perm in node.permissions:
                    if perm in parent_perms:
                        results.append(
                            f"[REDUNDANCY] Role '{role_name}' redundantly defines inherited permission '{perm}'"
                        )
                        
    return results

def enforce_least_privilege(roles_map, assigns):
    results = []
    
    for role_name, role_obj in roles_map.items():
        if not role_obj.permissions and not role_obj.inherits:
            results.append(
                f"[LEAST PRIVILEGE] Role '{role_name}' has no effective permissions"
            )

    for a in assigns:
        if a.role not in roles_map:
             results.append(
                 f"[LEAST PRIVILEGE] User '{a.user}' assigned undefined role '{a.role}'"
             )
             
    return results

def run_security_checks(ast):
    report = []
    
    roles_map, assigns, conflicts = build_tables(ast)
    
    report.extend(detect_role_conflicts(roles_map, assigns, conflicts))
    report.extend(detect_redundant_permissions(roles_map))
    report.extend(enforce_least_privilege(roles_map, assigns))
    
    return report
