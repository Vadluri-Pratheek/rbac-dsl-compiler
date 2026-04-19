import re
from flask import Flask, request, jsonify, render_template

from src.lexer import RBACLexer
from src.parser import RBACParser, RoleNode, AssignmentNode, ConflictNode
from src.semantic import analyze_program, get_structured_errors
from src.security import run_security_checks, get_structured_warnings
from src.fixer import apply_fixes

app = Flask(__name__)

def _build_lexer_parser():
    lexer = RBACLexer()
    lexer.build()
    parser = RBACParser()
    parser.build()
    return lexer, parser

def _collect_tokens(code):
    lexer = RBACLexer()
    lexer.build()
    lexer.lexer.input(code)
    tokens = []
    while True:
        tok = lexer.lexer.token()
        if not tok:
            break
        tokens.append({"type": tok.type, "value": tok.value, "line": tok.lineno})
    return tokens

def _partition_ast(ast):
    roles = {}
    assigns = []
    conflicts = []
    for node in ast.roles:
        if isinstance(node, RoleNode):
            if node.name not in roles:
                roles[node.name] = node
        elif isinstance(node, AssignmentNode):
            assigns.append(node)
        elif isinstance(node, ConflictNode):
            conflicts.append(node)
    return roles, assigns, conflicts

def analyze_source_code(code):
    lexer, parser = _build_lexer_parser()
    ast = parser.parse(code, lexer.lexer)
    tokens = _collect_tokens(code)

    errors = []

    if lexer.errors:
        for e in lexer.errors:
            m = re.search(r"Line (\d+)", e)
            errors.append({"line": int(m.group(1)) if m else 0, "message": e, "category": "error"})

    if parser.errors:
        for e in parser.errors:
            m = re.search(r"line (\d+)", e)
            errors.append({"line": int(m.group(1)) if m else 0, "message": e, "category": "error"})

    if errors:
        return {
            "success": False,
            "tokens": tokens,
            "ast": {},
            "symbol_table": {},
            "graph": {"nodes": [], "edges": []},
            "errors": errors,
            "warnings": [],
            "risks": [],
            "summary": {
                "roles": 0, "permissions": 0,
                "errors": len(errors), "warnings": 0, "risks": 0,
                "verdict": "UNSAFE", "verdict_color": "red"
            }
        }

    roles, assigns, conflicts = _partition_ast(ast)

    analyze_program(ast)
    sem_errors = get_structured_errors(ast)

    run_security_checks(ast)
    sec_warnings = get_structured_warnings(ast)

    for err in sem_errors:
        errors.append({"line": err["line"], "message": err["message"], "category": "error"})

    warnings = []
    risks = []
    for warn in sec_warnings:
        if "escalation" in warn["issue_type"] or "conflict" in warn["issue_type"]:
            risks.append({"line": warn["line"], "message": warn["desc"], "category": "risk"})
        else:
            warnings.append({"line": warn["line"], "message": warn["desc"], "category": "warning"})

    symbol_table = {}
    for name, r in roles.items():
        symbol_table[name] = {
            "permissions": list(r.permissions) if r.permissions else [],
            "inherits": r.inherits,
        }

    graph_nodes = []
    graph_edges = []
    for name, r in roles.items():
        graph_nodes.append({"id": name, "color": "normal"})
        if r.inherits:
            graph_edges.append({"from": r.inherits, "to": name, "type": "inherits"})
    for c in conflicts:
        graph_edges.append({"from": c.role1, "to": c.role2, "type": "conflict"})

    ast_dump = {
        "roles": list(roles.keys()),
        "assignments": [f"{a.role} -> {a.user}" for a in assigns],
        "conflicts": [f"{c.role1} <-> {c.role2}" for c in conflicts],
    }

    total_perms = len(set(p for r in roles.values() for p in (r.permissions or [])))
    if errors or risks:
        verdict, verdict_color = "UNSAFE", "red"
    elif warnings:
        verdict, verdict_color = "WARNINGS", "orange"
    else:
        verdict, verdict_color = "SAFE", "green"

    return {
        "success": True,
        "tokens": tokens,
        "ast": ast_dump,
        "symbol_table": symbol_table,
        "graph": {"nodes": graph_nodes, "edges": graph_edges},
        "errors": errors,
        "warnings": warnings,
        "risks": risks,
        "summary": {
            "roles": len(roles),
            "permissions": total_perms,
            "errors": len(errors),
            "warnings": len(warnings),
            "risks": len(risks),
            "verdict": verdict,
            "verdict_color": verdict_color,
        }
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze_endpoint():
    code = (request.json or {}).get("code", "")
    try:
        result = analyze_source_code(code)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "errors": [{"line": 0, "message": str(e), "category": "error"}],
                        "warnings": [], "risks": [], "tokens": [], "ast": {}, "symbol_table": {},
                        "graph": {"nodes": [], "edges": []},
                        "summary": {"roles": 0, "permissions": 0, "errors": 1, "warnings": 0,
                                    "risks": 0, "verdict": "UNSAFE", "verdict_color": "red"}}), 200

@app.route("/fix", methods=["POST"])
def fix_endpoint():
    code = (request.json or {}).get("code", "")
    try:
        lexer, parser = _build_lexer_parser()
        ast = parser.parse(code, lexer.lexer)
        if not ast:
            return jsonify({"success": False, "error": "Could not parse code."})

        analyze_program(ast)
        run_security_checks(ast)
        all_issues = get_structured_errors(ast) + get_structured_warnings(ast)
        fixed_source, changelog = apply_fixes(code, all_issues)
        return jsonify({"success": True, "fixed_code": fixed_source, "changelog": changelog})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
