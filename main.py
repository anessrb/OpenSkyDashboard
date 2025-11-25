import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import folium
from streamlit_folium import st_folium
import base64

# ================================
# CONFIGURATION
# ================================
CLIENT_ID = "anessrb-api-client"
CLIENT_SECRET = "YFw0KBia26v0GL4Hqm3wCWK7fBpSuv9Q"

OPENSKY_BASE_URL = "https://opensky-network.org/api/states/all"
OPENSKY_TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
OPENSKY_FLIGHTS_URL = "https://opensky-network.org/api/flights/all"
OPENSKY_TRACK_URL = "https://opensky-network.org/api/tracks/all"

# Régions prédéfinies
REGIONS = {
    "🌍 Monde Entier": (-90, 90, -180, 180),
    "🇪🇺 Europe": (35, 71, -11, 40),
    "🇺🇸 Amérique du Nord": (15, 72, -170, -50),
    "🇨🇳 Asie": (-10, 55, 60, 150),
    "🇫🇷 France": (41, 51, -5, 10),
    "🇬🇧 Royaume-Uni": (49, 61, -8, 2),
    "🗽 New York": (40, 41.5, -74.5, -73),
    "🌉 San Francisco": (37, 38, -123, -121.5),
}

# ================================
# PAGE CONFIG
# ================================
st.set_page_config(
    page_title="Flight Tracker Pro",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS moderne minimaliste bleu clair et blanc
st.markdown("""
<style>
    /* Fond principal */
    .stApp {
        background: linear-gradient(to bottom, #f0f9ff 0%, #ffffff 100%);
    }

    /* Header principal */
    .main-header {
        background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
        padding: 2.5rem;
        border-radius: 16px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(59, 130, 246, 0.2);
    }

    /* Cartes de métriques */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        border: 1px solid #e0f2fe;
    }

    /* Boîtes de statistiques */
    .stat-box {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid #3b82f6;
        margin: 0.5rem 0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(to bottom, #ffffff 0%, #f0f9ff 100%);
    }

    /* Titres */
    h1, h2, h3 {
        color: #1e40af;
        font-weight: 600;
    }

    /* Métriques Streamlit */
    [data-testid="stMetricValue"] {
        color: #1e40af;
        font-size: 2rem;
        font-weight: 600;
    }

    [data-testid="stMetricLabel"] {
        color: #64748b;
        font-size: 0.875rem;
        font-weight: 500;
    }

    /* Boutons */
    .stButton > button {
        background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.3);
        transform: translateY(-2px);
    }

    /* Selectbox et inputs */
    .stSelectbox, .stNumberInput, .stSlider {
        background: white;
        border-radius: 8px;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: white;
        border-radius: 12px;
        padding: 0.5rem;
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        color: #64748b;
        font-weight: 500;
        padding: 0.75rem 1.5rem;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
        color: white;
    }

    /* Dividers */
    hr {
        border-color: #e0f2fe;
        margin: 2rem 0;
    }

    /* Dataframes */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }

    /* Expander */
    .streamlit-expanderHeader {
        background: white;
        border-radius: 8px;
        border: 1px solid #e0f2fe;
    }
</style>
""", unsafe_allow_html=True)

# ================================
# SESSION STATE
# ================================
if 'access_token' not in st.session_state:
    st.session_state.access_token = None
if 'token_expiry' not in st.session_state:
    st.session_state.token_expiry = None
if 'flights_data' not in st.session_state:
    st.session_state.flights_data = None
if 'last_fetch' not in st.session_state:
    st.session_state.last_fetch = None
if 'fetch_count' not in st.session_state:
    st.session_state.fetch_count = 0
if 'selected_flight' not in st.session_state:
    st.session_state.selected_flight = None
if 'flight_history' not in st.session_state:
    st.session_state.flight_history = []

# ================================
# FONCTIONS D'AUTHENTIFICATION
# ================================
def get_oauth_token():
    """Obtenir un token OAuth2"""
    if (st.session_state.access_token and 
        st.session_state.token_expiry and 
        datetime.now() < st.session_state.token_expiry):
        return st.session_state.access_token, None
    
    try:
        response = requests.post(
            OPENSKY_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30  # Augmenté à 30 secondes
        )
        response.raise_for_status()

        token_data = response.json()
        access_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in', 1800)

        st.session_state.access_token = access_token
        st.session_state.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)

        return access_token, None
    except requests.exceptions.Timeout:
        # En cas de timeout, essayer sans authentification
        return None, "TIMEOUT"
    except Exception as e:
        return None, str(e)

