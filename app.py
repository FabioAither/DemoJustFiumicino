import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(layout="wide", page_title="Just Fiumicino - Dashboard")

@st.cache_resource
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def load_data(sheet_name):
    client = get_gsheet_client()
    sheet_url = st.secrets["google_sheets"]["url"]
    sh = client.open_by_url(sheet_url)
    ws = sh.worksheet(sheet_name)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    # Pulizia coordinate: trasforma in numeri e ignora errori
    if 'Lat' in df.columns and 'Lon' in df.columns:
        df['Lat'] = pd.to_numeric(df['Lat'], errors='coerce')
        df['Lon'] = pd.to_numeric(df['Lon'], errors='coerce')
    return df

try:
    df_luoghi = load_data("Luoghi")
    df_feedback = load_data("Feedback")
    df_config = load_data("Config")

    st.title("🎯 Just Fiumicino: Gestione Volantinaggio")
    
    if st.sidebar.button("🔄 Aggiorna Mappa"):
        st.cache_data.clear()
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🗺️ Mappa", "✍️ Gestione", "📝 Feedback"])

    with tab1:
        # Rimuoviamo righe con coordinate rotte
        df_map = df_luoghi.dropna(subset=['Lat', 'Lon'])
        
        if df_map.empty:
            st.warning("⚠️ Nessun dato valido trovato. Controlla le coordinate nel foglio Google.")
        else:
            col1, col2 = st.columns([3, 1])
            with col2:
                target_options = sorted(df_map['Target di Riferimento'].unique().tolist())
                t_filter = st.multiselect("Target", target_options)
                if t_filter:
                    df_map = df_map[df_map['Target di Riferimento'].isin(t_filter)]
                
                st.write(f"Zone attive: {len(df_map)}")
                
                st.divider()
                p_a = st.selectbox("Da:", df_map['Nome Zona'].unique(), key="pa")
                p_b = st.selectbox("A:", df_map['Nome Zona'].unique(), key="pb")
                r_a = df_map[df_map['Nome Zona'] == p_a].iloc[0]
                r_b = df_map[df_map['Nome Zona'] == p_b].iloc[0]
                url_p = f"https://www.google.com/maps/dir/?api=1&origin={r_a['Lat']},{r_a['Lon']}&destination={r_b['Lat']},{r_b['Lon']}&travelmode=walking"
                st.link_button("🚶 Percorso", url_p)

            with col1:
                m = folium.Map(location=[df_map['Lat'].mean(), df_map['Lon'].mean()], zoom_start=13)
                for _, row in df_map.iterrows():
                    nav = f"https://www.google.com/maps/search/?api=1&query={row['Lat']},{row['Lon']}"
                    folium.Marker([row['Lat'], row['Lon']], 
                                  popup=folium.Popup(f"<b>{row['Nome Zona']}</b><br><a href='{nav}' target='_blank'>🚀 Vai</a>", max_width=200)).add_to(m)
                st_folium(m, width=800, height=500)

    # ... (Resto del codice per Tab 2 e 3 rimane uguale a prima)
    with tab2:
        st.info("Usa questa sezione per aggiungere nuovi punti o il foglio Google per modifiche massive.")
        # (Codice gestione semplificato...)
        
except Exception as e:
    st.error(f"Dati non validi: {e}")
    st.info("Controlla che nel foglio Google le colonne Lat e Lon contengano solo numeri.")
