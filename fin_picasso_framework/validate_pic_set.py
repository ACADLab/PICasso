"""
Validate and enhance Pic_set.txt problems for quality.

Checks for:
- Unicode characters
- Ambiguous language
- Formatting issues
- Missing specifications
"""

import re
from pathlib import Path
from fin_picasso_framework.input_quality.input_validator import InputValidator

def validate_pic_set(file_path: str = "Pic_set.txt"):
    """Validate all problems in Pic_set.txt."""
    validator = InputValidator()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse problems
    pat = re.compile(r"Problem\s+(\d+)\s*\(([^)]+)\)(?:\s*\[Complexity\s+(\d+)\])?\s*:", re.I)
    matches = list(pat.finditer(content))
    
    print("=" * 70)
    print("PIC_SET.TXT VALIDATION REPORT")
    print("=" * 70)
    print(f"\nTotal problems found: {len(matches)}\n")
    
    all_issues = []
    problems_with_issues = []
    
    for i, m in enumerate(matches):
        problem_num = int(m.group(1))
        title = m.group(2).strip()
        complexity = m.group(3) if m.group(3) else "N/A"
        
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        
        # Validate this problem
        is_valid, issues = validator.validate(body)
        
        if issues:
            problems_with_issues.append(problem_num)
            all_issues.extend([(problem_num, issue) for issue in issues])
            print(f"❌ Problem {problem_num} ({title}) [Complexity {complexity}]:")
            for issue in issues:
                print(f"   - {issue}")
            print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total problems: {len(matches)}")
    print(f"Problems with issues: {len(problems_with_issues)}")
    print(f"Total issues found: {len(all_issues)}")
    
    if problems_with_issues:
        print(f"\nProblems needing fixes: {problems_with_issues}")
    else:
        print("\n✅ All problems passed validation!")
    
    # Check for unicode in entire file
    unicode_issues = validator._check_unicode(content)
    if unicode_issues:
        print(f"\n⚠️  Unicode issues in file: {len(unicode_issues)}")
        for issue in unicode_issues[:10]:
            print(f"   - {issue}")
    
    return len(problems_with_issues) == 0, all_issues

def sanitize_pic_set(input_file: str = "Pic_set.txt", output_file: str = "Pic_set_sanitized.txt"):
    """Sanitize Pic_set.txt and save to new file."""
    validator = InputValidator()
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Sanitize
    sanitized = validator.sanitize(content)
    
    # Save
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(sanitized)
    
    print(f"✅ Sanitized file saved to: {output_file}")
    return output_file

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--sanitize":
        sanitize_pic_set()
    else:
        is_valid, issues = validate_pic_set()
        if not is_valid:
            print("\n💡 Run with --sanitize to create a sanitized version")
            sys.exit(1)
        else:
            print("\n✅ All problems are valid!")


