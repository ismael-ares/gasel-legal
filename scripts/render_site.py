#!/usr/bin/env python3
"""Render the static legal pages from the Android legal catalogs."""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
DOMAIN_LINKS = {
    "routing.openstreetmap.de/about.html": "https://routing.openstreetmap.de/about.html",
    "policies.google.com/privacy": "https://policies.google.com/privacy",
    "google.com/help/terms_maps": "https://maps.google.com/help/terms_maps/",
    "openstreetmap.org/copyright": "https://www.openstreetmap.org/copyright",
    "router.project-osrm.org": "https://router.project-osrm.org/",
    "aepd.es": "https://www.aepd.es/",
}
DOCS = ("privacy", "legal", "licenses")
ANCHORS = {"privacy": "privacy", "legal": "legal", "licenses": "open-source"}
ASSETS = ("apache-license-2.0.txt", "flag-icons-mit.txt", "google-sans-flex.txt", "material-kolor-mit.txt")


def hero_burst_path() -> str:
    points = []
    for index in range(120):
        angle = math.tau * index / 120
        radius = 50 * (0.95 + 0.05 * math.cos(12 * angle))
        x = 50 + radius * math.sin(angle)
        y = 50 - radius * math.cos(angle)
        points.append(f"{x:.2f} {y:.2f}")
    return "M" + " L".join(points) + "Z"


def page_name(document: str, locale: str) -> str:
    suffix = "" if locale == "es" else f"-{locale}"
    return f"{document}{suffix}.html"


def h(value: str) -> str:
    return html.escape(value, quote=True)


def body_markup(value: str) -> str:
    contact = EMAIL_RE.search(value)
    escaped = h(value)
    if contact:
        addr = h(contact.group(0))
        escaped = escaped.replace(addr, f'<a href="mailto:{addr}" dir="ltr">{addr}</a>')
    for domain, href in DOMAIN_LINKS.items():
        escaped = re.sub(rf"(?<![\w@/=]){re.escape(domain)}(?![\w.-])", f'<a href="{href}">{domain}</a>', escaped, flags=re.I)
    return "\n".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in re.split(r"\n\s*\n", escaped.strip()))


def page_section(section_id: str, title: str, content: str, classes: str = "row") -> str:
    return f'<section class="{classes}" aria-labelledby="{section_id}-title"><h3 id="{section_id}-title">{h(title)}</h3><div class="row-body">{content}</div></section>'


