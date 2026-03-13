import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Configurazione Pagina
st.set_page_config(layout="wide", page_title="Just Fiumicino - Dashboard 10/10")

# --- CONNESSIONE GOOGLE SHEETS ---
@st.cache_resource
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

try:
    client = get_gsheet_client()
    sheet_url = st.secrets["google_sheets"]["url"]
    sh = client.open_by_url(sheet_url)
    
    # Caricamento dati
    def load_data(sheet_name):
        ws = sh.worksheet(sheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)

    df_luoghi = load_data("Luoghi")
    df_feedback = load_data("Feedback")
    df_config = load_data("Config")

    st.title("🎯 Just Fiumicino: Gestione Volantinaggio")

    tab1, tab2, tab3 = st.tabs(["🗺️ Mappa Interattiva", "✍️ Gestione Luoghi", "📝 Diario Feedback"])

    # --- TAB 1: MAPPA ---
    with tab1:
        if df_luoghi.empty:
            st.info("👋 Benvenuto! Il database è ancora vuoto. Vai nella scheda 'Gestione Luoghi' per aggiungere il primo punto di interesse.")
            # Mappa vuota di default su Fiumicino
            m = folium.Map(location=[41.7733, 12.2311], zoom_start=13)
            st_folium(m, width=900, height=500)
        else:
            col1, col2 = st.columns([3, 1])
            with col2:
                st.subheader("Filtri Strategici")
                # Filtro Target (gestisce anche se la colonna è vuota)
                target_options = df_luoghi['Target di Riferimento'].unique().tolist()
                target_filter = st.multiselect("Filtra per Target", target_options)
                
                df_map = df_luoghi.copy()
                if target_filter:
                    df_map = df_map[df_map['Target di Riferimento'].isin(target_filter)]
                
                st.write(f"Zone visualizzate: **{len(df_map)}**")
                
                st.divider()
                st.subheader("📏 Calcola Percorso")
                nomi_zone = df_luoghi['Nome Zona'].unique()
                p_a = st.selectbox("Da (Punto A):", nomi_zone, key="pa")
                p_b = st.selectbox("A (Punto B):", nomi_zone, key="pb")
                
                row_a = df_luoghi[df_luoghi['Nome Zona'] == p_a].iloc[0]
                row_b = df_luoghi[df_luoghi['Nome Zona'] == p_b].iloc[0]
                
                url_p = f"https://www.google.com/maps/dir/?api=1&origin={row_a['Lat']},{row_a['Lon']}&destination={row_b['Lat']},{row_b['Lon']}&travelmode=walking"
                st.link_button("🚶 Percorso a piedi", url_p)

            with col1:
                m = folium.Map(location=[df_map['Lat'].mean(), df_map['Lon'].mean()], zoom_start=13)
                for _, row in df_map.iterrows():
                    nav_url = f"https://www.google.com/maps/search/?api=1&query={row['Lat']},{row['Lon']}"
                    popup_h = f"<b>{row['Nome Zona']}</b><br>Target: {row['Target di Riferimento']}<br><a href='{nav_url}' target='_blank'>🚀 Navigatore</a>"
                    folium.Marker([row['Lat'], row['Lon']], popup=folium.Popup(popup_h, max_width=250)).add_to(m)
                st_folium(m, width=900, height=600)

    # --- TAB 2: GESTIONE ---
    with tab2:
        st.subheader("Aggiungi o Rimuovi Punti di Interesse")
        
        with st.form("nuovo_luogo_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                n = st.text_input("Nome Zona (es. Stazione Aeroporto)")
                la = st.number_input("Latitudine", format="%.6f", value=41.7733)
                lo = st.number_input("Longitudine", format="%.6f", value=12.2311)
            with col_b:
                t_lista = list(df_config['Tipo_Luogo'].values) if not df_config.empty else ["Stazione", "Centro Comm.", "Parco"]
                tipo = st.selectbox("Tipo di Luogo", t_lista)
                targ = st.text_input("Target (es. Pendolari, Famiglie)")
            
            ora = st.text_input("Orari di Affluenza")
            note = st.text_area("Note")
            
            if st.form_submit_button("Salva nel Database"):
                if n:
                    nuovo_id = len(df_luoghi) + 1
                    sh.worksheet("Luoghi").append_row([nuovo_id, n, la, lo, tipo, targ, ora, note])
                    st.success(f"✅ '{n}' aggiunto con successo! Ricarica la pagina per vederlo sulla mappa.")
                else:
                    st.error("Inserisci almeno il nome della zona.")

        if not df_luoghi.empty:
            st.divider()
            da_eliminare = st.selectbox("Elimina un luogo", df_luoghi['Nome Zona'].unique())
            if st.button("Elimina definitivamente"):
                cella = sh.worksheet("Luoghi").find(da_eliminare)
                sh.worksheet("Luoghi").delete_rows(cella.row)
                st.warning(f"Eliminato '{da_eliminare}'. Ricarica la pagina.")

    # --- TAB 3: FEEDBACK ---
    with tab3:
        st.subheader("Diario Feedback e Valutazione")
        if df_luoghi.empty:
            st.warning("Devi prima aggiungere dei luoghi per poter inserire dei feedback.")
        else:
            col_f1, col_f2 = st.columns([1, 1])
            with col_f1:
                with st.form("form_feedback"):
                    z = st.selectbox("Zona visitata", df_luoghi['Nome Zona'].unique())
                    id_z = df_luoghi[df_luoghi['Nome Zona'] == z]['ID'].values[0]
                    tl = st.text_input("Nome Team Leader")
                    comm = st.text_area("Commento distribuzione")
                    v = st.select_slider("Valutazione", options=[1, 2, 3, 4, 5])
                    if st.form_submit_button("Invia Feedback"):
                        dt = datetime.now().strftime("%Y-%m-%d %H:%M")
                        sh.worksheet("Feedback").append_row([len(df_feedback)+1, int(id_z), dt, tl, comm, v])
                        st.success(f"Feedback inviato per {z}!")
            
            with col_f2:
                st.write("### Ultimi feedback inseriti")
                if not df_feedback.empty:
                    df_view = df_feedback.sort_values(by='Data_Ora', ascending=False)
                    st.dataframe(df_view[['Data_Ora', 'Nome_TL', 'Commento', 'Valutazione']], use_container_width=True)
                else:
                    st.write("Nessun feedback presente.")

except Exception as e:
    st.error(f"❌ Errore di connessione: {e}")
    st.info("Assicurati che il foglio Google sia condiviso come 'Editor' con l'email del Service Account.")
