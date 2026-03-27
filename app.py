import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURAZIONE APPLE DESIGN ---
st.set_page_config(layout="wide", page_title="Just | Studio Luoghi", page_icon="📍")

# CSS Personalizzato per estetica Minimalista
st.markdown("""
    <style>
    /* Font e Sfondo */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #F5F5F7;
        color: #1D1D1F;
    }

    /* Sidebar pulita */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E5E5E7;
    }

    /* Bottoni stile Apple */
    .stButton > button {
        border-radius: 8px;
        border: None;
        background-color: #0071E3;
        color: white;
        padding: 0.5rem 1rem;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background-color: #0077ED;
        transform: scale(1.02);
    }

    /* Tabs minimaliste */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        background-color: transparent;
        border: none;
        color: #86868B;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #1D1D1F;
    }
    .stTabs [aria-selected="true"] {
        color: #0071E3 !important;
        border-bottom: 2px solid #0071E3 !important;
    }

    /* Tabelle e Card */
    div[data-testid="stDataFrame"] {
        background-color: white;
        border-radius: 12px;
        padding: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    
    /* Header */
    h1 { font-weight: 600; letter-spacing: -0.5px; color: #1D1D1F; }
    h2, h3 { font-weight: 500; color: #1D1D1F; }
    </style>
    """, unsafe_allow_stdio=True)

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
    except:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- DATI ---
df_luoghi, df_feedback, df_config = load_all_data()

