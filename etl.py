'''
etl.py implementa un pipeline ETL con arquitectura medallon (como vimos con Erick)
que extrae los datos relacionales de PostgreSQL y los transforma en colecciones 
NoSQL optimizadas para el dashboard de Metabase en MongoDB.                                                   
                                                                        
  - Bronce: extrae las 6 tablas de PostgreSQL en DataFrames
  - Plata: desnormaliza y enriquece en 3 colecciones (ventas_completas,
  catalogo_productos, clientes_perfil)
  - Oro: pre-agrega 8 colecciones de KPIs (kpi_ventas_temporales,
  kpi_horarios_afluencia, kpi_productos_sabores, kpi_segmentacion,
  kpi_metodos_pago, kpi_mayoreo, kpi_operaciones_personal, kpi_ticket_composicion)
'''

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from pymongo import MongoClient
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Informacion importante de las conexiones 
PG_CONN   = 'postgresql+psycopg2://admin:cuyos123@127.0.0.1:5433/datengeist'
MONGO_URI = 'mongodb://admin:cuyos123@localhost:27017/?authSource=admin'
MONGO_DB  = 'datengeist'

engine = create_engine(PG_CONN, pool_pre_ping=True)
mongo  = MongoClient(MONGO_URI)[MONGO_DB]

SABORES   = ['Vainilla','Chocolate','Fresa','Mango','Limón','Pistache','Nuez',
             'Cajeta','Guanábana','Mamey','Tamarindo','Coco','Frambuesa','Elote','Tequila']
DIAS      = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
MESES_NOM = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio',
              'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

# La siguiente funcion garantiza cada vez que corras el ETL partas desde cero, sin duplicados
# e inserta los nuevos
def upsert_collection(name, docs):
    coll = mongo[name]
    coll.delete_many({})
    if docs:
        coll.insert_many(docs)
    print('  -> {:<32} {:>8,} docs'.format(name, len(docs)))

print('Conexiones establecidas — PostgreSQL + MongoDB')

# BRONCE: Extraccion
print('\n' + '*-'*30)
print('  CAPA BRONCE — Extrayendo desde PostgreSQL')
print('*-'*30)

df_ventas    = pd.read_sql('SELECT * FROM ventas ORDER BY id_ticket', engine)
df_detalle   = pd.read_sql('SELECT * FROM detalle_ventas ORDER BY id_ticket', engine)
df_productos = pd.read_sql('SELECT * FROM dim_productos_y_sabores ORDER BY id_producto', engine)
df_clientes  = pd.read_sql('SELECT * FROM dim_clientes_y_segmentos ORDER BY id_cliente', engine)
df_clima     = pd.read_sql('SELECT * FROM variables_externas ORDER BY fecha', engine)
df_ops       = pd.read_sql('SELECT * FROM operaciones_y_personal ORDER BY fecha', engine)

# Normalizamos nombres de columnas a minusculas para consistencia
for df in [df_ventas, df_detalle, df_productos, df_clientes, df_clima, df_ops]:
    df.columns = df.columns.str.lower()

# Resumen de filas por tabla
for name, df in [
    ('ventas',                   df_ventas),
    ('detalle_ventas',           df_detalle),
    ('dim_productos_y_sabores',  df_productos),
    ('dim_clientes_y_segmentos', df_clientes),
    ('variables_externas',       df_clima),
    ('operaciones_y_personal',   df_ops),
]:
    print(' {:<28} {:>10,} filas'.format(name, len(df)))


