#!/usr/bin/env python3
"""Checks that every public legal document is localized and styled consistently."""

from pathlib import Path

ROOT = Path(__file__).parent
DOCUMENTS = ("privacy", "legal", "licenses")
SUFFIXES = ("", "-en", "-gl", "-ca", "-eu")

def main() -> int:
    errors: list[str] = []
    for document in DOCUMENTS:
        for suffix in SUFFIXES:
            path = ROOT / f"{document}{suffix}.html"
            if not path.exists():
                errors.append(f"Missing {path.name}")
                continue
            content = path.read_text(encoding="utf-8")
            if 'href="styles.css"' not in content:
                errors.append(f"{path.name} does not use styles.css")
            if "<style" in content:
                errors.append(f"{path.name} has inline CSS")
            if "<main" not in content or "<h1>" not in content:
                errors.append(f"{path.name} is missing its document structure")
    if errors:
        print("Legal site validation failed:\n" + "\n".join(f"- {error}" for error in errors))
        return 1
    print("Legal site validation passed: 15 localized pages share styles.css.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
