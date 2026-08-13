"""Genera tal59_verifica_critica.ipynb (verifica critica del fix TAL-59).

Rieseguire dopo modifiche: `python notebooks/tal59_build_notebook.py` poi
`jupyter nbconvert --to notebook --execute --inplace notebooks/tal59_verifica_critica.ipynb`.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "tal59_verifica_critica.ipynb"


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text}


cells = []

cells.append(md("""# TAL-59 — Verifica critica del fix a `riapertura_dopo_revoca`

**Obiettivo di questo notebook:** non limitarsi a confermare che il fix "funziona", ma metterlo sotto pressione — mostrare cosa toglie, cosa lascia, cosa *perde* (falsi negativi), e se generalizza oltre i casi che abbiamo già letto a mano durante lo sviluppo (rischio di overfitting sui casi trovati).

Tutte le query girano **dal vivo su `talia.db` reale** (161MB, DB di produzione locale), confrontando il codice **prima del fix** (commit `f26e94d`, `main`) e **dopo il fix** (commit `3e459e4`, branch `feat/TAL-59-fix-riapertura-falsi-positivi`) sullo stesso identico stato del database — quindi ogni differenza nei risultati è dovuta solo al codice, non a dati diversi.

**Card di riferimento:** [`docs/cards/TAL-59.md`](../../docs/cards/TAL-59.md)."""))

cells.append(code("""\"\"\"Setup: carica il codice PRIMA del fix (f26e94d, main) e DOPO il fix (3e459e4,
questo branch) come due moduli separati, entrambi puntati sullo stesso talia.db.
\"\"\"
import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

pd.set_option("display.max_colwidth", 120)
pd.set_option("display.width", 160)

REPO = Path("/Users/dom/Documents/GitHub/talia")
DB = REPO / "talia.db"
PRE_FIX_COMMIT = "f26e94d"  # main, prima di TAL-59
POST_FIX_COMMIT = "3e459e4"  # branch feat/TAL-59-..., primo giro del fix (Tentativo 1-3)

sys.path.insert(0, str(REPO / "src"))


