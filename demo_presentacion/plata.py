"""
plata.py — Capa Plata
Lee los Parquet de Bronce (.../tmp/), desnormaliza y enriquece,
guarda ventas_completas, catalogo_productos y clientes_perfil en MongoDB,
y persiste ventas_enriquecidas.parquet para que la capa Oro lo lea.

Ejecutar: python plata.py
Requiere haber corrido antes: python bronce.py
"""

import sys
import warnings
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

warnings.filterwarnings('ignore')

MONGO_URI = 'mongodb://admin:cuyos123@localhost:27017/?authSource=admin'
MONGO_DB  = 'datengeist_demo'

DIAS      = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
MESES_NOM = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

TMP = Path(__file__).parent / 'tmp'

BRONCE_FILES = [
    'bronce_ventas.parquet',
    'bronce_detalle.parquet',
    'bronce_productos.parquet',
    'bronce_clientes.parquet',
    'bronce_clima.parquet',
    'bronce_ops.parquet']


def _check_bronce():
    faltantes = [f for f in BRONCE_FILES if not (TMP / f).exists()]
    if faltantes:
        print('\n    ERROR: La capa Bronce aún no ha corrido.')
        print('  ⟶  Ejecuta primero: python /bronce.py')
        print('  Archivos faltantes en /tmp/:')
        for f in faltantes:
            print(f'      • {f}')
        sys.exit(1)


