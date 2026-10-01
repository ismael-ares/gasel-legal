#!/usr/bin/env python3
"""Import the public legal strings from an explicit Gasel checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = (
    ("eu", "eu-ES", "values-eu-rES", "Euskara"),
    ("es", "es-ES", "values", "Castellano"),
    ("ca", "ca-ES", "values-ca-rES", "Català"),
    ("en", "en-GB", "values-en-rGB", "English"),
    ("fr", "fr-FR", "values-fr-rFR", "Français"),
    ("gl", "gl-ES", "values-gl-rES", "Galego"),
    ("de", "de-DE", "values-de-rDE", "Deutsch"),
    ("ja", "ja-JP", "values-ja-rJP", "日本語"),
    ("pt", "pt-PT", "values-pt-rPT", "Português"),
    ("ru", "ru-RU", "values-ru-rRU", "Русский"),
)
DOCUMENTS = (
    ("privacy", "about_privacy_policy", "legal_privacy_summary", ("controller", "data", "services", "security", "retention")),
    ("legal", "about_legal_notice", "legal_notice_summary", ("controller", "information", "brands", "use")),
    ("licenses", "about_open_source_notices", "legal_licenses_summary", ("licenses", "attribution", "font")),
)
SECTION_KEYS = {
    "controller": "controller",
    "data": "data",
    "services": "services",
    "security": "security",
    "retention": "retention",
    "information": "information",
    "brands": "brands",
    "use": "use",
    "licenses": "licenses",
    "attribution": "attribution",
    "font": "font",
}
NAV_LABELS = {
    "eu": {"skip": "Saltatu edukira", "documents": "Legezko dokumentuak", "languages": "Dokumentuaren hizkuntza"},
    "es": {"skip": "Saltar al contenido", "documents": "Documentos legales", "languages": "Idioma del documento"},
    "ca": {"skip": "Ves al contingut", "documents": "Documents legals", "languages": "Idioma del document"},
    "en": {"skip": "Skip to content", "documents": "Legal documents", "languages": "Document language"},
    "fr": {"skip": "Aller au contenu", "documents": "Documents juridiques", "languages": "Langue du document"},
    "gl": {"skip": "Saltar ao contido", "documents": "Documentos legais", "languages": "Idioma do documento"},
    "de": {"skip": "Zum Inhalt springen", "documents": "Rechtliche Dokumente", "languages": "Dokumentsprache"},
    "ja": {"skip": "本文へ移動", "documents": "法的文書", "languages": "文書の言語"},
    "pt": {"skip": "Saltar para o conteúdo", "documents": "Documentos legais", "languages": "Idioma do documento"},
    "ru": {"skip": "Перейти к содержимому", "documents": "Юридические документы", "languages": "Язык документа"},
}
LANGUAGE_NAME_KEYS = {
    "eu": "language_basque", "es": "language_castilian", "ca": "language_catalan",
    "en": "language_english", "fr": "language_french", "gl": "language_galician",
    "de": "language_german", "ja": "language_japanese", "pt": "language_portuguese",
    "ru": "language_russian",
}


def decode_android_escapes(value: str) -> str:
    """Decode Android string escapes without treating UTF-8 as a legacy code page."""
    out: list[str] = []
    i = 0
    simple = {"n": "\n", "t": "\t", "r": "\r", "'": "'", '"': '"', "@": "@", "?": "?", "\\": "\\"}
    while i < len(value):
        if value[i] != "\\" or i + 1 >= len(value):
            out.append(value[i])
            i += 1
        elif value[i + 1] in simple:
            out.append(simple[value[i + 1]])
            i += 2
        elif value.startswith("\\u", i) and re.fullmatch(r"[0-9a-fA-F]{4}", value[i + 2:i + 6]):
            out.append(chr(int(value[i + 2:i + 6], 16)))
            i += 6
        else:
            out.append("\\")
            i += 1
    return "".join(out)


def read_android_strings(path: Path, language: str) -> dict[str, str]:
    if not path.is_file():
        raise ValueError(f"{language}: falta el catálogo {path.name}")
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise ValueError(f"{language}: XML inválido en {path.name}: {error}") from error
    values: dict[str, str] = {}
    for element in root:
        if element.tag == "string" and "name" in element.attrib:
            values[element.attrib["name"]] = decode_android_escapes("".join(element.itertext()))
    return values


def required(values: dict[str, str], key: str, language: str) -> str:
    value = values.get(key)
    if value is None or not value.strip():
        raise ValueError(f"{language}: falta la clave {key}")
    return value


def build_content(gasel_root: Path) -> tuple[dict[str, object], bytes]:
    legal_license = gasel_root / "app/src/main/res/raw/google_sans_flex_license.txt"
    if not legal_license.is_file():
        raise ValueError("Falta app/src/main/res/raw/google_sans_flex_license.txt")
    license_bytes = legal_license.read_bytes()
    license_hash = hashlib.sha256(license_bytes).hexdigest()
    locales: dict[str, object] = {}
    source_hashes: dict[str, str] = {}

    for lang, tag, folder, language_name in LANGUAGES:
        res = gasel_root / "app/src/main/res" / folder
        strings_path = res / "strings.xml"
        legal_path = res / "legal.xml"
        strings = read_android_strings(strings_path, lang)
        legal = read_android_strings(legal_path, lang)
        source_hashes[lang] = hashlib.sha256(
            strings_path.read_bytes() + b"\0" + legal_path.read_bytes()
        ).hexdigest()
        docs: dict[str, object] = {}
        for doc_id, title_key, summary_key, section_ids in DOCUMENTS:
            sections = []
            for section_id in section_ids:
                source_key = SECTION_KEYS[section_id]
                section = {
                    "id": section_id,
                    "title": required(legal, f"legal_{source_key}_title", lang),
                    "body": required(legal, f"legal_{source_key}_body", lang),
                }
                if section_id == "font":
                    section["license_file"] = "licenses/google-sans-flex.txt"
                sections.append(section)
            docs[doc_id] = {
                "title": required(strings, title_key, lang),
                "summary": required(legal, summary_key, lang),
                "updated": required(legal, "legal_last_updated", lang),
                "sections": sections,
            }
        locales[lang] = {
            "tag": tag,
            "language_name": language_name,
            "navigation": NAV_LABELS[lang],
            "documents": docs,
        }

    content: dict[str, object] = {
        "schema_version": 1,
        "language_order": [entry[0] for entry in LANGUAGES],
        "document_order": [entry[0] for entry in DOCUMENTS],
        "source_sha256": {
            "language_catalogs": source_hashes,
            "google_sans_flex_license": license_hash,
        },
        "locales": locales,
    }
    return content, license_bytes


def serialized(content: dict[str, object]) -> bytes:
    return (json.dumps(content, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gasel-root", required=True, type=Path, help="Path to the Gasel Android checkout")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Compare without writing")
    mode.add_argument("--write", action="store_true", help="Update content.json and the full font license")
    args = parser.parse_args()
    try:
        content, license_bytes = build_content(args.gasel_root.resolve())
    except (OSError, ValueError) as error:
        print(f"Import failed: {error}", file=sys.stderr)
        return 1

    content_path = ROOT / "content.json"
    license_path = ROOT / "licenses/google-sans-flex.txt"
    expected_content = serialized(content)
    if args.write:
        content_path.write_bytes(expected_content)
        license_path.parent.mkdir(parents=True, exist_ok=True)
        license_path.write_bytes(license_bytes)
        print("Imported ten legal catalogs and the complete Google Sans Flex license.")
        return 0

    problems = []
    if not content_path.is_file() or content_path.read_bytes() != expected_content:
        problems.append("content.json differs from the supplied Gasel checkout")
    if not license_path.is_file() or license_path.read_bytes() != license_bytes:
        problems.append("licenses/google-sans-flex.txt differs from the Android raw license")
    if problems:
        print("Import check failed:\n" + "\n".join(f"- {problem}" for problem in problems), file=sys.stderr)
        return 1
    print("Import check passed: ten legal catalogs and the complete license match Gasel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
