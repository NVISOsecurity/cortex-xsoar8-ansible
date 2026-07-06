#!/usr/bin/env python3
"""
Validate DOCUMENTATION and RETURN YAML blocks in all Ansible modules.

Exits with status 1 and prints actionable error messages when any module
contains a malformed block.  Intended for use as a CI gate via `make docs-validate`.
"""

import ast
import sys
from pathlib import Path

import yaml

modules_dir = Path(__file__).parent.parent / "modules"
errors = []

for module in sorted(modules_dir.glob("*.py")):
    try:
        tree = ast.parse(module.read_text())
    except SyntaxError as e:
        errors.append(f"  {module.name} [Python syntax]: {e}")
        continue

    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue

        block = node.targets[0].id
        if block not in {"DOCUMENTATION", "RETURN"}:
            continue

        try:
            raw = ast.literal_eval(node.value)
        except Exception as e:
            errors.append(f"  {module.name} [{block}]: cannot read string value: {e}")
            continue

        try:
            yaml.safe_load(raw)
        except yaml.YAMLError as e:
            errors.append(f"  {module.name} [{block}]: {e}")

if errors:
    print("\nERROR: YAML parse failures found in module documentation:\n")
    for err in errors:
        print(err)
    print("\nFix the DOCUMENTATION/RETURN blocks listed above before committing.")
    sys.exit(1)

total = len(list(modules_dir.glob("*.py")))
print(f"OK: all {total} modules passed DOCUMENTATION/RETURN YAML validation.")