# ================================
# FONCTIONS API
# ================================
def fetch_flights(bbox, include_ground=False):
    """Récupérer les vols en temps réel"""
    token, error = get_oauth_token()

    # Si timeout, essayer sans authentification (mode anonyme)
    use_auth = True
    if error == "TIMEOUT":
        st.warning("⚠️ Serveur d'authentification injoignable, utilisation du mode anonyme (limité)")
        use_auth = False
    elif error:
        return None, f"Erreur d'authentification: {error}"

    params = {
        'lamin': bbox[0],
        'lomin': bbox[2],
        'lamax': bbox[1],
        'lomax': bbox[3]
    }

    try:
        headers = {'Authorization': f'Bearer {token}'} if use_auth and token else {}
        response = requests.get(
            OPENSKY_BASE_URL,
            params=params,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        st.session_state.fetch_count += 1
        data = response.json()
        
        if not data or not data.get('states'):
            return None, "Aucun vol détecté dans cette région"
        
        COLUMNS = [
            'icao24', 'callsign', 'origin_country', 'time_position', 'last_contact',
            'longitude', 'latitude', 'baro_altitude', 'on_ground', 'velocity',
            'true_track', 'vertical_rate', 'sensors', 'geo_altitude', 'squawk',
            'spi', 'position_source'
        ]
        
        df = pd.DataFrame(data['states'], columns=COLUMNS)
        
        # Filtrer les vols au sol si nécessaire
        if not include_ground:
            df = df[df['on_ground'] == False].copy()
        
        # Filtrer les positions valides
        df = df[df['latitude'].notna() & df['longitude'].notna()].copy()
        
        if df.empty:
            return None, "Aucun vol avec position valide"
        
        # Conversions
        df['velocity_knots'] = df['velocity'].fillna(0) * 1.94384
        df['velocity_kmh'] = df['velocity'].fillna(0) * 3.6
        df['geo_altitude_ft'] = df['geo_altitude'].fillna(0) * 3.28084
        df['geo_altitude_m'] = df['geo_altitude'].fillna(0)
        df['vertical_rate_fpm'] = df['vertical_rate'].fillna(0) * 196.85
        
        # Nettoyage
        df['callsign'] = df['callsign'].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() else 'N/A'
        )
        
        # Direction de vol
        df['heading'] = df['true_track'].apply(lambda x: get_direction(x) if pd.notna(x) else 'N/A')
        
        # Statut de vol
        df['status'] = df.apply(lambda row: get_flight_status(row), axis=1)

        # Compagnie aérienne
        df['airline'] = df['callsign'].apply(get_airline_from_callsign)

        df = df.rename(columns={'latitude': 'lat', 'longitude': 'lon'})

        st.session_state.flights_data = df
        st.session_state.last_fetch = datetime.now()

        return df, None
        
    except Exception as e:
        return None, f"Erreur: {str(e)}"

def get_direction(degrees):
    """Convertir les degrés en direction cardinale"""
    if pd.isna(degrees):
        return 'N/A'
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    idx = int((degrees + 22.5) / 45) % 8
    return directions[idx]

def get_flight_status(row):
    """Déterminer le statut du vol"""
    if row['on_ground']:
        return '🛬 Au sol'
    vr = row['vertical_rate']
    if pd.notna(vr):
        if vr > 1:
            return '🛫 Montée'
        elif vr < -1:
            return '🛬 Descente'
    return '✈️ Croisière'

def get_airline_from_callsign(callsign):
    """Extraire la compagnie aérienne du callsign"""
    if pd.isna(callsign) or callsign == 'N/A':
        return 'Inconnu'

    # Dictionnaire des codes IATA/ICAO communs
    airline_codes = {
        'AFR': 'Air France', 'BAW': 'British Airways', 'DLH': 'Lufthansa',
        'UAE': 'Emirates', 'QTR': 'Qatar Airways', 'SIA': 'Singapore Airlines',
        'AAL': 'American Airlines', 'UAL': 'United Airlines', 'DAL': 'Delta',
        'RYR': 'Ryanair', 'EZY': 'easyJet', 'WZZ': 'Wizz Air',
        'THY': 'Turkish Airlines', 'AIC': 'Air India', 'CCA': 'Air China',
        'CSN': 'China Southern', 'JAL': 'Japan Airlines', 'ANA': 'All Nippon',
        'KLM': 'KLM', 'IBE': 'Iberia', 'SWR': 'Swiss',
        'ACA': 'Air Canada', 'QFA': 'Qantas', 'ETH': 'Ethiopian Airlines'
    }

    # Extraire les 3 premières lettres du callsign
    code = str(callsign).strip()[:3].upper()
    return airline_codes.get(code, code)

def fetch_flight_track(icao24, timestamp):
    """Récupérer la trajectoire d'un vol spécifique"""
    token, error = get_oauth_token()
    if error:
        return None, f"Erreur d'authentification: {error}"

    try:
        response = requests.get(
            OPENSKY_TRACK_URL,
            params={'icao24': icao24, 'time': int(timestamp)},
            headers={'Authorization': f'Bearer {token}'},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

        if not data or 'path' not in data:
            return None, "Aucune trajectoire disponible"

        # Convertir en DataFrame
        track_df = pd.DataFrame(data['path'], columns=['time', 'lat', 'lon', 'baro_altitude', 'true_track', 'on_ground'])
        return track_df, None

    except Exception as e:
        return None, f"Erreur: {str(e)}"

# ================================
# HEADER
# ================================
st.markdown("""
<div class="main-header">
    <h1>✈️ Flight Tracker Pro - Suivi Mondial des Vols</h1>
    <p>Surveillance en temps réel via OpenSky Network API</p>
</div>
""", unsafe_allow_html=True)

# ================================
# SIDEBAR
# ================================
with st.sidebar:
    st.image("logo.png", use_container_width=True)
    
    st.header("⚙️ Configuration")
    
    # Sélection de région
    selected_region = st.selectbox(
        "🌍 Région",
        list(REGIONS.keys()),
        index=0
    )
    bbox = REGIONS[selected_region]
    
    # Options d'affichage
    st.subheader("📊 Options d'affichage")
    include_ground = st.checkbox("Inclure les avions au sol", value=False)
    
    # Filtres
    st.subheader("🔍 Filtres")
    
    col1, col2 = st.columns(2)
    with col1:
        min_alt = st.number_input("Alt. min (ft)", 0, 50000, 0, 1000)
    with col2:
        max_alt = st.number_input("Alt. max (ft)", 0, 50000, 50000, 1000)
    
    min_speed = st.slider("Vitesse min (knots)", 0, 600, 0, 10)
    
    # Pays
    if st.session_state.flights_data is not None and 'origin_country' in st.session_state.flights_data.columns:
        countries = ['Tous'] + sorted(st.session_state.flights_data['origin_country'].unique().tolist())
        selected_country = st.selectbox("Pays d'origine", countries)
    else:
        selected_country = 'Tous'

    # Compagnies aériennes
    if st.session_state.flights_data is not None and 'airline' in st.session_state.flights_data.columns:
        airlines = ['Toutes'] + sorted(st.session_state.flights_data['airline'].unique().tolist())
        selected_airline = st.selectbox("Compagnie aérienne", airlines, key='airline_filter')
    else:
        selected_airline = 'Toutes'

    st.divider()
    
    # Contrôles de rafraîchissement
    st.subheader("🔄 Rafraîchissement")
    
    auto_refresh = st.checkbox("Auto-refresh", value=False)
    if auto_refresh:
        refresh_interval = st.slider("Intervalle (sec)", 15, 120, 30)
    
    if st.button("🔄 Rafraîchir maintenant", use_container_width=True):
        st.rerun()
    
    st.divider()
    
    # Statistiques de session
    st.subheader("📈 Session")
    st.metric("Requêtes API", st.session_state.fetch_count)
    if st.session_state.last_fetch:
        st.caption(f"Dernière màj: {st.session_state.last_fetch.strftime('%H:%M:%S')}")
    
    # Token info
    if st.session_state.token_expiry:
        time_left = (st.session_state.token_expiry - datetime.now()).total_seconds()
        if time_left > 0:
            st.caption(f"Token expire dans: {int(time_left/60)} min")

# ================================
# MAIN CONTENT
# ================================

# Récupération des données
with st.spinner("🛰️ Récupération des données de vol..."):
    df, error = fetch_flights(bbox, include_ground)

if error:
    st.error(f"❌ {error}")
    st.stop()

if df is None or df.empty:
    st.warning("Aucun vol disponible dans cette région")
    st.stop()

# Application des filtres
filtered_df = df.copy()
filtered_df = filtered_df[
    (filtered_df['geo_altitude_ft'] >= min_alt) &
    (filtered_df['geo_altitude_ft'] <= max_alt) &
    (filtered_df['velocity_knots'] >= min_speed)
]

if selected_country != 'Tous':
    filtered_df = filtered_df[filtered_df['origin_country'] == selected_country]

if selected_airline != 'Toutes':
    filtered_df = filtered_df[filtered_df['airline'] == selected_airline]

# ================================
# MÉTRIQUES PRINCIPALES
# ================================
st.subheader("📊 Vue d'ensemble")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "✈️ Vols totaux",
        len(df),
        f"{len(filtered_df)} filtrés"
    )