# Es necesario reconstruir el sabor que no estaba guardado como columna en PostgreSQL
df_productos['sabor'] = df_productos['id_producto'].apply(
    lambda x: SABORES[(int(x) - 1) // 5]
)

# Prcentaje de rentabilidad de cada producto:
#   rentabilidad = (precio - costo) / precio

df_productos['rentabilidad_pct'] = (
    (df_productos['precio_sug'] - df_productos['costo_prod_lt'])
    / df_productos['precio_sug']
).round(4)

print('\n Extracción completa')

# PLATA: ventas_completas
print('\n' + '*-'*30)
print('  CAPA PLATA — ventas_completas')
print('*-'*30)

# Descomponemos el timestamp en columnas utiles: anio, mes,    
# nombre del mes, semana, dia de la semana, nombre del dia y hora
df_v = df_ventas.copy()
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
#  etc.) directamente en cada venta
cli = df_clientes[['id_cliente','nombre','segmento','giro',
                    'ticket_prom','sabor_preferido','frecuencia_compra','ubicacion']].copy()
cli.columns = ['id_cliente','cliente_nombre','cliente_segmento','cliente_giro',
                'cliente_ticket_prom','cliente_sabor_preferido',
                'cliente_frecuencia','cliente_ubicacion']
df_v = df_v.merge(cli, on='id_cliente', how='left')

# Join con clima (agregamos temperatura, precipitacion y festivos 
# del dia de cada venta.  
clim = df_clima[['fecha','temperatura','precipitacion','eventos_festivos_locales']].copy()
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
    'id_ticket','timestamp','anio','mes','mes_nombre','semana',
    'dia_semana','dia_nombre','hora','payment_method','total','num_productos',
    'id_cliente','cliente_nombre','cliente_segmento','cliente_giro',
    'cliente_ticket_prom','cliente_sabor_preferido','cliente_frecuencia','cliente_ubicacion',
    'temperatura','precipitacion','eventos_festivos_locales',
]
docs_vc = df_v[COLS_VC].to_dict('records')

for doc in docs_vc:
    doc['id_ticket']  = int(doc['id_ticket'])
    doc['id_cliente'] = int(doc['id_cliente'])
    doc['total']      = float(doc['total'])
    if hasattr(doc['timestamp'], 'to_pydatetime'):
        doc['timestamp'] = doc['timestamp'].to_pydatetime()

CHUNK = 10_000
coll_vc = mongo['ventas_completas']
coll_vc.delete_many({})
for i in tqdm(range(0, len(docs_vc), CHUNK), desc='ventas_completas'):
    coll_vc.insert_many(docs_vc[i:i + CHUNK])
print(' ->  ventas_completas: {:,} docs'.format(len(docs_vc)))

# PLATA: catalogo_productos 

# Recorremos los 75 productos y construimos un documento por cada uno con todos sus campos,
# incluyendo rentabilidad_pct y margen_bruto que se calcularon en el bloque anterior.  

print('\nPLATA — catalogo_productos')
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
        'margen_bruto':     round(float(row['precio_sug']) - float(row['costo_prod_lt']), 2),
    })
upsert_collection('catalogo_productos', prod_docs)

# PLATA: clientes_perfil 

# Combinamos el perfil base del cliente (de dim_clientes_y_segmentos) con estadisticas
# reales calculadas desde df_ventas: total gastado, numero de compras, ticket real     
# promedio, fecha del primer y ultimo pedido. Estos datos de resumen se guardan como un
# subdocumento resumen dentro del documento del cliente.

print('\nPLATA — clientes_perfil')
cli_stats = df_ventas.groupby('id_cliente').agg(
    total_gastado = ('total', 'sum'),
    num_compras   = ('id_ticket', 'count'),
    ticket_real   = ('total', 'mean'),
    ultimo_pedido = ('timestamp', 'max'),
    primer_pedido = ('timestamp', 'min'),
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
            'ticket_real':   round(float(row['ticket_real']) if pd.notna(row.get('ticket_real')) else 0.0, 2),
            'ultimo_pedido': row['ultimo_pedido'].to_pydatetime() if pd.notna(row.get('ultimo_pedido')) else None,
            'primer_pedido': row['primer_pedido'].to_pydatetime() if pd.notna(row.get('primer_pedido')) else None,
        },
    })
upsert_collection('clientes_perfil', cli_docs)

#  ORO: kpi_ventas_temporales

# Agrupamos las ventas por mes y por semana de calendario. 
# Para cada periodo calculamos:
# ingresos totales, numero de tickets, ticket promedio y clientes unicos. Al final     
# mezclamos ambos grupos en una sola coleccion donde cada documento tiene un campo tipo
# que vale "mensual" o "semanal".

print('\n' + '='*60)
print('  CAPA ORO — KPIs')
print('='*60)

monthly = df_v.groupby(['anio','mes','mes_nombre']).agg(
    total_ventas    = ('total', 'sum'),
    num_tickets     = ('id_ticket', 'count'),
    ticket_prom     = ('total', 'mean'),
    clientes_unicos = ('id_cliente', 'nunique'),
).reset_index()
monthly['total_ventas'] = monthly['total_ventas'].round(2)
monthly['ticket_prom']  = monthly['ticket_prom'].round(2)

