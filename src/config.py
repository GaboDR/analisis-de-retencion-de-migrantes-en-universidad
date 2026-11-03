from pathlib import Path

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Rutas de datos
RAW_FUAS_DIR = BASE_DIR / "datasets" / "raw" / "fuas"
RAW_MAT_DIR = BASE_DIR / "datasets" / "raw" / "matricula"
INTERIM_DIR = BASE_DIR / "datasets" / "interim"
PROCESSED_DIR = BASE_DIR / "datasets" / "processed"

# Cohortes a procesar (Ingreso en t -> Seguimiento en t+1)
COHORTES = [2022, 2023, 2024, 2025]

# Columnas a extraer según esquemas oficiales SIES / MINEDUC
COLS_FUAS = [
    "MRUN", "NACIONALIDAD", "NEM", "COD_DEPE", 
    "EDAD", "GENERO", "ETNIA", "DECIL_SE4", "QUINTIL_SE4"
]

COLS_MATRICULA = [
    "MRUN", "CODIGO_UNICO", "ANIO_ING_CARR_ORI", "NIVEL_GLOBAL",
    "NIVEL_CARRERA_2", "GEN_ALU", "RANGO_EDAD", "TIPO_INST_1", 
    "TIPO_INST_2", "TIPO_INST_3", "MODALIDAD", "JORNADA", 
    "AREA_CONOCIMIENTO", "DUR_TOTAL_CARR", "FORMATO_VALORES",
    "VALOR_ARANCEL", "VALOR_MATRICULA", "ACREDITADA_CARR", 
    "ACREDITADA_INST", "ACRE_INST_ANIO", "REGION_SEDE", "FORMA_DE_INGRESO"
]

def obtener_csv(directorio_base: Path, prefijo_carpeta: str, anio: int) -> Path:
    """Busca automáticamente el archivo CSV dentro de la carpeta del año correspondiente."""
    carpeta = directorio_base / f"{prefijo_carpeta}-{anio}"
    archivos = list(carpeta.glob("*.csv")) + list(carpeta.glob("*.CSV"))
    if not archivos:
        raise FileNotFoundError(f"No se encontró ningún CSV en: {carpeta}")
    return archivos[0]