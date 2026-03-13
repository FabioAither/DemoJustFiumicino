import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(layout="wide", page_title="Just Fiumicino 10/10")

# --- CONNESSIONE GOOGLE SHEETS ---
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
    df.columns = [c.strip() for c in df.columns]
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

    tab1, tab2, tab3 = st.tabs(["🗺️ Mappa & Riepilogo", "✍️ Gestione Luoghi", "📝 Feedback"])

    # --- TAB 1: MAPPA E TABELLA RECAP ---
    with tab1:
        df_map = df_luoghi.dropna(subset=['Lat', 'Lon'])
        
        if df_map.empty:
            st.warning("⚠️ Nessun dato trovato nel foglio Google.")
        else:
            # Layout Superiore: Mappa e Filtri
            col_mappa, col_filtri = st.columns([3, 1])
            
            with col_filtri:
                st.subheader("Filtri")
                target_options = sorted(df_map['Target di Riferimento'].unique().tolist())
                t_filter = st.multiselect("Target di riferimento", target_options)
                
                if t_filter:
                    df_map = df_map[df_map['Target di Riferimento'].isin(t_filter)]
                
                st.write(f"Zone individuate: **{len(df_map)}**")
                
                st.divider()
                st.subheader("📏 Calcola Percorso")
                nomi_zone = sorted(df_map['Nome Zona'].unique())
                p_a = st.selectbox("Punto di partenza:", nomi_zone, key="pa")
                p_b = st.selectbox("Punto di arrivo:", nomi_zone, key="pb")
                r_a = df_map[df_map['Nome Zona'] == p_a].iloc[0]
                r_b = df_map[df_map['Nome Zona'] == p_b].iloc[0]
                url_p = f"https://www.google.com/maps/dir/?api=1&origin={r_a['Lat']},{r_a['Lon']}&destination={r_b['Lat']},{r_b['Lon']}&travelmode=walking"
                st.link_button("🏃 Percorso a piedi", url_p)

            with col_mappa:
                m = folium.Map(location=[df_map['Lat'].mean(), df_map['Lon'].mean()], zoom_start=13)
                for _, row in df_map.iterrows():
                    nav_url = f"https://www.google.com/maps/search/?api=1&query={row['Lat']},{row['Lon']}"
                    popup_html = f"""
                        <div style='font-family: sans-serif;'>
                            <b>{row['Nome Zona']}</b><br>
                            <small>{row['Tipo di Zona']}</small><br><br>
                            <a href='{nav_url}' target='_blank' style='color: white; background: #007bff; padding: 5px 10px; text-decoration: none; border-radius: 3px;'>🚀 Navigatore</a>
                        </div>
                    """
                    folium.Marker([row['Lat'], row['Lon']], popup=folium.Popup(popup_html, max_width=250)).add_to(m)
                st_folium(m, width="100%", height=500)

            # --- NUOVA SEZIONE: TABELLA RECAP SOTTO ---
            st.divider()
            st.subheader("📋 Dettaglio Operativo Zone")
            # Selezioniamo solo le colonne utili per il volantinaggio
            df_display = df_map[['Nome Zona', 'Tipo di Zona', 'Target di Riferimento', 'Orari di Affluenza', 'Note']]
            st.dataframe(df_display, use_container_width=True, hide_index=True)

    # --- TAB 2: GESTIONE ---
    with tab2:
        st.subheader("Modifica Punti di Interesse")
        st.write("I dati qui sotto sono quelli salvati nel foglio Google.")
        st.dataframe(df_luoghi, use_container_width=True)
        st.info("💡 Per aggiungere o eliminare punti velocemente, ti consiglio di agire direttamente sul Foglio Google e poi cliccare 'Aggiorna Dati'.")

    # --- TAB 3: FEEDBACK ---
    with tab3:
        st.subheader("📝 Diario Feedback")
        col_f1, col_f2 = st.columns([1, 1])
        with col_f1:
            with st.form("form_f"):
                z = st.selectbox("Zona visitata", sorted(df_luoghi['Nome Zona'].unique()))
                tl = st.text_input("Nome Team Leader")
                comm = st.text_area("Note sulla distribuzione")
                voto = st.select_slider("Valutazione", options=[1, 2, 3, 4, 5])
                if st.form_submit_button("Invia Feedback"):
                    dt = datetime.now().strftime("%Y-%m-%d %H:%M")
                    client = get_gsheet_client()
                    sh = client.open_by_url(st.secrets["google_sheets"]["url"])
                    sh.worksheet("Feedback").append_row([len(df_feedback)+1, z, dt, tl, comm, voto])
                    st.success("Feedback salvato!")
                    st.cache_data.clear()
        
        with col_f2:
            st.write("### Storico Feedback")
            if not df_feedback.empty:
                # Creazione stelline visive
                df_f_view = df_feedback.copy()
                df_f_view['Voto'] = df_f_view['Valutazione'].apply(lambda x: "⭐" * int(x))
                st.dataframe(df_f_view[['Data_Ora', 'ID_Luogo', 'Nome_TL', 'Commento', 'Voto']].sort_values(by='Data_Ora', ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"Errore: {e}")