def run_plata():
    print('\n' + '*-' * 30)
    print('   PLATA — Transformando documentos...')
    print('*-' * 30)

    _check_bronce()

    print('\n   Cargando datos de Bronce desde /tmp/ ...')
    df_ventas    = pd.read_parquet(TMP / 'bronce_ventas.parquet')
    df_detalle   = pd.read_parquet(TMP / 'bronce_detalle.parquet')
    df_productos = pd.read_parquet(TMP / 'bronce_productos.parquet')
    df_clientes  = pd.read_parquet(TMP / 'bronce_clientes.parquet')
    df_clima     = pd.read_parquet(TMP / 'bronce_clima.parquet')

    mongo = MongoClient(MONGO_URI)[MONGO_DB]

    def upsert(nombre, docs):
        col = mongo[nombre]
        col.delete_many({})
        if docs:
            col.insert_many(docs)
        print('      {:<30} {:>6,} docs'.format(nombre, len(docs)))

    # Ventas_completas 
    print('\n  Construyendo ventas_completas...')
    df_v = df_ventas.copy()
    # Descomponemos el timestamp en columnas utiles: anio, mes,    
    # nombre del mes, semana, dia de la semana, nombre del dia y hora
    df_v['timestamp']  = pd.to_datetime(df_v['timestamp'])
    df_v['fecha']      = df_v['timestamp'].dt.date.astype(str)
    df_v['anio']       = df_v['timestamp'].dt.year.astype(int)
    df_v['mes']        = df_v['timestamp'].dt.month.astype(int)
    df_v['mes_nombre'] = df_v['mes'].map(lambda m: MESES_NOM[m])
    df_v['semana']     = df_v['timestamp'].dt.isocalendar().week.astype(int)
    df_v['dia_semana'] = df_v['timestamp'].dt.dayofweek.astype(int)
    df_v['dia_nombre'] = df_v['dia_semana'].map(lambda d: DIAS[d])
    df_v['hora']       = df_v['timestamp'].dt.hour.astype(int)

    # MONGO NO tiene Joins
    # Asi que hacemos join con clientes , es decir agregamos
    # los datos del cliente (segmento, giro, ticket promedio,
    # etc.) directamente en cada venta
    cli = df_clientes[['id_cliente', 'nombre', 'segmento', 'giro',
                        'ticket_prom', 'sabor_preferido', 'frecuencia_compra', 'ubicacion']].copy()
    cli.columns = ['id_cliente', 'cliente_nombre', 'cliente_segmento', 'cliente_giro',
                   'cliente_ticket_prom', 'cliente_sabor_preferido',
                   'cliente_frecuencia', 'cliente_ubicacion']
    df_v = df_v.merge(cli, on='id_cliente', how='left')

    # Join con clima (agregamos temperatura, precipitacion y festivos 
    # del dia de cada venta. 
    clim = df_clima[['fecha', 'temperatura', 'precipitacion', 'eventos_festivos_locales']].copy()
    clim['fecha'] = clim['fecha'].astype(str)
    df_v = df_v.merge(clim, on='fecha', how='left')

    # Contamos cuantos productos distintos tiene cada ticket desde df_detalle. 
    cnt = df_detalle.groupby('id_ticket')['id_producto'].count().reset_index(name='num_productos')
    df_v = df_v.merge(cnt, on='id_ticket', how='left')

    # Convertimos el DataFrame a lista de diccionarios y lo cargamos en MongoDB en     
    # bloques de 10,000 documentos para no saturar la memoria.
    df_v['temperatura']              = df_v['temperatura'].fillna(0).astype(float)
    df_v['precipitacion']            = df_v['precipitacion'].fillna(0).astype(float)
    df_v['eventos_festivos_locales'] = df_v['eventos_festivos_locales'].fillna('')
    df_v['num_productos']            = df_v['num_productos'].fillna(0).astype(int)
    df_v['total']                    = df_v['total'].round(2)

    COLS_VC = [
        'id_ticket', 'timestamp', 'anio', 'mes', 'mes_nombre', 'semana',
        'dia_semana', 'dia_nombre', 'hora', 'payment_method', 'total', 'num_productos',
        'id_cliente', 'cliente_nombre', 'cliente_segmento', 'cliente_giro',
        'cliente_ticket_prom', 'cliente_sabor_preferido', 'cliente_frecuencia', 'cliente_ubicacion',
        'temperatura', 'precipitacion', 'eventos_festivos_locales']
    
    docs_vc = df_v[COLS_VC].to_dict('records')
    for doc in docs_vc:
        doc['id_ticket']  = int(doc['id_ticket'])
        doc['id_cliente'] = int(doc['id_cliente'])
        doc['total']      = float(doc['total'])
        if hasattr(doc['timestamp'], 'to_pydatetime'):
            doc['timestamp'] = doc['timestamp'].to_pydatetime()

    upsert('ventas_completas', docs_vc)

    # CatalogoProductos 

    # Recorremos los 75 productos y construimos un documento por cada uno con todos sus campos,
    # incluyendo rentabilidad_pct y margen_bruto que se calcularon en el bloque anterior.  

    print('\n   Construyendo catalogo_productos...')
    prod_docs = []
    for _, row in df_productos.iterrows():
        prod_docs.append({
            'id_producto':      int(row['id_producto']),
            'sabor':            row['sabor'],
            'categoria':        row['categoria'],
            'costo_prod_lt':    float(row['costo_prod_lt']),
            'precio_sug':       float(row['precio_sug']),
            'ingredientes':     row['ingredientes'],
            'rentabilidad_pct': float(row['rentabilidad_pct']),
            'margen_bruto':     round(float(row['precio_sug']) - float(row['costo_prod_lt']), 2)
        })
    upsert('catalogo_productos', prod_docs)

    # Clientes perfil 

    # Combinamos el perfil base del cliente (de dim_clientes_y_segmentos) con estadisticas
    # reales calculadas desde df_ventas: total gastado, numero de compras, ticket real     
    # promedio, fecha del primer y ultimo pedido. Estos datos de resumen se guardan como un
    # subdocumento resumen dentro del documento del cliente.

    print('\n   Construyendo clientes_perfil...')
    cli_stats = df_ventas.groupby('id_cliente').agg(
        total_gastado=('total',     'sum'),
        num_compras  =('id_ticket', 'count'),
        ticket_real  =('total',     'mean'),
        ultimo_pedido=('timestamp', 'max'),
        primer_pedido=('timestamp', 'min'),
    ).reset_index()
    cli_stats['total_gastado'] = cli_stats['total_gastado'].round(2)
    cli_stats['ticket_real']   = cli_stats['ticket_real'].round(2)
    df_cp = df_clientes.merge(cli_stats, on='id_cliente', how='left')
    df_cp['total_gastado'] = df_cp['total_gastado'].fillna(0)
    df_cp['num_compras']   = df_cp['num_compras'].fillna(0).astype(int)

    cli_docs = []
    for _, row in df_cp.iterrows():
        cli_docs.append({
            'id_cliente':        int(row['id_cliente']),
            'nombre':            row['nombre'],
            'giro':              row['giro'],
            'segmento':          row['segmento'],
            'frecuencia_compra': row['frecuencia_compra'],
            'ticket_prom':       float(row['ticket_prom']),
            'sabor_preferido':   row['sabor_preferido'],
            'ubicacion':         row['ubicacion'],
            'resumen': {
                'total_gastado': float(row['total_gastado']),
                'num_compras':   int(row['num_compras']),
                'ticket_real':   round(float(row.get('ticket_real', 0) or 0), 2),
                'ultimo_pedido': row['ultimo_pedido'].to_pydatetime()
                                 if pd.notna(row.get('ultimo_pedido')) else None,
                'primer_pedido': row['primer_pedido'].to_pydatetime()
                                 if pd.notna(row.get('primer_pedido')) else None,
            },
        })
    upsert('clientes_perfil', cli_docs)

    # Guardamos df_v enriquecido para la capa Oro 
    print('\n  Guardando ventas_enriquecidas para Oro...')
    df_v[COLS_VC + ['fecha']].to_parquet(
        TMP / 'plata_ventas_enriquecidas.parquet', index=False)
    print('      {:<30} {:>6,} filas'.format('plata_ventas_enriquecidas.parquet', len(df_v)))

    print('\n' + '*-' * 30)
    print('    PLATA completada — 3 colecciones en MongoDB')
    print('  ⟶  Siguiente: python oro.py')
    print('*-' * 30)

    mongo.client.close()


if __name__ == '__main__':
    run_plata()
