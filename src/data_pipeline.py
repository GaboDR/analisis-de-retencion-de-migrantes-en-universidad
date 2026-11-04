import csv
import pandas as pd
import numpy as np
from src.config import (
    RAW_FUAS_DIR, RAW_MAT_DIR, INTERIM_DIR, PROCESSED_DIR,
    COHORTES, COLS_FUAS, COLS_MATRICULA, obtener_csv
)

def detectar_formato_csv(ruta):
    """Detecta automáticamente la codificación y el delimitador (';', ',' o '\t') del CSV."""
    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with open(ruta, "r", encoding=encoding) as f:
                primera_linea = f.readline()
            # Contar cuál separador aparece más veces en el encabezado
            conteos = {sep: primera_linea.count(sep) for sep in [";", ",", "\t", "|"]}
            mejor_sep = max(conteos, key=conteos.get)
            if conteos[mejor_sep] > 0:
                return encoding, mejor_sep
        except UnicodeDecodeError:
            continue
    return "latin-1", ";"

def normalizar_nombre_col(col: str) -> str:
    """Limpia espacios, comillas, caracteres invisibles (BOM) y homologa Ñ/AÑO."""
    limpia = col.strip().strip('"').strip("'").upper()
    limpia = limpia.replace("AÑO_", "ANIO_").replace("ÑO", "NIO")
    return limpia

def leer_csv_mineduc(ruta, columnas_deseadas):
    """Lee solo las columnas disponibles en el CSV detectando separador y codificación."""
    encoding, sep = detectar_formato_csv(ruta)
    header = pd.read_csv(ruta, sep=sep, nrows=0, encoding=encoding)
    
    mapa_cols = {col: normalizar_nombre_col(col) for col in header.columns}
    cols_presentes = [col_orig for col_orig, col_up in mapa_cols.items() if col_up in columnas_deseadas]
    
    if not cols_presentes or "MRUN" not in [mapa_cols[c] for c in cols_presentes]:
        raise KeyError(
            f"\nNo se encontró 'MRUN' en {ruta.name} (sep='{sep}', encoding='{encoding}').\n"
            f"Columnas detectadas en el archivo: {list(mapa_cols.values())[:15]}"
        )
        
    df = pd.read_csv(
        ruta, sep=sep, usecols=cols_presentes, 
        encoding=encoding, low_memory=False
    )
    df.rename(columns=mapa_cols, inplace=True)
    return df

def limpiar_numerico(serie: pd.Series) -> pd.Series:
    """Convierte strings con coma decimal o espacios a float."""
    if serie.dtype == object or pd.api.types.is_string_dtype(serie):
        serie = serie.astype(str).str.replace(",", ".", regex=False).str.strip()
    return pd.to_numeric(serie, errors="coerce")