with col2:
    avg_speed = filtered_df['velocity_knots'].mean()
    st.metric(
        "⚡ Vitesse moy.",
        f"{avg_speed:.0f} kts",
        f"{avg_speed * 1.852:.0f} km/h"
    )

with col3:
    avg_alt = filtered_df['geo_altitude_ft'].mean()
    st.metric(
        "📏 Altitude moy.",
        f"{avg_alt:.0f} ft",
        f"{avg_alt * 0.3048:.0f} m"
    )

with col4:
    max_speed = filtered_df['velocity_knots'].max()
    st.metric(
        "🚀 Vitesse max",
        f"{max_speed:.0f} kts"
    )

with col5:
    max_altitude = filtered_df['geo_altitude_ft'].max()
    st.metric(
        "⛰️ Altitude max",
        f"{max_altitude:.0f} ft"
    )

st.divider()

# ================================
# ONGLETS PRINCIPAUX
# ================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🗺️ Carte Interactive",
    "📊 Analyses",
    "🔥 Heatmap Trafic",
    "✈️ Compagnies",
    "📋 Liste des Vols",
    "🔍 Détails Vol",
    "🌐 Statistiques Globales"
])

# ============ ONGLET 1: CARTE ============
with tab1:
    st.subheader("🗺️ Carte des vols en temps réel")

    if not filtered_df.empty:
        # Définir les couleurs par statut
        status_colors = {
            '🛫 Montée': '#FF0000',     # Rouge
            '🛬 Descente': '#000000',   # Noir
            '✈️ Croisière': '#0000FF',  # Bleu
            '🛬 Au sol': '#808080'      # Gris
        }

        # Calculer le centre de la carte
        center_lat = filtered_df['lat'].mean()
        center_lon = filtered_df['lon'].mean()

        # Calculer le zoom basé sur la bbox
        lat_range = bbox[1] - bbox[0]
        lon_range = bbox[3] - bbox[2]
        max_range = max(lat_range, lon_range)

        # Formule pour convertir la plage en niveau de zoom
        if max_range > 100:
            zoom_level = 1
        elif max_range > 50:
            zoom_level = 2
        elif max_range > 20:
            zoom_level = 3
        elif max_range > 10:
            zoom_level = 4
        else:
            zoom_level = 6

        # Créer la carte Plotly Scattermapbox (RAPIDE et FIABLE)
        fig = go.Figure()

        # Ajouter les avions par statut
        for status in filtered_df['status'].unique():
            df_status = filtered_df[filtered_df['status'] == status]

            fig.add_trace(go.Scattermapbox(
                lon=df_status['lon'],
                lat=df_status['lat'],
                mode='markers',
                name=status,
                marker=dict(
                    size=5,  # Petits points
                    color=status_colors.get(status, '#0000FF'),
                    opacity=0.9
                ),
                text=df_status.apply(lambda row:
                    f"<b>{row['callsign']}</b><br>" +
                    f"Pays: {row['origin_country']}<br>" +
                    f"Alt: {row['geo_altitude_ft']:.0f} ft<br>" +
                    f"Vitesse: {row['velocity_knots']:.0f} kts<br>" +
                    f"Statut: {row['status']}", axis=1
                ),
                hovertemplate='%{text}<extra></extra>'
            ))

        fig.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=center_lat, lon=center_lon),
                zoom=zoom_level,
                # Limiter l'affichage à une seule instance du monde
                bounds=dict(
                    west=-180,
                    east=180,
                    south=-85,
                    north=85
                )
            ),
            height=700,
            margin={"r":0,"t":0,"l":0,"b":0},
            showlegend=True,
            hovermode='closest'
        )

        st.plotly_chart(fig, use_container_width=True, config={
            'scrollZoom': True,
            'displayModeBar': True,
            'displaylogo': False
        })

    else:
        st.info("Aucun vol ne correspond aux filtres sélectionnés")