# --- SIDEBAR ---
with st.sidebar:
    st.title("Just")
    st.caption("Studio Luoghi | Fiumicino")
    
    if st.button("Aggiorna database", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.subheader("Filtri")
    t_options = sorted(df_luoghi['Target di Riferimento'].unique().tolist()) if not df_luoghi.empty else []
    t_sel = st.multiselect("Target di riferimento", t_options, help="Filtra le zone sulla mappa")
    
    st.markdown("---")
    st.subheader("Percorso")
    if not df_luoghi.empty and len(df_luoghi) >= 2:
        nomi = sorted(df_luoghi['Nome Zona'].unique())
        pa = st.selectbox("Partenza", nomi, key="pa")
        pb = st.selectbox("Arrivo", nomi, key="pb")
        ra = df_luoghi[df_luoghi['Nome Zona']==pa].iloc[0]
        rb = df_luoghi[df_luoghi['Nome Zona']==pb].iloc[0]
        url_p = f"https://www.google.com/maps/dir/?api=1&origin={ra['Lat']},{ra['Lon']}&destination={rb['Lat']},{rb['Lon']}&travelmode=driving&basemap=roadmap"
        st.link_button("Calcola in auto", url_p, use_container_width=True)

# --- CORPO PRINCIPALE ---
st.title("Gestione Volantinaggio")

t1, t2, t3 = st.tabs(["Mappa", "Gestione", "Feedback"])

# --- TAB 1: MAPPA ---
with t1:
    df_map = df_luoghi.dropna(subset=['Lat', 'Lon'])
    if t_sel:
        df_map = df_map[df_map['Target di Riferimento'].isin(t_sel)]
        
    if df_map.empty:
        st.info("Nessun dato disponibile. Inizia aggiungendo un luogo.")
    else:
        # Mappa con stile pulito
        m = folium.Map(location=[df_map['Lat'].mean(), df_map['Lon'].mean()], zoom_start=13, tiles="cartodbpositron")
        for _, r in df_map.iterrows():
            nav = f"https://www.google.com/maps/search/?api=1&query={r['Lat']},{r['Lon']}&basemap=roadmap"
            html = f"""
            <div style='font-family: -apple-system, sans-serif; padding: 10px;'>
                <h4 style='margin:0 0 5px 0;'>{r['Nome Zona']}</h4>
                <p style='font-size:13px; color:#86868B; margin:0 0 10px 0;'>{r['Target di Riferimento']}</p>
                <a href='{nav}' target='_blank' style='display:block; background:#0071E3; color:white; text-align:center; padding:8px; border-radius:6px; text-decoration:none; font-size:12px;'>📍 Apri in Mappe</a>
            </div>
            """
            folium.Marker([r['Lat'], r['Lon']], popup=folium.Popup(html, max_width=250)).add_to(m)
        
        st_folium(m, width="100%", height=550, returned_objects=[])
        
        st.subheader("Riepilogo zone")
        st.dataframe(df_map[['Nome Zona', 'Tipo di Zona', 'Target di Riferimento', 'Orari di Affluenza', 'Note']], use_container_width=True, hide_index=True)

# --- TAB 2: GESTIONE ---
with t2:
    st.subheader("Gestione Punti di Interesse")
    s_add, s_edit, s_del = st.tabs(["Aggiungi", "Modifica", "Rimuovi"])

    with s_add:
        st.caption("Clicca sulla mappa per catturare le coordinate")
        m_p = folium.Map(location=[41.7733, 12.2311], zoom_start=13, tiles="cartodbpositron")
        folium.LatLngPopup().add_to(m_p)
        last_c = st_folium(m_p, width="100%", height=400, key="p_map")
        
        c_lat, c_lon = "", ""
        if last_c and last_c.get("last_clicked"):
            c_lat, c_lon = last_c["last_clicked"]["lat"], last_c["last_clicked"]["lng"]
            st.toast(f"Coordinate catturate: {c_lat}")

        with st.form("add_f", clear_on_submit=True):
            name = st.text_input("Nome della zona")
            col1, col2 = st.columns(2)
            la_n = col1.text_input("Latitudine", value=str(c_lat))
            lo_n = col2.text_input("Longitudine", value=str(c_lon))
            
            tipi = sorted(df_config['Tipo_Luogo'].tolist()) if not df_config.empty else []
            t_n = st.selectbox("Tipo di zona", tipi + ["Altro"])
            if t_n == "Altro": t_n = st.text_input("Specifica tipo")
            
            targ_n = st.text_input("Target (es. Pendolari)")
            ora_n = st.text_input("Orari di affluenza")
            not_n = st.text_area("Note operative")
            
            if st.form_submit_button("Salva zona"):
                if name and la_n and lo_n:
                    ws = get_worksheet("Luoghi")
                    ws.append_row([len(df_luoghi)+1, name, la_n, lo_n, t_n, targ_n, ora_n, not_n])
                    if t_n not in tipi: get_worksheet("Config").append_row([t_n])
                    st.success("Zona salvata")
                    st.cache_data.clear()

    with s_edit:
        if not df_luoghi.empty:
            target_edit = st.selectbox("Seleziona luogo", df_luoghi['Nome Zona'].tolist())
            idx = df_luoghi[df_luoghi['Nome Zona'] == target_edit].index[0]
            cur = df_luoghi.iloc[idx]
            with st.form("edit_f"):
                e_n = st.text_input("Nome", value=cur['Nome Zona'])
                e_lat = st.text_input("Lat", value=str(cur['Lat']))
                e_lon = st.text_input("Lon", value=str(cur['Lon']))
                e_targ = st.text_input("Target", value=cur['Target di Riferimento'])
                e_note = st.text_area("Note", value=cur['Note'])
                if st.form_submit_button("Aggiorna"):
                    ws = get_worksheet("Luoghi")
                    ws.update(range_name=f'B{idx+2}:H{idx+2}', values=[[e_n, e_lat, e_lon, cur['Tipo di Zona'], e_targ, cur['Orari di Affluenza'], e_note]])
                    st.success("Dati aggiornati")
                    st.cache_data.clear()

    with s_del:
        if not df_luoghi.empty:
            target_del = st.selectbox("Luogo da eliminare", df_luoghi['Nome Zona'].tolist())
            if st.button("Elimina definitivamente", use_container_width=True):
                ws = get_worksheet("Luoghi")
                ws.delete_rows(ws.find(target_del).row)
                st.toast("Rimosso")
                st.cache_data.clear()

# --- TAB 3: FEEDBACK ---
with t3:
    st.subheader("Diario Feedback")
    c1, c2 = st.columns([1, 2])
    with c1:
        if not df_luoghi.empty:
            with st.form("f_form", clear_on_submit=True):
                z_f = st.selectbox("Zona", sorted(df_luoghi['Nome Zona'].unique()))
                tl_f = st.text_input("Team Leader")
                comm_f = st.text_area("Feedback")
                v_f = st.select_slider("Valutazione", options=[1, 2, 3, 4, 5])
                if st.form_submit_button("Invia report"):
                    get_worksheet("Feedback").append_row([len(df_feedback)+1, z_f, datetime.now().strftime("%d/%m/%Y %H:%M"), tl_f, comm_f, v_f])
                    st.success("Report inviato")
                    st.cache_data.clear()
    with c2:
        if not df_feedback.empty:
            df_fv = df_feedback.copy().sort_values(by='Data_Ora', ascending=False)
            # Stelline Apple Style
            df_fv['Rating'] = df_fv['Valutazione'].apply(lambda x: "★" * int(x) + "☆" * (5-int(x)))
            st.dataframe(df_fv[['Data_Ora', 'ID_Luogo', 'Nome_TL', 'Commento', 'Rating']], use_container_width=True, hide_index=True)
