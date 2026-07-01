import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
from io import BytesIO
import json

# ============================================================
# CONFIGURAZIONE
# ============================================================

st.set_page_config(
    page_title="Gestionale Nuoto V2",
    page_icon="🏊",
    layout="wide"
)

# ============================================================
# DATABASE
# ============================================================

conn = sqlite3.connect(
    "swim_app.db",
    check_same_thread=False
)

c = conn.cursor()

# ============================================================
# TABELLE
# ============================================================

c.execute("""
CREATE TABLE IF NOT EXISTS stagioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS atleti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    categoria TEXT,
    stagione TEXT NOT NULL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS presenze (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atleta_id INTEGER,
    data TEXT,
    stagione TEXT,
    tipo_evento TEXT,
    presenza INTEGER,
    voto INTEGER,
    commento TEXT,
    UNIQUE(
        atleta_id,
        data,
        stagione,
        tipo_evento
    )
)
""")

conn.commit()

# ============================================================
# STAGIONE DEFAULT
# ============================================================

c.execute(
    """
    INSERT OR IGNORE INTO stagioni(nome)
    VALUES(?)
    """,
    ("2025/2026",)
)

conn.commit()

# ============================================================
# FUNZIONI STAGIONI
# ============================================================

def get_stagioni():

    df = pd.read_sql(
        """
        SELECT nome
        FROM stagioni
        ORDER BY nome
        """,
        conn
    )

    if df.empty:
        return ["2025/2026"]

    return df["nome"].tolist()


def aggiungi_stagione(nome):

    c.execute(
        """
        INSERT OR IGNORE INTO stagioni(nome)
        VALUES(?)
        """,
        (nome,)
    )

    conn.commit()


def elimina_stagione(nome):

    c.execute(
        """
        DELETE FROM presenze
        WHERE stagione=?
        """,
        (nome,)
    )

    c.execute(
        """
        DELETE FROM atleti
        WHERE stagione=?
        """,
        (nome,)
    )

    c.execute(
        """
        DELETE FROM stagioni
        WHERE nome=?
        """,
        (nome,)
    )

    conn.commit()

# ============================================================
# FUNZIONI ATLETI
# ============================================================

def get_atleti(stagione):

    return pd.read_sql(
        """
        SELECT *
        FROM atleti
        WHERE stagione=?
        ORDER BY categoria,nome
        """,
        conn,
        params=(stagione,)
    )


def get_tutti_atleti():

    return pd.read_sql(
        """
        SELECT *
        FROM atleti
        ORDER BY stagione,categoria,nome
        """,
        conn
    )


def aggiungi_atleta(
    nome,
    categoria,
    stagione
):

    c.execute(
        """
        INSERT INTO atleti(
            nome,
            categoria,
            stagione
        )
        VALUES(?,?,?)
        """,
        (
            nome,
            categoria,
            stagione
        )
    )

    conn.commit()


def elimina_atleta(atleta_id):

    c.execute(
        """
        DELETE FROM presenze
        WHERE atleta_id=?
        """,
        (atleta_id,)
    )

    c.execute(
        """
        DELETE FROM atleti
        WHERE id=?
        """,
        (atleta_id,)
    )

    conn.commit()


def aggiorna_categoria_atleta(
    atleta_id,
    nuova_categoria
):

    c.execute(
        """
        UPDATE atleti
        SET categoria=?
        WHERE id=?
        """,
        (
            nuova_categoria,
            atleta_id
        )
    )

    conn.commit()

# ============================================================
# UTILITA'
# ============================================================

def pulisci_categoria(cat):

    if cat is None:
        return "Senza categoria"

    cat = str(cat).strip()

    if cat == "":
        return "Senza categoria"

    return cat

# ============================================================
# SESSION STATE
# ============================================================

if "stagione_corrente" not in st.session_state:
    st.session_state.stagione_corrente = "2025/2026"

if "registro" not in st.session_state:
    st.session_state.registro = {}

# ============================================================
# HEADER
# ============================================================

st.title("🏊 Gestionale Nuoto V2")

stagioni = get_stagioni()

indice = 0

if st.session_state.stagione_corrente in stagioni:
    indice = stagioni.index(
        st.session_state.stagione_corrente
    )

stagione_selezionata = st.selectbox(
    "Stagione sportiva",
    stagioni,
    index=indice
)

st.session_state.stagione_corrente = (
    stagione_selezionata
)

# ============================================================
# TAB PRINCIPALI
# ============================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📋 Allenamento vasca",
    "🏋️ Allenamento secco",
    "🏁 Gare",
    "👥 Atleti",
    "📊 Statistiche",
    "🗂️ Storico",
    "⚙️ Stagioni",
    "💾 Backup"
])

# ============================================================
# TAB 1
# ============================================================