# ============ ONGLET 2: ANALYSES ============
with tab2:
    st.subheader("📊 Analyses avancées")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Distribution des altitudes
        st.markdown("#### 📏 Distribution des altitudes")
        fig_alt = px.histogram(
            filtered_df,
            x='geo_altitude_ft',
            nbins=30,
            title="Répartition des vols par altitude",
            labels={'geo_altitude_ft': 'Altitude (ft)', 'count': 'Nombre de vols'},
            color_discrete_sequence=['#667eea']
        )
        fig_alt.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig_alt, use_container_width=True)
    
    with col2:
        # Distribution des vitesses
        st.markdown("#### ⚡ Distribution des vitesses")
        fig_speed = px.histogram(
            filtered_df,
            x='velocity_knots',
            nbins=30,
            title="Répartition des vols par vitesse",
            labels={'velocity_knots': 'Vitesse (knots)', 'count': 'Nombre de vols'},
            color_discrete_sequence=['#764ba2']
        )
        fig_speed.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig_speed, use_container_width=True)
    
    col3, col4 = st.columns(2)
    
    with col3:
        # Top pays
        st.markdown("#### 🌍 Top 10 pays")
        country_counts = filtered_df['origin_country'].value_counts().head(10)
        fig_countries = px.bar(
            x=country_counts.values,
            y=country_counts.index,
            orientation='h',
            title="Vols par pays d'origine",
            labels={'x': 'Nombre de vols', 'y': 'Pays'},
            color=country_counts.values,
            color_continuous_scale='Viridis'
        )
        fig_countries.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_countries, use_container_width=True)
    
    with col4:
        # Statut des vols
        st.markdown("#### 📊 Statut des vols")
        status_counts = filtered_df['status'].value_counts()
        fig_status = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Répartition par phase de vol",
            hole=0.4
        )
        fig_status.update_layout(height=400)
        st.plotly_chart(fig_status, use_container_width=True)
    
    # Heatmap altitude vs vitesse
    st.markdown("#### 🔥 Heatmap Altitude vs Vitesse")
    fig_heatmap = px.density_heatmap(
        filtered_df,
        x='velocity_knots',
        y='geo_altitude_ft',
        nbinsx=30,
        nbinsy=30,
        title="Densité des vols selon altitude et vitesse",
        labels={'velocity_knots': 'Vitesse (knots)', 'geo_altitude_ft': 'Altitude (ft)'},
        color_continuous_scale='Turbo'
    )
    fig_heatmap.update_layout(height=400)
    st.plotly_chart(fig_heatmap, use_container_width=True)

