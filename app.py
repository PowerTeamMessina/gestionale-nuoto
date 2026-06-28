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

c.execute("""
CREATE TABLE IF NOT EXISTS stagioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS atleti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    categoria TEXT,
    stagione TEXT
)
""")

conn.commit()


# ============================================================
# FUNZIONI MIGRAZIONE
# ============================================================

def colonna_esiste(tabella, colonna):
    info = c.execute(f"PRAGMA table_info({tabella})").fetchall()
    colonne = [x[1] for x in info]
    return colonna in colonne


# Se non esiste ancora la tabella presenze, la creo direttamente con tipo_evento
c.execute("""
CREATE TABLE IF NOT EXISTS presenze (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atleta_id INTEGER,
    data TEXT,
    stagione TEXT,
    tipo_evento TEXT,
    presenza INTEGER,
    voto REAL,
    commento TEXT,
    UNIQUE(atleta_id, data, stagione, tipo_evento)
)
""")

conn.commit()


# Migrazione vecchio DB: aggiungo stagione ad atleti se mancava
if not colonna_esiste("atleti", "stagione"):
    c.execute("ALTER TABLE atleti ADD COLUMN stagione TEXT")

c.execute("""
UPDATE atleti
SET stagione = '2025/2026'
WHERE stagione IS NULL OR stagione = ''
""")

conn.commit()


# Migrazione vecchia tabella presenze:
# se manca tipo_evento, ricreo la tabella con schema nuovo
if not colonna_esiste("presenze", "tipo_evento"):

    c.execute("""
    ALTER TABLE presenze RENAME TO presenze_old
    """)

    c.execute("""
    CREATE TABLE presenze (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        atleta_id INTEGER,
        data TEXT,
        stagione TEXT,
        tipo_evento TEXT,
        presenza INTEGER,
        voto REAL,
        commento TEXT,
        UNIQUE(atleta_id, data, stagione, tipo_evento)
    )
    """)

    colonne_old = [x[1] for x in c.execute("PRAGMA table_info(presenze_old)").fetchall()]

    if "stagione" in colonne_old:
        c.execute("""
        INSERT OR IGNORE INTO presenze
        (atleta_id, data, stagione, tipo_evento, presenza, voto, commento)
        SELECT atleta_id, data, 
               COALESCE(NULLIF(stagione, ''), '2025/2026'),
               'Allenamento',
               presenza, voto, commento
        FROM presenze_old
        """)
    else:
        c.execute("""
        INSERT OR IGNORE INTO presenze
        (atleta_id, data, stagione, tipo_evento, presenza, voto, commento)
        SELECT atleta_id, data,
               '2025/2026',
               'Allenamento',
               presenza, voto, commento
        FROM presenze_old
        """)

    c.execute("DROP TABLE presenze_old")
    conn.commit()


# Inserisco stagioni base
c.execute("INSERT OR IGNORE INTO stagioni (nome) VALUES (?)", ("2025/2026",))
c.execute("INSERT OR IGNORE INTO stagioni (nome) VALUES (?)", ("2026/2027",))

conn.commit()


# ============================================================
# FUNZIONI GENERALI
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


def elimina_stagione(nome_stagione):
    c.execute("DELETE FROM presenze WHERE stagione = ?", (nome_stagione,))
    c.execute("DELETE FROM atleti WHERE stagione = ?", (nome_stagione,))
    c.execute("DELETE FROM stagioni WHERE nome = ?", (nome_stagione,))
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


def get_presenze_data(data_evento, stagione, tipo_evento):
    return pd.read_sql("""
        SELECT atleta_id, data, stagione, tipo_evento, presenza, voto, commento
        FROM presenze
        WHERE data = ?
        AND stagione = ?
        AND tipo_evento = ?
    """, conn, params=(str(data_evento), stagione, tipo_evento))


def salva_presenza(atleta_id, data_evento, stagione, tipo_evento, presenza, voto, commento):
    c.execute("""
        INSERT INTO presenze (atleta_id, data, stagione, tipo_evento, presenza, voto, commento)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(atleta_id, data, stagione, tipo_evento)
        DO UPDATE SET
            presenza = excluded.presenza,
            voto = excluded.voto,
            commento = excluded.commento
    """, (
        atleta_id,
        str(data_evento),
        stagione,
        tipo_evento,
        int(presenza),
        float(voto) if voto is not None else None,
        commento
    ))
    conn.commit()


