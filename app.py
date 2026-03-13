import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(layout="wide", page_title="Just Fiumicino 10/10")

@st.cache_resource
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=30)
def load_data(sheet_name):
    client = get_gsheet_client()
    sheet_url = st.secrets["google_sheets"]["url"]
    sh = client.open_by_url(sheet_url)
    ws = sh.worksheet(sheet_name)
    df = pd.DataFrame(ws.get_all_records())
    
    # PULIZIA COLONNE (Rimuove spazi dai nomi delle colonne)
    df.columns = [c.strip() for c in df.columns]
    
    # PULIZIA COORDINATE (Forza la conversione in numeri)
    if 'Lat' in df.columns and 'Lon' in df.columns:
        df['Lat'] = pd.to_numeric(df['Lat'].astype(str).str.replace(',', '.'), errors='coerce')
        df['Lon'] = pd.to_numeric(df['Lon'].astype(str).str.replace(',', '.'), errors='coerce')
    return df

try:
    df_luoghi = load_data("Luoghi")
    df_feedback = load_data("Feedback")
    df_config = load_data("Config")

    st.title("🎯 Just Fiumicino: Gestione Volantinaggio")
    
    if st.sidebar.button("🔄 Aggiorna Dati"):
        st.cache_data.clear()
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🗺️ Mappa Interattiva", "✍️ Gestione Luoghi", "📝 Feedback"])

    with tab1:
        # Filtriamo solo i luoghi che hanno coordinate valide
        df_map = df_luoghi.dropna(subset=['Lat', 'Lon'])
        
        if df_map.empty:
            st.warning("⚠️ Nessun dato valido trovato nel foglio Google.")
            st.write("Verifica che le colonne **Lat** e **Lon** non siano vuote nel tuo file Google Sheets.")
            st.dataframe(df_luoghi) # Debug visivo
        else:
            col1, col2 = st.columns([3, 1])
            with col2:
                st.subheader("Filtri")
                target_options = sorted(df_map['Target di Riferimento'].unique().tolist())
                t_filter = st.multiselect("Filtra per Target", target_options)
                if t_filter:
                    df_map = df_map[df_map['Target di Riferimento'].isin(t_filter)]
                
                st.write(f"Zone: **{len(df_map)}**")
                st.divider()
                st.subheader("📏 Calcola Percorso")
                p_a = st.selectbox("Da:", df_map['Nome Zona'].unique(), key="pa")
                p_b = st.selectbox("A:", df_map['Nome Zona'].unique(), key="pb")
                r_a = df_map[df_map['Nome Zona'] == p_a].iloc[0]
                r_b = df_map[df_map['Nome Zona'] == p_b].iloc[0]
                url_p = f"https://www.google.com/maps/dir/?api=1&origin={r_a['Lat']},{r_a['Lon']}&destination={r_b['Lat']},{r_b['Lon']}&travelmode=walking"
                st.link_button("🚶 Percorso a piedi", url_p)

            with col1:
                # Creazione mappa centrata sui punti
                m = folium.Map(location=[df_map['Lat'].mean(), df_map['Lon'].mean()], zoom_start=13)
                for _, row in df_map.iterrows():
                    nav_url = f"https://www.google.com/maps/search/?api=1&query={row['Lat']},{row['Lon']}"
                    popup_html = f"<b>{row['Nome Zona']}</b><br>Target: {row['Target di Riferimento']}<br><a href='{nav_url}' target='_blank'>🚀 Apri Navigatore</a>"
                    folium.Marker([row['Lat'], row['Lon']], popup=folium.Popup(popup_html, max_width=250)).add_to(m)
                st_folium(m, width=900, height=550)

    with tab2:
        st.subheader("Gestione Punti di Interesse")
        st.info("Puoi modificare i dati direttamente dal tuo Foglio Google per fare prima.")
        st.dataframe(df_luoghi)

    with tab3:
        st.subheader("Diario Feedback")
        if not df_luoghi.empty:
            with st.form("f_form"):
                z = st.selectbox("Seleziona Zona", sorted(df_luoghi['Nome Zona'].unique()))
                tl = st.text_input("Nome Team Leader")
                comm = st.text_area("Feedback")
                v = st.slider("Voto", 1, 5, 3)
                if st.form_submit_button("Invia Feedback"):
                    dt = datetime.now().strftime("%Y-%m-%d %H:%M")
                    client = get_gsheet_client()
                    sh = client.open_by_url(st.secrets["google_sheets"]["url"])
                    sh.worksheet("Feedback").append_row([len(df_feedback)+1, z, dt, tl, comm, v])
                    st.success("Feedback Inviato!")
                    st.cache_data.clear()
        if not df_feedback.empty:
            st.write("### Storico Feedback")
            st.dataframe(df_feedback.sort_values(by='Data_Ora', ascending=False))

except Exception as e:
    st.error(f"Errore: {e}")
