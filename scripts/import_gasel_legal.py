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
    ("sq", "sq-AL", "values-sq-rAL"),
    ("ar", "ar-MA", "values-ar-rMA"),
    ("oc-aranes", "oc-ES-aranes", "values-b+oc+ES+aranes"),
    ("ast", "ast-ES", "values-b+ast+ES"),
    ("eu", "eu-ES", "values-eu-rES"),
    ("bs", "bs-BA", "values-bs-rBA"),
    ("bg", "bg-BG", "values-bg-rBG"),
    ("es", "es-ES", "values"),
    ("ca", "ca-ES", "values-ca-rES"),
    ("zh", "zh-CN", "values-zh-rCN"),
    ("hr", "hr-HR", "values-hr-rHR"),
    ("cs", "cs-CZ", "values-cs-rCZ"),
    ("da", "da-DK", "values-da-rDK"),
    ("nl", "nl-NL", "values-nl-rNL"),
    ("en", "en-GB", "values-en-rGB"),
    ("en-us", "en-US", "values-en-rUS"),
    ("et", "et-EE", "values-et-rEE"),
    ("fi", "fi-FI", "values-fi-rFI"),
    ("fr", "fr-FR", "values-fr-rFR"),
    ("gl", "gl-ES", "values-gl-rES"),
    ("de", "de-DE", "values-de-rDE"),
    ("hi", "hi-IN", "values-hi-rIN"),
    ("hu", "hu-HU", "values-hu-rHU"),
    ("is", "is-IS", "values-is-rIS"),
    ("it", "it-IT", "values-it-rIT"),
    ("ja", "ja-JP", "values-ja-rJP"),
    ("ko", "ko-KR", "values-ko-rKR"),
    ("lv", "lv-LV", "values-lv-rLV"),
    ("lt", "lt-LT", "values-lt-rLT"),
    ("mk", "mk-MK", "values-mk-rMK"),
    ("cnr", "cnr-Latn-ME", "values-b+cnr+Latn+ME"),
    ("nb", "nb-NO", "values-nb-rNO"),
    ("pl", "pl-PL", "values-pl-rPL"),
    ("pt-br", "pt-BR", "values-pt-rBR"),
    ("pt", "pt-PT", "values-pt-rPT"),
    ("ro", "ro-RO", "values-ro-rRO"),
    ("ru", "ru-RU", "values-ru-rRU"),
    ("sr-cyrl", "sr-Cyrl-RS", "values-b+sr+Cyrl+RS"),
    ("sr-latn", "sr-Latn-RS", "values-b+sr+Latn+RS"),
    ("sk", "sk-SK", "values-sk-rSK"),
    ("sl", "sl-SI", "values-sl-rSI"),
    ("sv", "sv-SE", "values-sv-rSE"),
    ("rif", "rif-Latn-MA", "values-b+rif+Latn+MA"),
    ("tr", "tr-TR", "values-tr-rTR"),
    ("uk", "uk-UA", "values-uk-rUA"),
    ("ur", "ur-PK", "values-ur-rPK"),
    ("ca-valencia", "ca-ES-valencia", "values-b+ca+ES+valencia"),
)
LEGAL_ASSETS = {
    "apache-license-2.0.txt": "apache_license_2_0.txt",
    "flag-icons-mit.txt": "flag_icons_mit_license.txt",
    "google-sans-flex.txt": "google_sans_flex_license.txt",
    "material-kolor-mit.txt": "material_kolor_mit_license.txt",
}
LANGUAGE_NAME_KEYS = {
    "sq": "language_albanian",
    "ar": "language_arabic",
    "oc-aranes": "language_aranese", "ast": "language_asturian",
    "eu": "language_basque", "bg": "language_bulgarian",
    "bs": "language_bosnian",
    "es": "language_castilian", "ca": "language_catalan",
    "hr": "language_croatian", "cs": "language_czech",
    "da": "language_danish", "en": "language_english", "en-us": "language_english_us",
    "fi": "language_finnish", "fr": "language_french", "gl": "language_galician",
    "et": "language_estonian",
    "de": "language_german", "it": "language_italian", "ja": "language_japanese", "pt": "language_portuguese",
    "pt-br": "language_portuguese_brazil",
    "hi": "language_hindi",
    "hu": "language_hungarian", "is": "language_icelandic",
    "ko": "language_korean",
    "nl": "language_dutch",
    "lv": "language_latvian", "lt": "language_lithuanian",
    "mk": "language_macedonian", "cnr": "language_montenegrin",
    "zh": "language_chinese_simplified",
    "pl": "language_polish",
    "ro": "language_romanian",
    "ru": "language_russian",
    "sr-cyrl": "language_serbian_cyrillic", "sr-latn": "language_serbian_latin",
    "sk": "language_slovak", "sl": "language_slovenian",
    "tr": "language_turkish",
    "nb": "language_norwegian_bokmal", "sv": "language_swedish",
    "rif": "language_tarifit", "uk": "language_ukrainian", "ur": "language_urdu",
    "ca-valencia": "language_valencian",
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


def build_content(gasel_root: Path, fixture_locales: set[str] | None = None) -> tuple[dict[str, object], dict[str, bytes]]:
    assets: dict[str, bytes] = {}
    asset_hashes: dict[str, str] = {}
    for site_name, android_name in LEGAL_ASSETS.items():
        source = gasel_root / "app/src/main/res/raw" / android_name
        if not source.is_file():
            raise ValueError(f"Falta app/src/main/res/raw/{android_name}")
        data = source.read_bytes()
        assets[site_name] = data
        asset_hashes[site_name] = hashlib.sha256(data).hexdigest()
    locales: dict[str, object] = {}
    source_hashes: dict[str, str] = {}

    spanish_folder = dict((lang, folder) for lang, _, folder in LANGUAGES)["es"]
    spanish_legal = read_android_strings(gasel_root / "app/src/main/res" / spanish_folder / "legal.xml", "es")
    required_legal_keys = tuple(spanish_legal)

    selected = set(fixture_locales) if fixture_locales is not None else None
    if selected is not None and ("es" not in selected or not selected.issubset({entry[0] for entry in LANGUAGES})):
        raise ValueError("El fixture debe incluir es y usar solo idiomas conocidos")
    for lang, tag, folder in LANGUAGES:
        if selected is not None and lang not in selected:
            continue
        res = gasel_root / "app/src/main/res" / folder
        strings_path = res / "strings.xml"
        legal_path = res / "legal.xml"
        strings = read_android_strings(strings_path, lang)
        legal = read_android_strings(legal_path, lang)
        language_name = required(strings, LANGUAGE_NAME_KEYS[lang], lang)
        source_hashes[lang] = hashlib.sha256(
            strings_path.read_bytes() + b"\0" + legal_path.read_bytes()
        ).hexdigest()
        structured = {key: required(legal, key, lang) for key in required_legal_keys}
        locale = {
            "tag": tag,
            "language_name": language_name,
            "strings": structured,
        }
        if lang in {"ar", "ur"}:
            locale["direction"] = "rtl"
        locales[lang] = locale

    content: dict[str, object] = {
        "schema_version": 1,
        "language_order": [entry[0] for entry in LANGUAGES if selected is None or entry[0] in selected],
        "document_order": ["privacy", "legal", "licenses"],
        "legal_keys": list(required_legal_keys),
        "source_sha256": {
            "language_catalogs": source_hashes,
            "legal_assets": asset_hashes,
        },
        "locales": locales,
    }
    return content, assets


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
        content, assets = build_content(args.gasel_root.resolve())
    except (OSError, ValueError) as error:
        print(f"Import failed: {error}", file=sys.stderr)
        return 1

    content_path = ROOT / "content.json"
    expected_content = serialized(content)
    if args.write:
        content_path.write_bytes(expected_content)
        for name, data in assets.items():
            target = ROOT / "licenses" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        print(f"Imported {len(LANGUAGES)} legal catalogs and {len(assets)} original license files.")
        return 0

    problems = []
    if not content_path.is_file() or content_path.read_bytes() != expected_content:
        problems.append("content.json differs from the supplied Gasel checkout")
    for name, data in assets.items():
        path = ROOT / "licenses" / name
        if not path.is_file() or path.read_bytes() != data:
            problems.append(f"licenses/{name} differs from its Android raw license")
    if problems:
        print("Import check failed:\n" + "\n".join(f"- {problem}" for problem in problems), file=sys.stderr)
        return 1
    print(f"Import check passed: {len(LANGUAGES)} legal catalogs and the complete license match Gasel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