def get_storico(stagione, tipo_evento=None):
    if tipo_evento is None or tipo_evento == "Tutti":
        return pd.read_sql("""
            SELECT 
                a.id AS atleta_id,
                a.nome,
                a.categoria,
                a.stagione,
                p.data,
                p.tipo_evento,
                p.presenza,
                p.voto,
                p.commento
            FROM presenze p
            JOIN atleti a ON a.id = p.atleta_id
            WHERE p.stagione = ?
            ORDER BY p.data DESC, p.tipo_evento, a.categoria, a.nome
        """, conn, params=(stagione,))
    else:
        return pd.read_sql("""
            SELECT 
                a.id AS atleta_id,
                a.nome,
                a.categoria,
                a.stagione,
                p.data,
                p.tipo_evento,
                p.presenza,
                p.voto,
                p.commento
            FROM presenze p
            JOIN atleti a ON a.id = p.atleta_id
            WHERE p.stagione = ?
            AND p.tipo_evento = ?
            ORDER BY p.data DESC, a.categoria, a.nome
        """, conn, params=(stagione, tipo_evento))


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

if "tipo_evento_corrente" not in st.session_state:
    st.session_state.tipo_evento_corrente = "Allenamento"


# ============================================================
# FUNZIONE REGISTRO GENERICA
# Allenamento e Gara usano la stessa logica, ma dati separati
# ============================================================

def mostra_registro(tipo_evento, stagione_selezionata):

    if tipo_evento == "Allenamento":
        titolo = "📋 Registro Allenamento"
        label_data = "Data allenamento"
        label_salva = "💾 SALVA ALLENAMENTO"
        nota_placeholder = "Nota opzionale"
    else:
        titolo = "🏁 Registro Gare"
        label_data = "Data gara"
        label_salva = "💾 SALVA GARA"
        nota_placeholder = "Nota/Risultato opzionale"

    st.header(titolo)

    st.info(f"Stagione selezionata: {stagione_selezionata}")
    st.info(f"Tipo registro: {tipo_evento}")

    data_evento = st.date_input(
        label_data,
        value=date.today(),
        key=f"data_{tipo_evento}"
    )

    df_atleti = get_atleti(stagione_selezionata)

    if df_atleti.empty:
        st.warning("Non ci sono atleti in questa stagione. Inseriscili nella sezione 👥 Atleti.")
        return

    df_atleti["categoria_pulita"] = df_atleti["categoria"].apply(pulisci_categoria)

    categorie = sorted(df_atleti["categoria_pulita"].unique().tolist())

    filtro_categoria = st.selectbox(
        "Filtra categoria",
        ["Tutte"] + categorie,
        key=f"filtro_categoria_{tipo_evento}"
    )

    if filtro_categoria == "Tutte":
        df_visibili = df_atleti.copy()
    else:
        df_visibili = df_atleti[
            df_atleti["categoria_pulita"] == filtro_categoria
        ].copy()

    chiave_data = f"{str(data_evento)}_{stagione_selezionata}_{tipo_evento}"

    if (
        st.session_state.data_corrente != chiave_data
        or st.session_state.tipo_evento_corrente != tipo_evento
    ):
        st.session_state.registro = {}
        st.session_state.data_corrente = chiave_data
        st.session_state.tipo_evento_corrente = tipo_evento

    presenze_salvate = get_presenze_data(data_evento, stagione_selezionata, tipo_evento)

    saved_dict = {}

    if not presenze_salvate.empty:
        for _, r in presenze_salvate.iterrows():
            atleta_id_salvato = int(r["atleta_id"])

            saved_dict[atleta_id_salvato] = {
                "presenza": bool(r["presenza"]),
                "voto": int(r["voto"]) if pd.notna(r["voto"]) else None,
                "commento": r["commento"] if pd.notna(r["commento"]) else ""
            }

    # Tutti assenti di default
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
        if st.button("❌ Tutti assenti", key=f"tutti_assenti_{tipo_evento}"):
            for _, row in df_visibili.iterrows():
                atleta_id = int(row["id"])
                st.session_state.registro[atleta_id]["presenza"] = False
                st.session_state.registro[atleta_id]["voto"] = None
            st.rerun()

    with col2:
        if st.button("✅ Tutti presenti", key=f"tutti_presenti_{tipo_evento}"):
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
        horizontal=True,
        key=f"stelle_gruppo_{tipo_evento}"
    )

    if st.button("⭐ Applica voto ai presenti", key=f"applica_voto_{tipo_evento}"):
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
            key=f"pres_{tipo_evento}_{atleta_id}"
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
                key=f"voto_{tipo_evento}_{atleta_id}"
            )

            voto = stelle_to_voto(stelle)

        else:
            voto = None
            st.session_state.registro[atleta_id]["voto"] = None
            st.write("Assente: nessun voto")

        commento = st.text_input(
            "Nota" if tipo_evento == "Allenamento" else "Nota/Risultato",
            value=st.session_state.registro[atleta_id]["commento"],
            key=f"commento_{tipo_evento}_{atleta_id}",
            placeholder=nota_placeholder
        )

        st.session_state.registro[atleta_id]["presenza"] = presenza
        st.session_state.registro[atleta_id]["voto"] = voto
        st.session_state.registro[atleta_id]["commento"] = commento

        st.markdown("---")

    # ========================================================
    # SALVATAGGIO
    # ========================================================

    if st.button(label_salva, type="primary", key=f"salva_{tipo_evento}"):

        for _, row in df_visibili.iterrows():

            atleta_id = int(row["id"])
            dati = st.session_state.registro[atleta_id]

            voto_salvato = dati["voto"] if dati["presenza"] else None

            salva_presenza(
                atleta_id=atleta_id,
                data_evento=data_evento,
                stagione=stagione_selezionata,
                tipo_evento=tipo_evento,
                presenza=dati["presenza"],
                voto=voto_salvato,
                commento=dati["commento"]
            )

        st.success(f"{tipo_evento} salvato correttamente ✅")

    st.caption("Se salvi più volte la stessa data e lo stesso tipo di registro, i dati vengono aggiornati.")


