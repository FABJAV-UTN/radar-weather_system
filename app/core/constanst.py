"""Constantes hidrometeorológicas del modelo Soria (2024)."""

# Relación Z-R Marshall-Palmer (sección 3.1)
Z_R_A = 200.0           # Coeficiente a
Z_R_B = 1.6             # Exponente b
Z_R_INVERSE_B = 1 / Z_R_B  # 0.625 para calcular R = (Z/a)^(1/b)

# Corrección local San Rafael (sección 3.1.1)
LOCAL_CORRECTION_FACTOR = 0.8  # Factor multiplicativo hasta calibración propia

# Valores de referencia para Componente Atmosférica A (sección 2.1, Tabla p.3)
I_REF = 40.0            # mm/h - Umbral tormenta severa semiárido
D_REF = 1.0             # h - Duración característica convectiva
P_REF = 25.0            # mm - Precipitación acumulada escorrentía rápida
T_RES_REF = 0.5         # h - Persistencia espacial núcleo convectivo

# Umbrales de erosividad (sección 3.3)
I30_THRESHOLD_LOW = 76.0  # mm/h - Límite régimen energía cinética
E_UNIT_HIGH = 0.283     # MJ·ha⁻¹·mm⁻¹ - Energía cinética unitaria (I > 76)

# Metadatos radar DACC (sección 4, p.7)
RADAR_TEMPORAL_RESOLUTION_MIN = 4   # minutos
RADAR_SPATIAL_RESOLUTION_M = 900    # 900m x 900m por celda
EPSG_CODE = 5346                    # POSGAR 2007 / Argentina Zone 4

# Área focal San Rafael (p.7)
AREA_FOCAL_BOUNDS = {
    "lat_min": -34.845250,
    "lat_max": -34.607013,
    "lon_min": -68.865279,
    "lon_max": -68.580237,
}