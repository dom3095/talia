"""
Scarica il corpus normativo TALIA da Normattiva (norme italiane) e EUR-Lex (norme UE).
Salva i testi come file Markdown in data/corpus_normativo/.

Uso:
    python scripts/download_corpus_normativo.py
    python scripts/download_corpus_normativo.py --solo nazionale
    python scripts/download_corpus_normativo.py --solo ue
"""

import argparse
import re
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent / "data" / "corpus_normativo"
TODAY = date.today().isoformat()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TALIA-corpus-bot/1.0; open source civic tool)",
    "Accept-Language": "it-IT,it;q=0.9",
}

# ---------------------------------------------------------------------------
# Catalogo norme
# ---------------------------------------------------------------------------

NORME_NAZIONALI = [
    {
        "id": "l-241-1990",
        "titolo": "L. 7 agosto 1990, n. 241 — Procedimento amministrativo e accesso ai documenti",
        "urn": "urn:nir:stato:legge:1990-08-07;241",
        "area": "nazionale",
        "rilevanza": "fulcro checklist M1 (revoca, annullamento, motivazione, accesso)",
    },
    {
        "id": "dlgs-33-2013",
        "titolo": "D.Lgs. 14 marzo 2013, n. 33 — Trasparenza (Decreto Trasparenza)",
        "urn": "urn:nir:stato:decreto.legislativo:2013-03-14;33",
        "area": "nazionale",
        "rilevanza": (
            "obblighi pubblicazione albo pretorio, FOIA (art. 5-5bis),"
            " limite dati personali (art. 7-bis)"
        ),
    },
    {
        "id": "l-190-2012",
        "titolo": "L. 6 novembre 2012, n. 190 — Anticorruzione (Legge Severino)",
        "urn": "urn:nir:stato:legge:2012-11-06;190",
        "area": "nazionale",
        "rilevanza": "PTPCT, misure prevenzione corruzione, vigilanza ANAC",
    },
    {
        "id": "dlgs-36-2023",
        "titolo": "D.Lgs. 31 marzo 2023, n. 36 — Codice dei contratti pubblici",
        "urn": "urn:nir:stato:decreto.legislativo:2023-03-31;36",
        "area": "nazionale",
        "rilevanza": "fonte primaria red flags M2: frazionamento, soglie, procedure sotto soglia",
    },
    {
        "id": "dlgs-39-2013",
        "titolo": "D.Lgs. 8 aprile 2013, n. 39 — Inconferibilità e incompatibilità incarichi",
        "urn": "urn:nir:stato:decreto.legislativo:2013-04-08;39",
        "area": "nazionale",
        "rilevanza": "check firmatari M1: conflitto di interessi, auto-annullamento",
    },
    {
        "id": "dlgs-267-2000",
        "titolo": "D.Lgs. 18 agosto 2000, n. 267 — TUEL (Testo Unico Enti Locali)",
        "urn": "urn:nir:stato:decreto.legislativo:2000-08-18;267",
        "area": "nazionale",
        "rilevanza": "struttura organi comuni, funzioni dirigenziali, delibere",
    },
    {
        "id": "dlgs-159-2011",
        "titolo": "D.Lgs. 6 settembre 2011, n. 159 — Codice Antimafia",
        "urn": "urn:nir:stato:decreto.legislativo:2011-09-06;159",
        "area": "nazionale",
        "rilevanza": "interdittive antimafia, white list, comunicazioni prefettizie",
    },
    {
        "id": "dlgs-196-2003",
        "titolo": "D.Lgs. 30 giugno 2003, n. 196 — Codice Privacy (come mod. da D.Lgs. 101/2018)",
        "urn": "urn:nir:stato:decreto.legislativo:2003-06-30;196",
        "area": "nazionale",
        "rilevanza": (
            "trattamento dati PA, base giuridica art. 2-ter,"
            " categorie particolari art. 2-sexies"
        ),
    },
    {
        "id": "dlgs-165-2001",
        "titolo": "D.Lgs. 30 marzo 2001, n. 165 — T.U. Pubblico Impiego",
        "urn": "urn:nir:stato:decreto.legislativo:2001-03-30;165",
        "area": "nazionale",
        "rilevanza": "concorsi pubblici art. 35, funzioni dirigenziali, incarichi art. 53",
    },
    {
        "id": "dlgs-175-2016",
        "titolo": "D.Lgs. 19 agosto 2016, n. 175 — TUSP (Società Partecipate)",
        "urn": "urn:nir:stato:decreto.legislativo:2016-08-19;175",
        "area": "nazionale",
        "rilevanza": "affidamenti in house, partecipate comunali, controllo analogo",
    },
    {
        "id": "l-287-1990",
        "titolo": "L. 10 ottobre 1990, n. 287 — Tutela della concorrenza (Antitrust)",
        "urn": "urn:nir:stato:legge:1990-10-10;287",
        "area": "nazionale",
        "rilevanza": "bid rigging (art. 2), concentrazione aggiudicatario",
    },
    {
        "id": "dlgs-24-2023",
        "titolo": "D.Lgs. 10 marzo 2023, n. 24 — Whistleblowing",
        "urn": "urn:nir:stato:decreto.legislativo:2023-03-10;24",
        "area": "nazionale",
        "rilevanza": "canale segnalazioni, tutela segnalante, obblighi enti",
    },
]

