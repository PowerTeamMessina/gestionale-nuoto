import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

# ============================================================
# CONFIGURAZIONE PAGINA
# ============================================================

st.set_page_config(
    page_title="Gestionale Nuoto",
    page_icon="🏊",
    layout="wide"
)

st.markdown("""
<style>
.block-container {
    padding-top: 0.8rem;
    padding-left: 0.8rem;
    padding-right: 0.8rem;
    padding-bottom: 2rem;
}

h1 {
    font-size: 1.7rem !important;
}

h2 {
    font-size: 1.3rem !important;
}

h3 {
    font-size: 1.15rem !important;
}

.stButton > button {
    width: 100%;
    min-height: 3rem;
    font-size: 1rem;
    border-radius: 10px;
}

div[data-testid="stMetricValue"] {
    font-size: 1.4rem;
}

hr {
    margin-top: 0.7rem;
    margin-bottom: 0.7rem;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE
# ============================================================

conn = sqlite3.connect("swim_app.db", check_same_thread=False)
c = conn.cursor()

# Tabella stagioni
c.execute("""
CREATE TABLE IF NOT EXISTS stagioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE
)
""")

# Tabella atleti
c.execute("""
CREATE TABLE IF NOT EXISTS atleti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    categoria TEXT,
    stagione TEXT
)
""")

# Tabella presenze
c.execute("""
CREATE TABLE IF NOT EXISTS presenze (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atleta_id INTEGER,
    data TEXT,
    stagione TEXT,
    presenza INTEGER,
    voto REAL,
    commento TEXT,
    UNIQUE(atleta_id, data, stagione)
)
""")

conn.commit()


# ============================================================
# MIGRAZIONE DATABASE VECCHIO
# Serve se avevi già un database senza colonna stagione
# ============================================================

def colonna_esiste(tabella, colonna):
    info = c.execute(f"PRAGMA table_info({tabella})").fetchall()
    colonne = [x[1] for x in info]
    return colonna in colonne


if not colonna_esiste("atleti", "stagione"):
    c.execute("ALTER TABLE atleti ADD COLUMN stagione TEXT")

if not colonna_esiste("presenze", "stagione"):
    c.execute("ALTER TABLE presenze ADD COLUMN stagione TEXT")

# assegna gli atleti e le presenze già esistenti alla stagione attuale
c.execute("""
UPDATE atleti
SET stagione = '2025/2026'
WHERE stagione IS NULL OR stagione = ''
""")

c.execute("""
UPDATE presenze
SET stagione = '2025/2026'
WHERE stagione IS NULL OR stagione = ''
""")

# stagioni di default
c.execute("INSERT OR IGNORE INTO stagioni (nome) VALUES (?)", ("2025/2026",))
c.execute("INSERT OR IGNORE INTO stagioni (nome) VALUES (?)", ("2026/2027",))

conn.commit()


# ============================================================
# FUNZIONI
# ============================================================

def get_stagioni():
    df = pd.read_sql("""
        SELECT nome
        FROM stagioni
        ORDER BY nome
    """, conn)

    if df.empty:
        return ["2025/2026"]

    return df["nome"].tolist()


def aggiungi_stagione(nome_stagione):
    c.execute("""
        INSERT OR IGNORE INTO stagioni (nome)
        VALUES (?)
    """, (nome_stagione,))
    conn.commit()


def get_atleti(stagione):
    return pd.read_sql("""
        SELECT *
        FROM atleti
        WHERE stagione = ?
        ORDER BY categoria, nome
    """, conn, params=(stagione,))


def get_tutti_atleti():
    return pd.read_sql("""
        SELECT *
        FROM atleti
        ORDER BY stagione, categoria, nome
    """, conn)


def get_presenze_data(data_allenamento, stagione):
    return pd.read_sql("""
        SELECT atleta_id, data, stagione, presenza, voto, commento
        FROM presenze
        WHERE data = ?
        AND stagione = ?
    """, conn, params=(str(data_allenamento), stagione))


def salva_presenza(atleta_id, data_allenamento, stagione, presenza, voto, commento):
    c.execute("""
        INSERT INTO presenze (atleta_id, data, stagione, presenza, voto, commento)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(atleta_id, data, stagione)
        DO UPDATE SET
            presenza = excluded.presenza,
            voto = excluded.voto,
            commento = excluded.commento
    """, (
        atleta_id,
        str(data_allenamento),
        stagione,
        int(presenza),
        float(voto) if voto is not None else None,
        commento
    ))
    conn.commit()


def get_storico(stagione):
    return pd.read_sql("""
        SELECT 
            a.id AS atleta_id,
            a.nome,
            a.categoria,
            a.stagione,
            p.data,
            p.presenza,
            p.voto,
            p.commento
        FROM presenze p
        JOIN atleti a ON a.id = p.atleta_id
        WHERE p.stagione = ?
        ORDER BY p.data DESC, a.categoria, a.nome
    """, conn, params=(stagione,))


def elimina_atleta(atleta_id):
    c.execute("DELETE FROM presenze WHERE atleta_id = ?", (atleta_id,))
    c.execute("DELETE FROM atleti WHERE id = ?", (atleta_id,))
    conn.commit()


def pulisci_categoria(categoria):
    if categoria is None:
        return "Senza categoria"
    if str(categoria).strip() == "":
        return "Senza categoria"
    return str(categoria).strip()


def voto_to_stelle(voto):
    if voto is None:
        return ""
    try:
        voto = int(voto)
    except:
        return ""
    return "⭐" * voto


def stelle_to_voto(stelle):
    return stelle.count("⭐")


# ============================================================
# SESSION STATE
# ============================================================

if "registro" not in st.session_state:
    st.session_state.registro = {}

if "data_corrente" not in st.session_state:
    st.session_state.data_corrente = str(date.today())

if "stagione_corrente" not in st.session_state:
    st.session_state.stagione_corrente = "2025/2026"


# ============================================================
# INTERFACCIA PRINCIPALE
# ============================================================

st.title("🏊 Gestionale Nuoto")

stagioni = get_stagioni()

if "2025/2026" in stagioni:
    index_default = stagioni.index("2025/2026")
else:
    index_default = 0

stagione_selezionata = st.selectbox(
    "Stagione sportiva",
    stagioni,
    index=index_default
)

# Se cambio stagione, resetto il registro visivo
if st.session_state.stagione_corrente != stagione_selezionata:
    st.session_state.registro = {}
    st.session_state.stagione_corrente = stagione_selezionata

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Registro",
    "👥 Atleti",
    "📊 Statistiche",
    "🗂️ Storico",
    "⚙️ Stagioni"
])


# ============================================================
# TAB 1 - REGISTRO
# ============================================================

with tab1:

    st.header("📋 Registro allenamento")

    st.info(f"Stagione selezionata: {stagione_selezionata}")

    data_allenamento = st.date_input(
        "Data allenamento",
        value=date.today()
    )

    df_atleti = get_atleti(stagione_selezionata)

    if df_atleti.empty:
        st.warning("Non ci sono atleti in questa stagione. Inseriscili nella sezione 👥 Atleti.")
    else:

        df_atleti["categoria_pulita"] = df_atleti["categoria"].apply(pulisci_categoria)

        categorie = sorted(df_atleti["categoria_pulita"].unique().tolist())

        filtro_categoria = st.selectbox(
            "Filtra categoria",
            ["Tutte"] + categorie
        )

        if filtro_categoria == "Tutte":
            df_visibili = df_atleti.copy()
        else:
            df_visibili = df_atleti[
                df_atleti["categoria_pulita"] == filtro_categoria
            ].copy()

        # reset se cambia data
        if st.session_state.data_corrente != str(data_allenamento):
            st.session_state.registro = {}
            st.session_state.data_corrente = str(data_allenamento)

        # carica dati già salvati per data + stagione
        presenze_salvate = get_presenze_data(data_allenamento, stagione_selezionata)

        saved_dict = {}

        if not presenze_salvate.empty:
            for _, r in presenze_salvate.iterrows():
                atleta_id_salvato = int(r["atleta_id"])

                saved_dict[atleta_id_salvato] = {
                    "presenza": bool(r["presenza"]),
                    "voto": int(r["voto"]) if pd.notna(r["voto"]) else None,
                    "commento": r["commento"] if pd.notna(r["commento"]) else ""
                }

        # inizializzazione: tutti assenti di default
        for _, row in df_atleti.iterrows():
            atleta_id = int(row["id"])

            if atleta_id not in st.session_state.registro:

                if atleta_id in saved_dict:
                    st.session_state.registro[atleta_id] = saved_dict[atleta_id]
                else:
                    st.session_state.registro[atleta_id] = {
                        "presenza": False,
                        "voto": None,
                        "commento": ""
                    }

        st.markdown("---")

        # ========================================================
        # MODIFICA RAPIDA
        # ========================================================

        st.subheader("⚡ Modifica rapida")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("❌ Tutti assenti"):
                for _, row in df_visibili.iterrows():
                    atleta_id = int(row["id"])
                    st.session_state.registro[atleta_id]["presenza"] = False
                    st.session_state.registro[atleta_id]["voto"] = None
                st.rerun()

        with col2:
            if st.button("✅ Tutti presenti"):
                for _, row in df_visibili.iterrows():
                    atleta_id = int(row["id"])
                    st.session_state.registro[atleta_id]["presenza"] = True

                    if st.session_state.registro[atleta_id]["voto"] is None:
                        st.session_state.registro[atleta_id]["voto"] = 3

                st.rerun()

        stelle_gruppo = st.radio(
            "Applica voto ai presenti",
            ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
            index=2,
            horizontal=True
        )

        if st.button("⭐ Applica voto ai presenti"):
            voto_gruppo = stelle_to_voto(stelle_gruppo)

            for _, row in df_visibili.iterrows():
                atleta_id = int(row["id"])

                if st.session_state.registro[atleta_id]["presenza"]:
                    st.session_state.registro[atleta_id]["voto"] = voto_gruppo

            st.rerun()

        st.markdown("---")

        # ========================================================
        # RIEPILOGO LIVE
        # ========================================================

        ids_visibili = [int(x) for x in df_visibili["id"].tolist()]

        presenti_live = sum(
            1 for atleta_id in ids_visibili
            if st.session_state.registro[atleta_id]["presenza"]
        )

        totale_live = len(ids_visibili)
        assenti_live = totale_live - presenti_live

        voti_presenti = [
            st.session_state.registro[atleta_id]["voto"]
            for atleta_id in ids_visibili
            if st.session_state.registro[atleta_id]["presenza"]
            and st.session_state.registro[atleta_id]["voto"] is not None
        ]

        media_stelle_live = (
            round(sum(voti_presenti) / len(voti_presenti), 2)
            if len(voti_presenti) > 0 else 0
        )

        percentuale_presenti = (
            round(presenti_live / totale_live * 100, 1)
            if totale_live > 0 else 0
        )

        st.subheader("📊 Riepilogo")

        m1, m2, m3, m4 = st.columns(4)

        m1.metric("Totale", totale_live)
        m2.metric("Presenti", presenti_live)
        m3.metric("Assenti", assenti_live)
        m4.metric("Media stelle", media_stelle_live)

        st.progress(percentuale_presenti / 100)
        st.caption(f"Percentuale presenti: {percentuale_presenti}%")

        st.markdown("---")

        # ========================================================
        # LISTA ATLETI
        # ========================================================

        st.subheader("🏊 Atleti")

        for _, row in df_visibili.iterrows():

            atleta_id = int(row["id"])
            nome = row["nome"]
            categoria = row["categoria_pulita"]

            presenza_attuale = bool(st.session_state.registro[atleta_id]["presenza"])

            st.markdown(f"### {nome}")
            st.write(f"Categoria: {categoria}")

            presenza = st.toggle(
                "Presente",
                value=presenza_attuale,
                key=f"pres_{atleta_id}"
            )

            if presenza:

                if st.session_state.registro[atleta_id]["voto"] is None:
                    st.session_state.registro[atleta_id]["voto"] = 3

                voto_corrente = int(st.session_state.registro[atleta_id]["voto"])

                stelle = st.radio(
                    "Valutazione",
                    ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
                    index=voto_corrente - 1,
                    horizontal=True,
                    key=f"voto_{atleta_id}"
                )

                voto = stelle_to_voto(stelle)

            else:
                voto = None
                st.session_state.registro[atleta_id]["voto"] = None
                st.write("Assente: nessun voto")

            commento = st.text_input(
                "Nota",
                value=st.session_state.registro[atleta_id]["commento"],
                key=f"commento_{atleta_id}",
                placeholder="Nota opzionale"
            )

            st.session_state.registro[atleta_id]["presenza"] = presenza
            st.session_state.registro[atleta_id]["voto"] = voto
            st.session_state.registro[atleta_id]["commento"] = commento

            st.markdown("---")

        # ========================================================
        # SALVATAGGIO
        # ========================================================

        if st.button("💾 SALVA ALLENAMENTO", type="primary"):

            for _, row in df_visibili.iterrows():

                atleta_id = int(row["id"])
                dati = st.session_state.registro[atleta_id]

                voto_salvato = dati["voto"] if dati["presenza"] else None

                salva_presenza(
                    atleta_id=atleta_id,
                    data_allenamento=data_allenamento,
                    stagione=stagione_selezionata,
                    presenza=dati["presenza"],
                    voto=voto_salvato,
                    commento=dati["commento"]
                )

            st.success("Allenamento salvato correttamente ✅")

        st.caption("Se salvi più volte la stessa data, i dati vengono aggiornati.")


# ============================================================
# TAB 2 - ATLETI
# ============================================================

with tab2:

    st.header("👥 Gestione atleti")

    st.info(f"Stai lavorando sulla stagione: {stagione_selezionata}")

    with st.form("form_atleta", clear_on_submit=True):

        nome = st.text_input("Nome atleta")

        categoria = st.text_input(
            "Categoria",
            placeholder="es. Esordienti, Ragazzi, Junior, Assoluti"
        )

        submit = st.form_submit_button("➕ Aggiungi atleta alla stagione selezionata")

        if submit:
            if nome.strip() == "":
                st.error("Inserisci il nome dell'atleta.")
            else:
                c.execute("""
                    INSERT INTO atleti (nome, categoria, stagione)
                    VALUES (?, ?, ?)
                """, (
                    nome.strip(),
                    categoria.strip(),
                    stagione_selezionata
                ))

                conn.commit()
                st.success(f"Atleta {nome} aggiunto alla stagione {stagione_selezionata}.")
                st.rerun()

    st.markdown("---")

    df_atleti = get_atleti(stagione_selezionata)

    if df_atleti.empty:
        st.info("Nessun atleta inserito in questa stagione.")
    else:

        st.subheader("Lista atleti stagione selezionata")

        st.dataframe(
            df_atleti[["id", "nome", "categoria", "stagione"]],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")

        st.subheader("🗑️ Elimina atleta da PC")

        st.warning(
            "Questa operazione elimina l'atleta dalla stagione selezionata e cancella anche le sue presenze associate."
        )

        opzioni_eliminazione = {
            f"{row['nome']} | {pulizia if (pulizia := pulisci_categoria(row['categoria'])) else 'Senza categoria'} | id={row['id']}": int(row["id"])
            for _, row in df_atleti.iterrows()
        }

        scelta = st.selectbox(
            "Seleziona atleta da eliminare",
            list(opzioni_eliminazione.keys())
        )

        conferma = st.checkbox("Confermo di voler eliminare questo atleta")

        if st.button("🗑️ Elimina atleta selezionato"):

            if not conferma:
                st.error("Prima devi spuntare la conferma.")
            else:
                atleta_id = opzioni_eliminazione[scelta]
                elimina_atleta(atleta_id)

                # pulisco il registro in memoria per evitare riferimenti a id cancellati
                if atleta_id in st.session_state.registro:
                    del st.session_state.registro[atleta_id]

                st.success(f"Atleta eliminato: {scelta}")
                st.rerun()

    st.markdown("---")

    st.subheader("📋 Tutti gli atleti nel database")

    tutti = get_tutti_atleti()

    if tutti.empty:
        st.info("Nessun atleta nel database.")
    else:
        st.dataframe(
            tutti[["id", "nome", "categoria", "stagione"]],
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# TAB 3 - STATISTICHE
# ============================================================

with tab3:

    st.header("📊 Statistiche automatiche")

    st.info(f"Statistiche stagione: {stagione_selezionata}")

    storico = get_storico(stagione_selezionata)

    if storico.empty:
        st.info("Non ci sono ancora allenamenti salvati per questa stagione.")
    else:

        totale_registrazioni = len(storico)
        totale_presenze = int(storico["presenza"].sum())
        totale_assenze = totale_registrazioni - totale_presenze

        media_stelle = storico.loc[
            storico["presenza"] == 1,
            "voto"
        ].mean()

        media_stelle = round(media_stelle, 2) if pd.notna(media_stelle) else 0

        percentuale_presenze = round(
            totale_presenze / totale_registrazioni * 100,
            1
        ) if totale_registrazioni > 0 else 0

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Registrazioni", totale_registrazioni)
        c2.metric("Presenti", totale_presenze)
        c3.metric("Assenti", totale_assenze)
        c4.metric("Media stelle", media_stelle)

        st.progress(percentuale_presenze / 100)
        st.caption(f"Percentuale presenze complessiva: {percentuale_presenze}%")

        st.markdown("---")

        stats = storico.groupby(
            ["atleta_id", "nome", "categoria", "stagione"],
            dropna=False
        ).agg(
            allenamenti_registrati=("presenza", "count"),
            presenze=("presenza", "sum"),
            media_stelle=("voto", "mean")
        ).reset_index()

        stats["assenze"] = stats["allenamenti_registrati"] - stats["presenze"]

        stats["percentuale_presenze"] = (
            stats["presenze"] / stats["allenamenti_registrati"] * 100
        )

        stats["media_stelle"] = stats["media_stelle"].round(2)
        stats["percentuale_presenze"] = stats["percentuale_presenze"].round(1)

        st.subheader("Statistiche per atleta")

        st.dataframe(
            stats[[
                "nome",
                "categoria",
                "stagione",
                "allenamenti_registrati",
                "presenze",
                "assenze",
                "percentuale_presenze",
                "media_stelle"
            ]],
            use_container_width=True,
            hide_index=True
        )

        csv = stats.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Scarica statistiche CSV",
            data=csv,
            file_name=f"statistiche_nuoto_{stagione_selezionata.replace('/', '-')}.csv",
            mime="text/csv"
        )


# ============================================================
# TAB 4 - STORICO
# ============================================================

with tab4:

    st.header("🗂️ Storico allenamenti")

    st.info(f"Storico stagione: {stagione_selezionata}")

    storico = get_storico(stagione_selezionata)

    if storico.empty:
        st.info("Nessuno storico disponibile per questa stagione.")
    else:

        storico["presenza_testo"] = storico["presenza"].map({
            1: "Presente",
            0: "Assente"
        })

        storico["stelle"] = storico["voto"].apply(
            lambda x: voto_to_stelle(x) if pd.notna(x) else ""
        )

        st.dataframe(
            storico[[
                "data",
                "nome",
                "categoria",
                "stagione",
                "presenza_testo",
                "stelle",
                "commento"
            ]],
            use_container_width=True,
            hide_index=True
        )

        csv_storico = storico.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Scarica storico CSV",
            data=csv_storico,
            file_name=f"storico_allenamenti_nuoto_{stagione_selezionata.replace('/', '-')}.csv",
            mime="text/csv"
        )


# ============================================================
# TAB 5 - STAGIONI
# ============================================================

with tab5:

    st.header("⚙️ Gestione stagioni")

    st.write("Qui puoi creare nuove stagioni sportive.")

    with st.form("form_stagione", clear_on_submit=True):

        nuova_stagione = st.text_input(
            "Nuova stagione",
            placeholder="es. 2027/2028"
        )

        crea = st.form_submit_button("➕ Crea stagione")

        if crea:
            if nuova_stagione.strip() == "":
                st.error("Inserisci il nome della stagione.")
            else:
                aggiungi_stagione(nuova_stagione.strip())
                st.success(f"Stagione {nuova_stagione} creata.")
                st.rerun()

    st.markdown("---")

    st.subheader("Stagioni disponibili")

    df_stagioni = pd.read_sql("""
        SELECT nome
        FROM stagioni
        ORDER BY nome
    """, conn)

    st.dataframe(
        df_stagioni,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    st.info(
        "Gli atleti sono separati per stagione. "
        "Un atleta inserito nel 2025/2026 non viene trasferito automaticamente nel 2026/2027."
    )
