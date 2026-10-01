#!/usr/bin/env python3
"""Render the static legal pages from content.json using only Python's standard library."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def page_name(document: str, locale: str) -> str:
    suffix = "" if locale == "es" else f"-{locale}"
    return f"{document}{suffix}.html"


def html_text(value: str, contact_email: str | None) -> str:
    escaped = html.escape(value, quote=True)
    if contact_email:
        label = html.escape(contact_email, quote=True)
        escaped_email = html.escape(contact_email, quote=True)
        escaped = escaped.replace(
            escaped_email,
            f'<a href="mailto:{label}">{label}</a>',
        )
    return escaped


def paragraph_markup(value: str, contact_email: str | None) -> str:
    paragraphs = re.split(r"\n\s*\n", value.strip())
    rendered = []
    for paragraph in paragraphs:
        escaped = html_text(paragraph, contact_email).replace("\n", "<br>\n")
        rendered.append(f"<p>{escaped}</p>")
    return "\n".join(rendered)


def render_document(
    content: dict[str, Any],
    locale: str,
    document_id: str,
    license_text: str,
) -> str:
    locales = content["locales"]
    language = locales[locale]
    document = language["documents"][document_id]
    contact_match = EMAIL_PATTERN.search(
        language["documents"]["privacy"]["sections"][0]["body"]
    )
    contact_email = contact_match.group(0) if contact_match else None

    document_links = []
    for target_id in content["document_order"]:
        target = language["documents"][target_id]
        current = ' aria-current="page"' if target_id == document_id else ""
        document_links.append(
            f'<a href="{page_name(target_id, locale)}"{current}>{html.escape(target["title"])}</a>'
        )

    language_links = []
    for target_locale in content["language_order"]:
        target = locales[target_locale]
        current = ' aria-current="page"' if target_locale == locale else ""
        language_links.append(
            f'<a href="{page_name(document_id, target_locale)}" lang="{html.escape(target["tag"], quote=True)}" '
            f'hreflang="{html.escape(target["tag"], quote=True)}"{current}>'
            f'{html.escape(target["language_name"])}</a>'
        )

    sections = []
    for section in document["sections"]:
        section_id = f"{document_id}-{section['id']}"
        body = paragraph_markup(section["body"], contact_email)
        license_block = ""
        if section.get("license_file"):
            license_block = (
                '<pre class="license-text" aria-label="Google Sans Flex SIL Open Font License">'
                f"{html.escape(license_text, quote=False)}</pre>"
            )
        license_markup = f"  {license_block}\n" if license_block else ""
        sections.append(
            f'<section class="legal-section" aria-labelledby="{section_id}-title">\n'
            f'  <h2 id="{section_id}-title">{html.escape(section["title"])}</h2>\n'
            f"  {body}\n"
            f"{license_markup}"
            "</section>"
        )

    title = html.escape(document["title"])
    nav = language["navigation"]
    return f'''<!doctype html>
<html lang="{html.escape(language["tag"], quote=True)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>{title} | Gasel</title>
  <link rel="icon" href="favicon.png" type="image/png">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <a class="skip-link" href="#main">{html.escape(nav["skip"])}</a>
  <header class="site-header">
    <a class="brand" href="index.html" aria-label="Gasel">
      <img class="brand-logo" src="gasel-logo.png" alt="" width="48" height="48">
      <span>Gasel</span>
    </a>
    <nav class="document-nav" aria-label="{html.escape(nav["documents"], quote=True)}">
      {' '.join(document_links)}
    </nav>
    <nav class="language-nav" aria-label="{html.escape(nav["languages"], quote=True)}">
      {' '.join(language_links)}
    </nav>
  </header>
  <main id="main" class="document-shell">
    <article class="legal-document">
      <header class="document-intro">
        <h1>{title}</h1>
        <p class="document-summary">{html.escape(document["summary"])}</p>
        <p class="updated">{html.escape(document["updated"])}</p>
      </header>
      {' '.join(sections)}
    </article>
  </main>
</body>
</html>
'''


def render_index(content: dict[str, Any]) -> str:
    spanish = content["locales"]["es"]
    privacy = spanish["documents"]["privacy"]
    title = html.escape(privacy["title"])
    return f'''<!doctype html>
<html lang="es-ES">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>Gasel</title>
  <link rel="icon" href="favicon.png" type="image/png">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <a class="brand" href="index.html" aria-label="Gasel">
      <img class="brand-logo" src="gasel-logo.png" alt="" width="48" height="48">
      <span>Gasel</span>
    </a>
  </header>
  <main id="main" class="document-shell index-page">
    <h1>Gasel</h1>
    <p><a href="privacy.html">{title}</a></p>
  </main>
</body>
</html>
'''


def expected_files(content: dict[str, Any], license_path: Path | None = None) -> dict[str, str]:
    license_file = license_path or ROOT / "licenses/google-sans-flex.txt"
    license_text = license_file.read_text(encoding="utf-8")
    files = {"index.html": render_index(content)}
    for locale in content["language_order"]:
        for document in content["document_order"]:
            files[page_name(document, locale)] = render_document(content, locale, document, license_text)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Write generated pages")
    mode.add_argument("--check", action="store_true", help="Compare generated pages without writing")
    args = parser.parse_args()
    try:
        content = json.loads((ROOT / "content.json").read_text(encoding="utf-8"))
        generated = expected_files(content)
    except (OSError, ValueError, KeyError) as error:
        print(f"Render failed: {error}", file=sys.stderr)
        return 1
    if args.write:
        for name, text in generated.items():
            (ROOT / name).write_text(text, encoding="utf-8", newline="\n")
        print(f"Rendered {len(generated) - 1} legal pages and index.html.")
        return 0
    differences = []
    for name, expected in generated.items():
        path = ROOT / name
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            differences.append(name)
    if differences:
        print("Render check failed; regenerate these pages:\n" + "\n".join(f"- {name}" for name in differences), file=sys.stderr)
        return 1
    print(f"Render check passed: {len(generated) - 1} pages are deterministic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
