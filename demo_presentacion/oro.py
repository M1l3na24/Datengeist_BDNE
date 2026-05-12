"""
oro.py — Capa Oro
Lee ventas_enriquecidas.parquet de Plata y los Parquet de Bronce,
calcula 7 colecciones KPI y las carga en MongoDB datengeist_demo.

Ejecutar: python oro.py
Requiere haber corrido antes: python bronce.py y python plata.py
"""

import sys
import warnings
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

warnings.filterwarnings('ignore')

MONGO_URI = 'mongodb://admin:cuyos123@localhost:27017/?authSource=admin'
MONGO_DB  = 'datengeist_demo'


COMISIONES = {
    'Efectivo':        0.000,
    'Tarjeta débito':  0.015,
    'Tarjeta crédito': 0.030,
    'Transferencia':   0.000,
    'QR':              0.010}

TMP = Path(__file__).parent / 'tmp'

COLECCIONES_KPI = [
    'kpi_ventas_temporales',
    'kpi_horarios_afluencia',
    'kpi_productos_sabores',
    'kpi_segmentacion',
    'kpi_metodos_pago',
    'kpi_mayoreo',
    'kpi_ticket_composicion']


def _check_plata():
    sentinel = TMP / 'plata_ventas_enriquecidas.parquet'
    if not sentinel.exists():
        print('\n    ERROR: La capa Plata aún no ha corrido.')
        print('  ⟶  Ejecuta primero: python plata.py')
        print(f'  Archivo faltante: .../tmp/plata_ventas_enriquecidas.parquet')
        sys.exit(1)

    bronce_files = [
        'bronce_ventas.parquet', 'bronce_detalle.parquet',
        'bronce_productos.parquet', 'bronce_clientes.parquet']
    
    faltantes = [f for f in bronce_files if not (TMP / f).exists()]
    if faltantes:
        print('\n    ERROR: Archivos de Bronce no encontrados.')
        print('  ⟶  Ejecuta primero: python bronce.py')
        for f in faltantes:
            print(f'      • {f}')
        sys.exit(1)


