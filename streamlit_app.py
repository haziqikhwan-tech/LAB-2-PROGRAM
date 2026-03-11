import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from pyproj import Transformer
import json
from folium.plugins import Fullscreen, MousePosition

# --- TETAPAN ASAS HALAMAN ---
st.set_page_config(page_title="LOT GEOMATIK PUO", layout="wide")

# --- DATABASE PENGGUNA (SIMULASI) ---
if "user_db" not in st.session_state:
    st.session_state["user_db"] = {
        "01dgu24f1061": {"nama": "Acap", "pwd": "123"},
        "01dgu24f1058": {"nama": "Haziq", "pwd": "123"},
        "01dgu24f1050": {"nama": "Norul", "pwd": "123"}
    }

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# --- FUNGSI PEMBANTU ---
def decimal_to_dms(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    s = int(round((deg - d - m/60) * 3600))
    if s >= 60: s = 0; m += 1
    if m >= 60: m = 0; d += 1
    return f"{d}°{m:02d}'{s:02d}\""

# --- PENGURUSAN LOGIN ---
if not st.session_state["logged_in"]:
    if st.session_state.get("reset_mode", False):
        st.markdown("### 🔑 Set Semula Kata Laluan")
        uid = st.text_input("ID untuk set semula")
        new_pwd = st.text_input("Kata Laluan Baru", type="password")
        if st.button("Simpan"):
            if uid in st.session_state["user_db"]:
                st.session_state["user_db"][uid]["pwd"] = new_pwd
                st.success("Berjaya! Sila log masuk.")
                st.session_state["reset_mode"] = False
                st.rerun()
        if st.button("Batal"):
            st.session_state["reset_mode"] = False
            st.rerun()
    else:
        col_l, col_m, col_r = st.columns([1, 1, 1])
        with col_m:
            st.markdown("<h2 style='text-align:center;'>🔐 Sistem Survey Lot PUO</h2>", unsafe_allow_html=True)
            user_id = st.text_input("ID Pengguna")
            user_pwd = st.text_input("Kata Laluan", type="password")
            if st.button("Masuk", use_container_width=True):
                db = st.session_state["user_db"]
                if user_id in db and db[user_id]["pwd"] == user_pwd:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = user_id
                    st.session_state["user_name"] = db[user_id]["nama"]
                    st.rerun()
                else: st.error("ID/Password Salah")
            if st.button("Lupa Kata Laluan?"):
                st.session_state["reset_mode"] = True
                st.rerun()
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    try:
        st.image("LOGO PUO.png", use_container_width=True)
    except:
        st.warning("⚠️ Logo tidak dijumpai.")
    
    st.markdown(f"<h3 style='text-align:center;'>👋 Hi, {st.session_state['user_name']}</h3>", unsafe_allow_html=True)
    st.divider()

    uploaded_file = st.file_uploader("📂 Upload CSV (STN, E, N)", type=["csv"])
    
    st.header("👁️ Kawalan Paparan")
    show_satellite = st.toggle("Imej Satelit (Google)", value=True)
    show_points = st.checkbox("Paparkan Titik Stesen", value=True)
    show_stn = st.checkbox("Paparkan No Stesen", value=True)
    show_brg = st.checkbox("Paparkan Bearing/Jarak", value=True)
    show_poly = st.checkbox("Paparkan Poligon", value=True)

    st.header("🎨 Gaya Visual")
    p_color = st.color_picker("Warna Sempadan", "#00FFFF")
    f_color = st.color_picker("Warna Isi", "#00FFFF")
    f_opac = st.slider("Kepekatan Isi", 0.0, 1.0, 0.3)

    st.header("🛠️ Tetapan Teknikal")
    size_stn = st.slider("Saiz No Stesen", 8, 30, 14)
    size_brg = st.slider("Saiz Bearing/Jarak", 6, 25, 10)
    epsg_input = st.text_input("Kod EPSG (RSO: 4390)", "4390")

    st.divider()
    if st.button("🚪 Log Keluar", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()

# --- HEADER UTAMA ---
st.markdown("<h1 style='text-align:center;'>POLITEKNIK UNGKU OMAR</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align:center; color:#555;'>Unit Geomatik - Sistem Visualisasi & Eksport GIS</h3>", unsafe_allow_html=True)
st.divider()

# --- LOGIK PEMPROSESAN ---
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.strip().str.upper()
        
        # Transformasi Koordinat (RSO ke WGS84)
        transformer = Transformer.from_crs(f"EPSG:{epsg_input}", "EPSG:4326", always_xy=True)
        df['lon'], df['lat'] = transformer.transform(df['E'].values, df['N'].values)
        
        center_lat, center_lon = df['lat'].mean(), df['lon'].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=19, max_zoom=22, tiles=None)
        
        # Paparan Peta Website
        if show_satellite:
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                attr='Google Satellite', name='Google Satellite', max_zoom=22, max_native_zoom=20
            ).add_to(m)
        else:
            folium.TileLayer('OpenStreetMap').add_to(m)
        
        Fullscreen(position="topright").add_to(m)
        MousePosition().add_to(m)

        features_for_geojson = []
        points_list = []
        total_dist = 0

        # Loop Pemprosesan
        for i in range(len(df)):
            p1 = df.iloc[i]
            p2 = df.iloc[(i + 1) % len(df)]
            loc1, loc2 = [p1['lat'], p1['lon']], [p2['lat'], p2['lon']]
            points_list.append(loc1)

            # Kira Bearing & Jarak
            dE, dN = p2['E'] - p1['E'], p2['N'] - p1['N']
            dist = np.sqrt(dE**2 + dN**2)
            total_dist += dist
            brg = np.degrees(np.arctan2(dE, dN)) % 360
            
            # GeoJSON (LINE)
            features_for_geojson.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[p1['lon'], p1['lat']], [p2['lon'], p2['lat']]]
                },
                "properties": {
                    "Info": "Sempadan Lot",
                    "Dari_Stn": int(p1['STN']),
                    "Ke_Stn": int(p2['STN']),
                    "Bearing": decimal_to_dms(brg),
                    "Jarak_m": round(dist, 3)
                }
            })

            # GeoJSON (POINT)
            features_for_geojson.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p1['lon'], p1['lat']]},
                "properties": {
                    "Stesen": int(p1['STN']), 
                    "N_RSO": round(p1['N'], 3), 
                    "E_RSO": round(p1['E'], 3)
                }
            })

            # Visual Website
            if show_points:
                stn_info = f"<b>STESEN {int(p1['STN'])}</b><hr>N: {p1['N']:.3f}<br>E: {p1['E']:.3f}"
                folium.CircleMarker(
                    location=loc1, radius=6, color='red', fill=True, fill_color='yellow',
                    popup=folium.Popup(stn_info, max_width=150),
                    tooltip=f"Klik untuk koordinat Stesen {int(p1['STN'])}"
                ).add_to(m)

            if show_stn:
                stn_txt = f'<div style="color:white; font-weight:bold; font-size:{size_stn}pt; text-shadow: 2px 2px 3px black; pointer-events:none;">{int(p1["STN"])}</div>'
                folium.Marker(loc1, icon=folium.DivIcon(html=stn_txt, icon_anchor=(-10, 10))).add_to(m)

            if show_brg:
                calc_angle = brg - 90
                if 90 < brg < 270: calc_angle -= 180 
                l_html = f'<div style="transform: rotate({calc_angle}deg); color:#00FFFF; font-size:{size_brg}pt; font-weight:bold; text-shadow: 2px 2px 4px black; text-align:center; width:120px; margin-left:-60px;">{decimal_to_dms(brg)}<br><span style="color:#FFD700;">{dist:.3f}m</span></div>'
                folium.Marker([(p1['lat']+p2['lat'])/2, (p1['lon']+p2['lon'])/2], icon=folium.DivIcon(html=l_html)).add_to(m)

        # 4. KIRA LUAS & PERIMETER
        area_m2 = 0.5 * np.abs(np.dot(df['E'], np.roll(df['N'], 1)) - np.dot(df['N'], np.roll(df['E'], 1)))
        area_acre = area_m2 * 0.000247105
        
        poly_coords = [[ [p['lon'], p['lat']] for _, p in df.iterrows() ]]
        poly_coords[0].append([df.iloc[0]['lon'], df.iloc[0]['lat']])

        # Masukkan perimeter ke dalam GeoJSON poligon
        features_for_geojson.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": poly_coords},
            "properties": {
                "Info": "Maklumat Lot",
                "Luas_m2": round(area_m2, 2),
                "Luas_Ekar": round(area_acre, 3),
                "Perimeter_m": round(total_dist, 2)
            }
        })

        if show_poly:
            # Popup poligon dengan Perimeter
            poly_popup = f"""
            <div style='font-family: sans-serif; min-width: 150px;'>
            <b style='color: #2c3e50;'>ANALISIS LOT</b><hr>
            <b>Luas:</b> {area_m2:.2f} m²<br>
            <b>Luas:</b> {area_acre:.3f} Ekar<br>
            <b>Perimeter:</b> {total_dist:.3f} m
            </div>
            """
            folium.Polygon(
                locations=points_list, color=p_color, weight=3,
                fill=True, fill_color=f_color, fill_opacity=f_opac,
                popup=folium.Popup(poly_popup, max_width=250)
            ).add_to(m)

        # Sidebar Analysis
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Keputusan Analisis")
        st.sidebar.metric("Luas (m²)", f"{area_m2:.2f}")
        st.sidebar.metric("Luas (Ekar)", f"{area_acre:.4f}")
        st.sidebar.metric("Perimeter (m)", f"{total_dist:.2f}")
        
        geojson_final = {"type": "FeatureCollection", "features": features_for_geojson}
        st.sidebar.download_button("📥 Export GeoJSON (Data Lengkap)", json.dumps(geojson_final, indent=4), "lot_geomatik_puo.geojson", "application/json", use_container_width=True)

        st_folium(m, width="100%", height=700, returned_objects=[])

    except Exception as e:
        st.error(f"Ralat Pemprosesan: {e}")
else:
    st.info("Sila muat naik fail CSV untuk memulakan visualisasi.")
