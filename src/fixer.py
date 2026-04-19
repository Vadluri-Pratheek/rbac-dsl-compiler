import re
from typing import List, Dict, Any, Tuple

SAFE        = "SAFE"
HEURISTIC   = "HEURISTIC"
DESTRUCTIVE = "DESTRUCTIVE"

_SEVERITY_LABEL = {
    SAFE:        "[SAFE       ]",
    HEURISTIC:   "[HEURISTIC  ]",
    DESTRUCTIVE: "[DESTRUCTIVE]",
}

def _blank_line(lines: List[str], lineno: int, tag: str) -> None:
    original = lines[lineno - 1].rstrip("\n\r")
    lines[lineno - 1] = f"# [FIXED-{tag}] was: {original}\n"

def _blank_block(lines: List[str], start: int, end: int, tag: str) -> None:
    for i in range(start, end + 1):
        original = lines[i - 1].rstrip("\n\r")
        if i == start:
            lines[i - 1] = f"# [FIXED-{tag}] (block start) was: {original}\n"
        else:
            lines[i - 1] = f"# [FIXED-{tag}] (block cont.) was: {original}\n"

def _remove_inherits_clause(lines: List[str], lineno: int) -> Tuple[str, str]:
    original = lines[lineno - 1]
    fixed = re.sub(r"\s+inherits\s+\w+", "", original)
    lines[lineno - 1] = fixed
    return original.rstrip(), fixed.rstrip()

def _remove_perm_token(lines: List[str], lineno: int, perm: str) -> Tuple[str, str]:
    original = lines[lineno - 1]
    escaped  = re.escape(perm)

    fixed = re.sub(r",\s*\b" + escaped + r"\b", "", original)
    if fixed == original:
        fixed = re.sub(r"\b" + escaped + r"\b\s*,\s*", "", original)
    if fixed == original:
        fixed = re.sub(r"\b" + escaped + r"\b", "", original)

    fixed = re.sub(r",\s*,", ",", fixed)
    fixed = re.sub(r",\s*([;}])", r"\1", fixed)
    fixed = re.sub(r"(permissions\s*:)\s*;", r"\1 # (no permissions remain)", fixed)
    fixed = re.sub(r",\s*$", "\n", fixed)

    lines[lineno - 1] = fixed
    return original.rstrip(), fixed.rstrip()

def _insert_comment_above(lines: List[str], lineno: int, comment: str) -> None:
    indent = re.match(r"^(\s*)", lines[lineno - 1]).group(1)
    lines.insert(lineno - 1, f"{indent}# [HEURISTIC-REVIEW] {comment}\n")

