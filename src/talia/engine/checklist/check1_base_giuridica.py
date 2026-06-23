"""TAL-6 — Check 1: base giuridica della revoca/annullamento.

Verifica che l'atto di autotutela dichiari la propria base giuridica
(art. 21-quinquies = revoca; art. 21-nonies = annullamento d'ufficio, L. 241/1990)
e che l'istituto citato sia coerente con la motivazione:

- **revoca** (21-quinquies): per sopravvenuti motivi di opportunità (*ex nunc*);
- **annullamento** (21-nonies): per illegittimità originaria (*ex tunc*).

Citare 21-quinquies parlando però di illegittimità (o viceversa) è un'incoerenza
→ red flag. La valutazione semantica è qui un'euristica su parole chiave; un
raffinamento LLM è previsto in TAL-11.
"""

from __future__ import annotations

import re
from enum import StrEnum

from ..fascicolo import ContestoFascicolo
from ..models import Citazione, Stato
from .base import Check, EsitoCheck, registra

_RIFERIMENTI = (
    "Art. 21-quinquies L. 241/1990 (revoca per sopravvenuti motivi di opportunità)",
    "Art. 21-nonies L. 241/1990 (annullamento d'ufficio per illegittimità originaria)",
    "Art. 21-octies L. 241/1990 (annullabilità per vizi formali — istituto distinto)",
    # imparzialità e commissioni
    "Art. 97 Cost. (imparzialità e buon andamento della pubblica amministrazione)",
    "Art. 6-bis L. 241/1990 (obbligo di astensione per conflitto di interessi nel procedimento)",
    "Art. 35-bis D.Lgs. 165/2001 "
    "(prevenzione conflitti di interesse nelle commissioni concorsuali e di gara)",
    "Art. 42 D.Lgs. 50/2016 (conflitto di interessi — gare indette prima del 2024)",
    "Art. 77 D.Lgs. 50/2016 (commissione giudicatrice: composizione, requisiti e incompatibilità)",
    # riservatezza / fuga di notizie
    "Art. 1 co. 1 lett. f) D.Lgs. 50/2016 (principio di riservatezza nelle procedure di gara)",
)

# Riconoscimento degli istituti. Il trattino è opzionale: negli atti reali si
# trova "21-quinquies", "21 quinquies" e perfino "21quinquies" (OCR).
_RE_REVOCA = re.compile(r"21\s*-?\s*quinquies", re.IGNORECASE)
_RE_ANNULLAMENTO = re.compile(r"21\s*-?\s*nonies", re.IGNORECASE)
# 21-octies = annullabilità per vizi di forma/procedura: istituto distinto da
# revoca e annullamento in autotutela; la sua presenza in un atto strutturato
# come "revoca" è una potenziale incoerenza giuridica.
_RE_OCTIES = re.compile(r"21\s*-?\s*octies", re.IGNORECASE)

# Parole spia della motivazione. In caso di segnali assenti l'esito è 🟡
# (da verificare), mai un giudizio netto. La valutazione semantica fine
# è demandata al check LLM (TAL-11).
_SEGNALI_REVOCA = (
    "sopravvenut",
    "opportunità",
    "mutamento della situazione",
    "nuova valutazione dell'interesse",
    "inopportun",
    "ragioni di merito",
    "interesse pubblico attuale",
)
_SEGNALI_ANNULLAMENTO = (
    # illegittimità generica
    "illegittim",
    "vizio",
    "violazione di legge",
    "eccesso di potere",
    "incompeten",
    "ripristino della legalità",
    "annullabil",
    "carenza di istruttoria",
    "difetto di motivazione",
    "contrario alla legge",
    # commissione: parzialità / terzietà
    # (art. 97 Cost.; art. 6-bis L. 241/1990; art. 35-bis D.Lgs. 165/2001;
    #  artt. 42 e 77 D.Lgs. 50/2016)
    "imparzialità",
    "terzietà",
    "incompatibilità",
    "conflitto di interess",
    "composizione della commissione",
    "commissario incompatibil",
    "carenza di requisit",
    "astensione",
    "ricusazion",
    "pregressi rapporti",
    "interessi personali",
    # riservatezza / fuga di notizie
    "fuga di notizie",
    "turbativa",
    "pregiudizio all'interesse",
    "pregiudizio grave",
    "riservatezza violat",
    "notizie riservat",
)


class Istituto(StrEnum):
    REVOCA = "revoca"
    ANNULLAMENTO = "annullamento"