NORME_UE = [
    {
        "id": "gdpr-679-2016",
        "titolo": "Reg. UE 2016/679 (GDPR) — Protezione dati personali",
        "celex": "32016R0679",
        "area": "ue",
        "rilevanza": (
            "minimizzazione dati negli output TALIA, anonimizzazione,"
            " base giuridica interesse pubblico"
        ),
    },
    {
        "id": "dir-2014-24-ue",
        "titolo": "Dir. UE 2014/24/UE — Appalti pubblici sopra soglia",
        "celex": "32014L0024",
        "area": "ue",
        "rilevanza": "principi parità trattamento, trasparenza, proporzionalità nelle gare",
    },
    {
        "id": "dir-2019-1024-ue",
        "titolo": "Dir. UE 2019/1024 — Dati aperti e riutilizzo settore pubblico (PSI)",
        "celex": "32019L1024",
        "area": "ue",
        "rilevanza": "base legale per riutilizzo open data PA, licenze, formati aperti",
    },
    {
        "id": "dir-2019-1937-ue",
        "titolo": "Dir. UE 2019/1937 — Whistleblowing (segnalazioni illeciti)",
        "celex": "32019L1937",
        "area": "ue",
        "rilevanza": "tutela segnalanti, recepita con D.Lgs. 24/2023",
    },
]

# ---------------------------------------------------------------------------
# Normattiva helpers
# ---------------------------------------------------------------------------

NAV_NOISE = re.compile(
    r'^(ITA|ENG|HOME|MENU|CERCA(?: AVANZATA)?|COOKIE|PRIVACY|CONTATTI|'
    r'ACCESSIBILITÀ|FAQ|NORMATTIVA|POLIGRAFICO|IPZS|STAMPA|CONDIVIDI|'
    r'TORNA IN CIMA|CARICA|LOADING|\d+)$',
    re.I,
)


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "noscript", "svg", "button", "form", "aside"]):
        tag.decompose()
    body = soup.find("body") or soup
    lines = [line.strip() for line in body.get_text(separator="\n").splitlines()]
    lines = [line for line in lines if line and not NAV_NOISE.match(line)]
    return "\n".join(lines)


def _get_normattiva_params(session: requests.Session, urn: str) -> tuple[str, str] | None:
    """Ritorna (dataPubblicazioneGazzetta, codiceRedazionale) per un URN."""
    url = f"https://www.normattiva.it/uri-res/N2Ls?{urn}"
    r = session.get(url, timeout=30)
    if r.status_code != 200:
        return None
    # Cerca pattern nel JS della pagina
    m = re.search(
        r'dataPubblicazioneGazzetta[=&amp;]+(\d{4}-\d{2}-\d{2}).*?codiceRedazionale[=&amp;]+([0-9A-Z]+)',
        r.text, re.S
    )
    if m:
        return m.group(1), m.group(2)
    # Fallback: cerca nel link attoCompleto
    m2 = re.search(
        r'attoCompleto\?atto\.dataPubblicazioneGazzetta=(\d{4}-\d{2}-\d{2})&atto\.codiceRedazionale=([0-9A-Z]+)',
        r.text
    )
    if m2:
        return m2.group(1), m2.group(2)
    return None


def download_norma_italiana(session: requests.Session, norma: dict, out_dir: Path) -> bool:
    out_file = out_dir / "nazionale" / f"{norma['id']}.md"
    if out_file.exists():
        print(f"  [skip] {norma['id']} già presente")
        return True

    print(f"  Fetching params: {norma['urn']}")
    params = _get_normattiva_params(session, norma["urn"])
    if not params:
        print(f"  [ERR] parametri non trovati per {norma['id']}")
        return False

    data_gu, codice = params
    print(f"  → dataPubblicazioneGazzetta={data_gu}, codiceRedazionale={codice}")

    # Prima visita la pagina per impostare i cookie
    session.get(f"https://www.normattiva.it/uri-res/N2Ls?{norma['urn']}", timeout=20)
    time.sleep(1)

    url_full = (
        f"https://www.normattiva.it/esporta/attoCompleto"
        f"?atto.dataPubblicazioneGazzetta={data_gu}&atto.codiceRedazionale={codice}"
    )
    r = session.get(url_full, timeout=90)
    if r.status_code != 200 or len(r.text) < 5000:
        print(f"  [ERR] download fallito ({r.status_code}, {len(r.text)} bytes)")
        return False

    testo = _clean_text(r.text)
    md = _build_md_nazionale(norma, testo, data_gu, codice)
    out_file.write_text(md, encoding="utf-8")
    print(f"  [OK] salvato {out_file.name} ({len(testo):,} chars)")
    return True