monthly_docs = []
for _, r in monthly.iterrows():
    monthly_docs.append({
        'tipo': 'mensual',
        'periodo': '{}-{:02d}'.format(int(r['anio']), int(r['mes'])),
        'anio': int(r['anio']), 'mes': int(r['mes']), 'mes_nombre': r['mes_nombre'],
        'total_ventas': float(r['total_ventas']), 'num_tickets': int(r['num_tickets']),
        'ticket_prom': float(r['ticket_prom']), 'clientes_unicos': int(r['clientes_unicos']),
    })

weekly = df_v.groupby(['anio','semana']).agg(
    total_ventas    = ('total', 'sum'),
    num_tickets     = ('id_ticket', 'count'),
    ticket_prom     = ('total', 'mean'),
    clientes_unicos = ('id_cliente', 'nunique'),
).reset_index()
weekly['total_ventas'] = weekly['total_ventas'].round(2)
weekly['ticket_prom']  = weekly['ticket_prom'].round(2)

weekly_docs = []
for _, r in weekly.iterrows():
    weekly_docs.append({
        'tipo': 'semanal',
        'periodo': '{}-W{:02d}'.format(int(r['anio']), int(r['semana'])),
        'anio': int(r['anio']), 'semana': int(r['semana']),
        'total_ventas': float(r['total_ventas']), 'num_tickets': int(r['num_tickets']),
        'ticket_prom': float(r['ticket_prom']), 'clientes_unicos': int(r['clientes_unicos']),
    })

upsert_collection('kpi_ventas_temporales', monthly_docs + weekly_docs)

# ── ORO: kpi_horarios_afluencia ───────────────────────────────────────────────
hora_agg = df_v.groupby(['hora','dia_semana','dia_nombre']).agg(
    total_tickets  = ('id_ticket', 'count'),
    total_ingresos = ('total', 'sum'),
    ticket_prom    = ('total', 'mean'),
).reset_index()
dias_unicos = df_v.groupby('dia_semana')['fecha'].nunique().to_dict()
hora_agg['n_dias']      = hora_agg['dia_semana'].map(dias_unicos)
hora_agg['avg_tickets'] = (hora_agg['total_tickets'] / hora_agg['n_dias']).round(2)
p75 = hora_agg['avg_tickets'].quantile(0.75)
p50 = hora_agg['avg_tickets'].quantile(0.50)

hora_docs = []
for _, r in hora_agg.iterrows():
    avg = float(r['avg_tickets'])
    hora_docs.append({
        'hora': int(r['hora']), 'dia_semana': int(r['dia_semana']), 'dia_nombre': r['dia_nombre'],
        'avg_tickets': avg, 'total_tickets': int(r['total_tickets']),
        'total_ingresos': round(float(r['total_ingresos']), 2),
        'ticket_prom': round(float(r['ticket_prom']), 2),
        'clasificacion': 'Hora pico' if avg >= p75 else ('Hora normal' if avg >= p50 else 'Hora baja'),
    })
upsert_collection('kpi_horarios_afluencia', hora_docs)

# ── ORO: kpi_productos_sabores ────────────────────────────────────────────────
det_prod = df_detalle.merge(
    df_productos[['id_producto','sabor','categoria','costo_prod_lt','precio_sug']],
    on='id_producto', how='left',
)
det_prod['subtotal']    = det_prod['precio_unitario'] * det_prod['cantidad']
det_prod['costo_total'] = det_prod['costo_prod_lt']   * det_prod['cantidad']

prod_kpi = det_prod.groupby(['id_producto','sabor','categoria']).agg(
    ingresos_totales  = ('subtotal',        'sum'),
    costo_total       = ('costo_total',     'sum'),
    unidades_vendidas = ('cantidad',        'sum'),
    num_tickets       = ('id_ticket',       'nunique'),
    precio_prom       = ('precio_unitario', 'mean'),
).reset_index()
prod_kpi['margen_bruto']    = (prod_kpi['ingresos_totales'] - prod_kpi['costo_total']).round(2)
prod_kpi['rentabilidad_lt'] = (prod_kpi['margen_bruto'] / prod_kpi['ingresos_totales']).round(4)
prod_kpi = prod_kpi.sort_values('ingresos_totales', ascending=False).reset_index(drop=True)
prod_kpi['ranking_ventas'] = prod_kpi.index + 1