class CheckBaseGiuridica(Check):
    id = "check-1"
    titolo = "Base giuridica della revoca/annullamento"
    riferimenti = _RIFERIMENTI

    def valuta(self, contesto: ContestoFascicolo) -> EsitoCheck:
        atto = contesto.atto_autotutela.testo
        testo = atto.testo

        match_revoca = _RE_REVOCA.search(testo)
        match_annullamento = _RE_ANNULLAMENTO.search(testo)
        match_octies = _RE_OCTIES.search(testo)

        # Caso 🔴: nessun riferimento normativo dell'autotutela.
        if not match_revoca and not match_annullamento:
            if match_octies:
                return self._esito(
                    Stato.ROSSO,
                    "Non è citata la base giuridica della revoca (art. 21-quinquies) "
                    "né dell'annullamento d'ufficio (art. 21-nonies). "
                    "L'atto richiama art. 21-octies (annullabilità per vizi di "
                    "forma/procedura), che è un istituto distinto e non costituisce "
                    "fondamento dell'autotutela discrezionale: verificare con un esperto "
                    "legale se il fondamento giuridico adottato sia corretto.",
                    [_cita(atto, match_octies)],
                )
            return self._esito(
                Stato.ROSSO,
                "Non è citata alcuna base giuridica dell'autotutela "
                "(art. 21-quinquies per la revoca o art. 21-nonies per l'annullamento "
                "d'ufficio). L'atto rimanda genericamente alla L. 241/1990 senza "
                "specificare l'articolo: la base giuridica è incompleta.",
            )

        # Caso 🟡: citati entrambi gli istituti → dichiarazione ambigua.
        if match_revoca and match_annullamento:
            citazioni = [
                _cita(atto, match_revoca),
                _cita(atto, match_annullamento),
            ]
            return self._esito(
                Stato.GIALLO,
                "L'atto cita sia la revoca (21-quinquies) sia l'annullamento "
                "(21-nonies): l'istituto dichiarato è ambiguo.",
                citazioni,
            )

        # Un solo istituto citato: ne verifico la coerenza con la motivazione.
        if match_revoca:
            istituto, match = Istituto.REVOCA, match_revoca
        else:
            istituto, match = Istituto.ANNULLAMENTO, match_annullamento

        n_revoca = _conta(testo, _SEGNALI_REVOCA)
        n_annull = _conta(testo, _SEGNALI_ANNULLAMENTO)
        citazione = _cita(atto, match)

        return self._valuta_coerenza(istituto, n_revoca, n_annull, citazione)

    def _valuta_coerenza(
        self,
        istituto: Istituto,
        n_revoca: int,
        n_annull: int,
        citazione: Citazione,
    ) -> EsitoCheck:
        # Segnali della motivazione "a favore" e "contro" l'istituto dichiarato.
        if istituto is Istituto.REVOCA:
            a_favore, contro = n_revoca, n_annull
            nome, atteso = "revoca (21-quinquies)", "sopravvenuti motivi di opportunità"
            opposto = "illegittimità originaria"
        else:
            a_favore, contro = n_annull, n_revoca
            nome = "annullamento d'ufficio (21-nonies)"
            atteso, opposto = "illegittimità originaria", "sopravvenuti motivi di opportunità"

        if contro > 0 and a_favore == 0:
            return self._esito(
                Stato.ROSSO,
                f"L'atto dichiara {nome} ma la motivazione richiama "
                f"{opposto}: istituto incoerente con la motivazione.",
                [citazione],
            )
        if a_favore > 0:
            return self._esito(
                Stato.VERDE,
                f"Base giuridica presente e coerente: {nome}, motivazione su {atteso}.",
                [citazione],
            )
        return self._esito(
            Stato.GIALLO,
            f"Base giuridica presente ({nome}) ma la motivazione non è chiaramente "
            "riconducibile all'istituto: da verificare.",
            [citazione],
        )


def _cita(atto, match: re.Match) -> Citazione:
    return Citazione(
        testo=atto.estratto(match.start(), match.end()),
        offset_inizio=match.start(),
        offset_fine=match.end(),
        pagina=atto.pagina_per_offset(match.start()),
    )


def _conta(testo: str, segnali: tuple[str, ...]) -> int:
    minuscolo = testo.lower()
    return sum(minuscolo.count(s) for s in segnali)


registra(CheckBaseGiuridica())
