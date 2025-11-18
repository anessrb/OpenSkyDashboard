import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

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

# Style CSS moderne
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stat-box {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
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
            timeout=10
        )
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in', 1800)
        
        st.session_state.access_token = access_token
        st.session_state.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
        
        return access_token, None
    except Exception as e:
        return None, str(e)

# ================================
# FONCTIONS API
# ================================
def fetch_flights(bbox, include_ground=False):
    """Récupérer les vols en temps réel"""
    token, error = get_oauth_token()
    if error:
        return None, f"Erreur d'authentification: {error}"
    
    params = {
        'lamin': bbox[0],
        'lomin': bbox[2],
        'lamax': bbox[1],
        'lomax': bbox[3]
    }
    
    try:
        response = requests.get(
            OPENSKY_BASE_URL,
            params=params,
            headers={'Authorization': f'Bearer {token}'},
            timeout=15
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
    if st.session_state.flights_data is not None:
        countries = ['Tous'] + sorted(st.session_state.flights_data['origin_country'].unique().tolist())
        selected_country = st.selectbox("Pays d'origine", countries)
    else:
        selected_country = 'Tous'
    
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
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️ Carte Interactive",
    "📊 Analyses",
    "📋 Liste des Vols",
    "🔍 Détails Vol",
    "🌐 Statistiques Globales"
])

# ============ ONGLET 1: CARTE ============
with tab1:
    st.subheader("🗺️ Carte des vols en temps réel")
    
    if not filtered_df.empty:
        # Créer la carte avec Plotly
        fig = go.Figure()
        
        # Ajouter les vols
        for status in filtered_df['status'].unique():
            df_status = filtered_df[filtered_df['status'] == status]
            
            fig.add_trace(go.Scattergeo(
                lon=df_status['lon'],
                lat=df_status['lat'],
                text=df_status.apply(lambda row: 
                    f"<b>{row['callsign']}</b><br>" +
                    f"Pays: {row['origin_country']}<br>" +
                    f"Altitude: {row['geo_altitude_ft']:.0f} ft<br>" +
                    f"Vitesse: {row['velocity_knots']:.0f} kts<br>" +
                    f"Direction: {row['heading']}<br>" +
                    f"Statut: {row['status']}", axis=1
                ),
                mode='markers',
                name=status,
                marker=dict(
                    size=8,
                    opacity=0.8,
                    line=dict(width=1, color='white')
                ),
                hovertemplate='%{text}<extra></extra>'
            ))
        
        fig.update_geos(
            projection_type="natural earth",
            showland=True,
            landcolor="rgb(243, 243, 243)",
            coastlinecolor="rgb(204, 204, 204)",
            showocean=True,
            oceancolor="rgb(230, 245, 255)",
            showcountries=True,
            countrycolor="rgb(204, 204, 204)"
        )
        
        fig.update_layout(
            height=600,
            margin={"r":0,"t":30,"l":0,"b":0},
            title=f"📍 {len(filtered_df)} vols actifs dans {selected_region}"
        )
        
        st.plotly_chart(fig, use_container_width=True)
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

# ============ ONGLET 3: LISTE DES VOLS ============
with tab3:
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

# ============ ONGLET 4: DÉTAILS VOL ============
with tab4:
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

# ============ ONGLET 5: STATS GLOBALES ============
with tab5:
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