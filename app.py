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

client = get_gsheet_client()
sheet_url = st.secrets["google_sheets"]["url"]
sh = client.open_by_url(sheet_url)

def load_data(sheet_name):
    worksheet = sh.worksheet(sheet_name)
    return pd.DataFrame(worksheet.get_all_records())

# --- CARICAMENTO DATI ---
df_luoghi = load_data("Luoghi")
df_feedback = load_data("Feedback")
df_config = load_data("Config")

# --- INTERFACCIA ---
st.title("🎯 Just Fiumicino: Gestione Volantinaggio")

tab1, tab2, tab3 = st.tabs(["🗺️ Mappa Interattiva", "✍️ Gestione Luoghi", "📝 Diario Feedback"])

# --- TAB 1: MAPPA ---
with tab1:
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.subheader("Filtri Strategici")
        target_filter = st.multiselect("Target di riferimento", df_luoghi['Target di Riferimento'].unique())
        
        df_map = df_luoghi.copy()
        if target_filter:
            df_map = df_map[df_map['Target di Riferimento'].isin(target_filter)]
            
        st.write(f"Trovate **{len(df_map)}** zone attive.")
        
        # Selezione per calcolo distanza
        st.divider()
        st.subheader("📏 Calcola Percorso")
        ponto_a = st.selectbox("Da (Punto A):", df_luoghi['Nome Zona'].unique(), index=0)
        ponto_b = st.selectbox("A (Punto B):", df_luoghi['Nome Zona'].unique(), index=1)
        
        lat_a = df_luoghi[df_luoghi['Nome Zona'] == ponto_a]['Lat'].values[0]
        lon_a = df_luoghi[df_luoghi['Nome Zona'] == ponto_a]['Lon'].values[0]
        lat_b = df_luoghi[df_luoghi['Nome Zona'] == ponto_b]['Lat'].values[0]
        lon_b = df_luoghi[df_luoghi['Nome Zona'] == ponto_b]['Lon'].values[0]
        
        url_percorso = f"https://www.google.com/maps/dir/?api=1&origin={lat_a},{lon_a}&destination={lat_b},{lon_b}&travelmode=walking"
        st.link_button("🚶 Apri percorso a piedi", url_percorso)

    with col1:
        m = folium.Map(location=[41.78, 12.25], zoom_start=13)
        for _, row in df_map.iterrows():
            # Link Navigatore
            nav_url = f"https://www.google.com/maps/search/?api=1&query={row['Lat']},{row['Lon']}"
            popup_html = f"""
                <b>{row['Nome Zona']}</b><br>
                Target: {row['Target di Riferimento']}<br>
                Orario: {row['Orari di Affluenza']}<br>
                <a href="{nav_url}" target="_blank">🚀 Apri Navigatore</a>
            """
            folium.Marker(
                [row['Lat'], row['Lon']],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=row['Nome Zona']
            ).add_to(m)
        st_folium(m, width=900, height=600)

# --- TAB 2: GESTIONE LUOGHI ---
with tab2:
    st.subheader("Aggiungi o Modifica Punti di Interesse")
    
    with st.expander("➕ Aggiungi Nuovo Luogo"):
        with st.form("nuovo_luogo"):
            nome = st.text_input("Nome Zona")
            lat = st.number_input("Latitudine", format="%.6f")
            lon = st.number_input("Longitudine", format="%.6f")
            tipo_lista = list(df_config['Tipo_Luogo'].values) + ["Altro..."]
            tipo = st.selectbox("Tipo di Luogo", tipo_lista)
            if tipo == "Altro...":
                tipo = st.text_input("Specifica nuovo tipo")
            
            target = st.text_input("Target di Riferimento")
            orario = st.text_input("Orari di Affluenza")
            note = st.text_area("Note iniziali")
            
            if st.form_submit_button("Salva nel Database"):
                nuovo_id = len(df_luoghi) + 1
                sh.worksheet("Luoghi").append_row([nuovo_id, nome, lat, lon, tipo, target, orario, note])
                st.success("Luogo salvato! Ricarica la pagina.")

    with st.expander("🗑️ Rimuovi Luogo"):
        da_eliminare = st.selectbox("Seleziona luogo da eliminare", df_luoghi['Nome Zona'].unique())
        if st.button("Conferma Eliminazione"):
            cella = sh.worksheet("Luoghi").find(da_eliminare)
            sh.worksheet("Luoghi").delete_rows(cella.row)
            st.warning("Eliminato. Ricarica la pagina.")

# --- TAB 3: DIARIO FEEDBACK ---
with tab3:
    st.subheader("📝 Diario Distribuzione e Feedback")
    
    col_f1, col_f2 = st.columns([1, 2])
    
    with col_f1:
        with st.form("nuovo_feedback"):
            luogo_f = st.selectbox("In quale zona hai distribuito?", df_luoghi['Nome Zona'].unique())
            id_luogo = df_luoghi[df_luoghi['Nome Zona'] == luogo_f]['ID'].values[0]
            nome_tl = st.text_input("Nome Team Leader")
            commento = st.text_area("Feedback sulla zona (es. problemi, consigli)")
            voto = st.select_slider("Valutazione (Stelline)", options=[1, 2, 3, 4, 5])
            voto_visual = "⭐" * voto
            
            if st.form_submit_button("Invia Feedback"):
                data_ora = datetime.now().strftime("%Y-%m-%d %H:%M")
                sh.worksheet("Feedback").append_row([len(df_feedback)+1, int(id_luogo), data_ora, nome_tl, commento, voto])
                st.success(f"Feedback inviato con {voto_visual}!")

    with col_f2:
        st.write("### Storico Feedback")
        # Uniamo i feedback con i nomi dei luoghi per chiarezza
        df_feed_display = df_feedback.merge(df_luoghi[['ID', 'Nome Zona']], left_on='ID_Luogo', right_on='ID')
        for _, f in df_feed_display.sort_values(by='Data_Ora', ascending=False).iterrows():
            with st.container():
                st.markdown(f"**{f['Nome Zona']}** | {f['Data_Ora']} | Voto: {'⭐'*int(f['Valutazione'])}")
                st.write(f"*{f['Nome_TL']} dice:* {f['Commento']}")
                st.divider()