prod_kpi_docs = []
for _, r in prod_kpi.iterrows():
    prod_kpi_docs.append({
        'id_producto': int(r['id_producto']), 'sabor': r['sabor'], 'categoria': r['categoria'],
        'ranking_ventas': int(r['ranking_ventas']),
        'ingresos_totales': round(float(r['ingresos_totales']), 2),
        'costo_total': round(float(r['costo_total']), 2),
        'margen_bruto': float(r['margen_bruto']), 'rentabilidad_lt': float(r['rentabilidad_lt']),
        'unidades_vendidas': int(r['unidades_vendidas']), 'num_tickets': int(r['num_tickets']),
        'precio_prom': round(float(r['precio_prom']), 2),
    })
upsert_collection('kpi_productos_sabores', prod_kpi_docs)

# ── ORO: kpi_segmentacion ─────────────────────────────────────────────────────
seg_kpi = df_v.groupby('cliente_segmento').agg(
    total_ingresos  = ('total',      'sum'),
    num_tickets     = ('id_ticket',  'count'),
    ticket_prom     = ('total',      'mean'),
    clientes_unicos = ('id_cliente', 'nunique'),
).reset_index()
seg_kpi = seg_kpi.sort_values('total_ingresos', ascending=False).reset_index(drop=True)
total_ing = float(seg_kpi['total_ingresos'].sum())
seg_kpi['pct_ingresos'] = (seg_kpi['total_ingresos'] / total_ing * 100).round(2)
seg_cli = df_clientes.groupby('segmento').agg(
    num_clientes       = ('id_cliente', 'count'),
    ticket_prom_perfil = ('ticket_prom', 'mean'),
).reset_index()
seg_cli.columns = ['cliente_segmento','num_clientes','ticket_prom_perfil']
seg_kpi = seg_kpi.merge(seg_cli, on='cliente_segmento', how='left')

seg_docs = []
for _, r in seg_kpi.iterrows():
    seg_docs.append({
        'segmento': r['cliente_segmento'],
        'total_ingresos': round(float(r['total_ingresos']), 2),
        'num_tickets': int(r['num_tickets']), 'ticket_prom': round(float(r['ticket_prom']), 2),
        'clientes_unicos': int(r['clientes_unicos']), 'num_clientes': int(r.get('num_clientes') or 0),
        'pct_ingresos': float(r['pct_ingresos']),
        'ticket_prom_perfil': round(float(r.get('ticket_prom_perfil') or 0), 2),
    })
upsert_collection('kpi_segmentacion', seg_docs)

# ── ORO: kpi_metodos_pago ─────────────────────────────────────────────────────
# Tasas de comisión estándar mercado mexicano (fuente: Concanaco / bancos 2024)
COMISIONES = {
    'Efectivo':       0.000,
    'Tarjeta débito': 0.015,
    'Tarjeta crédito':0.030,
    'Transferencia':  0.000,
    'QR':             0.010,
}

pago_kpi = df_v.groupby('payment_method').agg(
    monto_total       = ('total',     'sum'),
    num_transacciones = ('id_ticket', 'count'),
    ticket_prom       = ('total',     'mean'),
).reset_index()
total_t = float(pago_kpi['num_transacciones'].sum())
total_m = float(pago_kpi['monto_total'].sum())
pago_kpi['pct_transacciones'] = (pago_kpi['num_transacciones'] / total_t * 100).round(2)
pago_kpi['pct_monto']         = (pago_kpi['monto_total'] / total_m * 100).round(2)
pago_kpi = pago_kpi.sort_values('num_transacciones', ascending=False).reset_index(drop=True)

pago_docs = []
for _, r in pago_kpi.iterrows():
    tasa = COMISIONES.get(r['payment_method'], 0.0)
    pago_docs.append({
        'metodo': r['payment_method'],
        'monto_total': round(float(r['monto_total']), 2),
        'num_transacciones': int(r['num_transacciones']),
        'ticket_prom': round(float(r['ticket_prom']), 2),
        'pct_transacciones': float(r['pct_transacciones']),
        'pct_monto': float(r['pct_monto']),
        'comision_pct': tasa,
        'costo_comision_total': round(float(r['monto_total']) * tasa, 2),
    })
