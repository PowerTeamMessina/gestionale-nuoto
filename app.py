import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
from io import BytesIO
import json
import base64
import requests
import os
from datetime import datetime

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

def classifica_rendimento_evento(
    storico,
    tipo_evento
):

    dati = storico[
        storico["tipo_evento"] == tipo_evento
    ]

    if dati.empty:

        st.info("Nessun dato disponibile.")
        return

    ranking = dati.groupby(
        ["nome", "categoria"],
        dropna=False
    ).agg(
        registrazioni=("presenza", "count"),
        presenze=("presenza", "sum"),
        media_voti=("voto", "mean")
    ).reset_index()

    ranking["percentuale"] = (
        ranking["presenze"]
        /
        ranking["registrazioni"]
        * 100
    ).round(1)

    ranking["media_voti"] = (
        ranking["media_voti"]
        .fillna(0)
        .round(2)
    )

    ranking = ranking.sort_values(
        by=[
            "media_voti",
            "percentuale"
        ],
        ascending=[
            False,
            False
        ]
    ).reset_index(drop=True)

    posizioni = []

    for i in range(len(ranking)):

        if i == 0:
            
            posizioni.append(1)

        else:

            stesso_voto = (
                ranking.iloc[i]["media_voti"]
                ==
                ranking.iloc[i - 1]["media_voti"]
            )

            stessa_presenza = (
                ranking.iloc[i]["percentuale"]
                ==
                ranking.iloc[i - 1]["percentuale"]
            )

            if stesso_voto and stessa_presenza:

                posizioni.append(
                    posizioni[-1]
                )

            else:

                posizioni.append(i + 1)

    ranking.insert(
        0,
        "Posizione",
        posizioni
    )

    st.dataframe(
        ranking[
            [
                "Posizione",
                "nome",
                "categoria",
                "media_voti",
                "percentuale"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

# ============================================================
# BACKUP AUTOMATICO
# ============================================================

def crea_backup_automatico():

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

    with open(
        "backup_automatico.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            dati,
            f,
            ensure_ascii=False,
            indent=2
        )

def upload_backup_github():

    token = st.secrets["GITHUB_TOKEN"]
    owner = st.secrets["GITHUB_OWNER"]
    repo = st.secrets["GITHUB_REPO"]

    path = "backup_automatico.json"

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        contenuto = f.read()

    contenuto_b64 = base64.b64encode(
        contenuto.encode("utf-8")
    ).decode("utf-8")

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/contents/{path}"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    sha = None

    risposta = requests.get(
        url,
        headers=headers
    )

    if risposta.status_code == 200:

        sha = risposta.json()["sha"]

    payload = {
        "message": "Aggiornamento backup automatico",
        "content": contenuto_b64
    }

    if sha is not None:

        payload["sha"] = sha

    upload = requests.put(
        url,
        headers=headers,
        json=payload
    )

    if upload.status_code in [200, 201]:

        st.success(
            "✅ Backup sincronizzato su GitHub"
        )

    else:

        st.error(
            f"❌ Errore GitHub: "
            f"{upload.status_code}"
        )

def scarica_backup_github():

    token = st.secrets["GITHUB_TOKEN"]
    owner = st.secrets["GITHUB_OWNER"]
    repo = st.secrets["GITHUB_REPO"]

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/contents/"
        f"backup_automatico.json"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    risposta = requests.get(
        url,
        headers=headers
    )

    if risposta.status_code != 200:

        st.error(
            "❌ Impossibile scaricare il backup."
        )

        return False

    data = risposta.json()

    contenuto = base64.b64decode(
        data["content"]
    ).decode("utf-8")

    with open(
        "backup_automatico.json",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(contenuto)

    st.success(
        "✅ Backup scaricato da GitHub"
    )

    return True

def ripristina_backup_locale():

    with open(
        "backup_automatico.json",
        "r",
        encoding="utf-8"
    ) as f:

        dati = json.load(f)

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

    return True

def aggiornamento_automatico_giornaliero():

    file_data = "ultimo_aggiornamento.txt"

    oggi = datetime.now().strftime("%Y-%m-%d")

    ultima_data = None

    if os.path.exists(file_data):

        with open(file_data, "r") as f:
            ultima_data = f.read().strip()

    if ultima_data != oggi:

        try:

            if scarica_backup_github():

                ripristina_backup_locale()

                with open(file_data, "w") as f:
                    f.write(oggi)

        except Exception as e:

            st.error(
                f"Errore aggiornamento automatico: {e}"
            )


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
# REGISTRO GENERICO
# ============================================================

def mostra_registro(titolo, tipo_evento, stagione):

    st.header(titolo)

    data_default = date.today()

    if (
        st.session_state.data_aperta is not None
        and st.session_state.tipo_aperto == tipo_evento
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
        key=f"data_{tipo_evento}",
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
        tipo_evento,
    )

    chiave_data = f"{tipo_evento}_{data_evento}"

    if (
        "ultima_data_caricata" not in st.session_state
        or
        st.session_state.ultima_data_caricata != chiave_data
    ):

        st.session_state.registro = {}
        st.session_state.ultima_data_caricata = chiave_data

    registro_esistente = not presenze_salvate.empty

    if registro_esistente:
        st.success(
            "✅ Registro già esistente. "
            "Puoi modificarlo e salvarlo nuovamente."
        )
    else:
        st.info("📝 Nuovo registro.")

    dati_salvati = {}

    if registro_esistente:
        for _, r in presenze_salvate.iterrows():
            dati_salvati[int(r["atleta_id"])] = {
                "presenza": bool(r["presenza"]),
                "voto": int(r["voto"]) if pd.notna(r["voto"]) else 6,
                "commento": r["commento"] if pd.notna(r["commento"]) else "",
            }

    # -----------------------------------------
    # INIZIALIZZAZIONE SESSION
    # -----------------------------------------

    for _, row in df_atleti.iterrows():

        atleta_id = int(row["id"])

        if atleta_id in dati_salvati:

            st.session_state.registro[atleta_id] = dati_salvati[atleta_id]

        else:

            st.session_state.registro[atleta_id] = {
                "presenza": False,
                "voto": 6,
                "commento": "",
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

        st.markdown(f"### {row['nome']}")

        presenza = st.toggle(
            "Presente",
            value=st.session_state.registro[atleta_id]["presenza"],
            key=f"pres_{tipo_evento}_{data_evento}_{atleta_id}",
        )

        voto = None

        if presenza:
            presenti += 1

            voto_corrente = st.session_state.registro[atleta_id]["voto"]

            voto = st.slider(
                "Voto",
                min_value=1,
                max_value=10,
                value=voto_corrente if voto_corrente is not None else 6,
                key=f"voto_{tipo_evento}_{data_evento}_{atleta_id}"
            )

        commento = st.text_input(
            "Commento",
            value=st.session_state.registro[atleta_id]["commento"],
            key=f"comm_{tipo_evento}_{data_evento}_{atleta_id}",
        )

        st.session_state.registro[atleta_id] = {
            "presenza": presenza,
            "voto": voto if presenza else 6,
            "commento": commento,
        }

        st.markdown("---")

    assenti = totale - presenti

    c1, c2 = st.columns(2)

    c1.metric("Presenti", presenti)
    c2.metric("Assenti", assenti)

    # -----------------------------------------
    # SALVATAGGIO
    # -----------------------------------------

    if st.button(
        f"💾 Salva {tipo_evento}",
        key=f"salva_{tipo_evento}",
    ):
        for _, row in df_atleti.iterrows():

            atleta_id = int(row["id"])
            dati = st.session_state.registro[atleta_id]

            salva_presenza(
                atleta_id,
                data_evento,
                stagione,
                tipo_evento,
                dati["presenza"],
                dati["voto"] if dati["presenza"] else None,
                dati["commento"],
            )

        crea_backup_automatico()
        upload_backup_github()

        if registro_esistente:
            st.success("✅ Registro aggiornato correttamente.")
        else:
            st.success("✅ Nuovo registro salvato.")

        st.rerun()
        
def check_admin():

    if "admin" not in st.session_state:
        st.session_state.admin = False

    st.markdown("---")
    st.subheader("🔐 Accesso amministratore")

    if not st.session_state.admin:

        password = st.text_input(
            "Password amministratore",
            type="password"
        )

        if st.button("Accedi"):

            if password == st.secrets["ADMIN_PASSWORD"]:

                st.session_state.admin = True
                st.rerun()

            else:

                st.error(
                    "❌ Password errata"
                )

    else:

        st.success(
            "✅ Modalità amministratore attiva"
        )

        if st.button("🚪 Logout amministratore"):

            st.session_state.admin = False
            st.rerun()


# ============================================================
# HEADER
# ============================================================

st.title("🏊 Gestionale Nuoto Power Team 🏊")

st.markdown(
    """
    *created by Gabriele Grifò
    """
)

check_admin()

aggiornamento_automatico_giornaliero()

st.write("Admin:", st.session_state.admin)

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

(tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12) = st.tabs([
        "🏠 Dashboard",
        "📋 Allenamento vasca",
        "🏋️ Allenamento secco",
        "🏁 Gare",
        "👥 Atleti",
        "📊 Statistiche",
        "🗂️ Storico",
        "⚙️ Stagioni",
        "💾 Backup",
        "📅 Calendario",
        "📋 Registro settimanale",
        "🏁 Archivio Gare",
        "📈 Analisi Stagione"
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
        AND tipo_evento = 'Gare'
        """,
        conn,
        params=(stagione_selezionata,)
    ).iloc[0]["totale"]

    if pd.isna(totale_gare):
        totale_gare = 0

    # --------------------------------------------------------
    # MEDIA voti
    # --------------------------------------------------------

    media_voti = pd.read_sql(
        """
        SELECT AVG(voto) AS media
        FROM presenze
        WHERE stagione = ?
        AND voto IS NOT NULL
        """,
        conn,
        params=(stagione_selezionata,)
    ).iloc[0]["media"]

    if pd.isna(media_voti):
        media_voti = 0

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

        miglior_presenza = "-"
        miglior_percentuale = 0

        if not query_dashboard.empty:

            query_dashboard["percentuale"] = (
                query_dashboard["presenze"]
                /
                query_dashboard["registrazioni"]
            * 100
            )

            miglior_percentuale = round(
                query_dashboard["percentuale"].max(),
                1 
            )

            ex_aequo = query_dashboard[
                query_dashboard["percentuale"]
                == query_dashboard["percentuale"].max()
            ]

            miglior_presenza = ", ".join(
                ex_aequo["nome"].tolist()
            )

    # --------------------------------------------------------
    # CLASSIFICA VOTI
    # --------------------------------------------------------

    query_voti = pd.read_sql(
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

    if not query_voti.empty:

        miglior_rendimento = "-"
        miglior_media = 0

        if not query_voti.empty:

            miglior_media = round(
                query_voti["media"].max(),
                2
            )

            ex_aequo = query_voti[
                query_voti["media"]
                == query_voti["media"].max()
            ]

            miglior_rendimento = ", ".join(
                ex_aequo["nome"].tolist()
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
        "🎯 Media voti",
        round(media_voti, 2)
    )

    c5.metric(
        "📅 Ultima attività",
        ultima_attivita
    )

    st.markdown("---")

    st.subheader("🏆 Hall of FAME 🏆")
    
    c6, c7 = st.columns(2)

# --------------------------------------------------------
# PODIO PRESENZE
# --------------------------------------------------------

with c6:

    st.subheader("🏆 Podio presenze")

    if query_dashboard.empty:

        st.info("Nessun dato disponibile.")

    else:

        podio_presenze = query_dashboard.copy()

        podio_presenze["percentuale"] = (
            podio_presenze["presenze"]
            /
            podio_presenze["registrazioni"]
            * 100
        ).round(1)

        podio_presenze = podio_presenze.sort_values(
            by="percentuale",
            ascending=False
        ).reset_index(drop=True)

        valori_presenza = (
            podio_presenze["percentuale"]
            .drop_duplicates()
            .head(3)
            .tolist()
        )

        righe_podio = []

        medaglie = ["🥇", "🥈", "🥉"]

        for i, valore in enumerate(valori_presenza):

            gruppo = podio_presenze[
                podio_presenze["percentuale"] == valore
            ]

            nomi = ", ".join(
                gruppo["nome"].tolist()
            )

            righe_podio.append(
                {
                    "Medaglia": medaglie[i],
                    "Atleta/i": nomi,
                    "% Presenza": valore
                }
            )

        st.dataframe(
            pd.DataFrame(righe_podio),
            use_container_width=True,
            hide_index=True
        )


# --------------------------------------------------------
# PODIO RENDIMENTO
# --------------------------------------------------------

with c7:

    st.subheader("🎯 Podio rendimento")

    if query_voti.empty:

        st.info("Nessun dato disponibile.")

    else:

        podio_rendimento = query_voti.copy()

        podio_rendimento["media"] = (
            podio_rendimento["media"]
            .round(2)
        )

        podio_rendimento = podio_rendimento.sort_values(
            by="media",
            ascending=False
        ).reset_index(drop=True)

        valori_rendimento = (
            podio_rendimento["media"]
            .drop_duplicates()
            .head(3)
            .tolist()
        )

        righe_podio = []

        medaglie = ["🥇", "🥈", "🥉"]

        for i, valore in enumerate(valori_rendimento):

            gruppo = podio_rendimento[
                podio_rendimento["media"] == valore
            ]

            nomi = ", ".join(
                gruppo["nome"].tolist()
            )

            righe_podio.append(
                {
                    "Medaglia": medaglie[i],
                    "Atleta/i": nomi,
                    "Media voto": valore
                }
            )

        st.dataframe(
            pd.DataFrame(righe_podio),
            use_container_width=True,
            hide_index=True
        )
    
    # --------------------------------------------------------
    # HALL OF SHAME
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader("💀 Hall of SHAME 💀")

    classifica_assenze = query_dashboard.copy()

    classifica_assenze["assenze"] = (
        classifica_assenze["registrazioni"]
        - classifica_assenze["presenze"]
    )

    classifica_assenze["percentuale_assenze"] = (
        classifica_assenze["assenze"]
        /
        classifica_assenze["registrazioni"]
        * 100
    ).round(1)

    classifica_assenze = classifica_assenze.sort_values(
        by="percentuale_assenze",
        ascending=False
    ).reset_index(drop=True)

    icone = []

    for _, row in classifica_assenze.iterrows():

        p = row["percentuale_assenze"]

        if p >= 70:
            icone.append("💀💀💀")
        elif p >= 50:
            icone.append("🙈")
        elif p >= 30:
            icone.append("😴")
        elif p >= 15:
            icone.append("🤨")
        else:
            icone.append("😇")

    classifica_assenze.insert(
        0,
        "Hall of Shame",
        icone
    )

    st.dataframe(
        classifica_assenze[
            [
                "Hall of Shame",
                "nome",
                "assenze",
                "registrazioni",
                "percentuale_assenze"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )
    
    # --------------------------------------------------------
    # GRAFICI
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader("📊 Analisi visiva")

    grafico_presenze = pd.read_sql(
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

    if not grafico_presenze.empty:

        grafico_presenze["percentuale"] = (
            grafico_presenze["presenze"]
            /
            grafico_presenze["registrazioni"]
            * 100
        ).round(1)

        st.write("🏆 Percentuale presenze")

        st.bar_chart(
            grafico_presenze.set_index("nome")[
                "percentuale"
            ]
        )

    grafico_voti = pd.read_sql(
        """
        SELECT
            a.nome,
            AVG(p.voto) AS media_voti
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

    if not grafico_voti.empty:

        st.write("🎯 Media voti")

        st.bar_chart(
            grafico_voti.set_index("nome")[
                "media_voti"
            ]
        )
    
    # --------------------------------------------------------
    # BACKUP AUTOMATICO
    # --------------------------------------------------------
    if not st.session_state.admin:
        
        st.warning(
            "🔒 Backup disponibile solo agli amministratori."
        )
        pass
        
    else:

        st.markdown("---")

        st.subheader("💾 Stato backup")

        if os.path.exists(
            "backup_automatico.json"
        ):

            ultima_modifica = datetime.fromtimestamp(
                os.path.getmtime(
                    "backup_automatico.json"
                )
            )

            dimensione = round(
                os.path.getsize(
                    "backup_automatico.json"
                ) / 1024,
                2
            )

            c1, c2 = st.columns(2)

            c1.metric(
                "📅 Ultimo backup",
                ultima_modifica.strftime(
                    "%d/%m/%Y %H:%M"
                )
            )

            c2.metric(
                "📦 Dimensione",
                f"{dimensione} KB"
            )

            with open(
                "backup_automatico.json",
                "r",
                encoding="utf-8"
                
            ) as f:

                st.download_button(
                    "📥 Scarica backup automatico",
                    f.read(),
                    "backup_automatico.json",
                    "application/json"
                )

        else:

            st.warning(
                "Nessun backup automatico disponibile."
            )

# ============================================================
# TAB 1
# ============================================================

with tab1:

    if st.session_state.admin:

        mostra_registro("📋 Allenamento in vasca", "Allenamento in vasca", stagione_selezionata)
        pass

    else:
        st.warning(
            "🔒 Attività disponibile solo agli amministratori."
        )

# ============================================================
# TAB 2
# ============================================================

with tab2:

    if st.session_state.admin:

        mostra_registro("📋 Allenamento a secco", "Allenamento a secco", stagione_selezionata)
        pass
        
    else:
        
        st.warning(
            "🔒 Attività disponibile solo agli amministratori."
        )

# ============================================================
# TAB 3
# ============================================================

with tab3:

    if st.session_state.admin:

        mostra_registro("🏁 Gare", "Gare", stagione_selezionata)
        pass
        
    else:
        
        st.warning(
              "🔒 Attività disponibile solo agli amministratori."
        )

# ============================================================
# TAB 4
# ============================================================

with tab4:

    if st.session_state.admin:

        st.info("Per modificare gli atleti è necessario l'accesso amministratore.")

        st.header("👥 Gestione Atleti")

        # === FORM NUOVO ATLETA ===
        with st.form("form_nuovo_atleta", clear_on_submit=True):

            nome = st.text_input("Nome atleta")

            categoria = st.selectbox(
                "Categoria",
                [
                    "Assoluti",
                    "Ragazzi",
                    "Esordienti A",
                    "Esordienti B",
                ],
            )

            aggiungi = st.form_submit_button("➕ Aggiungi atleta")

            if aggiungi:
                if nome.strip() == "":
                    st.error("Inserisci il nome dell'atleta.")
                else:
                    aggiungi_atleta(
                        nome.strip(),
                        categoria.strip(),
                        stagione_selezionata,
                    )

                    st.success("Atleta aggiunto correttamente.")
                    st.rerun()

        st.markdown("---")

        # === LISTA ATLETI ===
        df_atleti = get_atleti(stagione_selezionata)

        if df_atleti.empty:
            st.info("Nessun atleta inserito.")
        else:
            st.subheader("Lista atleti")

            st.dataframe(
                df_atleti,
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("---")

            # === MODIFICA CATEGORIA ===
            st.subheader("✏️ Modifica categoria")

            opzioni = {
                f"{row['nome']} ({pulisci_categoria(row['categoria'])})": int(row["id"])
                for _, row in df_atleti.iterrows()
            }

            atleta_scelto = st.selectbox(
                "Atleta",
                list(opzioni.keys()),
                key="sel_atleta_categoria",
            )

            nuova_categoria = st.text_input(
                "Nuova categoria",
                key="nuova_categoria",
            )

            if st.button("💾 Aggiorna categoria"):
                aggiorna_categoria_atleta(
                    opzioni[atleta_scelto],
                    nuova_categoria,
                )

                st.success("Categoria aggiornata.")
                st.rerun()

            st.markdown("---")

            # === ELIMINA ATLETA ===
            st.subheader("🗑️ Elimina atleta")

            atleta_delete = st.selectbox(
                "Seleziona atleta da eliminare",
                list(opzioni.keys()),
                key="sel_delete_atleta",
            )

            conferma = st.checkbox("Confermo eliminazione atleta")

            if st.button("🗑️ Elimina atleta"):
                if not conferma:
                    st.error("Devi confermare.")
                else:
                    elimina_atleta(opzioni[atleta_delete])

                    st.success("Atleta eliminato.")
                    st.rerun()
                    pass

    else:
        st.warning("🔒 Attività disponibile solo agli amministratori.")


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
                "Gare"
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
            media_voti=(
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

        stats["media_voti"] = (
            stats["media_voti"]
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
            stats["media_voti"].mean(),
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
            "Media voti",
            media_globale
        )

        # =====================================================
        # SCHEDA ATLETA AVANZATA
        # =====================================================

        st.markdown("---")

        st.subheader("👤 Scheda atleta avanzata")

        atleta_scheda = st.selectbox(
            "Seleziona atleta",
            sorted(stats["nome"].unique()),
            key="scheda_atleta"
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

        media_voti_atleta = round(
            dati_atleta["media_voti"].mean(),
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
            "% Presenze",
            percentuale_atleta
        )

        c4.metric(
            "⭐ Media",
            media_voti_atleta
        )

        st.write(
            f"**Categoria:** {categoria_atleta}"
        )

        # -----------------------------------------------------
        # STORICO ATLETA
        # -----------------------------------------------------

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
                AND p.stagione = ?
            ORDER BY p.data DESC
            """,
            conn,
            params=(
                atleta_scheda,
                stagione_selezionata
            )
        )

        if not storico_atleta.empty:

            gare_disputate = len(
                storico_atleta[
                    storico_atleta["tipo_evento"]
                    == "Gare"
                ]
            )

            st.metric(
                "🏁 Gare disputate",
                gare_disputate
            )

            # -----------------------------------------
            # GRAFICO PRESENZE
            # -----------------------------------------

            grafico_presenze = storico_atleta.copy()

            grafico_presenze["data"] = pd.to_datetime(
                grafico_presenze["data"]
            )

            grafico_presenze = (
                grafico_presenze
                .sort_values("data")
            )

            st.markdown("---")

            st.subheader(
                "📈 Andamento presenze"
            )

            st.line_chart(
                grafico_presenze.set_index("data")[
                    "presenza"
                ]
            )

            # -----------------------------------------
            # GRAFICO voti
            # -----------------------------------------

            grafico_voti = (
                grafico_presenze.copy()
            )

            grafico_voti = grafico_voti[
                grafico_voti["voto"].notna()
            ]

            if not grafico_voti.empty:

                st.subheader(
                    "🎯 Andamento voti"
                )

                st.line_chart(
                    grafico_voti.set_index(
                        "data"
                    )[
                        "voto"
                    ]
                )

            # -----------------------------------------
            # ULTIME 10 ATTIVITA'
            # -----------------------------------------

            storico_atleta["presenza"] = (
                storico_atleta["presenza"]
                .map({
                    1: "✅",
                    0: "❌"
                })
            )

            storico_atleta["voto"] = (
                storico_atleta["voto"]
                .fillna("")
            )

            st.markdown("---")

            st.subheader(
                "📜 Ultime 10 attività"
            )

            st.dataframe(
                storico_atleta[
                    [
                        "data",
                        "tipo_evento",
                        "presenza",
                        "voto",
                        "commento"
                    ]
                ]
                .head(10),
                use_container_width=True,
                hide_index=True
            )

        # =====================================================
        # CLASSIFICA PRESENZE
        # =====================================================

        st.markdown("---")

        st.subheader("🏆 Classifica presenze")

        classifica = stats.copy()

        # Ordina prima per percentuale presenza decrescente
        classifica = classifica.sort_values(
            by="percentuale",
            ascending=False
        ).reset_index(drop=True)

        # Calcolo posizioni con ex aequo
        posizioni = []

        for i in range(len(classifica)):

            if i == 0:

                posizioni.append(1)

            else:

                if (
                    classifica.iloc[i]["percentuale"]
                    ==
                    classifica.iloc[i - 1]["percentuale"]
                ):

                    posizioni.append(
                    posizioni[-1]
                )

                else:

                    posizioni.append(i + 1)

        classifica.insert(
            0,
            "Posizione",
            posizioni
        )

        st.dataframe(
            classifica[
                [
                    "Posizione",
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

        st.subheader("🎯 Classifica rendimento complessivo")

        rendimento = stats.copy()

        rendimento = rendimento.sort_values(
            by=[
                "media_voti",
                "percentuale"
            ],
            ascending=[
                False,
                False
            ]
        ).reset_index(drop=True)

        medaglie_rendimento = []

        rank = []

        posizione = 1

        for i in range(len(rendimento)):

            if i == 0:

                rank.append(1)

            else:

                stesso_voto = (
                    rendimento.iloc[i]["media_voti"]
                    ==
                    rendimento.iloc[i - 1]["media_voti"]
                )

                stessa_presenza = (
                    rendimento.iloc[i]["percentuale"]
                    ==
                    rendimento.iloc[i - 1]["percentuale"]
                )

                if stesso_voto and stessa_presenza:

                    rank.append(rank[-1])

                else:

                    posizione = i + 1
                    rank.append(posizione)

        rendimento.insert(
            0,
            "Rank",
            rank
        )

        st.dataframe(
            rendimento[
                [
                    "Rank",
                    "nome",
                    "categoria",
                    "media_voti",
                    "presenze",
                    "percentuale"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")
        st.subheader("🏊 Classifica rendimento - Allenamento in vasca")

        classifica_rendimento_evento(
            storico,
            "Allenamento in vasca"
        )

        st.markdown("---")
        st.subheader("🏋️ Classifica rendimento - Allenamento a secco")

        classifica_rendimento_evento(
            storico,
            "Allenamento a secco"
        )

        st.markdown("---")
        st.subheader("🏁 Classifica rendimento - Gare")

        classifica_rendimento_evento(
            storico,
            "Gare"
        )

# ============================================================
# TAB 6
# ============================================================

with tab6:
    if not st.session_state.admin:
        
        st.warning(
            "🔒 Attività disponibile solo agli amministratori."
        )
        pass

    else:
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
                    "Gare"
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

            storico["voto"] = storico["voto"].fillna("")

            st.dataframe(
                storico[
                    [
                        "data",
                        "tipo_evento",
                        "nome",
                        "categoria",
                        "presenza",
                        "voto",
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

    if not st.session_state.admin:
        
        st.warning(
            "🔒 Attività disponibile solo agli amministratori."
        )
        pass

    else:
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

    if not st.session_state.admin:

        st.warning(
            "🔒 Backup disponibile solo agli amministratori."
        )
        pass

    else:

        st.header("💾 Backup & Export")

        st.markdown("---")

        st.subheader("📥 Ripristino da GitHub")

        if st.button(
            "📥 Scarica e ripristina backup GitHub"
        ):

            if scarica_backup_github():

                ripristina_backup_locale()

                st.success(
                    "✅ Backup ripristinato correttamente"
                )

                st.rerun()

        st.markdown("---")

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
                "Gare"
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
# TAB 10 - REGISTRO SETTIMANALE
# ============================================================

with tab10:

    st.header("📋 Registro Settimanale")

    data_riferimento = st.date_input(
        "Seleziona una data della settimana"
    )

    inizio_settimana = (
        pd.Timestamp(data_riferimento)
        - pd.Timedelta(days=data_riferimento.weekday())
    )

    fine_settimana = (
        inizio_settimana
        + pd.Timedelta(days=6)
    )

    st.info(
        f"Settimana dal "
        f"{inizio_settimana.date()} "
        f"al "
        f"{fine_settimana.date()}"
    )

    storico = pd.read_sql(
        """
        SELECT
            a.nome,
            p.data,
            p.presenza
        FROM presenze p
        JOIN atleti a
            ON a.id = p.atleta_id
        WHERE
            p.stagione = ?
        """,
        conn,
        params=(stagione_selezionata,)
    )

    if storico.empty:

        st.info(
            "Nessuna registrazione disponibile."
        )

    else:

        storico["data"] = pd.to_datetime(
            storico["data"]
        )

        storico = storico[
            (
                storico["data"]
                >= inizio_settimana
            )
            &
            (
                storico["data"]
                <= fine_settimana
            )
        ]

        if storico.empty:

            st.info(
                "Nessuna attività nella settimana selezionata."
            )

        else:

            giorni = [
                inizio_settimana + pd.Timedelta(days=i)
                for i in range(7)
            ]

            risultati = []

            for atleta in sorted(
                storico["nome"].unique()
            ):

                riga = {
                    "Atleta": atleta
                }

                presenti = 0
                totale = 0

                dati_atleta = storico[
                    storico["nome"] == atleta
                ]

                for giorno in giorni:

                    giorno_str = giorno.strftime(
                        "%d/%m"
                    )

                    giorno_dati = dati_atleta[
                        dati_atleta["data"].dt.date
                        == giorno.date()
                    ]

                    if giorno_dati.empty:

                        riga[giorno_str] = "-"

                    else:

                        presenza = int(
                            giorno_dati[
                                "presenza"
                            ].max()
                        )

                        if presenza == 1:

                            riga[giorno_str] = "✅"
                            presenti += 1

                        else:

                            riga[giorno_str] = "❌"

                        totale += 1

                riga["Totale"] = (
                    f"{presenti}/{totale}"
                    if totale > 0
                    else "-"
                )

                risultati.append(
                    riga
                )

            df_settimana = pd.DataFrame(
                risultati
            )

            st.dataframe(
                df_settimana,
                use_container_width=True,
                hide_index=True
            )

# ============================================================
# TAB 11 - ARCHIVIO GARE
# ============================================================

with tab11:

    st.header("🏁 Archivio Gare")

    archivio = pd.read_sql(
        """
        SELECT
            p.data,
            a.nome,
            a.categoria,
            p.presenza,
            p.voto,
            p.commento
        FROM presenze p
        JOIN atleti a
            ON a.id = p.atleta_id
        WHERE
            p.stagione = ?
            AND p.tipo_evento = 'Gare'
        ORDER BY p.data DESC
        """,
        conn,
        params=(stagione_selezionata,)
    )

    if archivio.empty:

        st.info(
            "Nessuna gara registrata."
        )

    else:

        ricerca = st.text_input(
            "🔎 Cerca atleta"
        )

        if ricerca:

            archivio = archivio[
                archivio["nome"]
                .str.contains(
                    ricerca,
                    case=False,
                    na=False
                )
            ]

        archivio["presenza"] = (
            archivio["presenza"]
            .map({
                1: "✅ Presente",
                0: "❌ Assente"
            })
        )

        archivio["voto"] = archivio["voto"].fillna("")

        totale_gare = (
            archivio["data"]
            .nunique()
        )

        totale_atleti = (
            archivio["nome"]
            .nunique()
        )

        c1, c2 = st.columns(2)

        c1.metric(
            "🏁 Gare registrate",
            totale_gare
        )

        c2.metric(
            "👥 Atleti coinvolti",
            totale_atleti
        )

        st.markdown("---")

        st.dataframe(
            archivio[
                [
                    "data",
                    "nome",
                    "categoria",
                    "presenza",
                    "voto",
                    "commento"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        csv = (
            archivio
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            "📥 Scarica archivio gare CSV",
            csv,
            "archivio_gare.csv",
            "text/csv"
        )
    
# ============================================================
# TAB 12 - ANALISI STAGIONE
# ============================================================

with tab12:

    st.header("📈 Analisi Stagione")

    analisi = pd.read_sql(
        """
        SELECT
            data,
            tipo_evento,
            presenza,
            voto
        FROM presenze
        WHERE stagione = ?
        """,
        conn,
        params=(stagione_selezionata,)
    )

    if analisi.empty:

        st.info(
            "Nessun dato disponibile."
        )

    else:

        analisi["data"] = pd.to_datetime(
            analisi["data"]
        )

        analisi["mese"] = (
            analisi["data"]
            .dt.strftime("%Y-%m")
        )

        # ----------------------------------------------------
        # ANALISI MENSILE
        # ----------------------------------------------------

        mensile = analisi.groupby(
            "mese"
        ).agg(
            registrazioni=(
                "presenza",
                "count"
            ),
            presenze=(
                "presenza",
                "sum"
            ),
            media_voti=(
                "voto",
                "mean"
            )
        ).reset_index()

        mensile["percentuale"] = (
            mensile["presenze"]
            /
            mensile["registrazioni"]
            * 100
        ).round(1)

        mensile["media_voti"] = (
            mensile["media_voti"]
            .fillna(0)
            .round(2)
        )

        # ----------------------------------------------------
        # BEST / WORST MONTH
        # ----------------------------------------------------

        best_month = mensile.sort_values(
            "percentuale",
            ascending=False
        ).iloc[0]

        worst_month = mensile.sort_values(
            "percentuale",
            ascending=True
        ).iloc[0]

        c1, c2 = st.columns(2)

        c1.metric(
            "🏆 Miglior mese",
            best_month["mese"],
            f"{best_month['percentuale']}%"
        )

        c2.metric(
            "📉 Peggior mese",
            worst_month["mese"],
            f"{worst_month['percentuale']}%"
        )

        st.markdown("---")

        # ----------------------------------------------------
        # GRAFICO PRESENZE
        # ----------------------------------------------------

        st.subheader(
            "📊 Percentuale presenze mensile"
        )

        st.line_chart(
            mensile.set_index("mese")[
                "percentuale"
            ]
        )

        # ----------------------------------------------------
        # GRAFICO voti
        # ----------------------------------------------------

        st.subheader(
            "🎯 Media voti mensile"
        )

        st.line_chart(
            mensile.set_index("mese")[
                "media_voti"
            ]
        )

        st.markdown("---")

        # ----------------------------------------------------
        # CONFRONTO EVENTI
        # ----------------------------------------------------

        st.subheader(
            "🏊 Confronto attività"
        )

        confronto = analisi.groupby(
            "tipo_evento"
        ).agg(
            registrazioni=(
                "presenza",
                "count"
            ),
            presenze=(
                "presenza",
                "sum"
            ),
            media_voti=(
                "voto",
                "mean"
            )
        ).reset_index()

        confronto["percentuale"] = (
            confronto["presenze"]
            /
            confronto["registrazioni"]
            * 100
        ).round(1)

        confronto["media_voti"] = (
            confronto["media_voti"]
            .fillna(0)
            .round(2)
        )

        st.dataframe(
            confronto,
            use_container_width=True,
            hide_index=True
        )

        st.bar_chart(
            confronto.set_index(
                "tipo_evento"
            )[
                "percentuale"
            ]
        )

        st.markdown("---")

        # ----------------------------------------------------
        # DATI MENSILI
        # ----------------------------------------------------

        st.subheader(
            "📋 Dettaglio mensile"
        )

        st.dataframe(
            mensile,
            use_container_width=True,
            hide_index=True
        )