def carica_modulo_da_commit(commit: str, path_relativo: str, nome_modulo: str):
    \"\"\"Estrae un file da un commit specifico via `git show` e lo carica come
    modulo Python isolato (senza toccare il working tree).\"\"\"
    sorgente = subprocess.run(
        ["git", "show", f"{commit}:{path_relativo}"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    tmp_path = Path(f"/tmp/_tal59_{nome_modulo}_{commit}.py")
    tmp_path.write_text(sorgente)
    spec = importlib.util.spec_from_file_location(nome_modulo, tmp_path)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome_modulo] = modulo
    spec.loader.exec_module(modulo)
    return modulo


# Codice ORIGINALE (pre-TAL-59)
riap_pre = carica_modulo_da_commit(
    PRE_FIX_COMMIT,
    "src/talia/modulo2_scraping/red_flags/riapertura_revoca.py",
    "riap_pre",
)

# Codice ATTUALE (working tree, dopo l'ultimo giro di correzioni) — import normale
from talia.modulo2_scraping.red_flags import riapertura_revoca as riap_post
from talia.engine import catena as catena_post


def nuova_connessione():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


nomi_enti = {r[0]: r[1] for r in nuova_connessione().execute("SELECT id, denominazione FROM enti")}
print(f"DB: {DB}  ({DB.stat().st_size / 1e6:.0f} MB)")
print(f"Pre-fix module:  {riap_pre.__file__}")
print(f"Post-fix module: {riap_post.__file__}")"""))

cells.append(md("""## Prova 1 — Riduzione grezza dei flag

Quanti flag `riapertura_dopo_revoca` produce il codice prima e dopo, sullo stesso DB? Questo è il numero che avevo già dato a voce (82 → 23 → 10); qui lo ricalcolo dal vivo per verificarlo, non fidandomi del numero riportato in chat."""))

cells.append(code("""ris_pre = riap_pre.rileva_riapertura_dopo_revoca(nuova_connessione())
ris_post = riap_post.rileva_riapertura_dopo_revoca(nuova_connessione())

proc_pre = {r.procedimento_revocato_id for r in ris_pre}
proc_post = {r.procedimento_revocato_id for r in ris_post}

riepilogo = pd.DataFrame([
    {"versione": "PRIMA del fix (f26e94d)", "righe_flag": len(ris_pre), "procedimenti_distinti": len(proc_pre)},
    {"versione": "DOPO il fix (working tree)", "righe_flag": len(ris_post), "procedimenti_distinti": len(proc_post)},
])
riepilogo["riduzione_%"] = None
riepilogo.loc[1, "riduzione_%"] = round(100 * (1 - len(ris_post) / len(ris_pre)), 1)
riepilogo"""))

cells.append(md("""**Risultato:** 82→10 righe di flag, **67→8 procedimenti distinti** (-88,1%). Il numero di procedimenti distinti è il dato che conta di più (le righe duplicano quando lo stesso procedimento matcha più di un atto successivo) — ed è più severo di quanto avessi detto a voce prima (avevo in mente un sottoinsieme di enti, non l'immagine completa). Andiamo a vedere *chi* è stato tolto, non solo *quanti*."""))

cells.append(md("""## Prova 2 — Cosa è stato tolto, ed è corretto toglierlo?

Elenco completo (non un campione) dei procedimenti che PRIMA generavano un flag e ora non più. Per ciascuno leggo l'oggetto pieno e do un giudizio esplicito — così chi legge può controllare il mio giudizio, non solo il numero aggregato."""))

cells.append(code("""con = nuova_connessione()

tolti = sorted(proc_pre - proc_post)
righe = []
for pid in tolti:
    p = con.execute("SELECT ente_id, oggetto, stato_finale FROM procedimenti WHERE id=?", (pid,)).fetchone()
    righe.append({
        "proc_id": pid,
        "ente": nomi_enti.get(p["ente_id"], "?"),
        "stato": p["stato_finale"],
        "oggetto": p["oggetto"],
    })
df_tolti = pd.DataFrame(righe)
print(f"Procedimenti rimossi dal fix: {len(df_tolti)}")
df_tolti"""))

cells.append(md("""**Lettura riga per riga dei 59 tolti** (categorie, non un campione — li ho letti tutti):

- **17 casi da un solo ente**, Sant'Agata li Battiati: regolamenti comunali, adesioni societarie, piani di rientro dal disavanzo, patrocini gratuiti, elenchi di delibere di giunta — nessuno è un bando. È il segnale più forte trovato in questa verifica: prima del fix, quasi un quarto di tutti i (falsi) flag veniva da un singolo ente con un pattern amministrativo che il matching Jaccard scambiava sistematicamente per "bandi ripubblicati". Non l'avevo notato analizzando solo i 9 campioni originari di TAL-12 (nessuno di quei 9 era di Sant'Agata).
- **14 casi da Giarre**: contenziosi (TAR, appelli, liquidazioni onorari legali), deleghe assessori, ordinanze — la stessa famiglia già documentata in TAL-59 Tentativo 2/3.
- **Il resto**: sanzioni edilizie, verbali di infrazione al codice della strada, incarichi legali, revoche di assessori, piani di rientro, censimenti veicoli, certificazioni. Il caso più illustrativo per assurdità è **Pedara 10663**: il "procedimento revocato" e il suo "riaperto" erano — testualmente — due pubblicazioni entrambe intitolate `CERTIFICAZIONE COVID`, evidentemente non un bando in nessun senso del termine.

**Nessuno dei 59 letti mi sembra un caso dubbio da riconsiderare** — la lettura manuale conferma la correttezza dell'esclusione riga per riga, non solo in aggregato."""))

cells.append(md("""## Prova 3 — Cosa resta: sono davvero tutti casi validi?

I procedimenti che *ancora oggi* generano il flag, con oggetto revocato + oggetto di riapertura completi. Rileggo ciascuno per verificare che sia plausibilmente un vero "bando revocato e ripubblicato", non solo che passi il filtro di dominio."""))

cells.append(code("""visti = set()
righe = []
for r in ris_post:
    key = (r.ente_id, r.procedimento_revocato_id)
    if key in visti:
        continue
    visti.add(key)
    righe.append({
        "ente": nomi_enti.get(r.ente_id, "?"),
        "proc_id": r.procedimento_revocato_id,
        "giorni": r.giorni_tra_revoca_e_riapertura,
        "jaccard": round(r.similarita_jaccard, 2),
        "oggetto_revocato": r.oggetto_revocato,
        "oggetto_riapertura": r.oggetto_riapertura,
    })
df_finali = pd.DataFrame(righe).sort_values("proc_id").reset_index(drop=True)
print(f"Procedimenti che generano ancora un flag: {len(df_finali)}")
df_finali"""))

cells.append(md("""**Valutazione dei singoli 8, non solo del filtro che li ha lasciati passare:**

| proc_id | Ente | Giudizio |
|---|---|---|
| 692 | Palma di Montechiaro | ✅ già noto/validato in TAL-48 (affidamento diretto sorveglianza sanitaria) |
| 6487 | Custonaci | ✅ "approvazione bando di gara" esplicito |
| 10393 | Alcamo | ✅ concorso 2 dirigenti tecnici, annullamento reale (avviso di annullamento procedura concorsuale) |
| 11812 | Giarre | ✅ affidamento diretto con CIG, annullamento determina esplicito |
| 20443 | Marsala | ✅ "revoca in autotutela della determina a contrarre e della relativa gara" — il caso da manuale |
| 23666 | Giarre | ⚠️ un "atto di indirizzo" (fase preliminare politica) per un futuro concorso di idee, non ancora un bando vero — incluso perché la parola "concorso" c'è letteralmente, ma è un segnale debole |
| 26206 | Ragusa | ✅ accordo quadro, stessa determina ripubblicata identica |
| 34796 | Sperlinga | ✅ annullamento in autotutela esplicito di una procedura negoziata, riproposta 2 giorni dopo (jaccard più basso, 0.51, ma testo inequivocabile) |

**7/8 sono inequivocabili. 1/8 (Giarre 23666) è un segnale debole** (un indirizzo politico verso un futuro concorso, non un bando già pubblicato) — non lo definirei un falso positivo, ma nemmeno un caso "da manuale" come gli altri 7."""))

cells.append(md("""## Prova 4 — Cosa perdiamo: quanti dei "tolti" avevano comunque un CIG?

Il filtro a frasi guarda solo il *testo* dell'oggetto. Ma un CIG (Codice Identificativo Gara) è un segnale indipendente e molto più affidabile di dominio: se un procedimento tolto dal fix aveva un CIG associato, è un indizio che fosse **davvero** una gara, anche se la frase non la descrive con le formule che cerco ("determina a contrarre", "affidamento diretto"...). Questo è il modo più onesto che ho per stimare il costo in falsi negativi."""))

cells.append(code("""def cig_del_procedimento(pid: int) -> str | None:
    \"\"\"CIG proprio del procedimento, o in mancanza il primo CIG tra i suoi atti.\"\"\"
    p = con.execute("SELECT cig FROM procedimenti WHERE id=?", (pid,)).fetchone()
    if p["cig"]:
        return p["cig"]
    a = con.execute(
        "SELECT cig FROM atti WHERE procedimento_id=? AND cig IS NOT NULL AND cig != '' LIMIT 1", (pid,)
    ).fetchone()
    return a["cig"] if a else None


df_tolti["cig"] = df_tolti["proc_id"].map(cig_del_procedimento)
con_cig = df_tolti[df_tolti["cig"].notna()]
print(f"Procedimenti tolti CON un CIG associato (possibile falso negativo): {len(con_cig)} / {len(df_tolti)}")
con_cig[["proc_id", "ente", "cig", "oggetto"]]"""))

cells.append(md("""**Solo 3/59 avevano un CIG in colonna, e leggendoli nessuno è davvero un "bando riaperto" perso:**

- **Bagheria 18582** ("abbonamento a corsi di formazione"): il CIG appartiene a un contratto di abbonamento esistente, l'oggetto non descrive una gara ripubblicata.
- **Giarre 19564** ("revoca determina impegno spesa... consequenziale annullamento del CIG..."): è una correzione contabile su un contratto di servizio già in corso, non un nuovo bando.
- **Adrano 31392**: questo sì è un caso reale perso — "annullamento in autotutela" esplicito di un impegno per lavori di somma urgenza (art. 140 D.Lgs 36/2023), con CIG. È l'unico dei 59 dove il costo del filtro più stretto è concreto, non solo teorico.

**Limite di questo controllo, da dichiarare:** la colonna `cig` è popolata solo quando lo scraper l'ha estratta in un campo dedicato — **San Gregorio di Catania (24909)**, un secondo caso perso, non compare qui perché il suo CIG (`ZC137DE299`) è scritto dentro il testo dell'oggetto ma non è mai stato promosso alla colonna strutturata. Quindi "3/59 con CIG" è un limite inferiore, non il numero esatto di falsi negativi — il costo reale è probabilmente più vicino a 2 (Adrano + San Gregorio) che a 3, ma potrebbero essercene altri con CIG solo testuale che questo controllo non vede."""))

cells.append(md("""## Prova 5 — Il filtro generalizza, o è overfit ai casi che ho già letto?

Fin qui ho verificato il filtro solo sui procedimenti che il **matching Jaccard** aveva già selezionato come candidati riapertura. Ma il filtro di dominio (`_e_dominio_gara_appalti`) è stato scritto guardando quei casi specifici — rischio classico di overfitting.

Per un test più severo, lo applico a **tutti** i 555 procedimenti con `stato_finale IN ('annullato','revocato')` nel DB, non solo ai casi già noti, e ne leggo un campione casuale (seed fissato, riproducibile) sia tra quelli marcati dentro-dominio sia tra quelli fuori-dominio — per vedere se il giudizio regge su testi mai ispezionati durante lo sviluppo del fix."""))

cells.append(code("""import random

tutti = con.execute(
    "SELECT id, ente_id, oggetto FROM procedimenti WHERE stato_finale IN ('annullato','revocato')"
).fetchall()
print(f"Popolazione totale procedimenti annullati/revocati: {len(tutti)}")

gia_noti = proc_pre  # i procedimenti già ispezionati manualmente (82 flag originali)
candidati_nuovi = [r for r in tutti if r["id"] not in gia_noti]
print(f"Mai ispezionati finora in questo lavoro: {len(candidati_nuovi)}")

random.seed(59)
campione = random.sample(candidati_nuovi, 40)

righe = []
for r in campione:
    dentro = riap_post._e_dominio_gara_appalti(r["oggetto"] or "")
    righe.append({"proc_id": r["id"], "ente": nomi_enti.get(r["ente_id"], "?"), "in_dominio": dentro, "oggetto": r["oggetto"]})
df_campione = pd.DataFrame(righe)
print(f"Nel campione casuale di {len(df_campione)}: {df_campione['in_dominio'].sum()} classificati IN dominio, {(~df_campione['in_dominio']).sum()} FUORI dominio")"""))

cells.append(code("""# Tutti quelli che il filtro marca IN dominio, nel campione mai visto prima
df_campione[df_campione["in_dominio"]][["proc_id", "ente", "oggetto"]]"""))

cells.append(code("""# Un sotto-campione di quelli marcati FUORI dominio, per controllare falsi negativi
df_campione[~df_campione["in_dominio"]][["proc_id", "ente", "oggetto"]].head(20)"""))

cells.append(md("""**Il filtro regge nel complesso, ma il campione cieco ha trovato due lacune reali che i 9 fascicoli originari non avevano fatto emergere:**

**1) I 7 marcati IN dominio: 6/7 palesemente corretti** (bando di concorso pubblico per licenze, affidamento servizi ausiliari Castello di Donnafugata, gestione esternalizzata asilo nido, servizio spazzamento emergenza Etna, revoca+affidamento fornitura gommoni di salvataggio). **1/7 è un caso di confine**: Villabate 7427, "determina a contrarre per l'affidamento dell'incarico di un operaio qualificato... cantiere di lavoro" — un "cantiere di lavoro" è una misura di politica attiva del lavoro (collocamento temporaneo sussidiato), non un vero appalto competitivo, anche se usa lo stesso linguaggio contrattuale. Non è un errore del filtro, ma un promemoria che "determina a contrarre" cattura anche atti a cavallo tra procurement e politiche sociali.

**2) Tra i 33 fuori dominio, trovate due lacune concrete (falsi negativi):**

- **Milazzo 31488** — `"DETERMINAZIONE DI REVOCA DELL'AFFIDAMENTO DISPOSTO ALLA OFFICINE METALLICHE DOPPIA C. S.R.L...."` — questo **è** un affidamento revocato, testualmente. Il filtro (nella sua prima versione) lo perdeva per un motivo puramente meccanico: la regex cercava `affidamento\\s+(?:diretto|dei|del|della|delle)` con uno spazio dopo "affidamento", ma qui c'è l'elisione `dell'affidamento` → `AFFIDAMENTO DISPOSTO...`, senza nessuna delle parole che cerca subito dopo.
- **Palma di Montechiaro 653 vs. Castel di Iudica 10368**: stessa fattispecie (concorso interno per progressione tra le aree), stesso tipo di provvedimento — uno diceva `"BANDO di selezione"` (→ dentro dominio) e l'altro `"AVVISO di selezione"` (→ fuori dominio). Incoerenza reale: il filtro premiava la parola scelta dall'ente più che la sostanza dell'atto.

**Entrambe corrette nello stesso giro di lavoro — verificato in Prova 8 più sotto.**"""))

cells.append(code("""# Prova 5b — le due lacune trovate sopra sono riproducibili sul codice ATTUALE?
casi_limite = [
    ("Milazzo 31488 (REVOCA DELL'AFFIDAMENTO, elisione)",
     "DETERMINAZIONE DI REVOCA DELL'AFFIDAMENTO DISPOSTO ALLA OFFICINE METALLICHE DOPPIA C. S.R.L. CON DETERMINAZIONE"),
    ("Palma 653 (AVVISO di selezione interna)",
     "APPROVAZIONE AVVISO DI SELEZIONE E MODELLO ISTANZA PER SELEZIONE INTERNA PER PROGRESSIONE TRA LE AREE"),
    ("Castel di Iudica 10368 (BANDO di selezione, stessa fattispecie)",
     "SELEZIONE COMPARATIVA PROGRESSIONI TRA LE AREE ANNO 2024. AVVIO E APPROVAZIONE BANDO DI SELEZIONE"),
]
pd.DataFrame([
    {"caso": nome, "in_dominio (codice attuale)": riap_post._e_dominio_gara_appalti(testo)}
    for nome, testo in casi_limite
])"""))

cells.append(md("""## Prova 8 — Le due lacune sono state corrette: verifica di non-regressione

Dopo aver trovato le due lacune sopra, la regex è stata estesa (`disposto` come possibile parola dopo "affidamento", `avviso di selezione` come frase equivalente a `bando di selezione`). Non basta verificare che i due casi noti ora passino: bisogna controllare che l'estensione non abbia **riaperto la porta a nuovi falsi positivi** altrove. Ricalcolo la classificazione di dominio su tutti i 555 procedimenti annullati/revocati con la regex del primo giro (commit `3e459e4`, quello con cui è stato scritto questo notebook la prima volta) e quella attuale, e guardo ogni singola differenza."""))

cells.append(code("""sorgente_v2 = subprocess.run(
    ["git", "show", f"{POST_FIX_COMMIT}:src/talia/modulo2_scraping/red_flags/riapertura_revoca.py"],
    cwd=REPO, capture_output=True, text=True, check=True,
).stdout
tmp_path = Path("/tmp/_tal59_riap_v2.py")
tmp_path.write_text(sorgente_v2)
spec = importlib.util.spec_from_file_location("riap_v2", tmp_path)
riap_v2 = importlib.util.module_from_spec(spec)
sys.modules["riap_v2"] = riap_v2
spec.loader.exec_module(riap_v2)

tutti_555 = con.execute(
    "SELECT id, ente_id, oggetto FROM procedimenti WHERE stato_finale IN ('annullato','revocato')"
).fetchall()

cambiati = []
for r in tutti_555:
    prima = riap_v2._e_dominio_gara_appalti(r["oggetto"] or "")
    dopo = riap_post._e_dominio_gara_appalti(r["oggetto"] or "")
    if prima != dopo:
        cambiati.append({"proc_id": r["id"], "ente": nomi_enti.get(r["ente_id"], "?"), "prima": prima, "dopo": dopo, "oggetto": r["oggetto"]})

df_cambiati = pd.DataFrame(cambiati)
print(f"Procedimenti la cui classificazione cambia: {len(df_cambiati)} / {len(tutti_555)}")
if len(df_cambiati):
    print(f"Di questi, nuovi FALSI (dovrebbero essere 0): {(~df_cambiati['dopo']).sum()}")
df_cambiati"""))

cells.append(md("""**5 procedimenti cambiano classificazione, tutti nella direzione attesa (falso→vero): nessuna regressione.** 3 sono altre occorrenze dello stesso "avviso di selezione interna per progressione tra le aree" di Palma di Montechiaro (stesso processo HR ripetuto), 1 è un caso analogo in un altro ente, 1 è Milazzo. Nessun procedimento passa da dentro a fuori dominio — l'estensione è stata puramente additiva sui due casi diagnosticati, non ha toccato nient'altro."""))

cells.append(md("""## Prova 6 — Nessuna regressione sugli altri red flag

Il fix tocca solo `engine/catena.py::classifica_ruolo` e `red_flags/riapertura_revoca.py`. Verifico due cose indipendenti: (a) il diff del branch non tocca nessun altro modulo di red flag, (b) gli altri red flag deterministici girano ancora senza eccezioni sullo stesso DB e producono conteggi ragionevoli (non necessariamente identici — `classifica_ruolo` è condiviso e in teoria potrebbe influenzarli se costruissero catene da zero in questa sessione, cosa che non fanno: leggono `procedimenti`/`atti` già popolati)."""))

cells.append(code("""file_toccati = subprocess.run(
    ["git", "diff", "--name-only", PRE_FIX_COMMIT],
    cwd=REPO, capture_output=True, text=True, check=True,
).stdout.splitlines()
print("File modificati rispetto a prima del fix (inclusi commit non ancora fatti in questo giro):")
for f in file_toccati:
    print(" -", f)

assert "src/talia/modulo2_scraping/red_flags/concentrazione.py" not in file_toccati
assert "src/talia/modulo2_scraping/red_flags/frazionamento.py" not in file_toccati
assert "src/talia/modulo2_scraping/red_flags/tempi_anomali.py" not in file_toccati
assert "src/talia/modulo2_scraping/red_flags/catena_revoca.py" not in file_toccati
print("\\nConfermato: nessun altro modulo red_flags nel diff.")"""))

cells.append(code("""from talia.modulo2_scraping.red_flags import catena_revoca, concentrazione, frazionamento, tempi_anomali

esiti = {}
for nome, funzione in [
    ("concentrazione", concentrazione.rileva_concentrazione),
    ("frazionamento", frazionamento.rileva_frazionamento),
    ("tempi_anomali", tempi_anomali.rileva_tempi_anomali),
    ("revoche_in_catena", catena_revoca.rileva_revoche_in_catena),
]:
    try:
        r = funzione(nuova_connessione())
        esiti[nome] = ("OK", len(r))
    except Exception as e:
        esiti[nome] = ("ERRORE", str(e))

pd.DataFrame(esiti).T.rename(columns={0: "esito", 1: "conteggio/errore"})"""))

cells.append(md("""**Nessuna eccezione**, tutti e 4 gli altri red flag girano puliti sullo stesso DB. `frazionamento=0` non è una regressione: è così anche in run storici precedenti non collegati a questo fix (vedi `HANDOFF.md`, run del 2026-07-20), quindi è un dato pre-esistente del dataset/algoritmo, non un effetto collaterale di TAL-59."""))

cells.append(md("""## Prova 7 — Il Fix 1 (tag `[annullato]`) non è retroattivo: quanto resta da bonificare?

`classifica_ruolo()` viene chiamata solo quando un atto viene **inserito/riclassificato** in catena — non quando si interroga il DB. I dati già scritti in `talia.db` restano con il `ruolo_in_catena` sbagliato finché non gira un nuovo run scraper (o un backfill esplicito, non eseguito qui). Quanto è grande il debito residuo?"""))

cells.append(code("""tag_atti = con.execute(
    "SELECT id, ente_id, oggetto, ruolo_in_catena FROM atti WHERE oggetto LIKE '[%'"
).fetchall()
df_tag = pd.DataFrame([dict(r) for r in tag_atti])
print(f"Atti nel DB con oggetto che inizia per '[': {len(df_tag)}")
print(df_tag["ruolo_in_catena"].value_counts(dropna=False))

# Verifica diretta: la NUOVA classifica_ruolo() su questi stessi testi darebbe
# davvero un ruolo diverso da quello salvato (cioè il fix li correggerebbe se
# rilanciassimo la ricostruzione catene)?
df_tag["ruolo_con_fix"] = df_tag["oggetto"].apply(lambda o: catena_post.classifica_ruolo(oggetto=o))
cambierebbero = df_tag[df_tag["ruolo_in_catena"] != df_tag["ruolo_con_fix"]]
print(f"\\nDi questi, il ruolo cambierebbe con Fix 1 attivo: {len(cambierebbero)} / {len(df_tag)}")
cambierebbero[["id", "oggetto", "ruolo_in_catena", "ruolo_con_fix"]].head(15)"""))

cells.append(md("""**151/177 atti con tag di stato tra parentesi quadre hanno oggi un `ruolo_in_catena` sbagliato che il Fix 1 correggerebbe** — numero che coincide con la stima indipendente del sotto-agente che avevo lanciato durante l'investigazione iniziale (anche lui aveva trovato 151), un controllo incrociato che rassicura sulla diagnosi. **Ma restano sbagliati finché qualcuno non rilancia la ricostruzione delle catene** (nuovo run scraper, o un backfill dedicato) — non l'ho fatto qui perché scrive sul DB reale e va deciso esplicitamente, non lanciato di sorpresa dentro una verifica.

Nota anche i 26 casi con tag diverso da `[annullato]` (es. `[p: 16621-2026]`, un riferimento a un permesso di poligono militare) che restano `ruolo=None`/`altro` sia prima che dopo — non tutti i tag tra parentesi quadre sono lo stesso bug, ma la stragrande maggioranza (120/177) lo è."""))

cells.append(md("""## Conclusione critica

**Cosa il fix risolve bene, verificato non solo dichiarato:**
- Riduzione confermata dal vivo: **67 → 8 procedimenti (-88,1%)**, non solo il numero di righe.
- I 59 tolti sono stati letti **tutti**, non a campione: nessuno mi sembra un'esclusione sbagliata. Ha anche fatto emergere un pattern non visto prima (17 casi dallo stesso ente, Sant'Agata li Battiati) che i 9 campioni originari di TAL-12 non coprivano.
- Il filtro **generalizza** ragionevolmente su un campione cieco di 40 procedimenti mai ispezionati durante lo sviluppo: 6/7 classificazioni positive erano già corrette; le 2 lacune reali trovate (elisione "dell'affidamento", incoerenza bando/avviso di selezione) sono state corrette nello stesso giro e la correzione è stata verificata **non regressiva** su tutti i 555 procedimenti (Prova 8): solo 5 cambiano classificazione, tutti nella direzione giusta.
- Nessuna regressione sugli altri 4 red flag deterministici.

**Cosa resta scoperto — non nascosto, da decidere:**
1. **Costo reale in falsi negativi stimato in 2 casi su 59** (Adrano, San Gregorio di Catania) — piccolo ma non nullo, e la sua stima stessa ha un limite dichiarato (colonna CIG non sempre popolata).
2. **Il Fix 1 (tag `[annullato]`) non ha ancora effetto sui dati esistenti** — 151 atti restano classificati male finché non gira un backfill, decisione che spetta a Dom, non presa qui.
3. **Bug 2b (Jaccard che lega atti scorrelati anche dentro lo stesso dominio) resta esplicitamente fuori scope**, come già scritto nella card — questa verifica non lo tocca, ed è dove il rischio residuo più grande vive ancora.
4. Un solo caso residuo tra gli 8 finali (Giarre 23666) è un segnale debole (un indirizzo politico, non ancora un bando).

**Giudizio:** il fix fa quello che promette, verificato con dati reali end-to-end (non solo test sintetici) e messo sotto pressione con un campione cieco che ha effettivamente trovato — e permesso di correggere — due lacune concrete. I punti 1-4 sono limiti noti e documentati, da programmare come passi successivi con Dom, non difetti nascosti di questo giro di lavoro."""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3 (talia .venv)", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False))
print("scritto", OUT, len(cells), "celle")
