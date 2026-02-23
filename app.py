import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import io 

# Configuración de página
st.set_page_config(page_title="Mapa Logístico - Análisis de Clientes", layout="wide")
st.title("🗺️ Mapa Interactivo: Análisis de Cobertura y Días de Entrega")

@st.cache_data
def load_data(file):
    return pd.read_excel(file)

# --- NUEVO: Template de la Base de Datos Principal ---
st.sidebar.header("📥 1. Formato de Base de Datos")
st.sidebar.write("Descarga esta plantilla para ver cómo estructurar tus datos antes de subirlos:")

# Creamos una fila de ejemplo real para guiar al usuario
template_main_data = {
    'CD': [95],
    'CODCLI': [922245],
    'X': [-63.683707],
    'Y': [-22.052948],
    'LU': [1],
    'MA': [1],
    'MI': [0],
    'JU': [0],
    'VI': [1],
    'SA': [0]
}
df_template_main = pd.DataFrame(template_main_data)

buffer_main = io.BytesIO()
with pd.ExcelWriter(buffer_main, engine='openpyxl') as writer:
    df_template_main.to_excel(writer, index=False, sheet_name='Base_Datos')

st.sidebar.download_button(
    label="⬇️ Descargar Plantilla Base",
    data=buffer_main.getvalue(),
    file_name="template_base_clientes.xlsx",
    mime="application/vnd.ms-excel",
    help="Contiene los encabezados correctos y un ejemplo de cómo llenar las coordenadas."
)

st.sidebar.markdown("---")

# --- CARGA DEL ARCHIVO ---
st.sidebar.header("📤 2. Sube tu Base de Datos")
uploaded_file = st.sidebar.file_uploader("Carga el archivo Excel aquí", type=["xlsx", "xls"])

if uploaded_file:
    df = load_data(uploaded_file)
    
    # Limpiar y convertir coordenadas a números
    if 'X' in df.columns and 'Y' in df.columns:
        df['X'] = pd.to_numeric(df['X'].astype(str).str.replace(',', '.'), errors='coerce')
        df['Y'] = pd.to_numeric(df['Y'].astype(str).str.replace(',', '.'), errors='coerce')
    
    st.sidebar.markdown("---")
    st.sidebar.header("3. Filtros Generales")
    
    # Filtro por CD
    lista_cd = df['CD'].dropna().unique().tolist()
    selected_cd = st.sidebar.selectbox("Selecciona el CD", lista_cd)
    
    # Filtro por Día
    dias = ['LU', 'MA', 'MI', 'JU', 'VI', 'SA']
    selected_day = st.sidebar.selectbox("Selecciona el Día a analizar", dias)
    
    # Filtramos por CD y eliminamos coordenadas inválidas
    df_cd = df[df['CD'] == selected_cd].copy()
    df_cd = df_cd.dropna(subset=['X', 'Y']) 
    
    if df_cd.empty:
        st.warning(f"No hay clientes con coordenadas válidas para el CD {selected_cd}.")
    else:
        st.sidebar.markdown("---")
        st.sidebar.header("4. Búsqueda de Clientes")
        search_type = st.sidebar.radio("Modalidad de búsqueda", ["Individual", "Masiva (Excel)"])
        
        target_clients = []
        
        if search_type == "Individual":
            cod_input = st.sidebar.text_input("Ingresa el CODCLI")
            if cod_input:
                try:
                    target_clients.append(int(cod_input))
                except ValueError:
                    st.sidebar.error("El CODCLI debe ser numérico.")
        else:
            # Template para búsqueda masiva
            template_df = pd.DataFrame(columns=['CODCLI'])
            buffer_mass = io.BytesIO()
            with pd.ExcelWriter(buffer_mass, engine='openpyxl') as writer:
                template_df.to_excel(writer, index=False, sheet_name='Template')
            
            st.sidebar.download_button(
                label="⬇️ Descargar Template de Búsqueda",
                data=buffer_mass.getvalue(),
                file_name="template_busqueda_masiva.xlsx",
                mime="application/vnd.ms-excel"
            )
            
            mass_file = st.sidebar.file_uploader("Sube tu template completado", type=["xlsx", "xls"], key="mass")
            if mass_file:
                df_mass = load_data(mass_file)
                if 'CODCLI' in df_mass.columns:
                    target_clients = df_mass['CODCLI'].dropna().astype(int).tolist()
                else:
                    st.sidebar.error("El archivo masivo debe tener una columna llamada 'CODCLI'.")

        # Crear mapa base
        cd_lat = df_cd['Y'].mean()
        cd_lon = df_cd['X'].mean()
        m = folium.Map(location=[cd_lat, cd_lon], zoom_start=12)
        resultados = []

        if target_clients:
            targets_df = df_cd[df_cd['CODCLI'].isin(target_clients)]
            
            if not targets_df.empty:
                m.location = [targets_df['Y'].mean(), targets_df['X'].mean()]
                m.zoom_start = 14
                
                for _, target in targets_df.iterrows():
                    t_lat = target['Y']
                    t_lon = target['X']
                    t_cod = target['CODCLI']
                    
                    folium.Marker(
                        location=[t_lat, t_lon],
                        popup=f"<b>Centro CODCLI:</b> {t_cod}",
                        icon=folium.Icon(color="red", icon="info-sign")
                    ).add_to(m)
                    
                    folium.Circle(
                        location=[t_lat, t_lon],
                        radius=1000,
                        color='blue',
                        fill=True,
                        fill_opacity=0.15
                    ).add_to(m)
                    
                    df_cd['Distancia_km'] = df_cd.apply(
                        lambda row: geodesic((t_lat, t_lon), (row['Y'], row['X'])).km, axis=1
                    )
                    
                    clientes_radio = df_cd[(df_cd['Distancia_km'] <= 1) & (df_cd[selected_day] == 1)]
                    
                    resultados.append({
                        "CODCLI Buscado": t_cod,
                        f"Clientes Free ({selected_day}) a <1km": len(clientes_radio)
                    })
                    
                    for _, cliente in clientes_radio.iterrows():
                        if cliente['CODCLI'] != t_cod: 
                            folium.CircleMarker(
                                location=[cliente['Y'], cliente['X']],
                                radius=5,
                                popup=f"CODCLI: {cliente['CODCLI']}<br>Día {selected_day}: Free",
                                color="green",
                                fill=True,
                                fill_color="green"
                            ).add_to(m)
            else:
                st.warning("Los códigos de cliente buscados no existen o no tienen coordenadas válidas.")
        else:
            st.info("Vista general del CD cargada. Ingresa un CODCLI en la barra lateral para ver el análisis de radio.")

        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader(f"Mapa del CD: {selected_cd}")
            st_folium(m, width=800, height=500)
            
        with col2:
            st.subheader("Resumen de Impacto")
            if resultados:
                df_resultados = pd.DataFrame(resultados)
                st.dataframe(df_resultados, use_container_width=True)
            else:
                st.write("Esperando parámetros de búsqueda...")
else:
    st.info("👈 Por favor, carga tu archivo de datos en la barra lateral para comenzar.")