def run_oro():
    print('\n' + '*-' * 30)
    print('   ORO — Calculando KPIs...')
    print('*-' * 30)

    _check_plata()

    print('\n   Cargando datos de Plata y Bronce...')
    df_v         = pd.read_parquet(TMP / 'plata_ventas_enriquecidas.parquet')
    df_detalle   = pd.read_parquet(TMP / 'bronce_detalle.parquet')
    df_productos = pd.read_parquet(TMP / 'bronce_productos.parquet')
    df_ventas    = pd.read_parquet(TMP / 'bronce_ventas.parquet')
    df_clientes  = pd.read_parquet(TMP / 'bronce_clientes.parquet')
    df_ops       = pd.read_parquet(TMP /  'bronce_ops.parquet')

    mongo = MongoClient(MONGO_URI)[MONGO_DB]

    def upsert(nombre, docs):
        col = mongo[nombre]
        col.delete_many({})
        if docs:
            col.insert_many(docs)
        print('     {:<30} {:>6,} docs'.format(nombre, len(docs)))

    print('\n   Calculando KPIs...\n')

    # kpi_ventas_temporales 

    # Agrupamos las ventas por mes y por semana de calendario. 
    # Para cada periodo calculamos:
    # ingresos totales, numero de tickets, ticket promedio y clientes unicos. Al final     
    # mezclamos ambos grupos en una sola coleccion donde cada documento tiene un campo tipo
    # que vale "mensual" o "semanal".

    monthly = df_v.groupby(['anio', 'mes', 'mes_nombre']).agg(
        total_ventas    =('total',      'sum'),
        num_tickets     =('id_ticket',  'count'),
        ticket_prom     =('total',      'mean'),
        clientes_unicos =('id_cliente', 'nunique'),
    ).reset_index()
    monthly['total_ventas'] = monthly['total_ventas'].round(2)
    monthly['ticket_prom']  = monthly['ticket_prom'].round(2)

    monthly_docs = []
    for _, r in monthly.iterrows():
        monthly_docs.append({
            'tipo':           'mensual',
            'periodo':        '{}-{:02d}'.format(int(r['anio']), int(r['mes'])),
            'anio':           int(r['anio']),
            'mes':            int(r['mes']),
            'mes_nombre':     r['mes_nombre'],
            'total_ventas':   float(r['total_ventas']),
            'num_tickets':    int(r['num_tickets']),
            'ticket_prom':    float(r['ticket_prom']),
            'clientes_unicos': int(r['clientes_unicos'])})

    weekly = df_v.groupby(['anio', 'semana']).agg(
        total_ventas    =('total',      'sum'),
        num_tickets     =('id_ticket',  'count'),
        ticket_prom     =('total',      'mean'),
        clientes_unicos =('id_cliente', 'nunique')
    ).reset_index()
    weekly['total_ventas'] = weekly['total_ventas'].round(2)
    weekly['ticket_prom']  = weekly['ticket_prom'].round(2)

    weekly_docs = []
    for _, r in weekly.iterrows():
        weekly_docs.append({
            'tipo':           'semanal',
            'periodo':        '{}-W{:02d}'.format(int(r['anio']), int(r['semana'])),
            'anio':           int(r['anio']),
            'semana':         int(r['semana']),
            'total_ventas':   float(r['total_ventas']),
            'num_tickets':    int(r['num_tickets']),
            'ticket_prom':    float(r['ticket_prom']),
            'clientes_unicos': int(r['clientes_unicos']),
        })
    upsert('kpi_ventas_temporales', monthly_docs + weekly_docs)

    # kpi_horarios_afluencia 

    # Agrupamos por combinacion de hora del dia + dia de la semana. 
    # Calculamos el promedio de tickets por hora dividiendo el total entre 
    # los dias distintos que existieron para ese dia de semana. Luego clasifica 
    # cada hora como "Hora pico", "Hora normal" o "Hora baja" usando los percentiles 
    # 75 y 50 como umbrales.

    hora_agg = df_v.groupby(['hora', 'dia_semana', 'dia_nombre']).agg(
        total_tickets  =('id_ticket', 'count'),
        total_ingresos =('total',     'sum'),
        ticket_prom    =('total',     'mean'),
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
            'hora':           int(r['hora']),
            'dia_semana':     int(r['dia_semana']),
            'dia_nombre':     r['dia_nombre'],
            'avg_tickets':    avg,
            'total_tickets':  int(r['total_tickets']),
            'total_ingresos': round(float(r['total_ingresos']), 2),
            'ticket_prom':    round(float(r['ticket_prom']), 2),
            'clasificacion':  'Hora pico' if avg >= p75 else ('Hora normal' if avg >= p50 else 'Hora baja')
        })
    upsert('kpi_horarios_afluencia', hora_docs)

    # kpi_productos_sabores 

    # Unimos la tabla de detalle de ventas con el catalogo de productos para tener sabor,
    # categoria y costos. Luego agrupa por producto y calcula: ingresos, costo, margen     
    # bruto, rentabilidad y unidades vendidas. Ordena de mayor a menor ingreso y asigna un
    # ranking_ventas. Alimenta el top 10 de productos y la tabla resumen del dashboard.


    det_prod = df_detalle.merge(
        df_productos[['id_producto', 'sabor', 'categoria', 'costo_prod_lt', 'precio_sug']],
        on='id_producto', how='left')
    det_prod['subtotal']    = det_prod['precio_unitario'] * det_prod['cantidad']
    det_prod['costo_total'] = det_prod['costo_prod_lt']   * det_prod['cantidad']

    prod_kpi = det_prod.groupby(['id_producto', 'sabor', 'categoria']).agg(
        ingresos_totales  =('subtotal',        'sum'),
        costo_total       =('costo_total',     'sum'),
        unidades_vendidas =('cantidad',        'sum'),
        num_tickets       =('id_ticket',       'nunique'),
        precio_prom       =('precio_unitario', 'mean'),
    ).reset_index()
    prod_kpi['margen_bruto']    = (prod_kpi['ingresos_totales'] - prod_kpi['costo_total']).round(2)
    prod_kpi['rentabilidad_lt'] = (prod_kpi['margen_bruto'] / prod_kpi['ingresos_totales']).round(4)
    prod_kpi = prod_kpi.sort_values('ingresos_totales', ascending=False).reset_index(drop=True)
    prod_kpi['ranking_ventas'] = prod_kpi.index + 1

    prod_kpi_docs = []
    for _, r in prod_kpi.iterrows():
        prod_kpi_docs.append({
            'id_producto':      int(r['id_producto']),
            'sabor':            r['sabor'],
            'categoria':        r['categoria'],
            'ranking_ventas':   int(r['ranking_ventas']),
            'ingresos_totales': round(float(r['ingresos_totales']), 2),
            'costo_total':      round(float(r['costo_total']), 2),
            'margen_bruto':     float(r['margen_bruto']),
            'rentabilidad_lt':  float(r['rentabilidad_lt']),
            'unidades_vendidas': int(r['unidades_vendidas']),
            'num_tickets':      int(r['num_tickets']),
            'precio_prom':      round(float(r['precio_prom']), 2),
        })
    upsert('kpi_productos_sabores', prod_kpi_docs)

    # kpi_segmentacion 

    # Agrupa ventas por segmento (VIP, Frecuente, Ocasional, Nuevo). Para cada segmento    
    # calcula ingresos, participacion porcentual, tickets y clientes unicos. Enriquece con
    # el conteo de clientes y ticket promedio de perfil desde la dimension de clientes.


    seg_kpi = df_v.groupby('cliente_segmento').agg(
        total_ingresos  =('total',      'sum'),
        num_tickets     =('id_ticket',  'count'),
        ticket_prom     =('total',      'mean'),
        clientes_unicos =('id_cliente', 'nunique'),
    ).reset_index()
    seg_kpi = seg_kpi.sort_values('total_ingresos', ascending=False).reset_index(drop=True)
    total_ing = float(seg_kpi['total_ingresos'].sum())
    seg_kpi['pct_ingresos'] = (seg_kpi['total_ingresos'] / total_ing * 100).round(2)
    seg_cli = df_clientes.groupby('segmento').agg(
        num_clientes       =('id_cliente', 'count'),
        ticket_prom_perfil =('ticket_prom', 'mean'),
    ).reset_index()
    seg_cli.columns = ['cliente_segmento', 'num_clientes', 'ticket_prom_perfil']
    seg_kpi = seg_kpi.merge(seg_cli, on='cliente_segmento', how='left')

    seg_docs = []
    for _, r in seg_kpi.iterrows():
        seg_docs.append({
            'segmento':           r['cliente_segmento'],
            'total_ingresos':     round(float(r['total_ingresos']), 2),
            'num_tickets':        int(r['num_tickets']),
            'ticket_prom':        round(float(r['ticket_prom']), 2),
            'clientes_unicos':    int(r['clientes_unicos']),
            'num_clientes':       int(r.get('num_clientes') or 0),
            'pct_ingresos':       float(r['pct_ingresos']),
            'ticket_prom_perfil': round(float(r.get('ticket_prom_perfil') or 0), 2)
        })
    upsert('kpi_segmentacion', seg_docs)

    # kpi_metodos_pago 

    # Agrupamos por metodo de pago. 
    # Calculamos el monto total, numero de transacciones,
    # participacion porcentual en volumen y en monto. 
    # Incluimos la tasa de comision estandar del mercado mexicano y 
    #el costo total estimado de comisiones por metodo. 

    pago_kpi = df_v.groupby('payment_method').agg(
        monto_total       =('total',     'sum'),
        num_transacciones =('id_ticket', 'count'),
        ticket_prom       =('total',     'mean'),
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
            'metodo':               r['payment_method'],
            'monto_total':          round(float(r['monto_total']), 2),
            'num_transacciones':    int(r['num_transacciones']),
            'ticket_prom':          round(float(r['ticket_prom']), 2),
            'pct_transacciones':    float(r['pct_transacciones']),
            'pct_monto':            float(r['pct_monto']),
            'comision_pct':         tasa,
            'costo_comision_total': round(float(r['monto_total']) * tasa, 2),
        })
    upsert('kpi_metodos_pago', pago_docs)

    # kpi_mayoreo 

    # Tiene dos tipos de documento: "por_producto" (que productos se venden mas en canal   
    # mayoreo, con unidades, ingresos y margen) y "por_cliente" (top 100 clientes
    # mayoristas ordenados por gasto total, con numero de pedidos y ticket promedio).

    # Pregunta 1b: ¿Que productos y con que frecuencia compran los clientes al por mayor?
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
    upsert('kpi_mayoreo', mayoreo_docs)


    # kpi_operaciones_personal  

    # Definimos un documento por cada combinacion fecha-turno. 
    # Guarda numero de empleados, costo por hora, costo total del turno y 
    # el promedio historico de tickets que entran en ese turno. 
    # El campo tickets_por_empleado relaciona directamente la afluencia con la      
    # plantilla disponible.

    # Pregunta 3b: ¿Cuantos empleados se necesitan en los horarios de mayor afluencia?
    TURNO_HORAS = {'Matutino': (8, 14), 'Vespertino': (14, 20), 'Nocturno': (20, 24)}

    # Promedio de tickets por hora en el rango de cada turno
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
    upsert('kpi_operaciones_personal', ops_docs)

    # ORO: kpi_ticket_composicion

    # Tiene tres tipos de documento: "resumen_global" (ticket promedio, mediana, p25, p75 y
    # maximo), "distribucion_lineas" (que porcentaje de tickets tienen 1, 2, 3, ...
    # productos) y "por_segmento" (cuantas lineas y unidades trae en promedio cada tipo de 
    # cliente).

    # Pregunta 6a: ¿Como luce el ticket promedio?
    ticket_size = df_detalle.groupby('id_ticket').agg(
    num_lineas     = ('id_producto', 'count'),
    total_unidades = ('cantidad',    'sum')
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
    upsert('kpi_ticket_composicion', comp_docs)

    # Resumen final
    total_docs = sum(mongo[c].count_documents({}) for c in COLECCIONES_KPI)

    print('\n' + '*-' * 30)
    print('    ORO completado — 7 colecciones KPI en MongoDB')
    print(f'  MongoDB datengeist_demo → {total_docs:,} documentos KPI')
    print('*-' * 30)

    mongo.client.close()


if __name__ == '__main__':
    run_oro()