with tab1:
    st.info(
        "Parte 2: Registro Allenamento in vasca"
    )

# ============================================================
# TAB 2
# ============================================================

with tab2:
    st.info(
        "Parte 2: Registro Allenamento a secco"
    )

# ============================================================
# TAB 3
# ============================================================

with tab3:
    st.info(
        "Parte 2: Registro Gare"
    )

# ============================================================
# TAB 4
# ============================================================

with tab4:

    st.header("👥 Gestione Atleti")

    with st.form(
        "form_nuovo_atleta",
        clear_on_submit=True
    ):

        nome = st.text_input(
            "Nome atleta"
        )

        categoria = st.text_input(
            "Categoria"
        )

        aggiungi = st.form_submit_button(
            "➕ Aggiungi atleta"
        )

        if aggiungi:

            if nome.strip() == "":

                st.error(
                    "Inserisci il nome dell'atleta."
                )

            else:

                aggiungi_atleta(
                    nome.strip(),
                    categoria.strip(),
                    stagione_selezionata
                )

                st.success(
                    "Atleta aggiunto correttamente."
                )

                st.rerun()

    st.markdown("---")

    df_atleti = get_atleti(
        stagione_selezionata
    )

    if df_atleti.empty:

        st.info(
            "Nessun atleta inserito."
        )

    else:

        st.subheader(
            "Lista atleti"
        )

        st.dataframe(
            df_atleti,
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")

        st.subheader(
            "✏️ Modifica categoria"
        )

        opzioni = {}

        for _, row in df_atleti.iterrows():

            testo = (
                f"{row['nome']} "
                f"({pulisci_categoria(row['categoria'])})"
            )

            opzioni[testo] = int(
                row["id"]
            )

        atleta_scelto = st.selectbox(
            "Atleta",
            list(opzioni.keys()),
            key="sel_atleta_categoria"
        )

        nuova_categoria = st.text_input(
            "Nuova categoria",
            key="nuova_categoria"
        )

        if st.button(
            "💾 Aggiorna categoria"
        ):

            aggiorna_categoria_atleta(
                opzioni[atleta_scelto],
                nuova_categoria
            )

            st.success(
                "Categoria aggiornata."
            )

            st.rerun()

        st.markdown("---")

        st.subheader(
            "🗑️ Elimina atleta"
        )

        atleta_delete = st.selectbox(
            "Seleziona atleta da eliminare",
            list(opzioni.keys()),
            key="sel_delete_atleta"
        )

        conferma = st.checkbox(
            "Confermo eliminazione atleta"
        )

        if st.button(
            "🗑️ Elimina atleta"
        ):

            if not conferma:

                st.error(
                    "Devi confermare."
                )

            else:

                elimina_atleta(
                    opzioni[atleta_delete]
                )

                st.success(
                    "Atleta eliminato."
                )

                st.rerun()

# ============================================================
# TAB 5
# ============================================================

with tab5:
    st.info(
        "Parte 4: Statistiche"
    )

# ============================================================
# TAB 6
# ============================================================

with tab6:
    st.info(
        "Parte 4: Storico"
    )

# ============================================================
# TAB 7
# ============================================================

with tab7:
    st.info(
        "Parte 3: Gestione Stagioni"
    )

# ============================================================
# TAB 8
# ============================================================

with tab8:
    st.info(
        "Parte 5: Backup / Export"
    )
# ============================================================
# REGISTRI
# ============================================================

def get_presenze_data(
    data_evento,
    stagione,
    tipo_evento
):

    return pd.read_sql(
        """
        SELECT *
        FROM presenze
        WHERE data = ?
        AND stagione = ?
        AND tipo_evento = ?
        """,
        conn,
        params=(
            str(data_evento),
            stagione,
            tipo_evento
        )
    )


def salva_presenza(
    atleta_id,
    data_evento,
    stagione,
    tipo_evento,
    presenza,
    voto,
    commento
):

    c.execute(
        """
        INSERT INTO presenze(
            atleta_id,
            data,
            stagione,
            tipo_evento,
            presenza,
            voto,
            commento
        )
        VALUES(?,?,?,?,?,?,?)

        ON CONFLICT(
            atleta_id,
            data,
            stagione,
            tipo_evento
        )

        DO UPDATE SET
            presenza = excluded.presenza,
            voto = excluded.voto,
            commento = excluded.commento
        """,
        (
            atleta_id,
            str(data_evento),
            stagione,
            tipo_evento,
            int(presenza),
            voto,
            commento
        )
    )

    conn.commit()


# ============================================================
# FUNZIONI STELLE
# ============================================================

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
# REGISTRO GENERICO
# ============================================================

def mostra_registro(
    titolo,
    tipo_evento,
    stagione
):

    st.header(titolo)

    data_evento = st.date_input(
        "Data",
        value=date.today(),
        key=f"data_{tipo_evento}"
    )

    df_atleti = get_atleti(stagione)

    if df_atleti.empty:

        st.warning(
            "Nessun atleta presente nella stagione selezionata."
        )

        return

    # -----------------------------------------
    # CARICAMENTO REGISTRO ESISTENTE
    # -----------------------------------------

    presenze_salvate = get_presenze_data(
        data_evento,
        stagione,
        tipo_evento
    )

    registro_esistente = (
        not presenze_salvate.empty
    )

    if registro_esistente:

        st.success(
            "✅ Registro già esistente. "
            "Puoi modificarlo e salvarlo nuovamente."
        )

    else:

        st.info(
            "📝 Nuovo registro."
        )

    dati_salvati = {}

    if registro_esistente:

        for _, r in presenze_salvate.iterrows():

            dati_salvati[
                int(r["atleta_id"])
            ] = {
                "presenza": bool(r["presenza"]),
                "voto": (
                    int(r["voto"])
                    if pd.notna(r["voto"])
                    else 4
                ),
                "commento": (
                    r["commento"]
                    if pd.notna(r["commento"])
                    else ""
                )
            }

    # -----------------------------------------
    # INIZIALIZZAZIONE SESSION
    # -----------------------------------------

    for _, row in df_atleti.iterrows():

        atleta_id = int(row["id"])

        if atleta_id not in st.session_state.registro:

            if atleta_id in dati_salvati:

                st.session_state.registro[
                    atleta_id
                ] = dati_salvati[
                    atleta_id
                ]

            else:

                st.session_state.registro[
                    atleta_id
                ] = {
                    "presenza": False,
                    "voto": 4,
                    "commento": ""
                }

    # -----------------------------------------
    # RIEPILOGO
    # -----------------------------------------

    totale = len(df_atleti)

    presenti = 0

    # -----------------------------------------
    # ATLETI
    # -----------------------------------------

    for _, row in df_atleti.iterrows():

        atleta_id = int(row["id"])

        st.markdown(
            f"### {row['nome']}"
        )

        presenza = st.toggle(
            "Presente",
            value=st.session_state.registro[
                atleta_id
            ]["presenza"],
            key=f"pres_{tipo_evento}_{atleta_id}"
        )

        voto = None

        if presenza:

            presenti += 1

            voto_corrente = st.session_state.registro[
                atleta_id
            ]["voto"]

            stelle = st.radio(
                "Valutazione",
                [
                    "⭐",
                    "⭐⭐",
                    "⭐⭐⭐",
                    "⭐⭐⭐⭐",
                    "⭐⭐⭐⭐⭐"
                ],
                index=max(
                    0,
                    min(4, voto_corrente - 1)
                ),
                horizontal=True,
                key=f"voto_{tipo_evento}_{atleta_id}"
            )

            voto = stelle_to_voto(
                stelle
            )

        commento = st.text_input(
            "Commento",
            value=st.session_state.registro[
                atleta_id
            ]["commento"],
            key=f"comm_{tipo_evento}_{atleta_id}"
        )

        st.session_state.registro[
            atleta_id
        ] = {
            "presenza": presenza,
            "voto": voto if presenza else 4,
            "commento": commento
        }

        st.markdown("---")

    assenti = totale - presenti

    c1, c2 = st.columns(2)

    c1.metric(
        "Presenti",
        presenti
    )

    c2.metric(
        "Assenti",
        assenti
    )

    # -----------------------------------------
    # SALVATAGGIO
    # -----------------------------------------

    if st.button(
        f"💾 Salva {tipo_evento}",
        key=f"salva_{tipo_evento}"
    ):

        for _, row in df_atleti.iterrows():

            atleta_id = int(
                row["id"]
            )

            dati = st.session_state.registro[
                atleta_id
            ]

            salva_presenza(
                atleta_id,
                data_evento,
                stagione,
                tipo_evento,
                dati["presenza"],
                dati["voto"]
                if dati["presenza"]
                else None,
                dati["commento"]
            )

        if registro_esistente:

            st.success(
                "✅ Registro aggiornato correttamente."
            )

        else:

            st.success(
                "✅ Nuovo registro salvato."
            )

        st.rerun()


# ============================================================
# TAB REGISTRI
# ============================================================

with tab1:

    mostra_registro(
        "📋 Allenamento in vasca",
        "Allenamento in vasca",
        stagione_selezionata
    )

with tab2:

    mostra_registro(
        "🏋️ Allenamento a secco",
        "Allenamento a secco",
        stagione_selezionata
    )

with tab3:

    mostra_registro(
        "🏁 Gare",
        "Gara",
        stagione_selezionata
    )
