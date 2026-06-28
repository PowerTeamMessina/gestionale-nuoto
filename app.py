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
CREATE TABLE IF NOT EXISTS atleti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    categoria TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS presenze (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atleta_id INTEGER,
    data TEXT,
    presenza INTEGER,
    voto REAL,
    commento TEXT,
    UNIQUE(atleta_id, data)
)
""")

conn.commit()


# ============================================================
# FUNZIONI
# ============================================================

def get_atleti():
    return pd.read_sql("""
        SELECT *
        FROM atleti
        ORDER BY categoria, nome
    """, conn)


def get_presenze_data(data_allenamento):
    return pd.read_sql("""
        SELECT atleta_id, data, presenza, voto, commento
        FROM presenze
        WHERE data = ?
    """, conn, params=(str(data_allenamento),))


def salva_presenza(atleta_id, data_allenamento, presenza, voto, commento):
    c.execute("""
        INSERT INTO presenze (atleta_id, data, presenza, voto, commento)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(atleta_id, data)
        DO UPDATE SET
            presenza = excluded.presenza,
            voto = excluded.voto,
            commento = excluded.commento
    """, (
        atleta_id,
        str(data_allenamento),
        int(presenza),
        float(voto) if voto is not None else None,
        commento
    ))
    conn.commit()


def get_storico():
    return pd.read_sql("""
        SELECT 
            a.id AS atleta_id,
            a.nome,
            a.categoria,
            p.data,
            p.presenza,
            p.voto,
            p.commento
        FROM presenze p
        JOIN atleti a ON a.id = p.atleta_id
        ORDER BY p.data DESC, a.categoria, a.nome
    """, conn)


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


# ============================================================
# INTERFACCIA PRINCIPALE
# ============================================================

st.title("🏊 Gestionale Nuoto")

tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Registro",
    "👥 Atleti",
    "📊 Statistiche",
    "🗂️ Storico"
])


# ============================================================
# TAB 1 - REGISTRO
# ============================================================

with tab1:

    st.header("📋 Registro allenamento")

    data_allenamento = st.date_input(
        "Data allenamento",
        value=date.today()
    )

    df_atleti = get_atleti()

    if df_atleti.empty:
        st.warning("Inserisci prima gli atleti nella sezione 👥 Atleti.")
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

        # Reset se cambia data
        if st.session_state.data_corrente != str(data_allenamento):
            st.session_state.registro = {}
            st.session_state.data_corrente = str(data_allenamento)

        # Carica dati già salvati per quella data
        presenze_salvate = get_presenze_data(data_allenamento)

        saved_dict = {}

        if not presenze_salvate.empty:
            for _, r in presenze_salvate.iterrows():
                atleta_id_salvato = int(r["atleta_id"])

                saved_dict[atleta_id_salvato] = {
                    "presenza": bool(r["presenza"]),
                    "voto": int(r["voto"]) if pd.notna(r["voto"]) else None,
                    "commento": r["commento"] if pd.notna(r["commento"]) else ""
                }

        # Inizializzazione:
        # tutti assenti di default
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
        # LISTA ATLETI SEMPLICE
        # ========================================================

        st.subheader("🏊 Atleti")

        for _, row in df_visibili.iterrows():

            atleta_id = int(row["id"])
            nome = row["nome"]
            categoria = row["categoria_pulita"]

            presenza_attuale = bool(st.session_state.registro[atleta_id]["presenza"])

            # Nome e categoria semplici, senza sfondi
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

    with st.form("form_atleta", clear_on_submit=True):

        nome = st.text_input("Nome atleta")

        categoria = st.text_input(
            "Categoria",
            placeholder="es. Esordienti, Ragazzi, Junior, Assoluti"
        )

        submit = st.form_submit_button("➕ Aggiungi atleta")

        if submit:
            if nome.strip() == "":
                st.error("Inserisci il nome dell'atleta.")
            else:
                c.execute("""
                    INSERT INTO atleti (nome, categoria)
                    VALUES (?, ?)
                """, (
                    nome.strip(),
                    categoria.strip()
                ))

                conn.commit()
                st.success(f"Atleta {nome} aggiunto.")

    st.markdown("---")

    df_atleti = get_atleti()

    if df_atleti.empty:
        st.info("Nessun atleta inserito.")
    else:

        st.dataframe(
            df_atleti,
            use_container_width=True,
            hide_index=True
        )

        st.subheader("🗑️ Elimina atleta")

        atleta_da_eliminare = st.selectbox(
            "Seleziona atleta",
            df_atleti["nome"].tolist()
        )

        if st.button("Elimina atleta selezionato"):

            atleta_id = int(
                df_atleti[df_atleti["nome"] == atleta_da_eliminare]["id"].iloc[0]
            )

            c.execute("DELETE FROM presenze WHERE atleta_id = ?", (atleta_id,))
            c.execute("DELETE FROM atleti WHERE id = ?", (atleta_id,))
            conn.commit()

            st.success(f"Atleta {atleta_da_eliminare} eliminato.")
            st.rerun()


# ============================================================
# TAB 3 - STATISTICHE
# ============================================================

with tab3:

    st.header("📊 Statistiche automatiche")

    storico = get_storico()

    if storico.empty:
        st.info("Non ci sono ancora allenamenti salvati.")
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
            ["atleta_id", "nome", "categoria"],
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
            file_name="statistiche_nuoto.csv",
            mime="text/csv"
        )


# ============================================================
# TAB 4 - STORICO
# ============================================================

with tab4:

    st.header("🗂️ Storico allenamenti")

    storico = get_storico()

    if storico.empty:
        st.info("Nessuno storico disponibile.")
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
            file_name="storico_allenamenti_nuoto.csv",
            mime="text/csv"
        )
