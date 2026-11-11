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
    "sq": {"skip": "Kalo te përmbajtja", "documents": "Dokumente ligjore", "languages": "Gjuha e dokumentit"},
    "ar": {"skip": "انتقل إلى المحتوى", "documents": "المستندات القانونية", "languages": "لغة المستند"},
    "oc-aranes": {"skip": "Ves tath contengut", "documents": "Documents legaus", "languages": "Lengua deth document"},
    "ast": {"skip": "Saltar al conteníu", "documents": "Documentos llexales", "languages": "Llingua del documentu"},
    "eu": {"skip": "Saltatu edukira", "documents": "Legezko dokumentuak", "languages": "Dokumentuaren hizkuntza"},
    "bs": {"skip": "Preskoči na sadržaj", "documents": "Pravni dokumenti", "languages": "Jezik dokumenta"},
    "bg": {"skip": "Към съдържанието", "documents": "Правни документи", "languages": "Език на документа"},
    "es": {"skip": "Saltar al contenido", "documents": "Documentos legales", "languages": "Idioma del documento"},
    "ca": {"skip": "Ves al contingut", "documents": "Documents legals", "languages": "Idioma del document"},
    "zh": {"skip": "跳转到正文", "documents": "法律文件", "languages": "文档语言"},
    "hr": {"skip": "Preskoči na sadržaj", "documents": "Pravni dokumenti", "languages": "Jezik dokumenta"},
    "cs": {"skip": "Přejít k obsahu", "documents": "Právní dokumenty", "languages": "Jazyk dokumentu"},
    "da": {"skip": "Gå til indholdet", "documents": "Juridiske dokumenter", "languages": "Dokumentets sprog"},
    "nl": {"skip": "Ga naar de inhoud", "documents": "Juridische documenten", "languages": "Documenttaal"},
    "en": {"skip": "Skip to content", "documents": "Legal documents", "languages": "Document language"},
    "en-us": {"skip": "Skip to content", "documents": "Legal documents", "languages": "Document language"},
    "et": {"skip": "Liigu sisu juurde", "documents": "Õigusdokumendid", "languages": "Dokumendi keel"},
    "fi": {"skip": "Siirry sisältöön", "documents": "Oikeudelliset asiakirjat", "languages": "Asiakirjan kieli"},
    "fr": {"skip": "Aller au contenu", "documents": "Documents juridiques", "languages": "Langue du document"},
    "gl": {"skip": "Saltar ao contido", "documents": "Documentos legais", "languages": "Idioma do documento"},
    "de": {"skip": "Zum Inhalt springen", "documents": "Rechtliche Dokumente", "languages": "Dokumentsprache"},
    "hi": {"skip": "मुख्य सामग्री पर जाएँ", "documents": "कानूनी दस्तावेज़", "languages": "दस्तावेज़ की भाषा"},
    "hu": {"skip": "Ugrás a tartalomhoz", "documents": "Jogi dokumentumok", "languages": "A dokumentum nyelve"},
    "is": {"skip": "Fara í efnið", "documents": "Lagaleg skjöl", "languages": "Tungumál skjalsins"},
    "it": {"skip": "Vai al contenuto", "documents": "Documenti legali", "languages": "Lingua del documento"},
    "ja": {"skip": "本文へ移動", "documents": "法的文書", "languages": "文書の言語"},
    "ko": {"skip": "본문으로 건너뛰기", "documents": "법률 문서", "languages": "문서 언어"},
    "lv": {"skip": "Pāriet uz saturu", "documents": "Juridiskie dokumenti", "languages": "Dokumenta valoda"},
    "lt": {"skip": "Pereiti prie turinio", "documents": "Teisiniai dokumentai", "languages": "Dokumento kalba"},
    "mk": {"skip": "Прескокни до содржината", "documents": "Правни документи", "languages": "Јазик на документот"},
    "cnr": {"skip": "Preskoči na sadržaj", "documents": "Pravni dokumenti", "languages": "Jezik dokumenta"},
    "nb": {"skip": "Hopp til innholdet", "documents": "Juridiske dokumenter", "languages": "Dokumentspråk"},
    "pl": {"skip": "Przejdź do treści", "documents": "Dokumenty prawne", "languages": "Język dokumentu"},
    "pt": {"skip": "Saltar para o conteúdo", "documents": "Documentos legais", "languages": "Idioma do documento"},
    "pt-br": {"skip": "Pular para o conteúdo", "documents": "Documentos legais", "languages": "Idioma do documento"},
    "ro": {"skip": "Sari la conținut", "documents": "Documente juridice", "languages": "Limba documentului"},
    "ru": {"skip": "Перейти к содержимому", "documents": "Юридические документы", "languages": "Язык документа"},
    "sr-cyrl": {"skip": "Пређи на садржај", "documents": "Правна документа", "languages": "Језик документа"},
    "sr-latn": {"skip": "Pređi na sadržaj", "documents": "Pravna dokumenta", "languages": "Jezik dokumenta"},
    "sk": {"skip": "Preskočiť na obsah", "documents": "Právne dokumenty", "languages": "Jazyk dokumentu"},
    "sl": {"skip": "Preskoči na vsebino", "documents": "Pravni dokumenti", "languages": "Jezik dokumenta"},
    "sv": {"skip": "Hoppa till innehållet", "documents": "Juridiska dokument", "languages": "Dokumentspråk"},
    "rif": {"skip": "Awiḍ ɣer ugbur", "documents": "Isɣawalen n lqanun", "languages": "Tutlayt n usebter"},
    "tr": {"skip": "İçeriğe atla", "documents": "Yasal belgeler", "languages": "Belge dili"},
    "uk": {"skip": "Перейти до вмісту", "documents": "Юридичні документи", "languages": "Мова документа"},
    "ur": {"skip": "مواد پر جائیں", "documents": "قانونی دستاویزات", "languages": "دستاویز کی زبان"},
    "ca-valencia": {"skip": "Ves al contingut", "documents": "Documents legals", "languages": "Idioma del document"},
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


