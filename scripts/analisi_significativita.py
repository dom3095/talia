"""
Analisi della significatività delle estrazioni su un fascicolo reale.

Uso: python3 scripts/analisi_significativita.py data/samples/1/

Ogni run è identificata da un ID casuale e loggata in logs/analisi_<id>.log.
I log contengono dati personali — sono in .gitignore, non committare.
"""

import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from talia.engine.attori import estrai_attori, estrai_riferimenti_atti  # noqa: E402
from talia.engine.checklist.base import esegui_checklist  # noqa: E402
from talia.engine.entita import estrai_entita  # noqa: E402
from talia.engine.fascicolo import AttoAnalizzato, RuoloAtto  # noqa: E402
from talia.engine.firmatari import nome_normalizzato  # noqa: E402
from talia.engine.pdf_text import estrai_testo  # noqa: E402
from talia.modulo1_fascicolo.analisi import (  # noqa: E402
    classifica_ruolo,
    costruisci_contesto,
    punteggi_ruolo,
)


class _Tee:
    """Duplica stdout su un file di log mantenendo l'output a terminale."""

    def __init__(self, log_path: Path) -> None:
        self._stdout = sys.stdout
        self._file = log_path.open("w", encoding="utf-8")

    def write(self, obj: str) -> int:
        self._stdout.write(obj)
        self._file.write(obj)
        return len(obj)

    def flush(self) -> None:
        self._stdout.flush()
        self._file.flush()

    def close(self) -> None:
        sys.stdout = self._stdout
        self._file.close()


def _avvia_log() -> tuple[str, Path]:
    """Crea il file di log e redirige stdout su Tee. Restituisce (run_id, log_path)."""
    run_id = uuid.uuid4().hex[:12]
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"analisi_{run_id}.log"
    sys.stdout = _Tee(log_path)  # type: ignore[assignment]
    return run_id, log_path


