import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from io import StringIO

# Dati delle zone
data = """Nome Zona,Lat,Lon,Tipo di Zona,Target di Riferimento,Orari di Affluenza,Note
Stazione Fiumicino Aeroporto,41.793,12.252,Stazione Ferroviaria,"Lavoratori aeroportuali, pendolari",08:00-10:00 / 17:00-19:30,Punto di massima densità per il personale di terra e turnisti ADR.
Uffici Indotto Hilton/Aeroporto,41.791,12.248,Uffici / Logistica,"Impiegati, personale amministrativo",17:30-19:00,Ottimo per intercettare chi lascia gli uffici a piedi verso i parcheggi.
Pista Ciclabile / Navette ADR,41.796,12.245,Snodo Logistico,"Personale operativo, logistica",12:00-14:00 / 17:00-19:00,Alta densità di lavoratori che non usano l'auto privata.
Officine Sportive,41.787,12.243,Centro Sportivo,"Sportivi (Padel/Palestra), Famiglie",17:00-20:00,Target giovane e propenso all'uso di app per il post-allenamento.
Zona Industriale Nord,41.815,12.275,Area Industriale,"Operai, addetti logistica",12:30-13:30,Utile per ordini di gruppo durante la pausa pranzo.
Parco Commerciale Da Vinci,41.812,12.336,Centro Commerciale,"Famiglie, Shopping, Lavoratori",11:00-13:00 / 16:00-21:00,Distribuzione ammessa solo su marciapiedi esterni.
The Wow Side (ex Leonardo),41.815,12.329,Centro Commerciale,"Famiglie, residenti locali",17:00-21:00,Zona coperta utile in caso di pioggia; alta affluenza nel weekend.
Stazione Parco Leonardo,41.817,12.333,Stazione Ferroviaria,Pendolari residenti,08:00-10:00 / 17:30-19:30,Intercetta i residenti del complesso che tornano da Roma.
Piazze Parco Leonardo,41.816,12.331,Area Residenziale,"Famiglie, giovani coppie",17:00-20:00,Target che abita in zona e usa abitualmente il delivery.
Campo Sportivo Cetorelli,41.777,12.235,Centro Sportivo,"Famiglie, ragazzi, sportivi",16:00-19:00,Picco durante gli allenamenti pomeridiani dei bambini.
Via Foce Micina,41.774,12.238,Arteria Commerciale,"Residenti, clienti attività locali",17:00-20:00,Snodo centrale di Isola Sacra con forte passaggio pedonale.
Olimpia Club,41.761,12.231,Centro Sportivo,"Famiglie, residenti",18:00-21:00,Frequentato da residenti locali; ottimo per conversione serale.
Darsena / Porto Canale,41.770,12.223,Area Pedonale,"Residenti, turisti locali",18:00-21:00,Zona di passeggio serale molto lenta.
Parco della Rema,41.772,12.231,Parco Pubblico,Famiglie con bambini,16:30-19:00,Ideale per intercettare i genitori durante il tempo libero."""

df = pd.read_csv(StringIO(data))

st.set_page_config(layout="wide", page_title="Dashboard Fiumicino")
st.title("🎯 Strategia Volantinaggio Fiumicino")

# Sidebar
st.sidebar.header("Filtra per necessità")
target = st.sidebar.multiselect("Chi vuoi colpire?", df['Target di Riferimento'].unique())
tipo = st.sidebar.multiselect("Tipo di luogo", df['Tipo di Zona'].unique())

df_filtered = df.copy()
if target:
    df_filtered = df_filtered[df_filtered['Target di Riferimento'].isin(target)]
if tipo:
    df_filtered = df_filtered[df_filtered['Tipo di Zona'].isin(tipo)]

# Mappa
m = folium.Map(location=[41.79, 12.27], zoom_start=13)
for _, row in df_filtered.iterrows():
    folium.Marker(
        [row['Lat'], row['Lon']],
        popup=f"<b>{row['Nome Zona']}</b><br>Orario: {row['Orari di Affluenza']}",
        tooltip=row['Nome Zona']
    ).add_to(m)

st_folium(m, width=1000, height=500)
st.write("### Elenco Zone Filtrate")
st.dataframe(df_filtered[['Nome Zona', 'Target di Riferimento', 'Orari di Affluenza', 'Note']])