def _find_role_block(lines: List[str], start_line: int) -> Tuple[int, int]:
    depth = 0
    for i in range(start_line - 1, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if depth == 0 and i >= start_line - 1:
            return start_line, i + 1
    return start_line, start_line

def _find_perms_line(lines: List[str], role_start: int) -> int:
    _, block_end = _find_role_block(lines, role_start)
    for i in range(role_start - 1, block_end):
        if re.search(r"\bpermissions\s*:", lines[i]):
            return i + 1
    return role_start

def apply_fixes(
    source: str,
    structured_issues: List[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    lines: List[str] = source.splitlines(keepends=True)
    lines = [ln if ln.endswith("\n") else ln + "\n" for ln in lines]

    changelog: List[Dict[str, Any]] = []

    edits: List[Dict[str, Any]] = []

    for issue in structured_issues:
        itype = issue.get("type", "")
        line  = issue.get("line")
        meta  = issue.get("meta", {})

        if itype == "DUPLICATE_ROLE":
            edits.append(dict(
                orig_line   = line,
                severity    = SAFE,
                action      = "remove_block",
                fix_type    = "DUPLICATE_ROLE_REMOVED",
                description = (
                    f"Removed duplicate definition of role '{meta.get('role', '?')}' "
                    f"(keeping first definition)."
                ),
                meta = meta,
            ))

        elif itype == "REDUNDANT_ASSIGN":
            edits.append(dict(
                orig_line   = line,
                severity    = SAFE,
                action      = "remove_line",
                fix_type    = "REDUNDANT_ASSIGN_REMOVED",
                description = (
                    f"Removed duplicate assignment: role '{meta.get('role', '?')}' "
                    f"-> user '{meta.get('user', '?')}' (already assigned earlier)."
                ),
                meta = meta,
            ))

        elif itype == "REDUNDANT_PERM_LOCAL":
            edits.append(dict(
                orig_line   = line,
                severity    = SAFE,
                action      = "remove_perm_in_block",
                fix_type    = "REDUNDANT_PERM_REMOVED",
                description = (
                    f"Removed duplicate permission '{meta.get('perm', '?')}' "
                    f"from role '{meta.get('role', '?')}'."
                ),
                meta = meta,
            ))

        elif itype == "CONFLICT_UNKNOWN_ROLE":
            edits.append(dict(
                orig_line   = line,
                severity    = SAFE,
                action      = "remove_line",
                fix_type    = "VACUOUS_CONFLICT_REMOVED",
                description = (
                    f"Removed conflict rule - role '{meta.get('unknown_role', '?')}' "
                    f"is undefined, making the rule vacuous."
                ),
                meta = meta,
            ))

        elif itype == "SELF_INHERIT":
            edits.append(dict(
                orig_line   = line,
                severity    = DESTRUCTIVE,
                action      = "remove_inherits",
                fix_type    = "SELF_INHERIT_FIXED",
                description = (
                    f"[DESTRUCTIVE] Removed 'inherits {meta.get('role', '?')}' "
                    f"from role '{meta.get('role', '?')}' - self-inheritance is "
                    f"structurally invalid."
                ),
                meta = meta,
            ))

        elif itype == "CYCLE_BROKEN":
            edits.append(dict(
                orig_line   = line,
                severity    = DESTRUCTIVE,
                action      = "remove_inherits",
                fix_type    = "CYCLE_BROKEN",
                description = (
                    f"[DESTRUCTIVE] Removed 'inherits {meta.get('parent', '?')}' "
                    f"from role '{meta.get('role', '?')}' to break inheritance cycle "
                    f"({meta.get('cycle_path', '?')}). Verify that removing this edge "
                    f"preserves the intended permission model."
                ),
                meta = meta,
            ))

        elif itype == "INHERITS_UNDEFINED":
            edits.append(dict(
                orig_line   = line,
                severity    = DESTRUCTIVE,
                action      = "remove_inherits",
                fix_type    = "INHERITS_UNDEFINED_FIXED",
                description = (
                    f"[DESTRUCTIVE] Removed 'inherits {meta.get('parent', '?')}' from "
                    f"role '{meta.get('role', '?')}' - '{meta.get('parent', '?')}' is "
                    f"undefined.  Conservative removal applied; alternatively, define "
                    f"'{meta.get('parent', '?')}' as a new role."
                ),
                meta = meta,
            ))

        elif itype == "UNDEFINED_ROLE_ASSIGN":
            edits.append(dict(
                orig_line   = line,
                severity    = DESTRUCTIVE,
                action      = "remove_line",
                fix_type    = "UNDEFINED_ASSIGN_REMOVED",
                description = (
                    f"[DESTRUCTIVE] Removed 'assign {meta.get('role', '?')} to "
                    f"{meta.get('user', '?')}' - role '{meta.get('role', '?')}' is "
                    f"undefined.  Conservative removal; alternatively, define the "
                    f"role '{meta.get('role', '?')}' first."
                ),
                meta = meta,
            ))

        elif itype == "REDUNDANT_INHERITED_PERM":
            edits.append(dict(
                orig_line   = line,
                severity    = DESTRUCTIVE,
                action      = "remove_perm_in_block",
                fix_type    = "REDUNDANT_INHERITED_PERM_REMOVED",
                description = (
                    f"[DESTRUCTIVE] Removed permission '{meta.get('perm', '?')}' "
                    f"from role '{meta.get('role', '?')}' - already inherited from "
                    f"parent chain.  Verify that downstream permission logic is unaffected."
                ),
                meta = meta,
            ))

        elif itype == "CONFLICT_VIOLATION":
            edits.append(dict(
                orig_line   = line,
                severity    = HEURISTIC,
                action      = "annotate",
                fix_type    = "CONFLICT_VIOLATION_FLAGGED",
                description = (
                    f"User '{meta.get('user', '?')}' holds both conflicting roles "
                    f"'{meta.get('role1', '?')}' and '{meta.get('role2', '?')}'. "
                    f"Manual review required - remove one of the assignment statements."
                ),
                meta = meta,
            ))

        elif itype == "PRIVILEGE_ESCALATION":
            edits.append(dict(
                orig_line   = line,
                severity    = HEURISTIC,
                action      = "annotate",
                fix_type    = "PRIV_ESCALATION_FLAGGED",
                description = (
                    f"Role '{meta.get('role', '?')}' inherits high-privilege role "
                    f"'{meta.get('parent', '?')}'. This inheritance may be intentional "
                    f"- manual review required before removing it."
                ),
                meta = meta,
            ))

        elif itype == "NO_PERMISSIONS":
            edits.append(dict(
                orig_line   = line,
                severity    = HEURISTIC,
                action      = "annotate",
                fix_type    = "NO_PERMISSIONS_FLAGGED",
                description = (
                    f"Role '{meta.get('role', '?')}' has no effective permissions "
                    f"(Least Privilege violation). Add at least one permission or "
                    f"verify this is intentional."
                ),
                meta = meta,
            ))

    in_place_edits = [e for e in edits if e["action"] != "annotate"]
    annotation_edits = [e for e in edits if e["action"] == "annotate"]

    in_place_edits.sort(key=lambda e: -(e["orig_line"] or 0))
    annotation_edits.sort(key=lambda e: -(e["orig_line"] or 0))

    processed_lines: set = set()

    for edit in in_place_edits:
        ln     = edit["orig_line"]
        action = edit["action"]
        meta   = edit["meta"]

        if ln is None:
            continue

        cl_entry = {
            "line":        ln,
            "severity":    edit["severity"],
            "fix_type":    edit["fix_type"],
            "description": edit["description"],
        }
        changelog.append(cl_entry)

        if ln in processed_lines:
            continue

        if action == "remove_line":
            _blank_line(lines, ln, edit["severity"])
            processed_lines.add(ln)

        elif action == "remove_block":
            start, end = _find_role_block(lines, ln)
            _blank_block(lines, start, end, edit["severity"])
            processed_lines.update(range(start, end + 1))

        elif action == "remove_inherits":
            _remove_inherits_clause(lines, ln)
            processed_lines.add(ln)

        elif action == "remove_perm":
            perm = meta.get("perm", "")
            if perm:
                _remove_perm_token(lines, ln, perm)
            processed_lines.add(ln)

        elif action == "remove_perm_in_block":
            perm_line = _find_perms_line(lines, ln)
            perm = meta.get("perm", "")
            if perm and perm_line not in processed_lines:
                _remove_perm_token(lines, perm_line, perm)
            processed_lines.add(perm_line)

    annotated_lines: set = set()

    for edit in annotation_edits:
        ln = edit["orig_line"]
        if ln is None:
            continue

        cl_entry = {
            "line":        ln,
            "severity":    edit["severity"],
            "fix_type":    edit["fix_type"],
            "description": edit["description"],
        }
        changelog.append(cl_entry)

        if ln not in annotated_lines:
            _insert_comment_above(lines, ln, edit["description"])
            annotated_lines.add(ln)

    changelog.sort(key=lambda e: (e["line"] or 0))

    return "".join(lines), changelog

def format_changelog(
    changelog: List[Dict[str, Any]],
    source_filename: str,
) -> str:
    col_sep = "  "
    header_width = 70

    lines = []
    lines.append("=" * header_width)
    lines.append("AUTO-FIX CHANGELOG")
    lines.append(f"Source file : {source_filename}")
    lines.append("=" * header_width)
    lines.append("")

    if not changelog:
        lines.append("  No fixable issues found.")
        lines.append("")
        return "\n".join(lines)

    safe_entries        = [e for e in changelog if e["severity"] == SAFE]
    heuristic_entries   = [e for e in changelog if e["severity"] == HEURISTIC]
    destructive_entries = [e for e in changelog if e["severity"] == DESTRUCTIVE]

    def _section(title: str, entries: List[Dict]) -> None:
        if not entries:
            return
        lines.append(f"  -- {title} ({'-' * max(0, header_width - len(title) - 6)})")
        for e in entries:
            ln_str   = f"Line {e['line']:>3}" if e["line"] else "Line   ?"
            sev_lbl  = _SEVERITY_LABEL.get(e["severity"], "[?       ]")
            fix_type = e["fix_type"].ljust(35)
            lines.append(f"  {sev_lbl}{col_sep}{ln_str}{col_sep}{fix_type}{col_sep}{e['description']}")
        lines.append("")

    _section("SAFE FIXES (applied automatically)", safe_entries)
    _section("DESTRUCTIVE FIXES (applied - destructive, review carefully)", destructive_entries)
    _section("HEURISTIC ANNOTATIONS (code annotated only - NOT modified)", heuristic_entries)

    lines.append(
        f"  Totals: {len(safe_entries)} SAFE | "
        f"{len(destructive_entries)} DESTRUCTIVE | "
        f"{len(heuristic_entries)} HEURISTIC"
    )
    lines.append("")
    lines.append(
        "  NOTE: HEURISTIC entries were NOT automatically fixed because the\n"
        "  correct resolution depends on intent.  Review each annotated line\n"
        "  and resolve manually before recompiling."
    )
    lines.append("=" * header_width)
    lines.append("")

    return "\n".join(lines)