def _build_md_nazionale(norma: dict, testo: str, data_gu: str, codice: str) -> str:
    return f"""---
id: {norma['id']}
titolo: "{norma['titolo']}"
fonte: Normattiva
url_fonte: "https://www.normattiva.it/uri-res/N2Ls?{norma['urn']}"
codice_gu: {codice}
data_gu: {data_gu}
rilevanza_talia: "{norma['rilevanza']}"
scaricato: {TODAY}
vigente_al: {TODAY}
---

# {norma['titolo']}

> Fonte: Normattiva — testo vigente al {TODAY}
> Codice GU: {codice} | Pubblicato: {data_gu}
> Rilevanza TALIA: {norma['rilevanza']}

---

{testo}
"""


# ---------------------------------------------------------------------------
# EUR-Lex helpers
# ---------------------------------------------------------------------------

def download_norma_ue(session: requests.Session, norma: dict, out_dir: Path) -> bool:
    out_file = out_dir / "ue" / f"{norma['id']}.md"
    if out_file.exists():
        print(f"  [skip] {norma['id']} già presente")
        return True

    url = f"https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:{norma['celex']}"
    print(f"  Fetching: {url}")
    r = session.get(url, timeout=60)
    if r.status_code != 200 or len(r.text) < 5000:
        print(f"  [ERR] {r.status_code}, {len(r.text)} bytes")
        return False

    testo = _clean_text(r.text)

    # Rimuovi righe di navigazione EUR-Lex
    lex_noise = re.compile(
        r'^(EUR-Lex|Eur-Lex|European Union|Login|Register|Cookies|Help|'
        r'Feedback|RSS|CELEX|ELI|Documento|Autenticazione|Cerca|Avviso legale).*',
        re.I
    )
    lines = [line for line in testo.splitlines() if not lex_noise.match(line)]
    testo = "\n".join(lines)

    md = _build_md_ue(norma, testo, url)
    out_file.write_text(md, encoding="utf-8")
    print(f"  [OK] salvato {out_file.name} ({len(testo):,} chars)")
    return True


def _build_md_ue(norma: dict, testo: str, url: str) -> str:
    return f"""---
id: {norma['id']}
titolo: "{norma['titolo']}"
fonte: EUR-Lex
celex: {norma['celex']}
url_fonte: "{url}"
rilevanza_talia: "{norma['rilevanza']}"
scaricato: {TODAY}
---

# {norma['titolo']}

> Fonte: EUR-Lex — testo in lingua italiana
> CELEX: {norma['celex']}
> Rilevanza TALIA: {norma['rilevanza']}

---

{testo}
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scarica corpus normativo TALIA")
    parser.add_argument("--solo", choices=["nazionale", "ue"], help="Scarica solo una categoria")
    args = parser.parse_args()

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "nazionale").mkdir(exist_ok=True)
    (BASE_DIR / "ue").mkdir(exist_ok=True)

    s = requests.Session()
    s.headers.update(HEADERS)

    # Warm-up sessione Normattiva
    s.get("https://www.normattiva.it/", timeout=15)

    ok = err = 0

    if args.solo != "ue":
        print("\n=== NORME NAZIONALI (Normattiva) ===")
        for norma in NORME_NAZIONALI:
            print(f"\n→ {norma['titolo'][:60]}")
            if download_norma_italiana(s, norma, BASE_DIR):
                ok += 1
            else:
                err += 1
            time.sleep(2)  # cortesia verso il server

    if args.solo != "nazionale":
        print("\n=== NORME UE (EUR-Lex) ===")
        for norma in NORME_UE:
            print(f"\n→ {norma['titolo'][:60]}")
            if download_norma_ue(s, norma, BASE_DIR):
                ok += 1
            else:
                err += 1
            time.sleep(1)

    print(f"\n{'='*50}")
    print(f"Completato: {ok} OK, {err} errori")
    print(f"Corpus in: {BASE_DIR}")


if __name__ == "__main__":
    main()