def procesar_cohorte(anio_t: int) -> pd.DataFrame:
    anio_t1 = anio_t + 1
    print(f"\n--- Procesando Cohorte {anio_t} (Seguimiento en {anio_t1}) ---")
    
    ruta_fuas = obtener_csv(RAW_FUAS_DIR, "Postulaciones-a-Becas-y-Creditos", anio_t)
    ruta_mat_t = obtener_csv(RAW_MAT_DIR, "Matricula-Ed-Superior", anio_t)
    ruta_mat_t1 = obtener_csv(RAW_MAT_DIR, "Matricula-Ed-Superior", anio_t1)
    
    # 1. Cargar Matrícula año t y filtrar mechones de Pregrado
    mat_t = leer_csv_mineduc(ruta_mat_t, COLS_MATRICULA)
    mat_t["MRUN"] = limpiar_numerico(mat_t["MRUN"])
    mat_t["ANIO_ING_CARR_ORI"] = limpiar_numerico(mat_t["ANIO_ING_CARR_ORI"])
    mat_t["DUR_TOTAL_CARR"] = limpiar_numerico(mat_t["DUR_TOTAL_CARR"])
    
    cond_mechon = mat_t["ANIO_ING_CARR_ORI"] == anio_t
    cond_pregrado = mat_t["NIVEL_GLOBAL"].astype(str).str.upper().str.strip() == "PREGRADO"
    cond_duracion = mat_t["DUR_TOTAL_CARR"] > 2
    
    cohorte_t = mat_t[cond_mechon & cond_pregrado & cond_duracion].copy()
    cohorte_t.dropna(subset=["MRUN"], inplace=True)
    cohorte_t["MRUN"] = cohorte_t["MRUN"].astype(np.int64)
    
    # Deduplicar MRUN priorizando carrera de mayor duración formal
    cohorte_t.sort_values(by=["MRUN", "DUR_TOTAL_CARR"], ascending=[True, False], inplace=True)
    cohorte_t.drop_duplicates(subset=["MRUN"], keep="first", inplace=True)
    cohorte_t.drop(columns=["NIVEL_GLOBAL", "ANIO_ING_CARR_ORI"], inplace=True)
    print(f"Estudiantes 1er año Pregrado ({anio_t}): {len(cohorte_t):,}")

    # 2. Cargar FUAS año t
    fuas_t = leer_csv_mineduc(ruta_fuas, COLS_FUAS)
    fuas_t["MRUN"] = limpiar_numerico(fuas_t["MRUN"])
    fuas_t["NACIONALIDAD"] = limpiar_numerico(fuas_t["NACIONALIDAD"])
    fuas_t.dropna(subset=["MRUN", "NACIONALIDAD"], inplace=True)
    fuas_t["MRUN"] = fuas_t["MRUN"].astype(np.int64)
    fuas_t["NACIONALIDAD"] = fuas_t["NACIONALIDAD"].astype(int)
    
    if "NEM" in fuas_t.columns:
        fuas_t["NEM"] = limpiar_numerico(fuas_t["NEM"])
        
    fuas_t.drop_duplicates(subset=["MRUN"], keep="first", inplace=True)
    
    # 3. Inner Merge: Matrícula t + FUAS t
    df_cohorte = pd.merge(cohorte_t, fuas_t, on="MRUN", how="inner")
    print(f"Cruce efectivo Matrícula + FUAS ({anio_t}): {len(df_cohorte):,}")

    # 4. Cargar Matrícula año t+1 (solo MRUN y CODIGO_UNICO para ahorrar RAM)
    mat_t1 = leer_csv_mineduc(ruta_mat_t1, ["MRUN", "CODIGO_UNICO"])
    mat_t1["MRUN"] = limpiar_numerico(mat_t1["MRUN"])
    mat_t1.dropna(subset=["MRUN"], inplace=True)
    mat_t1["MRUN"] = mat_t1["MRUN"].astype(np.int64)
    
    # A) Permanencia en la misma carrera (MRUN + CODIGO_UNICO)
    pares_t1 = set(zip(mat_t1["MRUN"], mat_t1["CODIGO_UNICO"].astype(str).str.strip()))
    pares_t = zip(df_cohorte["MRUN"], df_cohorte["CODIGO_UNICO"].astype(str).str.strip())
    df_cohorte["PERMANECE_CARRERA"] = [1 if par in pares_t1 else 0 for par in pares_t]
    
    # B) Permanencia en el sistema de Educación Superior (cualquier carrera en t+1)
    mruns_t1 = set(mat_t1["MRUN"].unique())
    df_cohorte["PERMANECE_SISTEMA"] = df_cohorte["MRUN"].isin(mruns_t1).astype(int)
    
    # 5. Variables analíticas limpias
    for col_num in ["VALOR_ARANCEL", "VALOR_MATRICULA", "ACRE_INST_ANIO"]:
        if col_num in df_cohorte.columns:
            df_cohorte[col_num] = limpiar_numerico(df_cohorte[col_num]).fillna(0)
            
    df_cohorte["ES_EXTRANJERO"] = (df_cohorte["NACIONALIDAD"] == 1).astype(int)
    df_cohorte["ANIO_COHORTE"] = anio_t
    
    # Guardar respaldo intermedio por año
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df_cohorte.to_parquet(INTERIM_DIR / f"cohorte_{anio_t}.parquet", index=False)
    return df_cohorte

def construir_dataset_maestro():
    lista_cohortes = [procesar_cohorte(anio) for anio in COHORTES]
    df_maestro = pd.concat(lista_cohortes, ignore_index=True)
    
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ruta_salida = PROCESSED_DIR / "dataset_maestro_permanencia.parquet"
    df_maestro.to_parquet(ruta_salida, index=False)
    print(f"\nDataset maestro guardado en: {ruta_salida}")
    print(f"Total filas: {len(df_maestro):,} | Extranjeros: {df_maestro['ES_EXTRANJERO'].sum():,}")
    return df_maestro

if __name__ == "__main__":
    construir_dataset_maestro()