# ============ ONGLET 3: HEATMAP TRAFIC ============
with tab3:
    st.subheader("🔥 Heatmap de densité du trafic aérien")

    if not filtered_df.empty:
        st.markdown("""
        Cette visualisation montre la concentration géographique du trafic aérien en temps réel.
        Les zones rouges indiquent une forte densité de vols.
        """)

        # Créer une heatmap de densité
        fig_density = go.Figure()

        fig_density.add_trace(go.Densitymapbox(
            lon=filtered_df['lon'],
            lat=filtered_df['lat'],
            z=[1] * len(filtered_df),  # Poids égal pour chaque vol
            radius=15,
            colorscale=[
                [0, 'rgba(59, 130, 246, 0)'],      # Bleu transparent
                [0.2, 'rgba(59, 130, 246, 0.3)'],  # Bleu clair
                [0.4, 'rgba(34, 197, 94, 0.5)'],   # Vert
                [0.6, 'rgba(234, 179, 8, 0.7)'],   # Jaune
                [0.8, 'rgba(249, 115, 22, 0.9)'],  # Orange
                [1, 'rgba(239, 68, 68, 1)']        # Rouge vif
            ],
            showscale=True,
            colorbar=dict(
                title="Densité",
                thickness=15,
                len=0.7
            ),
            hovertemplate='Densité de trafic<extra></extra>'
        ))

        # Calculer le centre de la carte
        center_lat = filtered_df['lat'].median()
        center_lon = filtered_df['lon'].median()

        fig_density.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=center_lat, lon=center_lon),
                zoom=3,
                bounds=dict(west=-180, east=180, south=-85, north=85)
            ),
            height=700,
            margin={"r":0,"t":0,"l":0,"b":0},
            hovermode='closest'
        )

        st.plotly_chart(fig_density, use_container_width=True, config={
            'scrollZoom': True,
            'displayModeBar': True,
            'displaylogo': False
        })

        # Statistiques de densité
        st.markdown("### 📊 Statistiques de concentration")

        st.info("💡 **Comment lire la heatmap**: Les zones rouges/orange indiquent une forte concentration de vols. "
                "Les zones sont calculées sur des grilles de 2° x 2° (environ 200 km).")

        col1, col2, col3, col4 = st.columns(4)

        # Calculer les zones avec le plus de trafic (grilles plus petites)
        lat_bins = 90   # 2 degrés par bin
        lon_bins = 180  # 2 degrés par bin

        lat_edges = np.linspace(-90, 90, lat_bins + 1)
        lon_edges = np.linspace(-180, 180, lon_bins + 1)

        # Compter les vols par zone
        df_temp = filtered_df.copy()
        df_temp['lat_bin'] = pd.cut(df_temp['lat'], bins=lat_edges, labels=False)
        df_temp['lon_bin'] = pd.cut(df_temp['lon'], bins=lon_edges, labels=False)

        zone_counts = df_temp.groupby(['lat_bin', 'lon_bin']).size().reset_index(name='count')

        if len(zone_counts) > 0:
            max_zone = zone_counts.loc[zone_counts['count'].idxmax()]
            max_zone_lat = (lat_edges[int(max_zone['lat_bin'])] + lat_edges[int(max_zone['lat_bin']) + 1]) / 2
            max_zone_lon = (lon_edges[int(max_zone['lon_bin'])] + lon_edges[int(max_zone['lon_bin']) + 1]) / 2

            with col1:
                st.metric("🎯 Zone la plus dense", f"{int(max_zone['count'])} vols")

            with col2:
                st.metric("📍 Centre lat.", f"{max_zone_lat:.1f}°")

            with col3:
                st.metric("📍 Centre lon.", f"{max_zone_lon:.1f}°")

            with col4:
                # Calculer la dispersion géographique (écart-type moyen)
                dispersion = df_temp[['lat', 'lon']].std().mean()
                st.metric("📏 Dispersion", f"{dispersion:.1f}°")

            st.caption(f"💡 La zone la plus dense (lat: {max_zone_lat:.1f}°, lon: {max_zone_lon:.1f}°) "
                      f"contient {int(max_zone['count'])} vols dans un carré de ~200 km de côté.")

        # Top 10 zones les plus denses
        st.markdown("### 🏆 Top 10 zones de trafic intense")
        st.caption("📍 Chaque zone représente un carré d'environ 200 km x 200 km")

        top_zones = zone_counts.nlargest(10, 'count').copy()
        top_zones['lat_center'] = top_zones['lat_bin'].apply(lambda x: (lat_edges[int(x)] + lat_edges[int(x) + 1]) / 2)
        top_zones['lon_center'] = top_zones['lon_bin'].apply(lambda x: (lon_edges[int(x)] + lon_edges[int(x) + 1]) / 2)

        # Ajouter une région approximative pour mieux comprendre
        def get_region(lat, lon):
            if 35 <= lat <= 55 and -10 <= lon <= 30:
                return "🇪🇺 Europe"
            elif 25 <= lat <= 50 and -125 <= lon <= -65:
                return "🇺🇸 Amérique du Nord"
            elif 30 <= lat <= 45 and 100 <= lon <= 145:
                return "🇯🇵 Asie de l'Est"
            elif -40 <= lat <= -10 and -80 <= lon <= -30:
                return "🇧🇷 Amérique du Sud"
            elif -45 <= lat <= -10 and 110 <= lon <= 155:
                return "🇦🇺 Océanie"
            elif 0 <= lat <= 35 and 40 <= lon <= 80:
                return "🌍 Moyen-Orient"
            else:
                return "🌐 Autre"

        display_zones = pd.DataFrame({
            'Rang': range(1, len(top_zones) + 1),
            'Vols': top_zones['count'].values,
            'Centre Lat.': [f"{lat:.1f}°" for lat in top_zones['lat_center'].values],
            'Centre Lon.': [f"{lon:.1f}°" for lon in top_zones['lon_center'].values],
            'Région': [get_region(lat, lon) for lat, lon in zip(top_zones['lat_center'].values, top_zones['lon_center'].values)]
        })

        st.dataframe(display_zones, use_container_width=True, hide_index=True)

    else:
        st.info("Aucune donnée disponible pour la heatmap")