# ============================================================
# INTERFACCIA PRINCIPALE
# ============================================================

st.title("🏊 Gestionale Nuoto")

stagioni = get_stagioni()

if len(stagioni) == 0:
    aggiungi_stagione("2025/2026")
    stagioni = get_stagioni()

if st.session_state.stagione_corrente in stagioni:
    index_default = stagioni.index(st.session_state.stagione_corrente)
elif "2025/2026" in stagioni:
    index_default = stagioni.index("2025/2026")
else:
    index_default = 0

stagione_selezionata = st.selectbox(
    "Stagione sportiva",
    stagioni,
    index=index_default
)

if st.session_state.stagione_corrente != stagione_selezionata:
    st.session_state.registro = {}
    st.session_state.stagione_corrente = stagione_selezionata

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📋 Registro Allenamento",
    "🏁 Registro Gare",
    "👥 Atleti",
    "📊 Statistiche",
    "🗂️ Storico",
    "⚙️ Stagioni"
])


# ============================================================
# TAB 1 - REGISTRO ALLENAMENTO
# ============================================================

with tab1:
    mostra_registro("Allenamento", stagione_selezionata)


# ============================================================
# TAB 2 - REGISTRO GARE
# ============================================================

with tab2:
    mostra_registro("Gara", stagione_selezionata)


# ============================================================
# TAB 3 - ATLETI
# ============================================================

with tab3:

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
            "Questa operazione elimina l'atleta dalla stagione selezionata "
            "e cancella anche allenamenti, gare, voti e commenti associati."
        )

        opzioni_eliminazione = {}

        for _, row in df_atleti.iterrows():
            nome_opzione = (
                f"{row['nome']} | "
                f"{pulisci_categoria(row['categoria'])} | "
                f"id={row['id']}"
            )
            opzioni_eliminazione[nome_opzione] = int(row["id"])

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
# TAB 4 - STATISTICHE
# ============================================================

