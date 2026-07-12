"""Script diagnostico temporaneo: perche' alcuni host rispondono 403/timeout
da GitHub Actions ma non da rete locale (vedi health-check 2026-07-12).

Testa piu' varianti (metodo, header) su un campione di host portalepa
(quasi tutti falliti nel run reale) e halley (quasi tutti OK, controllo),
e stampa gli header di risposta per identificare il vendor del WAF.

Da rimuovere a diagnosi conclusa — non e' parte della suite permanente.
"""

from __future__ import annotations

import ssl
import urllib.error
import urllib.request

_TIMEOUT = 10

_CAMPIONE = {
    "portalepa (fallito nel run reale)": "https://aliminusa.soluzionipa.it",
    "portalepa (fallito nel run reale) 2": "https://caltagirone.soluzionipa.it",
    "halley (OK nel run reale, controllo)": "https://cloud.halleysac.it",
    "halley (OK nel run reale, controllo) 2": "https://servizi.comune.mussomeli.cl.it",
}

_VARIANTI = {
    "A_head_minimal": {
        "metodo": "HEAD",
        "headers": {"User-Agent": "TALIA-healthcheck/1.0 (+https://github.com/, uso interno progetto civico)"},
    },
    "B_get_minimal": {
        "metodo": "GET",
        "headers": {"User-Agent": "TALIA-healthcheck/1.0 (+https://github.com/, uso interno progetto civico)"},
    },
    "C_get_browserlike": {
        "metodo": "GET",
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        },
    },
}


def _prova(url: str, metodo: str, headers: dict) -> None:
    req = urllib.request.Request(url, method=metodo, headers=headers)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ctx) as resp:
            interessanti = {
                k: v
                for k, v in resp.headers.items()
                if k.lower()
                in (
                    "server",
                    "cf-ray",
                    "x-akamai-request-id",
                    "x-iinfo",
                    "x-sucuri-id",
                    "x-cache",
                    "via",
                )
            }
            print(f"    OK {resp.status} — header rilevanti: {interessanti or '(nessuno)'}")
    except urllib.error.HTTPError as e:
        interessanti = {
            k: v
            for k, v in e.headers.items()
            if k.lower()
            in (
                "server",
                "cf-ray",
                "x-akamai-request-id",
                "x-iinfo",
                "x-sucuri-id",
                "x-cache",
                "via",
            )
        }
        corpo = ""
        try:
            corpo = e.read(300).decode("utf-8", errors="replace")
        except Exception:
            pass
        print(f"    HTTPError {e.code} — header: {interessanti or '(nessuno)'} — corpo[:300]: {corpo!r}")
    except Exception as e:  # noqa: BLE001
        print(f"    Errore: {e!r}")


def main() -> None:
    for nome_host, url in _CAMPIONE.items():
        print(f"\n=== {nome_host}: {url} ===")
        for nome_variante, cfg in _VARIANTI.items():
            print(f"  --- {nome_variante} ({cfg['metodo']}) ---")
            _prova(url, cfg["metodo"], cfg["headers"])


if __name__ == "__main__":
    main()