upsert_collection('kpi_metodos_pago', pago_docs)

# ── ORO: kpi_mayoreo ─────────────────────────────────────────────────────────
# Pregunta 1b: ¿Qué productos y con qué frecuencia compran los clientes al por mayor?
mayoreo_det = df_detalle[df_detalle['tipo_venta'] == 'Mayoreo'].copy()
mayoreo_det['subtotal']    = mayoreo_det['precio_unitario'] * mayoreo_det['cantidad']
mayoreo_det = mayoreo_det.merge(
    df_productos[['id_producto','sabor','categoria','costo_prod_lt']], on='id_producto', how='left'
)
mayoreo_det['costo_total'] = mayoreo_det['costo_prod_lt'] * mayoreo_det['cantidad']

por_prod = mayoreo_det.groupby(['id_producto','sabor','categoria']).agg(
    unidades_vendidas = ('cantidad',     'sum'),
    ingresos_totales  = ('subtotal',     'sum'),
    costo_total       = ('costo_total',  'sum'),
    num_tickets       = ('id_ticket',    'nunique'),
    cantidad_prom     = ('cantidad',     'mean'),
).reset_index()
por_prod['margen_bruto'] = (por_prod['ingresos_totales'] - por_prod['costo_total']).round(2)
por_prod = por_prod.sort_values('unidades_vendidas', ascending=False).reset_index(drop=True)
por_prod['ranking'] = por_prod.index + 1

tickets_mayor = mayoreo_det[['id_ticket']].drop_duplicates()
tickets_mayor = tickets_mayor.merge(df_ventas[['id_ticket','id_cliente','total']], on='id_ticket', how='left')
tickets_mayor = tickets_mayor.merge(
    df_clientes[['id_cliente','nombre','segmento','giro','frecuencia_compra']], on='id_cliente', how='left'
)
por_cliente = tickets_mayor.groupby(['id_cliente','nombre','segmento','giro','frecuencia_compra']).agg(
    total_gastado = ('total',     'sum'),
    num_pedidos   = ('id_ticket', 'count'),
    ticket_prom   = ('total',     'mean'),
).reset_index()
por_cliente = por_cliente.sort_values('total_gastado', ascending=False).reset_index(drop=True)
por_cliente['ranking'] = por_cliente.index + 1

mayoreo_docs = []
for _, r in por_prod.iterrows():
    mayoreo_docs.append({
        'tipo': 'por_producto',
        'id_producto': int(r['id_producto']), 'sabor': r['sabor'], 'categoria': r['categoria'],
        'ranking': int(r['ranking']),
        'unidades_vendidas': int(r['unidades_vendidas']),
        'ingresos_totales': round(float(r['ingresos_totales']), 2),
        'margen_bruto': round(float(r['margen_bruto']), 2),
        'num_tickets': int(r['num_tickets']),
        'cantidad_prom': round(float(r['cantidad_prom']), 2),
    })
for _, r in por_cliente.head(100).iterrows():
    mayoreo_docs.append({
        'tipo': 'por_cliente',
        'id_cliente': int(r['id_cliente']), 'nombre': r['nombre'],
        'segmento': r['segmento'], 'giro': r['giro'],
        'frecuencia_compra': r['frecuencia_compra'],
        'ranking': int(r['ranking']),
        'total_gastado': round(float(r['total_gastado']), 2),
        'num_pedidos': int(r['num_pedidos']),
        'ticket_prom': round(float(r['ticket_prom']), 2),
    })
upsert_collection('kpi_mayoreo', mayoreo_docs)

# ── ORO: kpi_operaciones_personal ────────────────────────────────────────────
# Pregunta 3b: ¿Cuántos empleados se necesitan en los horarios de mayor afluencia?
TURNO_HORAS = {'Matutino': (8, 14), 'Vespertino': (14, 20), 'Nocturno': (20, 24)}

# Promedio de tickets por hora en el rango de cada turno (para relacionar afluencia con plantilla)
tickets_por_hora = df_v.groupby('hora')['id_ticket'].count().to_dict()
total_dias = df_v['fecha'].nunique()

