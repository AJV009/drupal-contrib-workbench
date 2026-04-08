#!/usr/bin/env python3
"""Validate skills in .claude/skills/ against the agentskills.io specification.

Runs without external deps beyond PyYAML (which is in the stdlib on most
modern distros, or installable via the host package manager). No need for
strictyaml or the upstream skills-ref library.

Checks per skill:
  - Frontmatter parses as YAML
  - `name` field: 1-64 chars, lowercase alphanumerics + hyphens, no leading/
    trailing/consecutive hyphens, matches parent directory
  - `description` field: non-empty, 1-1024 chars
  - `compatibility` field (if present): 1-500 chars
  - `metadata` field (if present): mapping
  - `license` field (if present): string
  - SKILL.md line count (warning if >500; tool-reference skills may accept)

Usage:
  python3 .claude/skills/skill-maintainer/scripts/validate.py

Exit codes:
  0 - all skills pass (warnings OK)
  1 - at least one error

Output:
  Per skill: [STATUS] name lines=N/500 desc=N/1024
  Errors prefixed with "ERROR:"
  Warnings prefixed with "warn:"
  Summary at bottom.
"""

import re
import sys
import pathlib

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Install with: pip install PyYAML", file=sys.stderr)
    sys.exit(2)


def parse_frontmatter(text: str):
    """Extract and parse the YAML frontmatter block from a SKILL.md text."""
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if not m:
        return None, "missing or malformed frontmatter (no leading --- block)"
    try:
        fm = yaml.safe_load(m.group(1))
    except Exception as e:
        return None, f"YAML parse error: {e}"
    if not isinstance(fm, dict):
        return None, "frontmatter is not a mapping"
    return fm, None


def check_name(fm, parent_name):
    """Return list of errors for the `name` field."""
    errs = []
    name = fm.get('name', '')
    if not isinstance(name, str) or not name:
        errs.append("name field is missing or empty")
        return errs
    if len(name) > 64:
        errs.append(f"name length {len(name)} > 64")
    if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', name):
        errs.append(
            f'name "{name}" must be lowercase alphanumerics + single hyphens, '
            "no leading/trailing/consecutive hyphens"
        )
    if name != parent_name:
        errs.append(f'name "{name}" must match parent directory name "{parent_name}"')
    return errs


def check_description(fm):
    """Return list of errors for the `description` field."""
    errs = []
    desc = fm.get('description')
    if not isinstance(desc, str):
        errs.append("description must be a string")
        return errs
    desc_stripped = desc.strip().replace('\n', ' ')
    if not desc_stripped:
        errs.append("description is empty")
        return errs
    if len(desc_stripped) > 1024:
        errs.append(f"description length {len(desc_stripped)} > 1024")
    return errs


def check_optional_fields(fm):
    """Return list of errors for optional frontmatter fields."""
    errs = []
    if 'compatibility' in fm:
        c = fm['compatibility']
        if not isinstance(c, str) or not c:
            errs.append("compatibility must be a non-empty string if present")
        elif len(c) > 500:
            errs.append(f"compatibility length {len(c)} > 500")
    if 'metadata' in fm and not isinstance(fm['metadata'], dict):
        errs.append("metadata must be a mapping")
    if 'license' in fm and not isinstance(fm['license'], str):
        errs.append("license must be a string")
    return errs


def validate_skill(skill_dir: pathlib.Path):
    """Validate a single skill directory. Returns (errors, warnings, stats)."""
    errors = []
    warnings = []
    stats = {'lines': 0, 'desc_len': 0}

    skill_md = skill_dir / 'SKILL.md'
    if not skill_md.exists():
        errors.append("missing SKILL.md")
        return errors, warnings, stats

    text = skill_md.read_text()
    stats['lines'] = text.count('\n') + 1

    fm, err = parse_frontmatter(text)
    if err:
        errors.append(err)
        return errors, warnings, stats

    errors.extend(check_name(fm, skill_dir.name))
    errors.extend(check_description(fm))
    errors.extend(check_optional_fields(fm))

    desc = fm.get('description', '')
    if isinstance(desc, str):
        stats['desc_len'] = len(desc.strip().replace('\n', ' '))

    if stats['lines'] > 500:
        warnings.append(
            f"SKILL.md is {stats['lines']} lines (spec recommends <=500). "
            "Accepted for tool-reference skills; workflow skills should trim."
        )

    return errors, warnings, stats


def main():
    skills_root = pathlib.Path('.claude/skills')
    if not skills_root.exists():
        print(f"ERROR: {skills_root} not found. Run from workspace root.", file=sys.stderr)
        sys.exit(2)

    total_errors = 0
    total_warnings = 0
    results = []

    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        errors, warnings, stats = validate_skill(skill_dir)
        results.append((skill_dir.name, errors, warnings, stats))
        total_errors += len(errors)
        total_warnings += len(warnings)

    # Report
    for name, errors, warnings, stats in results:
        status = "PASS" if not errors else "FAIL"
        lines = stats.get('lines', 0)
        desc_len = stats.get('desc_len', 0)
        line_flag = "✓" if lines <= 500 else "⚠"
        desc_flag = "✓" if 0 < desc_len <= 1024 else "✗"
        print(f"[{status}] {name:30} lines={lines:4}/500 {line_flag} desc={desc_len:4}/1024 {desc_flag}")
        for e in errors:
            print(f"       ERROR: {e}")
        for w in warnings:
            print(f"       warn:  {w}")

    print()
    print(f"Total: {len(results)} skills, {total_errors} errors, {total_warnings} warnings")

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == '__main__':
    main()