# ============ ONGLET 4: COMPAGNIES AÉRIENNES ============
with tab4:
    st.subheader("✈️ Analyse par compagnie aérienne")

    if not filtered_df.empty:
        # Compter les vols par compagnie
        airline_counts = filtered_df['airline'].value_counts().reset_index()
        airline_counts.columns = ['Compagnie', 'Nombre de vols']

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### 📊 Top 15 compagnies aériennes")

            top_15_airlines = airline_counts.head(15)

            fig_airlines = px.bar(
                top_15_airlines,
                x='Nombre de vols',
                y='Compagnie',
                orientation='h',
                title="Compagnies avec le plus de vols actifs",
                labels={'Nombre de vols': 'Vols actifs', 'Compagnie': 'Compagnie aérienne'},
                color='Nombre de vols',
                color_continuous_scale='Blues'
            )
            fig_airlines.update_layout(
                showlegend=False,
                height=500,
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig_airlines, use_container_width=True)

        with col2:
            st.markdown("### 🥇 Statistiques")

            total_airlines = filtered_df['airline'].nunique()
            st.metric("Nombre de compagnies", total_airlines)

            top_airline = airline_counts.iloc[0]
            st.markdown(f"""
            <div class="stat-box">
                <h4>👑 Compagnie #1</h4>
                <p><b>{top_airline['Compagnie']}</b></p>
                <p>{top_airline['Nombre de vols']} vols actifs</p>
                <p>{(top_airline['Nombre de vols'] / len(filtered_df) * 100):.1f}% du trafic</p>
            </div>
            """, unsafe_allow_html=True)

            # Compagnie la plus rapide en moyenne
            avg_speed_by_airline = filtered_df.groupby('airline')['velocity_knots'].mean().reset_index()
            avg_speed_by_airline.columns = ['Compagnie', 'Vitesse moyenne']
            fastest_airline = avg_speed_by_airline.loc[avg_speed_by_airline['Vitesse moyenne'].idxmax()]

            st.markdown(f"""
            <div class="stat-box">
                <h4>🚀 Plus rapide (moyenne)</h4>
                <p><b>{fastest_airline['Compagnie']}</b></p>
                <p>{fastest_airline['Vitesse moyenne']:.0f} knots</p>
            </div>
            """, unsafe_allow_html=True)

            # Compagnie qui vole le plus haut en moyenne
            avg_alt_by_airline = filtered_df.groupby('airline')['geo_altitude_ft'].mean().reset_index()
            avg_alt_by_airline.columns = ['Compagnie', 'Altitude moyenne']
            highest_airline = avg_alt_by_airline.loc[avg_alt_by_airline['Altitude moyenne'].idxmax()]

            st.markdown(f"""
            <div class="stat-box">
                <h4>⛰️ Plus haut (moyenne)</h4>
                <p><b>{highest_airline['Compagnie']}</b></p>
                <p>{highest_airline['Altitude moyenne']:.0f} ft</p>
            </div>
            """, unsafe_allow_html=True)

        # Graphique en camembert
        st.markdown("### 🥧 Répartition du trafic")

        col1, col2 = st.columns(2)

        with col1:
            # Top 10 + Autres
            top_10_airlines = airline_counts.head(10)
            others_count = airline_counts.iloc[10:]['Nombre de vols'].sum()

            if others_count > 0:
                pie_data = pd.concat([
                    top_10_airlines,
                    pd.DataFrame({'Compagnie': ['Autres'], 'Nombre de vols': [others_count]})
                ])
            else:
                pie_data = top_10_airlines

            fig_pie = px.pie(
                pie_data,
                values='Nombre de vols',
                names='Compagnie',
                title="Part de marché (Top 10)",
                hole=0.4
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col2:
            # Statut des vols par compagnie (pour les top 5)
            top_5_airlines = airline_counts.head(5)['Compagnie'].tolist()

            status_by_airline = filtered_df[filtered_df['airline'].isin(top_5_airlines)].groupby(
                ['airline', 'status']
            ).size().reset_index(name='count')

            fig_status = px.bar(
                status_by_airline,
                x='airline',
                y='count',
                color='status',
                title="Statut des vols (Top 5 compagnies)",
                labels={'airline': 'Compagnie', 'count': 'Nombre de vols', 'status': 'Statut'},
                barmode='stack'
            )
            fig_status.update_layout(height=400)
            st.plotly_chart(fig_status, use_container_width=True)

        # Tableau détaillé
        st.markdown("### 📋 Tableau détaillé par compagnie")

        detailed_stats = filtered_df.groupby('airline').agg({
            'icao24': 'count',
            'velocity_knots': 'mean',
            'geo_altitude_ft': 'mean',
            'origin_country': lambda x: x.mode()[0] if len(x.mode()) > 0 else 'N/A'
        }).reset_index()

        detailed_stats.columns = [
            'Compagnie',
            'Nombre de vols',
            'Vitesse moyenne (kts)',
            'Altitude moyenne (ft)',
            'Pays principal'
        ]

        detailed_stats = detailed_stats.sort_values('Nombre de vols', ascending=False)

        st.dataframe(
            detailed_stats,
            column_config={
                'Compagnie': st.column_config.TextColumn('Compagnie', width='medium'),
                'Nombre de vols': st.column_config.NumberColumn('Vols', format='%d'),
                'Vitesse moyenne (kts)': st.column_config.NumberColumn('Vitesse moy.', format='%.0f kts'),
                'Altitude moyenne (ft)': st.column_config.NumberColumn('Altitude moy.', format='%.0f ft'),
                'Pays principal': st.column_config.TextColumn('Pays', width='medium'),
            },
            use_container_width=True,
            hide_index=True,
            height=400
        )

        # Sélection d'une compagnie spécifique
        st.markdown("### 🔍 Détails d'une compagnie")

        unique_airlines = sorted(filtered_df['airline'].unique().tolist())

        selected_airline_detail = st.selectbox(
            "Choisir une compagnie",
            options=unique_airlines,
            key='airline_detail_selector'
        )

        if selected_airline_detail:
            airline_flights = filtered_df[filtered_df['airline'] == selected_airline_detail].copy()

            if len(airline_flights) == 0:
                st.warning(f"Aucun vol trouvé pour {selected_airline_detail}")
            else:
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("✈️ Vols actifs", len(airline_flights))

                with col2:
                    avg_speed = airline_flights['velocity_knots'].mean()
                    st.metric("⚡ Vitesse moy.", f"{avg_speed:.0f} kts" if pd.notna(avg_speed) else "N/A")

                with col3:
                    avg_alt = airline_flights['geo_altitude_ft'].mean()
                    st.metric("📏 Altitude moy.", f"{avg_alt:.0f} ft" if pd.notna(avg_alt) else "N/A")

                with col4:
                    country_mode = airline_flights['origin_country'].mode()
                    country = country_mode[0] if len(country_mode) > 0 else 'N/A'
                    st.metric("🌍 Pays", country)

                # Carte des vols de cette compagnie
                st.markdown(f"#### 🗺️ Vols de {selected_airline_detail}")

                # Vérifier qu'il y a des données valides pour la carte
                valid_flights = airline_flights.dropna(subset=['lat', 'lon'])

                if len(valid_flights) == 0:
                    st.warning("Pas de données de position valides pour cette compagnie")
                else:
                    fig_airline_map = go.Figure()

                    status_colors = {
                        '🛫 Montée': '#FF0000',
                        '🛬 Descente': '#000000',
                        '✈️ Croisière': '#0000FF',
                        '🛬 Au sol': '#808080'
                    }

                    for status in valid_flights['status'].unique():
                        df_status = valid_flights[valid_flights['status'] == status]
                        if len(df_status) > 0:
                            fig_airline_map.add_trace(go.Scattermapbox(
                                lon=df_status['lon'],
                                lat=df_status['lat'],
                                mode='markers',
                                name=status,
                                marker=dict(
                                    size=8,
                                    color=status_colors.get(status, '#0000FF'),
                                    opacity=0.9
                                ),
                                text=df_status.apply(lambda row: f"""
                                <b>{row['callsign']}</b><br>
                                Altitude: {row['geo_altitude_ft']:.0f} ft<br>
                                Vitesse: {row['velocity_knots']:.0f} kts<br>
                                Direction: {row['heading']}<br>
                                Pays: {row['origin_country']}
                                """, axis=1),
                                hovertemplate='%{text}<extra></extra>'
                            ))

                    center_lat = valid_flights['lat'].median()
                    center_lon = valid_flights['lon'].median()

                    fig_airline_map.update_layout(
                        mapbox=dict(
                            style="open-street-map",
                            center=dict(lat=center_lat, lon=center_lon),
                            zoom=3,
                            bounds=dict(west=-180, east=180, south=-85, north=85)
                        ),
                        height=500,
                        margin={"r":0,"t":0,"l":0,"b":0},
                        showlegend=True,
                        hovermode='closest'
                    )

                    st.plotly_chart(fig_airline_map, use_container_width=True, config={
                        'scrollZoom': True,
                        'displayModeBar': True,
                        'displaylogo': False
                    })

    else:
        st.info("Aucune donnée disponible pour l'analyse des compagnies")

# ============ ONGLET 5: LISTE DES VOLS ============
with tab5:
    st.subheader("📋 Liste détaillée des vols")
    
    # Options d'affichage
    col1, col2, col3 = st.columns(3)
    with col1:
        sort_by = st.selectbox("Trier par", [
            'velocity_knots', 'geo_altitude_ft', 'callsign', 'origin_country'
        ], format_func=lambda x: {
            'velocity_knots': 'Vitesse',
            'geo_altitude_ft': 'Altitude',
            'callsign': 'Indicatif',
            'origin_country': 'Pays'
        }[x])
    
    with col2:
        sort_order = st.radio("Ordre", ['Décroissant', 'Croissant'], horizontal=True)
    
    with col3:
        rows_per_page = st.selectbox("Lignes par page", [10, 25, 50, 100])
    
    # Tri
    ascending = sort_order == 'Croissant'
    display_df = filtered_df.sort_values(sort_by, ascending=ascending).reset_index(drop=True)
    
    # Affichage paginé
    st.dataframe(
        display_df[[
            'callsign', 'origin_country', 'status', 'geo_altitude_ft',
            'velocity_knots', 'heading', 'lat', 'lon'
        ]].head(rows_per_page),
        column_config={
            'callsign': st.column_config.TextColumn('Indicatif', width='medium'),
            'origin_country': st.column_config.TextColumn('Pays', width='medium'),
            'status': st.column_config.TextColumn('Statut', width='small'),
            'geo_altitude_ft': st.column_config.ProgressColumn(
                'Altitude (ft)',
                format='%.0f',
                min_value=0,
                max_value=50000,
                width='medium'
            ),
            'velocity_knots': st.column_config.ProgressColumn(
                'Vitesse (kts)',
                format='%.0f',
                min_value=0,
                max_value=600,
                width='medium'
            ),
            'heading': st.column_config.TextColumn('Direction', width='small'),
            'lat': st.column_config.NumberColumn('Latitude', format='%.4f', width='small'),
            'lon': st.column_config.NumberColumn('Longitude', format='%.4f', width='small'),
        },
        use_container_width=True,
        hide_index=True,
        height=600
    )
    
    # Export CSV
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Télécharger CSV",
        data=csv,
        file_name=f"flights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

# ============ ONGLET 6: DÉTAILS VOL ============
with tab6:
    st.subheader("🔍 Recherche et détails d'un vol")
    
    # Recherche
    search_callsign = st.text_input("🔎 Rechercher par indicatif (ex: AFR447)", "")
    
    if search_callsign:
        search_results = filtered_df[
            filtered_df['callsign'].str.contains(search_callsign.upper(), na=False)
        ]
        
        if not search_results.empty:
            st.success(f"✅ {len(search_results)} vol(s) trouvé(s)")
            
            for idx, flight in search_results.iterrows():
                with st.expander(f"✈️ {flight['callsign']} - {flight['origin_country']}", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("**🆔 Identification**")
                        st.write(f"ICAO24: `{flight['icao24']}`")
                        st.write(f"Indicatif: `{flight['callsign']}`")
                        st.write(f"Pays: {flight['origin_country']}")
                        st.write(f"Squawk: {flight['squawk'] if pd.notna(flight['squawk']) else 'N/A'}")
                    
                    with col2:
                        st.markdown("**📍 Position & Altitude**")
                        st.write(f"Latitude: {flight['lat']:.4f}°")
                        st.write(f"Longitude: {flight['lon']:.4f}°")
                        st.write(f"Altitude: {flight['geo_altitude_ft']:.0f} ft ({flight['geo_altitude_m']:.0f} m)")
                        st.write(f"Altitude baro: {flight['baro_altitude'] * 3.28084:.0f} ft" if pd.notna(flight['baro_altitude']) else "N/A")
                    
                    with col3:
                        st.markdown("**⚡ Vitesse & Direction**")
                        st.write(f"Vitesse: {flight['velocity_knots']:.0f} kts ({flight['velocity_kmh']:.0f} km/h)")
                        st.write(f"Direction: {flight['heading']} ({flight['true_track']:.1f}°)" if pd.notna(flight['true_track']) else "N/A")
                        st.write(f"Taux vertical: {flight['vertical_rate_fpm']:.0f} fpm" if pd.notna(flight['vertical_rate']) else "N/A")
                        st.write(f"Statut: {flight['status']}")
                    
                    # Mini carte
                    st.markdown("**🗺️ Position sur la carte**")
                    flight_map = pd.DataFrame({
                        'lat': [flight['lat']],
                        'lon': [flight['lon']]
                    })
                    st.map(flight_map, zoom=8)
        else:
            st.warning(f"Aucun vol trouvé avec l'indicatif '{search_callsign}'")
    else:
        st.info("👆 Entrez un indicatif de vol pour afficher les détails")
        
        # Afficher quelques exemples
        st.markdown("**Exemples de vols actifs:**")
        sample_flights = filtered_df.head(5)
        for idx, flight in sample_flights.iterrows():
            st.write(f"• {flight['callsign']} ({flight['origin_country']}) - {flight['status']}")

# ============ ONGLET 7: STATS GLOBALES ============
with tab7:
    st.subheader("🌐 Statistiques globales")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📊 Résumé statistique complet")
        
        stats_data = {
            'Métrique': [
                'Nombre total de vols',
                'Vols filtrés affichés',
                'Nombre de pays représentés',
                'Vitesse moyenne',
                'Vitesse médiane',
                'Vitesse max',
                'Altitude moyenne',
                'Altitude médiane',
                'Altitude max',
                'Taux de montée moyen',
                'Taux de descente moyen'
            ],
            'Valeur': [
                len(df),
                len(filtered_df),
                filtered_df['origin_country'].nunique(),
                f"{filtered_df['velocity_knots'].mean():.1f} kts",
                f"{filtered_df['velocity_knots'].median():.1f} kts",
                f"{filtered_df['velocity_knots'].max():.1f} kts",
                f"{filtered_df['geo_altitude_ft'].mean():.0f} ft",
                f"{filtered_df['geo_altitude_ft'].median():.0f} ft",
                f"{filtered_df['geo_altitude_ft'].max():.0f} ft",
                f"{filtered_df[filtered_df['vertical_rate'] > 0]['vertical_rate_fpm'].mean():.0f} fpm",
                f"{filtered_df[filtered_df['vertical_rate'] < 0]['vertical_rate_fpm'].mean():.0f} fpm"
            ]
        }
        
        st.dataframe(
            pd.DataFrame(stats_data),
            use_container_width=True,
            hide_index=True
        )
    
    with col2:
        st.markdown("### 🏆 Records")
        
        # Vol le plus rapide
        fastest = filtered_df.loc[filtered_df['velocity_knots'].idxmax()]
        st.markdown(f"""
        <div class="stat-box">
            <h4>🚀 Vol le plus rapide</h4>
            <p><b>{fastest['callsign']}</b></p>
            <p>{fastest['velocity_knots']:.0f} knots</p>
            <p>({fastest['origin_country']})</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Vol le plus haut
        highest = filtered_df.loc[filtered_df['geo_altitude_ft'].idxmax()]
        st.markdown(f"""
        <div class="stat-box">
            <h4>⛰️ Vol le plus haut</h4>
            <p><b>{highest['callsign']}</b></p>
            <p>{highest['geo_altitude_ft']:.0f} ft</p>
            <p>({highest['origin_country']})</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Graphique temporel
    st.markdown("### 📈 Tendances")
    
    # Distribution par quadrant géographique
    filtered_df['quadrant'] = filtered_df.apply(lambda row: 
        f"{'N' if row['lat'] > 0 else 'S'}{' ' if row['lon'] > 0 else ' W'}", axis=1
    )
    
    quadrant_counts = filtered_df['quadrant'].value_counts()
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_quad = px.bar(
            x=quadrant_counts.index,
            y=quadrant_counts.values,
            title="Répartition géographique des vols",
            labels={'x': 'Quadrant', 'y': 'Nombre de vols'},
            color=quadrant_counts.values,
            color_continuous_scale='Blues'
        )
        fig_quad.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_quad, use_container_width=True)
    
    with col2:
        # Direction des vols
        heading_counts = filtered_df['heading'].value_counts()
        fig_heading = px.bar_polar(
            r=heading_counts.values,
            theta=heading_counts.index,
            title="Distribution des directions de vol",
            color=heading_counts.values,
            color_continuous_scale='Viridis'
        )
        fig_heading.update_layout(height=400)
        st.plotly_chart(fig_heading, use_container_width=True)
    
    # Matrice de corrélation
    st.markdown("### 🔬 Analyse de corrélation")
    
    numeric_cols = ['velocity_knots', 'geo_altitude_ft', 'vertical_rate', 'true_track']
    corr_df = filtered_df[numeric_cols].corr()
    
    fig_corr = px.imshow(
        corr_df,
        text_auto='.2f',
        title="Matrice de corrélation entre les variables",
        color_continuous_scale='RdBu_r',
        aspect='auto'
    )
    fig_corr.update_layout(height=400)
    st.plotly_chart(fig_corr, use_container_width=True)
    
    # Box plots comparatifs
    st.markdown("### 📦 Comparaisons par statut de vol")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_box_speed = px.box(
            filtered_df,
            x='status',
            y='velocity_knots',
            title="Vitesse par phase de vol",
            labels={'status': 'Phase de vol', 'velocity_knots': 'Vitesse (knots)'},
            color='status'
        )
        fig_box_speed.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_box_speed, use_container_width=True)
    
    with col2:
        fig_box_alt = px.box(
            filtered_df,
            x='status',
            y='geo_altitude_ft',
            title="Altitude par phase de vol",
            labels={'status': 'Phase de vol', 'geo_altitude_ft': 'Altitude (ft)'},
            color='status'
        )
        fig_box_alt.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_box_alt, use_container_width=True)

# ================================
# FOOTER
# ================================
st.divider()

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown("""
    **Flight Tracker Pro** - Application développée avec Streamlit  
    📡 Données en temps réel via [OpenSky Network API](https://opensky-network.org)  
    🔄 Dernière mise à jour: """ + (st.session_state.last_fetch.strftime('%H:%M:%S') if st.session_state.last_fetch else 'N/A'))

with col2:
    st.metric("⏱️ Temps de réponse", f"{st.session_state.fetch_count * 2} sec")

with col3:
    if st.button("ℹ️ À propos", use_container_width=True):
        st.info("""
        **Flight Tracker Pro v2.0**
        
        Fonctionnalités:
        • Suivi mondial en temps réel
        • Filtres avancés multi-critères
        • Analyses statistiques complètes
        • Visualisations interactives
        • Export de données CSV
        • Auto-refresh configurable
        
        Développé avec ❤️ pour les passionnés d'aviation
        """)

# ================================
# AUTO-REFRESH
# ================================
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()