ops_docs = []
for _, r in df_ops.iterrows():
    h_ini, h_fin = TURNO_HORAS.get(r['turno'], (0, 8))
    horas_turno = h_fin - h_ini
    tickets_turno = sum(tickets_por_hora.get(h, 0) for h in range(h_ini, h_fin))
    avg_tickets_turno = round(tickets_turno / total_dias, 2)
    n_emp = int(r['num_empleados'])
    ops_docs.append({
        'fecha': str(r['fecha']),
        'turno': r['turno'],
        'hora_inicio': h_ini,
        'hora_fin': h_fin,
        'num_empleados': n_emp,
        'costo_hora': float(r['costo_hora']),
        'costo_turno': round(float(r['costo_hora']) * horas_turno * n_emp, 2),
        'avg_tickets_turno': avg_tickets_turno,
        'tickets_por_empleado': round(avg_tickets_turno / n_emp, 2) if n_emp else 0,
    })
upsert_collection('kpi_operaciones_personal', ops_docs)

# ── ORO: kpi_ticket_composicion ──────────────────────────────────────────────
# Pregunta 6a: ¿Cómo luce el ticket promedio?
ticket_size = df_detalle.groupby('id_ticket').agg(
    num_lineas     = ('id_producto', 'count'),
    total_unidades = ('cantidad',    'sum'),
).reset_index()
ticket_size = ticket_size.merge(df_ventas[['id_ticket','total','id_cliente']], on='id_ticket', how='left')
ticket_size = ticket_size.merge(df_clientes[['id_cliente','segmento']], on='id_cliente', how='left')

dist_lineas = ticket_size.groupby('num_lineas').agg(
    num_tickets   = ('id_ticket', 'count'),
    ticket_prom   = ('total',     'mean'),
    unidades_prom = ('total_unidades', 'mean'),
).reset_index()
dist_lineas['pct_tickets'] = (dist_lineas['num_tickets'] / dist_lineas['num_tickets'].sum() * 100).round(2)

seg_comp = ticket_size.groupby('segmento').agg(
    lineas_prom   = ('num_lineas',     'mean'),
    unidades_prom = ('total_unidades', 'mean'),
    ticket_prom   = ('total',          'mean'),
).reset_index()

comp_docs = [{
    'tipo': 'resumen_global',
    'lineas_prom':         round(float(ticket_size['num_lineas'].mean()), 2),
    'unidades_prom':       round(float(ticket_size['total_unidades'].mean()), 2),
    'ticket_prom':         round(float(ticket_size['total'].mean()), 2),
    'ticket_mediana':      round(float(ticket_size['total'].median()), 2),
    'ticket_p25':          round(float(ticket_size['total'].quantile(0.25)), 2),
    'ticket_p75':          round(float(ticket_size['total'].quantile(0.75)), 2),
    'ticket_max':          round(float(ticket_size['total'].max()), 2),
}]
for _, r in dist_lineas.iterrows():
    comp_docs.append({
        'tipo': 'distribucion_lineas',
        'num_lineas': int(r['num_lineas']),
        'num_tickets': int(r['num_tickets']),
        'pct_tickets': float(r['pct_tickets']),
        'ticket_prom': round(float(r['ticket_prom']), 2),
        'unidades_prom': round(float(r['unidades_prom']), 2),
    })
for _, r in seg_comp.iterrows():
    comp_docs.append({
        'tipo': 'por_segmento',
        'segmento': r['segmento'],
        'lineas_prom': round(float(r['lineas_prom']), 2),
        'unidades_prom': round(float(r['unidades_prom']), 2),
        'ticket_prom': round(float(r['ticket_prom']), 2),
    })
upsert_collection('kpi_ticket_composicion', comp_docs)

# ── Verificación final ────────────────────────────────────────────────────────
print('\n' + '='*62)
print('  RESUMEN FINAL — MongoDB')
print('='*62)
colecciones = [
    'ventas_completas','catalogo_productos','clientes_perfil',
    'kpi_ventas_temporales','kpi_horarios_afluencia','kpi_productos_sabores',
    'kpi_segmentacion','kpi_metodos_pago',
    'kpi_mayoreo','kpi_operaciones_personal','kpi_ticket_composicion',
]
total = 0
for col in colecciones:
    n = mongo[col].count_documents({})
    total += n
    print('  📦  {:<32} {:>8,} docs'.format(col, n))
print('-'*62)
print('  TOTAL  {:>43,} docs'.format(total))
print('\n✅ ETL completado — MongoDB listo para Metabase')
