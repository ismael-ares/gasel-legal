# Gasel Legal

This repository contains the public privacy policy, legal notice and open-source notices for Gasel. The site is static HTML and CSS: reading a document does not require JavaScript, a build service, a CDN or a network request for fonts. Its import, render and validation scripts use Python 3.10 or newer and the standard library.

The one hundred forty-one public routes are generated from Gasel Android's forty-seven localized `legal.xml` and `strings.xml` catalogs. Each language has one complete page at `privacy[-locale].html`, with anchored summary, privacy, legal notice and open-source sections. The old `legal[-locale].html` and `licenses[-locale].html` URLs remain as visible, same-language redirects to their matching sections. `content.json` records every imported legal string and stable SHA-256 hashes for the source catalogs and bundled license files. The HTML files are generated output; do not edit their text or navigation by hand.

## Update content from Gasel

Pass the actual Android repository path explicitly. The two repositories do not need to be siblings.

```bash
python3 scripts/import_gasel_legal.py --gasel-root /path/to/gasel --write
python3 scripts/render_site.py --write
python3 scripts/import_gasel_legal.py --gasel-root /path/to/gasel --check
python3 scripts/render_site.py --check
python3 check_site.py
python3 -m unittest discover -s tests
git diff --check
```

Update the legal text and document titles in Gasel's localized resources first. The importer reads XML with `xml.etree.ElementTree`, checks every required language and key, preserves UTF-8 text, and decodes only the Android escapes it supports. It stops with the language and missing key rather than silently copying Spanish into an incomplete translation. The ordered section keys are kept in `scripts/import_gasel_legal.py`; review them against `LegalDocument` in Gasel when that enum changes.

Apache 2.0, flag-icons MIT, Google Sans Flex OFL and Material Kolor MIT license texts are copied byte for byte from Android's raw resources. The import check confirms their bytes and SHA-256 values. Do not translate, shorten or edit those texts.

## Change layout and presentation

Change `scripts/render_site.py` for document structure or navigation, then run `python3 scripts/render_site.py --write`. Change `styles.css` for presentation. The renderer escapes all imported content; the only generated inline links are email addresses already present in the privacy contact section. Do not put HTML markup in a legal string.

All paths used by `LegalDocument.webUrl` remain stable. The language picker retains the current section and language names come from Gasel's localized catalogs in their stable order. Arabic and Urdu declare right-to-left direction while English license text and email links remain left-to-right. `index.html` remains a direct Spanish fallback and never redirects based on the browser language.

The shared `styles.css` uses the Gasel palette in light and dark system themes. It uses system fonts, supports reflow at 320 CSS pixels and 200% zoom, and keeps complete license texts in the open-source section. Static navigation links and legacy routes work without JavaScript; `site.js` enhances theme transitions, active-section state and language filtering. `check_site.py` parses the pages locally, checks routes, anchors, language metadata, assets, source license bytes and deterministic output; it does not contact the network.

## Brand assets

`gasel-logo.png` is a 384 × 384 transparent crop derived from Gasel's official Android splash asset at `app/src/main/res/drawable-nodpi/gasel_logo_splash.png`; `favicon.png` is the corresponding 64 × 64 derivation. The artwork is not redrawn. To recreate them, crop the source PNG to its non-transparent alpha bounds, scale the crop with Lanczos into a transparent square (384 px with 18 px inset for the header, 64 px with 4 px inset for the favicon), and center it. The source PNG has transparent padding, so keep the crop step; do not enlarge the small legacy website logo.

## Local preview

Serve the repository root and open the URL in a browser:

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

Review representative Spanish, Arabic, Dutch, Japanese and German pages in light and dark modes at 320, 390, 768 and 1280 CSS pixels. Check keyboard focus, 200% zoom, print layout, and the full license on a licenses page. Stop the temporary server when the review is complete.

GitHub Pages publication is configured outside this content workflow. Do not publish by pushing this branch or enabling Pages as part of a local content change; verify the deployed pages separately after an explicitly authorized deployment.
