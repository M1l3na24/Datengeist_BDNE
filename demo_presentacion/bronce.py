"""
bronce.py — Capa Bronce
Extrae 6 tablas de PostgreSQL y las guarda como Parquet en /tmp/
para que la capa Plata las pueda leer.

Ejecutar: python bronce.py
"""

import sys
import warnings
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

warnings.filterwarnings('ignore')

PG_CONN = 'postgresql+psycopg2://admin:cuyos123@127.0.0.1:5433/datengeist_demo'

SABORES_DEMO = [
    'Vainilla', 'Chocolate', 'Fresa', 'Mango', 'Limón',
    'Pistache', 'Nuez', 'Cajeta', 'Tamarindo', 'Coco']

N_CATS = 5

TMP = Path(__file__).parent / 'tmp'


def run_bronce():
    print('\n' + '*-' * 30)
    print(' BRONCE — Extrayendo desde PostgreSQL...')
    print('*-' * 30)

    TMP.mkdir(exist_ok=True)

    print('\n  Conectando a PostgreSQL...')
    engine = create_engine(PG_CONN, pool_pre_ping=True)

    print('\n  Leyendo tablas...')
    df_ventas    = pd.read_sql('SELECT * FROM ventas ORDER BY id_ticket',                engine)
    df_detalle   = pd.read_sql('SELECT * FROM detalle_ventas ORDER BY id_ticket',        engine)
    df_productos = pd.read_sql('SELECT * FROM dim_productos_y_sabores ORDER BY id_producto', engine)
    df_clientes  = pd.read_sql('SELECT * FROM dim_clientes_y_segmentos ORDER BY id_cliente', engine)
    df_clima     = pd.read_sql('SELECT * FROM variables_externas ORDER BY fecha',        engine)
    df_ops       = pd.read_sql('SELECT * FROM operaciones_y_personal ORDER BY fecha',    engine)

    # Normalizamos nombres de columnas a minusculas para consistencia
    for df in [df_ventas, df_detalle, df_productos, df_clientes, df_clima, df_ops]:
        df.columns = df.columns.str.lower()

    # Reconstruimos la columna sabor y rentabilidad 
    df_productos['sabor'] = df_productos['id_producto'].apply(
        lambda x: SABORES_DEMO[(int(x) - 1) // N_CATS])
    #   rentabilidad = (precio - costo) / precio
    df_productos['rentabilidad_pct'] = (
        (df_productos['precio_sug'] - df_productos['costo_prod_lt'])
        / df_productos['precio_sug']).round(4)

    tablas = [
        ('ventas',                   df_ventas),
        ('detalle_ventas',           df_detalle),
        ('dim_productos_y_sabores',  df_productos),
        ('dim_clientes_y_segmentos', df_clientes),
        ('variables_externas',       df_clima),
        ('operaciones_y_personal',   df_ops)]
    
    for nombre, df in tablas:
        print('     {:<28} {:>6,} filas'.format(nombre, len(df)))

    print('\n   Guardando DataFrames en /tmp/ ...')
    df_ventas.to_parquet(   TMP / 'bronce_ventas.parquet',    index=False)
    df_detalle.to_parquet(  TMP / 'bronce_detalle.parquet',   index=False)
    df_productos.to_parquet(TMP / 'bronce_productos.parquet', index=False)
    df_clientes.to_parquet( TMP / 'bronce_clientes.parquet',  index=False)
    df_clima.to_parquet(    TMP / 'bronce_clima.parquet',     index=False)
    df_ops.to_parquet(      TMP / 'bronce_ops.parquet',       index=False)

    engine.dispose()

    print('\n' + '*-' * 30)
    print('   BRONCE completado — 6 archivos guardados en /tmp/')
    print('  ⟶  Siguiente: python /plata.py')
    print('*-' * 30)


if __name__ == '__main__':
    run_bronce()
