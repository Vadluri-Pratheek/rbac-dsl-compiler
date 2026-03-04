from src.lexer import RBACLexer
from src.parser import RBACParser
from src.semantic import analyze_program
from src.security import run_security_checks
import sys

def compile_rbac_policy(filename):
    try:
        with open(filename, 'r') as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: Couldn't find '{filename}'")
        return False
    
    print(f"--- Compiling: {filename} ---")
    
    # 1. Lex & Parse
    lexer = RBACLexer()
    lexer.build()
    
    parser = RBACParser()
    parser.build()
    ast = parser.parse(code, lexer.lexer)
    
    if parser.errors:
        print(f"\n[!] Parser failed with {len(parser.errors)} errors.")
        return False
    
    # 2. Semantic Checks (Critical)
    errors = analyze_program(ast)
    if errors:
        print("\n[!] Semantic errors found:")
        for e in errors: print(f"  -> {e}")
        return False
    
    # 3. Security Analysis (Warnings)
    warnings = run_security_checks(ast)
    if warnings:
        print("\n[!] Security Warnings:")
        for w in warnings: print(f"  * {w}")
    else:
        print("\nDone. Policy looks solid.")
    
    print("\n--- Finished ---\n")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <policy.rbac>")
        sys.exit(1)
    
    success = compile_rbac_policy(sys.argv[1])
    sys.exit(0 if success else 1)