def sezione(titolo: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {titolo}")
    print('=' * 60)


def sotto(titolo: str) -> None:
    print(f"\n--- {titolo} ---")


def analizza(cartella: Path) -> None:
    pdf_files = sorted(cartella.glob("*.pdf"))
    txt_files = sorted(cartella.glob("*.txt"))
    tutti_i_file = pdf_files + txt_files

    if not tutti_i_file:
        print("Nessun PDF o TXT trovato.")
        sys.exit(1)

    print(f"\nFascicolo: {cartella.resolve()}")
    print(f"File trovati: {len(tutti_i_file)}")
    for f in tutti_i_file:
        print(f"  • {f.name}")

    # ── 1. ESTRAZIONE TESTO ─────────────────────────────────────────────────
    sezione("1. ESTRAZIONE TESTO")
    atti_testo = []
    for f in tutti_i_file:
        try:
            atto = estrai_testo(f)
            n_char = len(atto.testo)
            n_pag = len(atto.pagine)
            print(f"\n  {f.name}")
            print(f"    pagine: {n_pag}  |  caratteri: {n_char}  |  fonte: {atto.fonte.value}")
            # Densità: char/pagina (bassa → potenziale OCR scarso)
            densita = n_char / n_pag if n_pag else 0
            flag = " ⚠️ densità bassa (OCR?)" if densita < 100 else ""
            print(f"    densità: {densita:.0f} char/pag{flag}")
            atti_testo.append((f.name, atto))
        except Exception as e:
            print(f"    ERRORE: {e}")

    # ── 2. CLASSIFICAZIONE RUOLI ────────────────────────────────────────────
    sezione("2. CLASSIFICAZIONE RUOLI")
    classificati = []
    for nome_file, atto in atti_testo:
        sc_aut, sc_orig = punteggi_ruolo(atto)
        ruolo = classifica_ruolo(atto)
        print(f"\n  {nome_file}")
        print(f"    autotutela: {sc_aut}  |  originario: {sc_orig}  |  → {ruolo.value}")
        classificati.append((nome_file, atto, ruolo))

    n_aut = sum(1 for _, _, r in classificati if r == RuoloAtto.AUTOTUTELA)
    n_orig = sum(1 for _, _, r in classificati if r == RuoloAtto.ORIGINARIO)
    n_sco = sum(1 for _, _, r in classificati if r == RuoloAtto.SCONOSCIUTO)
    print(f"\n  TOTALE → autotutela: {n_aut}  originario: {n_orig}  sconosciuto: {n_sco}")

    # ── 3. ENTITÀ ESTRATTE ──────────────────────────────────────────────────
    sezione("3. ENTITÀ ESTRATTE")
    tutti_entita = []
    for nome_file, atto, ruolo in classificati:
        entita = estrai_entita(atto)
        tutti_entita.append((nome_file, atto, ruolo, entita))
        print(f"\n  {nome_file}  [{ruolo.value}]")
        print(f"    date:      {len(entita.date)}")
        print(f"    importi:   {len(entita.importi)}")
        print(f"    CIG:       {len(entita.cig)}")
        print(f"    CUP:       {len(entita.cup)}")
        print(f"    norme:     {len(entita.norme)}")
        print(f"    firmatari: {len(entita.firmatari)}")

        if entita.norme:
            sotto("    Norme citate")
            for n in entita.norme:
                print(f"      · {n.valore}")

        if entita.firmatari:
            sotto("    Firmatari")
            for f in entita.firmatari:
                print(f"      · {f.valore}")

        if entita.importi:
            sotto("    Importi")
            for i in entita.importi:
                print(f"      · {i.valore} €  ('{i.testo_originale}')")

    # ── 4. ATTORI E RUOLI ISTITUZIONALI ─────────────────────────────────────
    sezione("4. ATTORI E RUOLI ISTITUZIONALI")
    ruolo_a_nomi: dict[str, list[str]] = defaultdict(list)
    tutti_attori_per_atto = []

    for nome_file, atto, ruolo, _entita in tutti_entita:
        attori = estrai_attori(atto)
        tutti_attori_per_atto.append((nome_file, attori))
        print(f"\n  {nome_file}  [{ruolo.value}]")
        if attori:
            for a in attori:
                nome_disp = a.nome if a.nome else "(anonimo)"
                print(f"    · {a.ruolo:<35} {nome_disp}  [pag. {a.pagina}]")
                if a.nome:
                    ruolo_a_nomi[a.ruolo].append(a.nome)
        else:
            print("    (nessun attore trovato)")

    # Cross-atto: chi appare in più atti?
    sotto("RIEPILOGO ATTORI CROSS-ATTO")
    # Raggruppa per frozenset nome (gestisce ordine invertito cognome/nome e nomi parziali).
    fs_a_nome: dict[frozenset, str] = {}   # rappresentante canonico (nome più lungo)
    fs_a_ruoli: dict[frozenset, set[str]] = defaultdict(set)
    fs_a_conti: dict[frozenset, int] = Counter()

    for _nome_file, attori in tutti_attori_per_atto:
        for a in attori:
            if not a.nome:
                continue
            fs = nome_normalizzato(a.nome)
            fs_a_conti[fs] += 1
            fs_a_ruoli[fs].add(a.ruolo)
            # Mantieni il nome più lungo come rappresentante del gruppo
            if fs not in fs_a_nome or len(a.nome) > len(fs_a_nome[fs]):
                fs_a_nome[fs] = a.nome

    for fs, cnt in sorted(fs_a_conti.items(), key=lambda x: -x[1]):
        nome = fs_a_nome[fs]
        ruoli_list = ", ".join(sorted(fs_a_ruoli[fs]))
        print(f"  [{cnt} atti] {nome}  →  {ruoli_list}")

    # Segnala chi ha ruoli multipli (potenziale conflitto di interessi)
    multi_ruolo = {fs_a_nome[fs]: r for fs, r in fs_a_ruoli.items() if len(r) > 1}
    if multi_ruolo:
        print("\n  ⚠️  RUOLI MULTIPLI (stessa persona, ruoli diversi cross-atto):")
        for nome, ruoli in sorted(multi_ruolo.items(), key=lambda x: -len(x[1])):
            print(f"    · {nome}  →  {', '.join(sorted(ruoli))}")

    # ── 5. RIFERIMENTI AD ATTI ──────────────────────────────────────────────
    sezione("5. RIFERIMENTI AD ATTI (CATENA PROCEDURALE)")
    chiave_a_atti: dict[str, list[str]] = defaultdict(list)
    tutti_rif_per_atto = []

    for nome_file, atto, ruolo, _entita in tutti_entita:
        rif = estrai_riferimenti_atti(atto)
        tutti_rif_per_atto.append((nome_file, rif))
        print(f"\n  {nome_file}  [{ruolo.value}]")
        if rif:
            for r in rif[:10]:  # prime 10 per leggibilità
                print(f"    · {r.testo_originale.strip()[:80]}  [pag. {r.pagina}]")
            if len(rif) > 10:
                print(f"    ... e altri {len(rif)-10}")
            for r in rif:
                chiave_a_atti[r.chiave].append(nome_file)
        else:
            print("    (nessun riferimento trovato)")

    sotto("RIFERIMENTI RICORRENTI CROSS-ATTO (catena)")
    for chiave, file_list in sorted(chiave_a_atti.items(), key=lambda x: -len(x[1])):
        if len(file_list) > 1:
            print(f"  [{len(file_list)}x] {chiave}")
            for f in file_list:
                print(f"      ← {f}")

    # ── 6. CHECKLIST ────────────────────────────────────────────────────────
    sezione("6. CHECKLIST")
    atti_analizzati = [
        AttoAnalizzato.da_testo(atto, ruolo=ruolo, etichetta=nome_file)
        for nome_file, atto, ruolo, entita in tutti_entita
    ]
    contesto = costruisci_contesto(atti_analizzati)

    if contesto.atto_autotutela:
        print(f"\n  atto autotutela: {contesto.atto_autotutela.etichetta}")
    else:
        print("\n  ⚠️  nessun atto autotutela identificato → checklist non applicabile")
        return

    if contesto.atto_originario:
        print(f"  atto originario: {contesto.atto_originario.etichetta}")
    else:
        print("  atto originario: (non trovato)")

    esiti = esegui_checklist(contesto)
    print()
    for esito in esiti:
        print(f"  {esito.stato.emoji}  [{esito.id}] {esito.titolo}")
        print(f"       {esito.spiegazione}")
        for cit in esito.citazioni:
            estratto = cit.testo[:120].replace("\n", " ").strip()
            print(f"       📎 pag.{cit.pagina}: «{estratto}»")

    # ── 7. RIEPILOGO SIGNIFICATIVITÀ ────────────────────────────────────────
    sezione("7. RIEPILOGO SIGNIFICATIVITÀ")

    # Conta entità totali
    tot_date = sum(len(e.date) for _, _, _, e in tutti_entita)
    tot_norme = sum(len(e.norme) for _, _, _, e in tutti_entita)
    tot_firmatari = sum(len(e.firmatari) for _, _, _, e in tutti_entita)
    tot_importi = sum(len(e.importi) for _, _, _, e in tutti_entita)
    tot_cig = sum(len(e.cig) for _, _, _, e in tutti_entita)
    tot_attori = sum(len(a) for _, a in tutti_attori_per_atto)
    n_persone_uniche = len(fs_a_nome)
    tot_rif = sum(len(r) for _, r in tutti_rif_per_atto)
    rif_ricorrenti = sum(1 for v in chiave_a_atti.values() if len(v) > 1)

    from talia.engine.models import Stato
    rossi = [e for e in esiti if e.stato is Stato.ROSSO]
    gialli = [e for e in esiti if e.stato is Stato.GIALLO]
    verdi = [e for e in esiti if e.stato is Stato.VERDE]
    na = [e for e in esiti if e.stato is Stato.NON_APPLICABILE]

    print(f"""
  ENTITÀ
    date:           {tot_date:>3}
    norme citate:   {tot_norme:>3}
    firmatari:      {tot_firmatari:>3}
    importi:        {tot_importi:>3}
    CIG:            {tot_cig:>3}

  ATTORI/PROCEDIMENTI
    attori trovati: {tot_attori:>3}  (menzioni totali)
    persone uniche: {n_persone_uniche:>3}  (dopo dedup nome/cognome invertito)
    ruoli multipli: {len(multi_ruolo):>3}  {"⚠️" if multi_ruolo else ""}
    rif. ad atti:   {tot_rif:>3}
    rif. ricorrenti:{rif_ricorrenti:>3}  (appaiono in ≥2 atti → catena tracciabile)

  CHECKLIST
    🔴 rossi:   {len(rossi)}
    🟡 gialli:  {len(gialli)}
    🟢 verdi:   {len(verdi)}
    ⚪ N/A:     {len(na)}
""")

    # Sintesi qualitativa
    print("  SINTESI:")
    if n_aut == 0:
        print("  ✗ Nessun atto autotutela → pipeline non attivabile.")
    elif n_aut == 1:
        print("  ✓ Atto autotutela identificato correttamente.")
    else:
        print(f"  ~ {n_aut} candidati autotutela → ambiguità (selezionato per punteggio max).")

    if rif_ricorrenti > 0:
        print(f"  ✓ Catena procedurale tracciabile ({rif_ricorrenti} riferimenti cross-atto).")
    else:
        print("  ~ Catena procedurale non rilevata (rif. cross-atto assenti).")

    if multi_ruolo:
        print(
            f"  ⚠️  {len(multi_ruolo)} persona/e con ruoli multipli"
            " → potenziale conflitto da approfondire."
        )

    if rossi:
        print(f"  ⚠️  {len(rossi)} check rossi → segnalazioni concrete da verificare:")
        for e in rossi:
            print(f"       · [{e.id}] {e.titolo}")

    if tot_cig == 0:
        print("  ~ CIG assente: procedura interna (non appalto), atteso.")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Uso: python3 {sys.argv[0]} <cartella_fascicolo>")
        sys.exit(1)
    run_id, log_path = _avvia_log()
    print(f"run_id: {run_id}  |  log: {log_path}")
    try:
        analizza(Path(sys.argv[1]))
    finally:
        if isinstance(sys.stdout, _Tee):
            sys.stdout.close()
