# ✈️ Flight Tracker Pro

### Real-Time Global Flight Tracking • OpenSky Network API • Streamlit • Plotly

**Flight Tracker Pro** is a full-featured Streamlit application that visualizes, analyzes, and tracks real-time commercial flights around the world using the **OpenSky Network API**.

It includes: an interactive world map, advanced analytics, detailed flight lists, filtering tools, auto-refresh, statistics dashboards, and CSV export.

---

## 🚀 Key Features

### 🗺️ **Real-Time Interactive Map**

* Live global flight visualization
* Region presets (Europe, USA, Asia, France, etc.)
* Color-coded markers based on flight phase (climb, descent, cruise, ground)
* Hover popups with full flight details (callsign, altitude, speed, heading, country)

### 📊 **Advanced Analytics**

* Altitude & speed histograms
* Altitude–speed heatmap
* Country distribution charts
* Full statistical summary (means, medians, max values)

### 📋 **Flight List Dashboard**

* Sorting (speed, altitude, callsign, country)
* Pagination
* Styled columns (progress bars, formatters)
* CSV export

### 🔍 **Flight Search**

* Search by callsign (e.g., AFR447)
* Detailed flight information + mini-map
* ICAO24, country, altitude, speed, vertical rate, direction

### 🌐 **Global Statistics**

* Correlation matrix
* Box plots by flight status
* Geographical quadrant distribution
* Polar chart showing heading distribution

### ⚙️ **Display Settings & Controls**

* Altitude filter
* Speed filter
* Country filter
* Option to include/exclude grounded aircraft
* Auto-refresh (15–120 sec)
* Token expiration tracking
* API request counter

---

## 🛠️ Installation

### 1️⃣ Clone the repository

```bash
git clone git@github.com:anessrb/OpenSkyDashboard.git
cd OpenSkyDashboard
```

### 2️⃣ Create your virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3️⃣ Launch the application

```bash
streamlit run app.py
```

---

## 🔑 API Configuration – OpenSky OAuth2

The app uses OAuth2 `client_credentials`.

In `app.py`, replace with your credentials:

```python
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
```

Token endpoint:

```
POST https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token
```

---

## 🧩 Technologies Used

| Technology              | Purpose                         |
| ----------------------- | ------------------------------- |
| **Streamlit**           | Fast, interactive web interface |
| **Plotly**              | Interactive visualizations      |
| **Pandas**              | Data processing                 |
| **OpenSky Network API** | Real-time flight data           |
| **Python**              | Backend logic                   |

---

## 📚 Project Structure

```
📁 OpenSkyDashboard
│── app.py                # Main application
│── requirements.txt      # Python dependencies
│── logo.png              # Sidebar branding
│── README.md             # Documentation
```

---

## 🖼️ Screenshots (Optional)

You can add screenshots here, such as:

* 🌍 Real-time world map
* 📊 Speed & altitude distributions
* 🔍 Flight details panel
* 📋 Flight list table

---

## 👨‍💻 Author

**Aness Rabia**

**Georgios Stephanou**



