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
    
    # PULIZIA NUMERICA AVANZATA
    for col in ['Lat', 'Lon']:
        if col in df.columns:
            # Trasforma tutto in stringa, pulisce spazi, cambia virgole in punti
            df[col] = df[col].astype(str).str.replace(',', '.').str.strip()
            # Converte in numero, se non ci riesce mette NaN (Not a Number)
            df[col] = pd.to_numeric(df[col], errors='coerce')
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
        # Teniamo solo le righe che hanno coordinate valide dopo la pulizia
        df_map = df_luoghi.dropna(subset=['Lat', 'Lon'])
        
        if df_map.empty:
            st.warning("⚠️ Nessun dato valido trovato.")
            st.write("Dati attuali nel foglio (prime righe):", df_luoghi.head())
            st.info("💡 Suggerimento: Controlla che nel foglio Google le colonne Lat e Lon contengano solo numeri col punto (es: 41.793).")
        else:
            col1, col2 = st.columns([3, 1])
            with col2:
                st.subheader("Filtri")
                # Filtro Target
                target_col = 'Target di Riferimento'
                target_options = sorted(df_map[target_col].unique().tolist())
                t_filter = st.multiselect("Target", target_options)
                
                if t_filter:
                    df_map = df_map[df_map[target_col].isin(t_filter)]
                
                st.write(f"Zone attive: {len(df_map)}")
                
                st.divider()
                st.subheader("📏 Percorso")
                nomi_zone = sorted(df_map['Nome Zona'].unique())
                p_a = st.selectbox("Da:", nomi_zone, key="pa")
                p_b = st.selectbox("A:", nomi_zone, key="pb")
                r_a = df_map[df_map['Nome Zona'] == p_a].iloc[0]
                r_b = df_map[df_map['Nome Zona'] == p_b].iloc[0]
                url_p = f"https://www.google.com/maps/dir/?api=1&origin={r_a['Lat']},{r_a['Lon']}&destination={r_b['Lat']},{r_b['Lon']}&travelmode=walking"
                st.link_button("🚶 Apri Percorso", url_p)

            with col1:
                # Centro mappa
                m = folium.Map(location=[df_map['Lat'].mean(), df_map['Lon'].mean()], zoom_start=13)
                for _, row in df_map.iterrows():
                    nav = f"https://www.google.com/maps/search/?api=1&query={row['Lat']},{row['Lon']}"
                    popup_c = f"<b>{row['Nome Zona']}</b><br>Target: {row['Target di Riferimento']}<br><a href='{nav}' target='_blank'>🚀 Navigatore</a>"
                    folium.Marker([row['Lat'], row['Lon']], popup=folium.Popup(popup_c, max_width=250)).add_to(m)
                st_folium(m, width=800, height=500)

    with tab2:
        st.subheader("Aggiungi Nuovo Punto")
        with st.form("nuovo_p"):
            c1, c2 = st.columns(2)
            with c1:
                nome = st.text_input("Nome Zona")
                la = st.text_input("Latitudine (es. 41.773)")
                lo = st.text_input("Longitudine (es. 12.231)")
            with c2:
                t_lista = list(df_config['Tipo_Luogo'].values) if not df_config.empty else ["Stazione", "Parco"]
                tipo = st.selectbox("Tipo", t_lista)
                targ = st.text_input("Target")
            
            if st.form_submit_button("Salva nel Database"):
                if nome and la and lo:
                    client = get_gsheet_client()
                    sh = client.open_by_url(st.secrets["google_sheets"]["url"])
                    sh.worksheet("Luoghi").append_row([len(df_luoghi)+1, nome, la.replace(',', '.'), lo.replace(',', '.'), tipo, targ, "", ""])
                    st.success("Salvato! Clicca su Aggiorna Mappa.")
                    st.cache_data.clear()

    with tab3:
        st.subheader("Feedback")
        if not df_luoghi.empty:
            with st.form("feed"):
                z = st.selectbox("Zona", sorted(df_luoghi['Nome Zona'].unique()))
                tl = st.text_input("Nome TL")
                v = st.slider("Voto", 1, 5, 3)
                if st.form_submit_button("Invia"):
                    dt = datetime.now().strftime("%Y-%m-%d %H:%M")
                    client = get_gsheet_client()
                    sh = client.open_by_url(st.secrets["google_sheets"]["url"])
                    sh.worksheet("Feedback").append_row([len(df_feedback)+1, z, dt, tl, "", v])
                    st.success("Feedback Inviato!")
                    st.cache_data.clear()
        if not df_feedback.empty:
            st.dataframe(df_feedback)

except Exception as e:
    st.error(f"Errore tecnico: {e}")
