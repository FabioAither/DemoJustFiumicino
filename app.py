import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Configurazione Pagina
st.set_page_config(layout="wide", page_title="Just Fiumicino - Dashboard Professionale")

# --- CONNESSIONE GOOGLE SHEETS CON CACHE ---
@st.cache_resource
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

# Questa funzione salva i dati in memoria per 5 minuti (300 secondi)
@st.cache_data(ttl=300)
def load_data(sheet_name):
    client = get_gsheet_client()
    sheet_url = st.secrets["google_sheets"]["url"]
    sh = client.open_by_url(sheet_url)
    ws = sh.worksheet(sheet_name)
    return pd.DataFrame(ws.get_all_records())

try:
    # Caricamento dati
    df_luoghi = load_data("Luoghi")
    df_feedback = load_data("Feedback")
    df_config = load_data("Config")

    st.title("🎯 Just Fiumicino: Gestione Volantinaggio")
    
    # Tasto per forzare l'aggiornamento se necessario
    if st.sidebar.button("🔄 Aggiorna Dati"):
        st.cache_data.clear()
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🗺️ Mappa Interattiva", "✍️ Gestione Luoghi", "📝 Diario Feedback"])

    # --- TAB 1: MAPPA ---
    with tab1:
        if df_luoghi.empty:
            st.info("👋 Il database è vuoto. Aggiungi il primo punto dalla scheda 'Gestione Luoghi'.")
            m = folium.Map(location=[41.77, 12.23], zoom_start=13)
            st_folium(m, width=900, height=500)
        else:
            col1, col2 = st.columns([3, 1])
            with col2:
                st.subheader("Filtri")
                target_col = 'Target di Riferimento'
                target_options = sorted(df_luoghi[target_col].unique().tolist())
                target_filter = st.multiselect("Target di riferimento", target_options)
                
                df_map = df_luoghi.copy()
                if target_filter:
                    df_map = df_map[df_map[target_col].isin(target_filter)]
                
                st.write(f"Zone: **{len(df_map)}**")
                
                st.divider()
                st.subheader("📏 Percorso")
                nomi_zone = sorted(df_luoghi['Nome Zona'].unique())
                p_a = st.selectbox("Da:", nomi_zone, key="pa")
                p_b = st.selectbox("A:", nomi_zone, key="pb")
                
                row_a = df_luoghi[df_luoghi['Nome Zona'] == p_a].iloc[0]
                row_b = df_luoghi[df_luoghi['Nome Zona'] == p_b].iloc[0]
                
                url_p = f"https://www.google.com/maps/dir/?api=1&origin={row_a['Lat']},{row_a['Lon']}&destination={row_b['Lat']},{row_b['Lon']}&travelmode=walking"
                st.link_button("🚶 Cammina", url_p)

            with col1:
                # Centro mappa dinamico
                m = folium.Map(location=[df_map['Lat'].mean(), df_map['Lon'].mean()], zoom_start=13)
                for _, row in df_map.iterrows():
                    nav_url = f"https://www.google.com/maps/search/?api=1&query={row['Lat']},{row['Lon']}"
                    popup_h = f"<b>{row['Nome Zona']}</b><br>Target: {row['Target di Riferimento']}<br><a href='{nav_url}' target='_blank'>🚀 Navigatore</a>"
                    folium.Marker([row['Lat'], row['Lon']], popup=folium.Popup(popup_h, max_width=250)).add_to(m)
                st_folium(m, width=900, height=600)

    # --- TAB 2: GESTIONE ---
    with tab2:
        st.subheader("Nuovo Punto di Interesse")
        with st.form("nuovo_luogo"):
            c1, c2 = st.columns(2)
            with c1:
                n = st.text_input("Nome Zona")
                la = st.number_input("Lat", format="%.6f", value=41.773)
                lo = st.number_input("Lon", format="%.6f", value=12.231)
            with c2:
                t_lista = sorted(df_config['Tipo_Luogo'].values) if not df_config.empty else ["Stazione", "Parco"]
                tipo = st.selectbox("Tipo", t_lista)
                targ = st.text_input("Target")
            
            ora = st.text_input("Orari")
            note = st.text_area("Note")
            
            if st.form_submit_button("Salva"):
                # Qui scriviamo direttamente nel foglio (senza cache)
                client = get_gsheet_client()
                sh = client.open_by_url(st.secrets["google_sheets"]["url"])
                sh.worksheet("Luoghi").append_row([len(df_luoghi)+1, n, la, lo, tipo, targ, ora, note])
                st.success("Salvato! Clicca 'Aggiorna Dati' nella barra a sinistra per vederlo.")
                st.cache_data.clear()

    # --- TAB 3: FEEDBACK ---
    with tab3:
        st.subheader("Diario Feedback")
        if not df_luoghi.empty:
            with st.form("f_form"):
                z = st.selectbox("Zona", sorted(df_luoghi['Nome Zona'].unique()))
                id_z = df_luoghi[df_luoghi['Nome Zona'] == z]['ID'].values[0]
                tl = st.text_input("Nome TL")
                comm = st.text_area("Commento")
                v = st.select_slider("Valutazione", options=[1, 2, 3, 4, 5])
                if st.form_submit_button("Invia"):
                    dt = datetime.now().strftime("%Y-%m-%d %H:%M")
                    client = get_gsheet_client()
                    sh = client.open_by_url(st.secrets["google_sheets"]["url"])
                    sh.worksheet("Feedback").append_row([len(df_feedback)+1, int(id_z), dt, tl, comm, v])
                    st.success("Inviato!")
                    st.cache_data.clear()
        
        if not df_feedback.empty:
            st.write("### Storico")
            st.dataframe(df_feedback.sort_values(by='Data_Ora', ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Errore: {e}")
    st.info("Attendi 60 secondi e ricarica la pagina. Se l'errore persiste, controlla la connessione al foglio.")
