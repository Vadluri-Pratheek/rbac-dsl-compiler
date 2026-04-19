from src.lexer import RBACLexer
from src.parser import RBACParser
from src.semantic import analyze_program, get_structured_errors
from src.security import run_security_checks, get_structured_warnings
import sys
import os
import re

def sort_messages(messages):
    def extract_line(msg):
        match = re.search(r"\[Line (\d+)\]", msg)
        return int(match.group(1)) if match else (float("inf") if "?" in msg else 0)
    return sorted(messages, key=extract_line)

def _parse_source(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: Couldn't find '{filename}'")
        sys.exit(1)

    lexer = RBACLexer()
    lexer.build()

    parser = RBACParser()
    parser.build()
    ast = parser.parse(code, lexer.lexer)

    if lexer.errors:
        print("\n[!] Lexer failed with errors:")
        for e in lexer.errors:
            print(f"  -> {e}")
        sys.exit(1)

    if parser.errors:
        print(f"\n[!] Parser failed with {len(parser.errors)} errors.")
        for e in parser.errors:
            print(f"  -> {e}")
        sys.exit(1)

    return code, ast

def compile_rbac_policy(filename, fix_mode=False):
    print(f"--- Compiling: {filename} ---")

    code, ast = _parse_source(filename)

    errors = analyze_program(ast)
    if errors:
        errors = sort_messages(errors)
        print("\n[!] Semantic errors found:")
        for e in errors:
            print(f"  -> {e}")

    warnings = run_security_checks(ast)
    if warnings:
        warnings = sort_messages(warnings)
        print("\n[!] Security Warnings:")
        for w in warnings:
            print(f"  * {w}")
    elif not errors:
        print("\nDone. Policy looks solid.")

    try:
        with open("rbac_report.txt", "w", encoding="utf-8") as f:
            f.write("RBAC Policy Verification Report\n")
            f.write(f"File: {filename}\n")
            f.write("--------------------------------\n\n")

            if errors:
                f.write("SEMANTIC ERRORS:\n")
                for e in errors:
                    f.write(e + "\n")
                f.write("\n")

            if warnings:
                f.write("SECURITY WARNINGS:\n")
                for w in warnings:
                    f.write(w + "\n")
                f.write("\n")

            if not errors and not warnings:
                f.write("Policy is SAFE and SOLID.\n")
            elif errors:
                f.write("Result: UNSAFE POLICY (Compilation Failed)\n")
            else:
                f.write("Result: POLICY COMPILED WITH WARNINGS\n")
    except Exception as exc:
        print(f"\n[!] Failed to write report file: {exc}")

    if fix_mode and (errors or warnings):
        _run_fixer(filename, code, ast)

    print("\n--- Finished ---\n")
    return len(errors) == 0

def _run_fixer(filename, source, ast):
    from src.fixer import apply_fixes, format_changelog

    structured_semantic  = get_structured_errors(ast)
    structured_security  = get_structured_warnings(ast)
    all_issues           = structured_semantic + structured_security

    if not all_issues:
        print("\n[Fix] No fixable issues found.")
        return

    fixed_source, changelog = apply_fixes(source, all_issues)

    stem     = os.path.splitext(filename)[0]
    out_path = f"{stem}_fixed.rbac"
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(fixed_source)
        print(f"\\n[Fix] Fixed policy written to: {out_path}")
    except Exception as exc:
        print(f"\\n[!] Could not write fixed file: {exc}")

    changelog_text = format_changelog(changelog, filename)
    try:
        with open("rbac_report.txt", "a", encoding="utf-8") as f:
            f.write("\\n")
            f.write(changelog_text)
        print("[Fix] Changelog appended to: rbac_report.txt")
    except Exception as exc:
        print(f"\\n[!] Could not append changelog: {exc}")
    from src.fixer import SAFE, HEURISTIC, DESTRUCTIVE
    safe_n  = sum(1 for e in changelog if e["severity"] == SAFE)
    heur_n  = sum(1 for e in changelog if e["severity"] == HEURISTIC)
    dest_n  = sum(1 for e in changelog if e["severity"] == DESTRUCTIVE)
    print(
        f"[Fix] Applied {safe_n} SAFE | {dest_n} DESTRUCTIVE | "
        f"{heur_n} HEURISTIC (annotated only) fix(es)."
    )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <policy.rbac> [--fix]")
        sys.exit(1)

    policy_file = sys.argv[1]
    fix_flag    = "--fix" in sys.argv[2:]

    success = compile_rbac_policy(policy_file, fix_mode=fix_flag)
    sys.exit(0 if success else 1)
