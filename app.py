import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Configurazione Pagina
st.set_page_config(layout="wide", page_title="Just Fiumicino Pro")

# --- CONNESSIONE GOOGLE SHEETS ---
@st.cache_resource
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

def get_worksheet(name):
    client = get_gsheet_client()
    sheet_url = st.secrets["google_sheets"]["url"]
    sh = client.open_by_url(sheet_url)
    return sh.worksheet(name)

@st.cache_data(ttl=10)
def load_all_data():
    try:
        df_l = pd.DataFrame(get_worksheet("Luoghi").get_all_records())
        df_f = pd.DataFrame(get_worksheet("Feedback").get_all_records())
        df_c = pd.DataFrame(get_worksheet("Config").get_all_records())
        df_l.columns = [c.strip() for c in df_l.columns]
        if not df_l.empty:
            df_l['Lat'] = pd.to_numeric(df_l['Lat'].astype(str).str.replace(',', '.'), errors='coerce')
            df_l['Lon'] = pd.to_numeric(df_l['Lon'].astype(str).str.replace(',', '.'), errors='coerce')
        return df_l, df_f, df_c
    except Exception as e:
        st.error(f"Errore nel caricamento dati: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- LOGICA APPLICATIVA ---
df_luoghi, df_feedback, df_config = load_all_data()

# --- SIDEBAR (FILTRI E PERCORSO) ---
with st.sidebar:
    st.header("⚙️ Pannello Controllo")
    if st.button("🔄 Aggiorna Dati"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.subheader("🔍 Filtri Mappa")
    t_options = sorted(df_luoghi['Target di Riferimento'].unique().tolist()) if not df_luoghi.empty else []
    t_sel = st.multiselect("Seleziona Target", t_options)
    
    st.divider()
    st.subheader("🚗 Calcola Percorso")
    if not df_luoghi.empty and len(df_luoghi) >= 2:
        nomi = sorted(df_luoghi['Nome Zona'].unique())
        pa = st.selectbox("Punto A (Partenza):", nomi, key="pa")
        pb = st.selectbox("Punto B (Arrivo):", nomi, key="pb")
        ra = df_luoghi[df_luoghi['Nome Zona']==pa].iloc[0]
        rb = df_luoghi[df_luoghi['Nome Zona']==pb].iloc[0]
        # PERCORSO: Driving + Roadmap
        url_p = f"https://www.google.com/maps/dir/?api=1&origin={ra['Lat']},{ra['Lon']}&destination={rb['Lat']},{rb['Lon']}&travelmode=driving&basemap=roadmap"
        st.link_button("🚗 Calcola Percorso in Auto", url_p, use_container_width=True)

# --- CORPO PRINCIPALE ---
st.title("🎯 Just Fiumicino: Gestione Volantinaggio")
tab1, tab2, tab3 = st.tabs(["🗺️ Mappa & Riepilogo", "✍️ Gestione Luoghi", "📝 Feedback"])

# --- TAB 1: MAPPA ---
with tab1:
    df_map = df_luoghi.dropna(subset=['Lat', 'Lon'])
    if t_sel:
        df_map = df_map[df_map['Target di Riferimento'].isin(t_sel)]
        
    if df_map.empty:
        st.info("Nessun dato da visualizzare. Aggiungi luoghi o cambia filtri.")
    else:
        # Mappa centrata
        m = folium.Map(location=[df_map['Lat'].mean(), df_map['Lon'].mean()], zoom_start=13)
        for _, r in df_map.iterrows():
            # NAVIGATORE: Roadmap + Nuovo testo
            nav = f"https://www.google.com/maps/search/?api=1&query={r['Lat']},{r['Lon']}&basemap=roadmap"
            html = f"""
            <div style='font-family: sans-serif; min-width: 150px;'>
                <b>{r['Nome Zona']}</b><br>
                <p style='font-size: 12px; margin: 5px 0;'>Target: {r['Target di Riferimento']}</p>
                <a href='{nav}' target='_blank' style='display: block; text-align: center; background: #4285F4; color: white; padding: 8px; border-radius: 5px; text-decoration: none;'>📍Apri in Mappe</a>
            </div>
            """
            folium.Marker([r['Lat'], r['Lon']], popup=folium.Popup(html, max_width=250)).add_to(m)
        st_folium(m, width="100%", height=500, returned_objects=[])
        
        st.divider()
        st.subheader("📋 Riepilogo Operativo Zone")
        st.dataframe(df_map[['Nome Zona', 'Tipo di Zona', 'Target di Riferimento', 'Orari di Affluenza', 'Note']], use_container_width=True, hide_index=True)

# --- TAB 2: GESTIONE ---
with tab2:
    st.subheader("Centro Gestione Luoghi")
    sub_add, sub_edit, sub_del = st.tabs(["➕ Aggiungi", "✏️ Modifica", "🗑️ Rimuovi"])

    with sub_add:
        st.write("### 1. Clicca sulla mappa per ottenere le coordinate")
        m_picker = folium.Map(location=[41.7733, 12.2311], zoom_start=13)
        folium.LatLngPopup().add_to(m_picker) 
        last_click = st_folium(m_picker, width=700, height=400, key="picker_map")
        
        c_lat, c_lon = "", ""
        if last_click and last_click.get("last_clicked"):
            c_lat = last_click["last_clicked"]["lat"]
            c_lon = last_click["last_clicked"]["lng"]
            st.success(f"📍 Coordinate catturate: {c_lat}, {c_lon}")

        with st.form("form_add"):
            nome_n = st.text_input("Nome Zona")
            col1, col2 = st.columns(2)
            lat_n = col1.text_input("Latitudine", value=str(c_lat))
            lon_n = col2.text_input("Longitudine", value=str(c_lon))
            
            tipi = sorted(df_config['Tipo_Luogo'].tolist()) if not df_config.empty else []
            tipo_n = st.selectbox("Tipo", tipi + ["Altro..."])
            if tipo_n == "Altro...": tipo_n = st.text_input("Specifica tipo")
            
            targ_n = st.text_input("Target")
            ora_n = st.text_input("Orari")
            note_n = st.text_area("Note")
            
            if st.form_submit_button("Salva nel Database"):
                if nome_n and lat_n