def table(headers: list[str], rows: list[list[str]], labels: list[str] | None = None) -> str:
    thead = "".join(f'<th scope="col">{h(label)}</th>' for label in headers)
    body = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            attr = f' data-l="{h(labels[i])}"' if labels else ""
            cells.append(f"<td{attr}>{h(cell)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="tbl"><table><thead><tr>{thead}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def render_redirect(content: dict[str, Any], locale: str, document_id: str) -> str:
    language = content["locales"][locale]
    strings = language["strings"]
    target = f'{page_name("privacy", locale)}#{ANCHORS[document_id]}'
    title_key = "legal_notice_title" if document_id == "legal" else "legal_licenses_title"
    title = strings[title_key]
    auto = f'<script>location.replace({json.dumps(target)});</script>'
    return f'''<!doctype html>
<html lang="{h(language["tag"])}"{' dir="rtl"' if language.get("direction") == "rtl" else ""}><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark"><meta http-equiv="refresh" content="0;url={h(target)}"><title>{h(title)} | Gasel</title><link rel="stylesheet" href="styles.css"><script defer src="site.js"></script></head>
<body class="site"><main class="document-shell"><header class="bar-brand"><a class="brand" href="index.html"><img class="brand-logo" src="gasel-logo.png" alt="" width="48" height="48">Gasel</a></header><section class="panel redirect-panel"><h1>{h(title)}</h1><p>{h(strings["legal_hero_promise"])}</p><p><a href="{h(target)}">{h(strings["legal_open_web"])}</a></p></section></main>{auto}</body></html>'''


def render_document(content: dict[str, Any], locale: str, document_id: str, licenses: dict[str, str]) -> str:
    if document_id != "privacy":
        return render_redirect(content, locale, document_id)
    language = content["locales"][locale]
    s = language["strings"]
    direction = ' dir="rtl"' if language.get("direction") == "rtl" else ""

    facts = []
    for item in ("account", "ads", "location", "device", "prices", "outbound"):
        facts.append(f'<li class="fact"><h3>{h(s[f"legal_fact_{item}_title"])}</h3><p>{h(s[f"legal_fact_{item}_body"])}</p></li>')

    use_rows = [[s[f"legal_uses_{item}_{field}"] for field in ("data", "purpose", "leaves")] for item in ("location", "area", "prefs", "errors")]
    use_headers = [s[f"legal_uses_col_{key}"] for key in ("data", "purpose", "leaves")]
    use_table = table(use_headers, use_rows, use_headers)
    service_cards = []
    for item in ("ministry", "osrm", "maps", "geocoder", "backup"):
        service_url = {"ministry": "https://geoportalgasolineras.es/geoportal-instalaciones/Inicio", "osrm": "https://router.project-osrm.org/", "maps": "https://policies.google.com/privacy"}.get(item)
        service_name = h(s[f"legal_svc_{item}_name"])
        if service_url: service_name = f'<a href="{service_url}">{service_name}</a>'
        service_cards.append(f'<article class="service"><span class="service-tag">{h(s[f"legal_svc_{item}_tag"])}</span><h4>{service_name}</h4>{body_markup(s[f"legal_svc_{item}_body"])}</article>')
    storage_rows = [[s[f"legal_storage_{item}_{field}"] for field in ("data", "time", "backup")] for item in ("prefs", "area", "distances", "cache", "report")]
    storage_headers = [s[f"legal_storage_col_{key}"] for key in ("data", "time", "backup")]
    storage_table = table(storage_headers, storage_rows, storage_headers)
    rights = '<ul class="rights">' + "".join(f"<li>{h(s[f'legal_right_{key}'])}</li>" for key in ("access", "rectification", "erasure", "restriction", "objection", "portability")) + "</ul>"

    privacy_blocks = [
        page_section("p-controller", s["legal_p_controller_title"], body_markup(s["legal_p_controller_body_1"])),
        page_section("p-uses", s["legal_p_uses_title"], use_table + body_markup(s["legal_p_uses_body_1"] + "\n\n" + s["legal_p_uses_body_2"])),
        page_section("p-sharing", s["legal_p_sharing_title"], body_markup(s["legal_p_sharing_body_1"]) + '<div class="services">' + "".join(service_cards) + '</div>' + body_markup(s["legal_p_sharing_body_2"])),
        page_section("p-storage", s["legal_p_storage_title"], storage_table + body_markup(s["legal_p_storage_body_1"])),
    ]
    for item, key in (("errors", "errors"), ("basis", "basis"), ("transfers", "transfers"), ("rights", "rights"), ("minors", "minors"), ("changes", "changes")):
        paragraphs = [s[f"legal_p_{item}_body_{i}"] for i in range(1, 4) if f"legal_p_{item}_body_{i}" in s]
        extra = rights if item == "rights" else ""
        privacy_blocks.append(page_section(f"p-{item}", s[f"legal_p_{item}_title"], extra + body_markup("\n\n".join(paragraphs))))

    notice_blocks = []
    for item, body_count in (("owner", 1), ("about", 1), ("source", 2), ("warranty", 2), ("maps", 2), ("brands", 2), ("ip", 1), ("liability", 1), ("law", 1)):
        paragraphs = "\n\n".join(s[f"legal_n_{item}_body_{i}"] for i in range(1, body_count + 1))
        notice_blocks.append(page_section(f"n-{item}", s[f"legal_n_{item}_title"], body_markup(paragraphs)))

    components = [
        ("Jetpack Compose BOM · 2026.02.01 / Material 3 · 1.5.0-alpha25", "compose_use", "Apache 2.0"),
        ("AndroidX (Activity, AppCompat, Core, Lifecycle, DataStore, SplashScreen)", "androidx_use", "Apache 2.0"),
        ("Material Icons", "icons_use", "Apache 2.0"),
        ("Kotlin · 2.4.10 / kotlinx.coroutines", "kotlin_use", "Apache 2.0"),
        ("Retrofit · 3.0.0 / OkHttp / Okio", "network_use", "Apache 2.0"),
        ("Gson", "gson_use", "Apache 2.0"),
        ("Accompanist Permissions · 0.37.3", "accompanist_use", "Apache 2.0"),
        ("Material Kolor · 5.0.0 / Material Color Utilities", "color_use", "MIT · Apache 2.0"),
        ("Google Sans Flex", "font_use", "SIL OFL 1.1"),
        ("flag-icons", "flag_icons_use", "MIT"),
        (s["legal_comp_commons_flags_name"], "commons_flags_use", s["legal_license_public_domain"]),
        ("Google Maps SDK · 19.0.0", "maps_use", s["legal_license_google_terms"]),
        (s["legal_comp_osm_name"], "osm_use", "ODbL 1.0"),
    ]
    comp_rows = [[name, s[f"legal_comp_{use}"], license_name] for name, use, license_name in components]
    component_headers = [s[f"legal_comp_col_{key}"] for key in ("name", "use", "license")]
    comp_table = table(component_headers, comp_rows, component_headers)
    license_disclosures = []
    license_labels = {
        "apache-license-2.0.txt": "Apache License 2.0",
        "flag-icons-mit.txt": "MIT License · flag-icons",
        "google-sans-flex.txt": "SIL Open Font License 1.1 · Google Sans Flex",
        "material-kolor-mit.txt": "MIT License · Material Kolor",
    }
    for file in ASSETS:
        license_disclosures.append(f'<details class="license-disclosure"><summary>{h(license_labels[file])}</summary><pre class="license-text" lang="en" dir="ltr">{html.escape(licenses[file], quote=False)}</pre></details>')
    license_content = page_section("l-components", s["legal_l_components_title"], comp_table) + page_section("l-texts", s["legal_l_texts_title"], "".join(license_disclosures))

    languages = []
    for target_locale in content["language_order"]:
        target = content["locales"][target_locale]
        current = ' aria-current="true"' if locale == target_locale else ""
        languages.append(f'<li><a class="lang-item" href="{page_name("privacy", target_locale)}#summary" lang="{h(target["tag"])}" hreflang="{h(target["tag"])}"{current}><span class="li-code">{h(target_locale.upper())}</span><span class="li-name">{h(target["language_name"])}</span></a></li>')
    nav = [("summary", "legal_nav_summary", "summary"), ("privacy", "legal_nav_privacy", "privacy"), ("legal", "legal_nav_notice", "legal"), ("open-source", "legal_nav_licenses", "licenses")]
    nav_links = "".join(f'<a class="chip" href="#{anchor}" data-nav-target="{anchor}">{h(s[key])}</a>' for anchor, key, _ in nav)

    return f'''<!doctype html>
<html lang="{h(language["tag"])}"{direction}><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="color-scheme" content="light dark"><title>{h(s["legal_hero_title"])} | Gasel</title><link rel="icon" href="favicon.png" type="image/png"><link rel="stylesheet" href="styles.css"><script defer src="site.js"></script></head>
<body class="site"><a class="skip-link" href="#main">{h(s["legal_nav_summary"])}</a>
<header class="bar"><div class="bar-in gut"><a class="brand" href="index.html" aria-label="Gasel"><img class="brand-logo" src="gasel-logo.png" alt="" width="48" height="48"><span class="brand-name">Gasel</span></a><nav class="document-nav" aria-label="{h(s["legal_web_sections"])}">{nav_links}</nav>
<details class="lang"><summary class="lang-btn"><span class="sr-only">{h(s["legal_web_language"])}</span><span class="lang-code">{h(locale.upper())}</span><svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><div class="lang-panel"><label class="sr-only" for="language-search">{h(s["legal_web_language_filter"])}</label><input id="language-search" class="lang-q" type="search" placeholder="{h(s["legal_web_language_filter"])}" autocomplete="off"><ul class="lang-list">{"".join(languages)}</ul><p class="lang-empty" hidden>{h(s["legal_web_language_empty"])}</p></div></details>
<button class="theme-btn" id="theme-btn" type="button" data-dark-label="{h(s["legal_web_theme_dark"])}" data-light-label="{h(s["legal_web_theme_light"])}" aria-label="{h(s["legal_web_theme_dark"])}" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><mask id="moon-cut"><rect width="24" height="24" fill="#fff"/><circle class="cut" cx="24" cy="2" r="7" fill="#000"/></mask><g class="rays"><path d="M12 1.8v2.4M12 19.8v2.4M1.8 12h2.4M19.8 12h2.4M4.8 4.8l1.7 1.7M17.5 17.5l1.7 1.7M4.8 19.2l1.7-1.7M17.5 6.5l1.7-1.7"/></g><circle class="core" cx="12" cy="12" r="5" mask="url(#moon-cut)"/></svg></button></div></header>
<main id="main" class="wrap gut"><header id="summary" data-sec="summary" class="hero" tabindex="-1" aria-labelledby="hero-title"><div class="hero-copy"><p class="eyebrow">{h(s["legal_eyebrow"])}</p><h1 id="hero-title">{h(s["legal_hero_title"])}</h1><p class="promise">{h(s["legal_hero_promise"])}</p><p class="updated">{h(s["legal_updated"])}</p></div><div class="hero-mark"><svg class="hero-burst" viewBox="0 0 100 100" aria-hidden="true"><path d="{hero_burst_path()}"/></svg><img src="gasel-logo.png" alt="" width="104" height="104"></div><div class="facts-wrap"><h2 class="sr-only">{h(s["legal_summary_title"])}</h2><ul class="facts">{"".join(facts)}</ul></div></header>
<section id="privacy" data-sec="privacy" class="panel" aria-labelledby="privacy-title"><header class="panel-head"><h2 id="privacy-title">{h(s["legal_privacy_title"])}</h2><p class="lead">{h(s["legal_privacy_lead"])}</p></header>{"".join(privacy_blocks)}</section>
<section id="legal" data-sec="legal" class="panel" aria-labelledby="legal-title"><header class="panel-head"><h2 id="legal-title">{h(s["legal_notice_title"])}</h2><p class="lead">{h(s["legal_notice_lead"])}</p></header>{"".join(notice_blocks)}</section>
<section id="open-source" data-sec="open-source" class="panel" aria-labelledby="open-source-title"><header class="panel-head"><h2 id="open-source-title">{h(s["legal_licenses_title"])}</h2><p class="lead">{h(s["legal_licenses_lead"])}</p></header>{license_content}</section>
<footer class="foot"><a class="foot-brand" href="index.html"><img src="gasel-logo.png" width="48" height="48" alt=""><strong>Gasel</strong></a><dl><div><dt>{h(s["legal_footer_contact"])}</dt><dd><a href="mailto:gasel@yvel.uk" dir="ltr">gasel@yvel.uk</a></dd></div><div><dt>{h(s["legal_footer_identifier"])}</dt><dd>uk.yvel.gasel</dd></div><div><dt>{h(s["legal_footer_code"])}</dt><dd><a href="https://github.com/ismael-ares/gasel">github.com/ismael-ares/gasel</a></dd></div><div><dt>{h(s["legal_footer_updated"])}</dt><dd>{h(s["legal_updated"])}</dd></div></dl></footer></main></body></html>'''


def render_index(content: dict[str, Any]) -> str:
    return f'''<!doctype html><html lang="es-ES"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="0;url=privacy.html#summary"><title>Gasel</title><link rel="stylesheet" href="styles.css"></head><body><main class="document-shell"><h1>Gasel</h1><p><a href="privacy.html#summary">{h(content["locales"]["es"]["strings"]["legal_open_web"])}</a></p></main></body></html>'''


def expected_files(content: dict[str, Any], license_paths: dict[str, Path] | Path | None = None) -> dict[str, str]:
    if isinstance(license_paths, Path):
        paths = {file: license_paths.parent / file for file in ASSETS}
    elif license_paths is None:
        paths = {file: ROOT / "licenses" / file for file in ASSETS}
    else:
        paths = license_paths
    licenses = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    generated = {"index.html": render_index(content)}
    for locale in content["language_order"]:
        for document in DOCS:
            generated[page_name(document, locale)] = render_document(content, locale, document, licenses)
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
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
        print(f"Rendered {len(generated) - 1} legacy routes.")
        return 0
    differences = [name for name, expected in generated.items() if not (ROOT / name).is_file() or (ROOT / name).read_text(encoding="utf-8") != expected]
    if differences:
        print("Render check failed; regenerate these pages:\n" + "\n".join(f"- {name}" for name in differences), file=sys.stderr)
        return 1
    print(f"Render check passed: {len(generated) - 1} routes are deterministic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