def build_content(gasel_root: Path) -> tuple[dict[str, object], bytes]:
    legal_license = gasel_root / "app/src/main/res/raw/google_sans_flex_license.txt"
    if not legal_license.is_file():
        raise ValueError("Falta app/src/main/res/raw/google_sans_flex_license.txt")
    license_bytes = legal_license.read_bytes()
    license_hash = hashlib.sha256(license_bytes).hexdigest()
    locales: dict[str, object] = {}
    source_hashes: dict[str, str] = {}

    for lang, tag, folder in LANGUAGES:
        res = gasel_root / "app/src/main/res" / folder
        strings_path = res / "strings.xml"
        legal_path = res / "legal.xml"
        strings = read_android_strings(strings_path, lang)
        legal = read_android_strings(legal_path, lang)
        language_name = required(strings, LANGUAGE_NAME_KEYS[lang], lang)
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
        locale = {
            "tag": tag,
            "language_name": language_name,
            "navigation": NAV_LABELS[lang],
            "documents": docs,
        }
        if lang in {"ar", "ur"}:
            locale["direction"] = "rtl"
        locales[lang] = locale

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
        print(f"Imported {len(LANGUAGES)} legal catalogs and the complete Google Sans Flex license.")
        return 0

    problems = []
    if not content_path.is_file() or content_path.read_bytes() != expected_content:
        problems.append("content.json differs from the supplied Gasel checkout")
    if not license_path.is_file() or license_path.read_bytes() != license_bytes:
        problems.append("licenses/google-sans-flex.txt differs from the Android raw license")
    if problems:
        print("Import check failed:\n" + "\n".join(f"- {problem}" for problem in problems), file=sys.stderr)
        return 1
    print(f"Import check passed: {len(LANGUAGES)} legal catalogs and the complete license match Gasel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
