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
    sh = client.open_by_url(st.secrets["google_sheets"]["url"])
    return sh.worksheet(name)

@st.cache_data(ttl=10)
def load_all_data():
    df_l = pd.DataFrame(get_worksheet("Luoghi").get_all_records())
    df_f = pd.DataFrame(get_worksheet("Feedback").get_all_records())
    df_c = pd.DataFrame(get_worksheet("Config").get_all_records())
    df_l.columns = [c.strip() for c in df_l.columns]
    if not df_l.empty:
        df_l['Lat'] = pd.to_numeric(df_l['Lat'].astype(str).str.replace(',', '.'), errors='coerce')
        df_l['Lon'] = pd.to_numeric(df_l['Lon'].astype(str).str.replace(',', '.'), errors='coerce')
    return df_l, df_f, df_c

# --- LOGICA APPLICATIVA ---
try:
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
        st.subheader("📏 Calcola Percorso")
        if not df_luoghi.empty:
            nomi = sorted(df_luoghi['Nome Zona'].unique())
            pa = st.selectbox("Punto A (Partenza):", nomi, key="pa")
            pb = st.selectbox("Punto B (Arrivo):", nomi, key="pb")
            ra = df_luoghi[df_luoghi['Nome Zona']==pa].iloc[0]
            rb = df_luoghi[df_luoghi['Nome Zona']==pb].iloc[0]
            url_p = f"https://www.google.com/maps/dir/?api=1&origin={ra['Lat']},{ra['Lon']}&destination={rb['Lat']},{rb['Lon']}&travelmode=walking"
            st.link_button("🚶 Apri percorso a piedi", url_p, use_container_width=True)

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
            # Mappa a tutta larghezza
            m = folium.Map(location=[df_map['Lat'].mean(), df_map['Lon'].mean()], zoom_start=13)
            for _, r in df_map.iterrows():
                nav = f"https://www.google.com/maps/search/?api=1&query={r['Lat']},{r['Lon']}"
                html = f"<b>{r['Nome Zona']}</b><br>Target: {r['Target di Riferimento']}<br><a href='{nav}' target='_blank'>🚀 Navigatore</a>"
                folium.Marker([r['Lat'], r['Lon']], popup=folium.Popup(html, max_width=200)).add_to(m)
            st_folium(m, width="100%", height=500, returned_objects=[])
            
            st.divider()
            st.subheader("📋 Riepilogo Operativo Zone")
            st.dataframe(df_map[['Nome Zona', 'Tipo di Zona', 'Target di Riferimento', 'Orari di Affluenza', 'Note']], use_container_width=True, hide_index=True)

    # --- TAB 2: GESTIONE (CON MAPPA INTERATTIVA) ---
    with tab2:
        st.subheader("Centro Gestione Luoghi")
        sub_add, sub_edit, sub_del = st.tabs(["➕ Aggiungi", "✏️ Modifica", "🗑️ Rimuovi"])

        with sub_add:
            st.write("### 1. Clicca sulla mappa per ottenere le coordinate")
            # Mappa per selezione coordinate
            m_picker = folium.Map(location=[41.7733, 12.2311], zoom_start=13)
            folium.LatLngPopup().add_to(m_picker) # Mostra le coordinate al click
            last_click = st_folium(m_picker, width=700, height=400, key="picker_map")
            
            clicked_lat = ""
            clicked_lon = ""
            if last_click and last_click.get("last_clicked"):
                clicked_lat = last_click["last_clicked"]["lat"]
                clicked_lon = last_click["last_clicked"]["lng"]
                st.success(f"📍 Coordinate catturate: {clicked_lat}, {clicked_lon}")

            st.write("### 2. Compila i dettagli")
            with st.form("form_aggiunta"):
                nome_n = st.text_input("Nome Zona")
                col1, col2 = st.columns(2)
                # I campi lat/lon vengono pre-compilati se l'utente clicca sulla mappa
                lat_n = col1.text_input("Latitudine", value=str(clicked_lat))
                lon_n = col2.text_input("Longitudine", value=str(clicked_lon))
                
                tipi = sorted(df_config['Tipo_Luogo'].tolist()) if not df_config.empty else []
                tipo_n = st.selectbox("Tipo di Luogo", tipi + ["Altro..."])
                if tipo_n == "Altro...": tipo_n = st.text_input("Specifica tipo")
                
                targ_n = st.text_input("Target di Riferimento")
                ora_n = st.text_input("Orari")
                note_n = st.text_area("Note")
                
                if st.form_submit_button("Salva nel Database"):
                    ws_l = get_worksheet("Luoghi")
                    ws_l.append_row([len(df_luoghi)+1, nome_n, lat_n, lon_n, tipo_n, targ_n, ora_n, note_n])
                    if tipo_n not in tipi: get_worksheet("Config").append_row([tipo_n])
                    st.success("Zona salvata con successo!")
                    st.cache_data.clear()

        with sub_edit:
            if not df_luoghi.empty:
                nome_mod = st.selectbox("Scegli luogo da modificare", df_luoghi['Nome Zona'].tolist())
                r_idx = df_luoghi[df_luoghi['Nome Zona'] == nome_mod].index[0]
                r_data = df_luoghi.iloc[r_idx]
                with st.form("form_edit"):
                    en = st.text_input("Nome", value=r_data['Nome Zona'])
                    c1, c2 = st.columns(2)
                    ela = c1.text_input("Lat", value=str(r_data['Lat']))
                    elo = c2.text_input("Lon", value=str(r_data['Lon']))
                    etarg = st.text_input("Target", value=r_data['Target di Riferimento'])
                    enote = st.text_area("Note", value=r_data['Note'])
                    if st.form_submit_button("Salva Modifiche"):
                        ws_l = get_worksheet("Luoghi")
                        row_n = int(r_idx) + 2
                        ws_l.update(range_name=f'B{row_n}:H{row_n}', values=[[en, ela, elo, r_data['Tipo di Zona'], etarg, r_data['Orari di Affluenza'], enote]])
                        st.success("Dati aggiornati!")
                        st.cache_data.clear()

        with sub_del:
            nome_del = st.selectbox("Scegli luogo da eliminare", df_luoghi['Nome Zona'].tolist(), key="del_sel")
            if st.button("ELIMINA DEFINITIVAMENTE"):
                ws_l = get_worksheet("Luoghi")
                ws_l.delete_rows(ws_l.find(nome_del).row)
                st.error(f"'{nome_del}' rimosso.")
                st.cache_data.clear()

    # --- TAB 3: FEEDBACK ---
    with tab3:
        st.subheader("📝 Diario Feedback")
        c1, c2 = st.columns([1, 1])
        with c1:
            with st.form("form_feed"):
                z_f = st.selectbox("Zona", sorted(df_luoghi['Nome Zona'].unique()))
                tl_f = st.text_input("Team Leader")
                comm_f = st.text_area("Commento")
                v_f = st.select_slider("Valutazione", options=[1, 2, 3, 4, 5])
                if st.form_submit_button("Invia Feedback"):
                    get_worksheet("Feedback").append_row([len(df_feedback)+1, z_f, datetime.now().strftime("%Y-%m-%d %H:%M"), tl_f, comm_f, v_f])
                    st.success("Feedback salvato!")
                    st.cache_data.clear()
        with c2:
            if not df_feedback.empty:
                df_fv = df_feedback.copy().sort_values(by='Data_Ora', ascending=False)
                df_fv['Valutazione'] = df_fv['Valutazione'].apply(lambda x: "⭐" * int(x))
                st.dataframe(df_fv[['Data_Ora', 'ID_Luogo', 'Nome_TL', 'Commento', 'Valutazione']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Errore: {e}")
