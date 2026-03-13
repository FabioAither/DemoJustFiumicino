import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(layout="wide", page_title="Just Fiumicino - Dashboard Operativa")

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
    
    # Pulizia nomi colonne e coordinate
    df_l.columns = [c.strip() for c in df_l.columns]
    if not df_l.empty:
        df_l['Lat'] = pd.to_numeric(df_l['Lat'].astype(str).str.replace(',', '.'), errors='coerce')
        df_l['Lon'] = pd.to_numeric(df_l['Lon'].astype(str).str.replace(',', '.'), errors='coerce')
    return df_l, df_f, df_c

try:
    df_luoghi, df_feedback, df_config = load_all_data()

    st.title("🎯 Just Fiumicino: Gestione Volantinaggio")
    
    if st.sidebar.button("🔄 Aggiorna Dati"):
        st.cache_data.clear()
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🗺️ Mappa & Riepilogo", "✍️ Gestione Luoghi", "📝 Feedback"])

    # --- TAB 1: MAPPA ---
    with tab1:
        df_map = df_luoghi.dropna(subset=['Lat', 'Lon'])
        if df_map.empty:
            st.info("👋 Database vuoto o dati non validi. Aggiungi un luogo nella scheda Gestione.")
        else:
            c_map, c_filt = st.columns([3, 1])
            with c_filt:
                st.subheader("Filtri")
                t_options = sorted(df_map['Target di Riferimento'].unique().tolist())
                t_sel = st.multiselect("Target", t_options)
                if t_sel: df_map = df_map[df_map['Target di Riferimento'].isin(t_sel)]
                
                st.divider()
                st.subheader("📏 Percorso")
                nomi = sorted(df_map['Nome Zona'].unique())
                pa = st.selectbox("Da:", nomi, key="pa")
                pb = st.selectbox("A:", nomi, key="pb")
                ra, rb = df_map[df_map['Nome Zona']==pa].iloc[0], df_map[df_map['Nome Zona']==pb].iloc[0]
                url_p = f"https://www.google.com/maps/dir/?api=1&origin={ra['Lat']},{ra['Lon']}&destination={rb['Lat']},{rb['Lon']}&travelmode=walking"
                st.link_button("🚶 Cammina", url_p)

            with c_map:
                m = folium.Map(location=[df_map['Lat'].mean(), df_map['Lon'].mean()], zoom_start=13)
                for _, r in df_map.iterrows():
                    nav = f"https://www.google.com/maps/search/?api=1&query={r['Lat']},{r['Lon']}"
                    html = f"<b>{r['Nome Zona']}</b><br><a href='{nav}' target='_blank'>🚀 Navigatore</a>"
                    folium.Marker([r['Lat'], r['Lon']], popup=folium.Popup(html, max_width=200)).add_to(m)
                st_folium(m, width="100%", height=500)
            
            st.divider()
            st.subheader("📋 Riepilogo Zone")
            st.dataframe(df_map[['Nome Zona', 'Tipo di Zona', 'Target di Riferimento', 'Orari di Affluenza', 'Note']], use_container_width=True, hide_index=True)

    # --- TAB 2: GESTIONE (ADD / EDIT / DELETE) ---
    with tab2:
        st.subheader("Centro Gestione Punti di Interesse")
        sub2_1, sub2_2, sub2_3 = st.tabs(["➕ Aggiungi", "✏️ Modifica", "🗑️ Rimuovi"])

        # AGGIUNGI
        with sub2_1:
            with st.form("add_form"):
                n = st.text_input("Nome Zona")
                c1, c2 = st.columns(2)
                lat_in = c1.text_input("Latitudine (es. 41.77)")
                lon_in = c2.text_input("Longitudine (es. 12.23)")
                
                tipi = sorted(df_config['Tipo_Luogo'].tolist()) if not df_config.empty else []
                tipo_sel = st.selectbox("Tipo di Zona", tipi + ["+ Aggiungi Nuovo Tipo"])
                if tipo_sel == "+ Aggiungi Nuovo Tipo":
                    tipo_sel = st.text_input("Specifica nuovo tipo")
                
                target = st.text_input("Target di Riferimento")
                orari = st.text_input("Orari")
                note = st.text_area("Note")
                
                if st.form_submit_button("Salva Nuovo Luogo"):
                    ws_l = get_worksheet("Luoghi")
                    new_id = len(df_luoghi) + 1
                    ws_l.append_row([new_id, n, lat_in.replace(',','.'), lon_in.replace(',','.'), tipo_sel, target, orari, note])
                    
                    # Se è un nuovo tipo, lo salva in Config
                    if tipo_sel not in tipi:
                        get_worksheet("Config").append_row([tipo_sel])
                    
                    st.success(f"Luogo '{n}' aggiunto!")
                    st.cache_data.clear()

        # MODIFICA
        with sub2_2:
            if df_luoghi.empty: st.write("Nessun dato da modificare.")
            else:
                mod_target = st.selectbox("Seleziona Luogo da modificare", df_luoghi['Nome Zona'].tolist())
                index_row = df_luoghi[df_luoghi['Nome Zona'] == mod_target].index[0]
                current_data = df_luoghi.iloc[index_row]
                
                with st.form("edit_form"):
                    new_n = st.text_input("Nome", value=current_data['Nome Zona'])
                    c1, c2 = st.columns(2)
                    new_lat = c1.text_input("Lat", value=str(current_data['Lat']))
                    new_lon = c2.text_input("Lon", value=str(current_data['Lon']))
                    new_target = st.text_input("Target", value=current_data['Target di Riferimento'])
                    new_orari = st.text_input("Orari", value=current_data['Orari di Affluenza'])
                    new_note = st.text_area("Note", value=current_data['Note'])
                    
                    if st.form_submit_button("Salva Modifiche"):
                        ws_l = get_worksheet("Luoghi")
                        # +2 perché df parte da 0 e Sheets ha intestazione
                        row_num = int(index_row) + 2
                        ws_l.update(range_name=f'B{row_num}:H{row_num}', 
                                    values=[[new_n, new_lat.replace(',','.'), new_lon.replace(',','.'), current_data['Tipo di Zona'], new_target, new_orari, new_note]])
                        st.success("Modifiche salvate!")
                        st.cache_data.clear()

        # RIMUOVI
        with sub2_3:
            del_target = st.selectbox("Seleziona Luogo da eliminare", df_luoghi['Nome Zona'].tolist(), key="del")
            if st.button("ELIMINA DEFINITIVAMENTE"):
                ws_l = get_worksheet("Luoghi")
                cell = ws_l.find(del_target)
                ws_l.delete_rows(cell.row)
                st.error(f"'{del_target}' rimosso dal database.")
                st.cache_data.clear()

    # --- TAB 3: FEEDBACK ---
    with tab3:
        st.subheader("📝 Diario Distribuzione")
        c_f1, c_f2 = st.columns([1, 1])
        with c_f1:
            with st.form("f_form"):
                z = st.selectbox("Zona visitata", sorted(df_luoghi['Nome Zona'].unique()))
                tl = st.text_input("Team Leader")
                comm = st.text_area("Commento")
                v = st.select_slider("Voto", options=[1, 2, 3, 4, 5])
                if st.form_submit_button("Invia"):
                    dt = datetime.now().strftime("%Y-%m-%d %H:%M")
                    get_worksheet("Feedback").append_row([len(df_feedback)+1, z, dt, tl, comm, v])
                    st.success("Feedback salvato!")
                    st.cache_data.clear()
        with c_f2:
            if not df_feedback.empty:
                df_f_v = df_feedback.copy().sort_values(by='Data_Ora', ascending=False)
                df_f_v['Valutazione'] = df_f_v['Valutazione'].apply(lambda x: "⭐" * int(x))
                st.dataframe(df_f_v[['Data_Ora', 'ID_Luogo', 'Nome_TL', 'Commento', 'Valutazione']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Errore tecnico: {e}")