with tab4:

    st.header("📊 Statistiche automatiche")

    st.info(f"Statistiche stagione: {stagione_selezionata}")

    tipo_statistiche = st.selectbox(
        "Tipo dati",
        ["Allenamento", "Gara", "Tutti"],
        index=0
    )

    storico = get_storico(stagione_selezionata, tipo_statistiche)

    if storico.empty:
        st.info("Non ci sono ancora dati salvati per questa selezione.")
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
            ["atleta_id", "nome", "categoria", "stagione", "tipo_evento"],
            dropna=False
        ).agg(
            registrazioni=("presenza", "count"),
            presenze=("presenza", "sum"),
            media_stelle=("voto", "mean")
        ).reset_index()

        stats["assenze"] = stats["registrazioni"] - stats["presenze"]

        stats["percentuale_presenze"] = (
            stats["presenze"] / stats["registrazioni"] * 100
        )

        stats["media_stelle"] = stats["media_stelle"].round(2)
        stats["percentuale_presenze"] = stats["percentuale_presenze"].round(1)

        st.subheader("Statistiche per atleta")

        st.dataframe(
            stats[[
                "nome",
                "categoria",
                "stagione",
                "tipo_evento",
                "registrazioni",
                "presenze",
                "assenze",
                "percentuale_presenze",
                "media_stelle"
            ]],
            use_container_width=True,
            hide_index=True
        )

        nome_file = (
            f"statistiche_nuoto_"
            f"{stagione_selezionata.replace('/', '-')}_"
            f"{tipo_statistiche}.csv"
        )

        csv = stats.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Scarica statistiche CSV",
            data=csv,
            file_name=nome_file,
            mime="text/csv"
        )


# ============================================================
# TAB 5 - STORICO
# ============================================================

with tab5:

    st.header("🗂️ Storico")

    st.info(f"Storico stagione: {stagione_selezionata}")

    tipo_storico = st.selectbox(
        "Tipo storico",
        ["Allenamento", "Gara", "Tutti"],
        index=0
    )

    storico = get_storico(stagione_selezionata, tipo_storico)

    if storico.empty:
        st.info("Nessuno storico disponibile per questa selezione.")
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
                "tipo_evento",
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

        nome_file_storico = (
            f"storico_nuoto_"
            f"{stagione_selezionata.replace('/', '-')}_"
            f"{tipo_storico}.csv"
        )

        csv_storico = storico.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Scarica storico CSV",
            data=csv_storico,
            file_name=nome_file_storico,
            mime="text/csv"
        )


# ============================================================
# TAB 6 - STAGIONI
# ============================================================

with tab6:

    st.header("⚙️ Gestione stagioni")

    st.write("Qui puoi creare o eliminare stagioni sportive.")

    st.subheader("➕ Aggiungi stagione")

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

    st.subheader("📋 Stagioni disponibili")

    df_stagioni = pd.read_sql("""
        SELECT nome
        FROM stagioni
        ORDER BY nome
    """, conn)

    if df_stagioni.empty:
        st.info("Nessuna stagione disponibile.")
    else:
        st.dataframe(
            df_stagioni,
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")

    st.subheader("🗑️ Elimina stagione")

    st.warning(
        "Attenzione: eliminando una stagione verranno cancellati anche tutti gli atleti, "
        "gli allenamenti, le gare, le presenze, i voti e i commenti associati a quella stagione."
    )

    stagioni_disponibili = get_stagioni()

    if len(stagioni_disponibili) == 0:
        st.info("Non ci sono stagioni da eliminare.")
    else:

        stagione_da_eliminare = st.selectbox(
            "Seleziona stagione da eliminare",
            stagioni_disponibili,
            key="stagione_da_eliminare"
        )

        conferma_eliminazione = st.checkbox(
            f"Confermo di voler eliminare definitivamente la stagione {stagione_da_eliminare}"
        )

        if st.button("🗑️ Elimina stagione selezionata"):

            if not conferma_eliminazione:
                st.error("Prima devi spuntare la conferma.")
            else:
                elimina_stagione(stagione_da_eliminare)

                st.session_state.registro = {}

                stagioni_rimanenti = get_stagioni()

                if len(stagioni_rimanenti) == 0:
                    aggiungi_stagione("2025/2026")
                    st.session_state.stagione_corrente = "2025/2026"
                else:
                    st.session_state.stagione_corrente = stagioni_rimanenti[0]

                st.success(f"Stagione eliminata: {stagione_da_eliminare}")
                st.rerun()

    st.markdown("---")

    st.info(
        "Allenamenti e gare sono separati nel database. "
        "Le statistiche e lo storico possono essere filtrati per Allenamento, Gara oppure Tutti."
    )
