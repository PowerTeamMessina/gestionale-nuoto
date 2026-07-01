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
    page_title="Gestionale Nuoto",
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

if "data_aperta" not in st.session_state:
    st.session_state.data_aperta = None

if "tipo_aperto" not in st.session_state:
    st.session_state.tipo_aperto = None

# ============================================================
# HEADER
# ============================================================

st.title("🏊 Gestionale Nuoto")

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

tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "🏠 Dashboard",
    "📋 Allenamento vasca",
    "🏋️ Allenamento secco",
    "🏁 Gare",
    "👥 Atleti",
    "📊 Statistiche",
    "🗂️ Storico",
    "⚙️ Stagioni",
    "💾 Backup",
    "📅 Calendario"
])

# ============================================================
# TAB 0 - DASHBOARD
# ============================================================

with tab0:

    st.header("🏠 Dashboard")

    # --------------------------------------------------------
    # ATLETI
    # --------------------------------------------------------

    totale_atleti = len(
        get_atleti(stagione_selezionata)
    )

    # --------------------------------------------------------
    # REGISTRAZIONI
    # --------------------------------------------------------

    totale_eventi = pd.read_sql(
        """
        SELECT COUNT(DISTINCT data || tipo_evento)
        AS totale
        FROM presenze
        WHERE stagione = ?
        """,
        conn,
        params=(stagione_selezionata,)
    ).iloc[0]["totale"]

    if pd.isna(totale_eventi):
        totale_eventi = 0

    # --------------------------------------------------------
    # GARE
    # --------------------------------------------------------

    totale_gare = pd.read_sql(
        """
        SELECT COUNT(DISTINCT data)
        AS totale
        FROM presenze
        WHERE stagione = ?
        AND tipo_evento = 'Gara'
        """,
        conn,
        params=(stagione_selezionata,)
    ).iloc[0]["totale"]

    if pd.isna(totale_gare):
        totale_gare = 0

    # --------------------------------------------------------
    # MEDIA STELLE
    # --------------------------------------------------------

    media_stelle = pd.read_sql(
        """
        SELECT AVG(voto) AS media
        FROM presenze
        WHERE stagione = ?
        AND voto IS NOT NULL
        """,
        conn,
        params=(stagione_selezionata,)
    ).iloc[0]["media"]

    if pd.isna(media_stelle):
        media_stelle = 0

    # --------------------------------------------------------
    # ULTIMA ATTIVITA'
    # --------------------------------------------------------

    ultima_attivita = pd.read_sql(
        """
        SELECT MAX(data) AS data
        FROM presenze
        WHERE stagione = ?
        """,
        conn,
        params=(stagione_selezionata,)
    ).iloc[0]["data"]

    if ultima_attivita is None:
        ultima_attivita = "-"

    # --------------------------------------------------------
    # CLASSIFICA PRESENZE
    # --------------------------------------------------------

    query_dashboard = pd.read_sql(
        """
        SELECT
            a.nome,
            SUM(p.presenza) AS presenze,
            COUNT(*) AS registrazioni
        FROM presenze p
        JOIN atleti a
            ON a.id = p.atleta_id
        WHERE p.stagione = ?
        GROUP BY a.nome
        """,
        conn,
        params=(stagione_selezionata,)
    )

    miglior_presenza = "-"
    miglior_percentuale = 0

    if not query_dashboard.empty:

        query_dashboard["percentuale"] = (
            query_dashboard["presenze"]
            /
            query_dashboard["registrazioni"]
            * 100
        )

        best = query_dashboard.sort_values(
            "percentuale",
            ascending=False
        ).iloc[0]

        miglior_presenza = best["nome"]
        miglior_percentuale = round(
            best["percentuale"],
            1
        )

    # --------------------------------------------------------
    # CLASSIFICA STELLE
    # --------------------------------------------------------

    query_stelle = pd.read_sql(
        """
        SELECT
            a.nome,
            AVG(p.voto) AS media
        FROM presenze p
        JOIN atleti a
            ON a.id = p.atleta_id
        WHERE
            p.stagione = ?
            AND p.voto IS NOT NULL
        GROUP BY a.nome
        """,
        conn,
        params=(stagione_selezionata,)
    )

    miglior_rendimento = "-"
    miglior_media = 0

    if not query_stelle.empty:

        best = query_stelle.sort_values(
            "media",
            ascending=False
        ).iloc[0]

        miglior_rendimento = best["nome"]
        miglior_media = round(
            best["media"],
            2
        )

    # --------------------------------------------------------
    # METRICHE
    # --------------------------------------------------------

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "👥 Atleti",
        totale_atleti
    )

    c2.metric(
        "🏊 Registrazioni",
        totale_eventi
    )

    c3.metric(
        "🏁 Gare",
        totale_gare
    )

    c4.metric(
        "⭐ Media stelle",
        round(media_stelle, 2)
    )

    c5.metric(
        "📅 Ultima attività",
        ultima_attivita
    )

    st.markdown("---")

    c6, c7 = st.columns(2)

    c6.metric(
        "🏆 Miglior presenza",
        miglior_presenza,
        f"{miglior_percentuale}%"
    )

    c7.metric(
        "⭐ Miglior rendimento",
        miglior_rendimento,
        miglior_media
    )

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

    st.header("📊 Statistiche")

    storico = pd.read_sql(
        """
        SELECT
            a.nome,
            a.categoria,
            p.tipo_evento,
            p.presenza,
            p.voto
        FROM presenze p
        JOIN atleti a
            ON a.id = p.atleta_id
        WHERE p.stagione = ?
        """,
        conn,
        params=(stagione_selezionata,)
    )

    if storico.empty:

        st.info(
            "Nessun dato disponibile."
        )

    else:

        filtro = st.selectbox(
            "Tipo evento",
            [
                "Tutti",
                "Allenamento in vasca",
                "Allenamento a secco",
                "Gara"
            ]
        )

        if filtro != "Tutti":

            storico = storico[
                storico["tipo_evento"] == filtro
            ]

        stats = storico.groupby(
            ["nome", "categoria"],
            dropna=False
        ).agg(
            registrazioni=(
                "presenza",
                "count"
            ),
            presenze=(
                "presenza",
                "sum"
            ),
            media_stelle=(
                "voto",
                "mean"
            )
        ).reset_index()

        stats["assenze"] = (
            stats["registrazioni"]
            - stats["presenze"]
        )

        stats["percentuale"] = (
            stats["presenze"]
            / stats["registrazioni"]
            * 100
        ).round(1)

        stats["media_stelle"] = (
            stats["media_stelle"]
            .fillna(0)
            .round(2)
        )

        totale_reg = int(
            stats["registrazioni"].sum()
        )

        totale_pres = int(
            stats["presenze"].sum()
        )

        totale_ass = int(
            stats["assenze"].sum()
        )

        media_globale = round(
            stats["media_stelle"].mean(),
            2
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Registrazioni",
            totale_reg
        )

        c2.metric(
            "Presenze",
            totale_pres
        )

        c3.metric(
            "Assenze",
            totale_ass
        )

        c4.metric(
            "Media stelle",
            media_globale
        )

        # =====================================================
        # SCHEDA ATLETA
        # =====================================================

        st.markdown("---")

        st.subheader("👤 Scheda atleta")

        atleta_scheda = st.selectbox(
            "Seleziona atleta",
            sorted(stats["nome"].unique())
        )

        dati_atleta = stats[
            stats["nome"] == atleta_scheda
        ]

        presenze_atleta = int(
            dati_atleta["presenze"].sum()
        )

        assenze_atleta = int(
            dati_atleta["assenze"].sum()
        )

        percentuale_atleta = round(
            dati_atleta["percentuale"].mean(),
            1
        )

        media_stelle_atleta = round(
            dati_atleta["media_stelle"].mean(),
            2
        )

        categoria_atleta = (
            dati_atleta["categoria"]
            .iloc[0]
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "✅ Presenze",
            presenze_atleta
        )

        c2.metric(
            "❌ Assenze",
            assenze_atleta
        )

        c3.metric(
            "%",
            percentuale_atleta
        )

        c4.metric(
            "⭐ Media",
            media_stelle_atleta
        )

        st.write(
            f"**Categoria:** {categoria_atleta}"
        )

        storico_atleta = pd.read_sql(
            """
            SELECT
                p.data,
                p.tipo_evento,
                p.presenza,
                p.voto,
                p.commento
            FROM presenze p
            JOIN atleti a
                ON a.id = p.atleta_id
            WHERE
                a.nome = ?
            AND
                p.stagione = ?
            ORDER BY p.data DESC
            """,
            conn,
            params=(
                atleta_scheda,
                stagione_selezionata
            )
        )

        if not storico_atleta.empty:

            storico_atleta["presenza"] = (
                storico_atleta["presenza"]
                .map({
                    1: "Presente",
                    0: "Assente"
                })
            )

            storico_atleta["stelle"] = (
                storico_atleta["voto"]
                .fillna(0)
                .astype(int)
                .apply(
                    lambda x: "⭐" * x
                )
            )

            st.markdown("---")

            st.subheader(
                "📜 Storico atleta"
            )

            st.dataframe(
                storico_atleta[
                    [
                        "data",
                        "tipo_evento",
                        "presenza",
                        "stelle",
                        "commento"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

        st.dataframe(
            stats,
            use_container_width=True,
            hide_index=True
        )

        # =====================================================
        # CLASSIFICA PRESENZE
        # =====================================================

        st.markdown("---")

        st.subheader("🏆 Classifica presenze")

        classifica = stats.copy()

        classifica = classifica.sort_values(
            by="percentuale",
            ascending=False
        ).reset_index(drop=True)

        medaglie = []

        for i in range(len(classifica)):

            if i == 0:
                medaglie.append("🥇")
            elif i == 1:
                medaglie.append("🥈")
            elif i == 2:
                medaglie.append("🥉")
            else:
                medaglie.append(str(i + 1))

        classifica.insert(
            0,
            "Rank",
            medaglie
        )

        st.dataframe(
            classifica[
                [
                    "Rank",
                    "nome",
                    "categoria",
                    "presenze",
                    "assenze",
                    "percentuale"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        csv = (
            stats
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            "📥 Scarica statistiche CSV",
            csv,
            "statistiche.csv",
            "text/csv"
        )
        
        # =====================================================
        # CLASSIFICA RENDIMENTO
        # =====================================================

        st.markdown("---")

        st.subheader("⭐ Classifica rendimento")

        rendimento = stats.copy()

        rendimento = rendimento.sort_values(
            by="media_stelle",
            ascending=False
        ).reset_index(drop=True)

        medaglie_rendimento = []

        for i in range(len(rendimento)):

            if i == 0:
                medaglie_rendimento.append("🥇")
            elif i == 1:
                medaglie_rendimento.append("🥈")
            elif i == 2:
                medaglie_rendimento.append("🥉")
            else:
                medaglie_rendimento.append(str(i + 1))

        rendimento.insert(
            0,
            "Rank",
            medaglie_rendimento
        )

        st.dataframe(
            rendimento[
                [
                    "Rank",
                    "nome",
                    "categoria",
                    "media_stelle",
                    "presenze",
                    "percentuale"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# TAB 6
# ============================================================

with tab6:

    st.header("🗂️ Storico")

    storico = pd.read_sql(
        """
        SELECT
            p.data,
            p.tipo_evento,
            a.nome,
            a.categoria,
            p.presenza,
            p.voto,
            p.commento
        FROM presenze p
        JOIN atleti a
            ON a.id = p.atleta_id
        WHERE p.stagione = ?
        ORDER BY p.data DESC
        """,
        conn,
        params=(stagione_selezionata,)
    )

    if storico.empty:

        st.info(
            "Nessun storico disponibile."
        )

    else:

        filtro = st.selectbox(
            "Filtro evento",
            [
                "Tutti",
                "Allenamento in vasca",
                "Allenamento a secco",
                "Gara"
            ],
            key="filtro_storico"
        )

        if filtro != "Tutti":

            storico = storico[
                storico["tipo_evento"] == filtro
            ]

        storico["presenza"] = storico["presenza"].map(
            {
                1: "Presente",
                0: "Assente"
            }
        )

        storico["stelle"] = (
            storico["voto"]
            .fillna(0)
            .astype(int)
            .apply(
                lambda x: "⭐" * x
            )
        )

        st.dataframe(
            storico[
                [
                    "data",
                    "tipo_evento",
                    "nome",
                    "categoria",
                    "presenza",
                    "stelle",
                    "commento"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        csv = (
            storico
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            "📥 Scarica storico CSV",
            csv,
            "storico.csv",
            "text/csv"
        )

# ============================================================
# TAB 7
# ============================================================

with tab7:

    st.header("⚙️ Gestione Stagioni")

    # =====================================================
    # NUOVA STAGIONE
    # =====================================================

    st.subheader("➕ Nuova stagione")

    nuova_stagione = st.text_input(
        "Nome stagione",
        placeholder="es. 2026/2027"
    )

    if st.button(
        "➕ Crea stagione"
    ):

        if nuova_stagione.strip() == "":

            st.error(
                "Inserisci il nome della stagione."
            )

        else:

            aggiungi_stagione(
                nuova_stagione.strip()
            )

            st.success(
                "Stagione creata correttamente."
            )

            st.rerun()

    st.markdown("---")

    # =====================================================
    # ELENCO STAGIONI
    # =====================================================

    st.subheader(
        "📋 Stagioni presenti"
    )

    df_stagioni = pd.DataFrame(
        {
            "Stagione": get_stagioni()
        }
    )

    st.dataframe(
        df_stagioni,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    # =====================================================
    # COPIA ATLETI
    # =====================================================

    st.subheader(
        "📄 Copia atleti"
    )

    stagioni_disponibili = (
        get_stagioni()
    )

    if len(stagioni_disponibili) > 1:

        stagione_origine = st.selectbox(
            "Stagione origine",
            stagioni_disponibili,
            key="stagione_origine"
        )

        stagione_destinazione = st.selectbox(
            "Stagione destinazione",
            stagioni_disponibili,
            key="stagione_destinazione"
        )

        if st.button(
            "📄 Copia atleti"
        ):

            if (
                stagione_origine
                ==
                stagione_destinazione
            ):

                st.error(
                    "Le due stagioni devono essere diverse."
                )

            else:

                df_source = get_atleti(
                    stagione_origine
                )

                count = 0

                for _, row in df_source.iterrows():

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
                            row["nome"],
                            row["categoria"],
                            stagione_destinazione
                        )
                    )

                    count += 1

                conn.commit()

                st.success(
                    f"{count} atleti copiati."
                )

                st.rerun()

    else:

        st.info(
            "Servono almeno due stagioni."
        )

    st.markdown("---")

    # =====================================================
    # ELIMINA STAGIONE
    # =====================================================

    st.subheader(
        "🗑️ Elimina stagione"
    )

    stagione_delete = st.selectbox(
        "Seleziona stagione",
        stagioni_disponibili,
        key="delete_stagione"
    )

    conferma = st.checkbox(
        "Confermo eliminazione stagione"
    )

    if st.button(
        "🗑️ Elimina stagione"
    ):

        if not conferma:

            st.error(
                "Devi confermare."
            )

        else:

            elimina_stagione(
                stagione_delete
            )

            st.success(
                "Stagione eliminata."
            )

            st.rerun()

# ============================================================
# TAB 8
# ============================================================

with tab8:

    st.header("💾 Backup & Export")

    # =====================================================
    # EXPORT JSON COMPLETO
    # =====================================================

    st.subheader("📥 Backup JSON completo")

    if st.button("📥 Genera backup JSON"):

        dati = {}

        dati["stagioni"] = pd.read_sql(
            "SELECT * FROM stagioni",
            conn
        ).to_dict(orient="records")

        dati["atleti"] = pd.read_sql(
            "SELECT * FROM atleti",
            conn
        ).to_dict(orient="records")

        dati["presenze"] = pd.read_sql(
            "SELECT * FROM presenze",
            conn
        ).to_dict(orient="records")

        json_data = json.dumps(
            dati,
            ensure_ascii=False,
            indent=2
        )

        st.download_button(
            "💾 Scarica backup JSON",
            json_data,
            file_name="backup_nuoto.json",
            mime="application/json"
        )

    st.markdown("---")

    # =====================================================
    # IMPORT JSON
    # =====================================================

    st.subheader("📤 Ripristino da JSON")

    uploaded_file = st.file_uploader(
        "Carica backup JSON",
        type="json"
    )

    conferma_import = st.checkbox(
        "Confermo il ripristino completo"
    )

    if (
        uploaded_file is not None
        and
        st.button("📤 Importa backup")
    ):

        if not conferma_import:

            st.error(
                "Devi confermare il ripristino."
            )

        else:

            dati = json.loads(
                uploaded_file
                .getvalue()
                .decode("utf-8")
            )

            c.execute(
                "DELETE FROM presenze"
            )

            c.execute(
                "DELETE FROM atleti"
            )

            c.execute(
                "DELETE FROM stagioni"
            )

            for row in dati.get(
                "stagioni",
                []
            ):

                c.execute(
                    """
                    INSERT INTO stagioni(
                        id,
                        nome
                    )
                    VALUES(?,?)
                    """,
                    (
                        row["id"],
                        row["nome"]
                    )
                )

            for row in dati.get(
                "atleti",
                []
            ):

                c.execute(
                    """
                    INSERT INTO atleti(
                        id,
                        nome,
                        categoria,
                        stagione
                    )
                    VALUES(?,?,?,?)
                    """,
                    (
                        row["id"],
                        row["nome"],
                        row["categoria"],
                        row["stagione"]
                    )
                )

            for row in dati.get(
                "presenze",
                []
            ):

                c.execute(
                    """
                    INSERT INTO presenze(
                        id,
                        atleta_id,
                        data,
                        stagione,
                        tipo_evento,
                        presenza,
                        voto,
                        commento
                    )
                    VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        row["id"],
                        row["atleta_id"],
                        row["data"],
                        row["stagione"],
                        row["tipo_evento"],
                        row["presenza"],
                        row["voto"],
                        row["commento"]
                    )
                )

            conn.commit()

            st.success(
                "Backup importato correttamente."
            )

            st.rerun()

    st.markdown("---")

    # =====================================================
    # EXPORT EXCEL
    # =====================================================

    st.subheader("📊 Export Excel")

    if st.button(
        "📊 Genera Excel stagione"
    ):

        output = BytesIO()

        storico = pd.read_sql(
            """
            SELECT
                p.data,
                p.tipo_evento,
                a.nome,
                a.categoria,
                p.presenza,
                p.voto,
                p.commento
            FROM presenze p
            JOIN atleti a
                ON a.id = p.atleta_id
            WHERE p.stagione = ?
            """,
            conn,
            params=(stagione_selezionata,)
        )

        atleti = get_atleti(
            stagione_selezionata
        )

        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:

            atleti.to_excel(
                writer,
                sheet_name="Atleti",
                index=False
            )

            storico.to_excel(
                writer,
                sheet_name="Storico",
                index=False
            )

        output.seek(0)

        st.download_button(
            "📥 Scarica Excel",
            output.getvalue(),
            file_name=(
                f"nuoto_"
                f"{stagione_selezionata}.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            )
        )

# ============================================================
# TAB 9 - CALENDARIO REGISTRAZIONI
# ============================================================

with tab9:

    st.header("📅 Calendario registrazioni")

    calendario = pd.read_sql(
        """
        SELECT
            data,
            tipo_evento,
            COUNT(*) AS registrazioni,
            SUM(presenza) AS presenti
        FROM presenze
        WHERE stagione = ?
        GROUP BY data, tipo_evento
        ORDER BY data DESC
        """,
        conn,
        params=(stagione_selezionata,)
    )

    if calendario.empty:

        st.info(
            "Nessuna registrazione presente."
        )

    else:

        filtro = st.selectbox(
            "Tipo evento",
            [
                "Tutti",
                "Allenamento in vasca",
                "Allenamento a secco",
                "Gara"
            ],
            key="filtro_calendario"
        )

        if filtro != "Tutti":

            calendario = calendario[
                calendario["tipo_evento"] == filtro
            ]

        st.dataframe(
            calendario,
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")

        st.subheader(
            "🔄 Apri registrazione"
        )

        scelta = st.selectbox(
            "Seleziona una registrazione",
            [
                f"{row['data']} | {row['tipo_evento']}"
                for _, row in calendario.iterrows()
            ]
        )

        if st.button(
            "🔄 Apri registro"
        ):

            parti = scelta.split(" | ")

            st.session_state.data_aperta = parti[0]
            st.session_state.tipo_aperto = parti[1]

            st.success(
                "Registrazione selezionata."
            )

            st.info(
                "Vai nella scheda corrispondente."
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

    data_default = date.today()

    if (
        st.session_state.data_aperta is not None
        and
        st.session_state.tipo_aperto == tipo_evento
    ):

        try:

            data_default = pd.to_datetime(
                st.session_state.data_aperta
            ).date()

        except:
            pass

    data_evento = st.date_input(
        "Data",
        value=data_default,
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
