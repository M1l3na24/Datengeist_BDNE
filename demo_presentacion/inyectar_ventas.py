"""
inyectar_ventas.py — Datengeist Demo
Simula 5 ventas en tiempo real.
Cada venta se inserta en PostgreSQL datengeist_demo y luego
el ETL actualiza MongoDB para que el dashboard de Metabase refleje los cambios.

Uso:
  python inyectar_ventas.py           # 
  python inyectar_ventas.py --rapido  # controla si el ETL corre por venta o una sola vez al final
"""

import os
import sys
import random
import subprocess
from datetime import datetime

from pymongo import MongoClient
from sqlalchemy import create_engine, text

# Configuracion
RAPIDO   = '--rapido' in sys.argv
DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
ETL_SCRIPT = os.path.join(DEMO_DIR, 'etl_demo.py')

PG_CONN   = 'postgresql+psycopg2://admin:cuyos123@127.0.0.1:5433/datengeist_demo'
MONGO_URI = 'mongodb://admin:cuyos123@localhost:27017/?authSource=admin'
MONGO_DB  = 'datengeist_demo'

# Fecha de la sesion demo (dentro del rango de datos generados)
DEMO_FECHA = datetime(2025, 1, 15)


# -----> Las 5 ventas de la sesión demo 
#   Cada item: (id_producto, cantidad, id_sabor, tipo_venta, descripcion_legible)
#   Sabores demo: Vainilla=1, Chocolate=2, Fresa=3, Mango=4, Limón=5,
#                 Pistache=6, Nuez=7, Cajeta=8, Tamarindo=9, Coco=10
#   Productos:  ID = (sabor_idx * 5) + cat_idx  (1-based)
#     Vainilla   Artesanal=1 Premium=2 Bajo azúcar=3 Niños=4 Temporada=5
#     Chocolate  Artesanal=6 Premium=7 ...
#     Fresa      11-15, Mango 16-20, Limón 21-25, Pistache 26-30
#     Nuez 31-35, Cajeta 36-40, Tamarindo 41-45, Coco 46-50
VENTAS_DEMO = [
    {
        'cliente_id':     1,
        'cliente_nombre': 'Restaurante El Sabor',
        'segmento':       'VIP ',
        'descripcion_cli': 'El chef llega con su pedido semanal',
        'pedido_str':     'Tamarindo Premium ×2 + Cajeta Artesanal + Coco Premium',
        'payment_method': 'Tarjeta crédito',
        'hora':           14,
        'items': [
            (42, 2, 9, 'Mostrador'),   # Tamarindo Premium ×2
            (36, 1, 8, 'Mostrador'),   # Cajeta Artesanal ×1
            (47, 1, 10, 'Mostrador'),  # Coco Premium ×1
        ],
    },
    {
        'cliente_id':     2,
        'cliente_nombre': 'María González',
        'segmento':       'Frecuente ',
        'descripcion_cli': 'Viene por la nieve de la familia',
        'pedido_str':     'Vainilla Artesanal + Fresa Niños ×2',
        'payment_method': 'Efectivo',
        'hora':           17,
        'items': [
            (1,  1, 1, 'Para llevar'),   # Vainilla Artesanal ×1
            (14, 2, 3, 'Para llevar'),   # Fresa Ninios ×2
        ],
    },
    {
        'cliente_id':     3,
        'cliente_nombre': 'Pastelería La Dulce Vida',
        'segmento':       'Frecuente ',
        'descripcion_cli': 'Surtido para la vitrina de la tarde',
        'pedido_str':     'Chocolate Premium ×2 + Limón Artesanal ×3 + Nuez Temporada',
        'payment_method': 'Transferencia',
        'hora':           16,
        'items': [
            (7,  2, 2, 'Pedido online'),  # Chocolate Premium ×2
            (21, 3, 5, 'Pedido online'),  # Limon Artesanal ×3
            (35, 1, 7, 'Pedido online'),  # Nuez Temporada ×1
        ],
    },
    {
        'cliente_id':     4,
        'cliente_nombre': 'Colegio Benito Juárez',
        'segmento':       'Ocasional ',
        'descripcion_cli': 'Convivio de fin de semestre — pedido grande',
        'pedido_str':     'Fresa Niños ×5 + Mango Niños ×4 + Vainilla Niños ×3',
        'payment_method': 'QR',
        'hora':           12,
        'items': [
            (14, 5, 3, 'Mayoreo'),  # Fresa Ninios ×5
            (19, 4, 4, 'Mayoreo'),  # Mango Ninios ×4
            (4,  3, 1, 'Mayoreo'),  # Vainilla Ninios ×3
        ],
    },
    {
        'cliente_id':     5,
        'cliente_nombre': 'Juan Ramírez',
        'segmento':       'Nuevo ',
        'descripcion_cli': 'Primera visita a la tienda',
        'pedido_str':     'Mango Temporada ×1',
        'payment_method': 'Tarjeta débito',
        'hora':           18,
        'items': [
            (20, 1, 4, 'Mostrador'),  # Mango Temporada ×1
        ],
    },
]


def cargar_precios(engine):
    """Carga precios de productos desde PostgreSQL demo."""
    with engine.connect() as conn:
        rows = conn.execute(
            text('SELECT id_producto, precio_sug FROM dim_productos_y_sabores')
        ).fetchall()
    return {r[0]: float(r[1]) for r in rows}


def siguiente_ticket_id(engine):
    """Obtiene el siguiente ID de ticket disponible."""
    with engine.connect() as conn:
        result = conn.execute(text('SELECT COALESCE(MAX(id_ticket), 0) FROM ventas')).fetchone()
    return int(result[0]) + 1


def insertar_venta(engine, ticket_id, venta, precios):
    """Inserta una venta y su detalle en PostgreSQL."""
    hora = venta['hora']
    ts   = DEMO_FECHA.replace(hour=hora, minute=random.randint(10, 55), second=random.randint(0, 59))

    total = sum(
        precios.get(pid, 50.0) * round(random.uniform(0.95, 1.05), 2) * qty
        for pid, qty, _, _ in venta['items']
    )

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO ventas (id_ticket, timestamp, id_cliente, payment_method, total)
            VALUES (:tid, :ts, :cid, :pm, :tot)
        """), {'tid': ticket_id, 'ts': ts, 'cid': venta['cliente_id'],
               'pm': venta['payment_method'], 'tot': round(total, 2)})

        for prod_id, cantidad, sabor_id, tipo_v in venta['items']:
            precio_u = round(precios.get(prod_id, 50.0) * random.uniform(0.95, 1.05), 2)
            conn.execute(text("""
                INSERT INTO detalle_ventas (id_ticket, id_producto, id_sabor, cantidad, precio_unitario, tipo_venta)
                VALUES (:tid, :pid, :sid, :qty, :pu, :tv)
            """), {'tid': ticket_id, 'pid': prod_id, 'sid': sabor_id,
                   'qty': cantidad, 'pu': precio_u, 'tv': tipo_v})

    return round(total, 2)


def ejecutar_etl():
    """Ejecuta etl_demo.py en silencio y devuelve True si tuvo exito."""
    result = subprocess.run([sys.executable, ETL_SCRIPT])
    return result.returncode == 0


def verificar_mongo():
    """Muestra el conteo de documentos en cada coleccion de MongoDB."""
    print('\n   Verificando colecciones en MongoDB...')
    mongo = MongoClient(MONGO_URI)[MONGO_DB]
    colecciones = [
        'ventas_completas', 'catalogo_productos', 'clientes_perfil',
        'kpi_ventas_temporales', 'kpi_horarios_afluencia', 'kpi_productos_sabores',
        'kpi_segmentacion', 'kpi_metodos_pago',
        'kpi_mayoreo', 'kpi_operaciones_personal', 'kpi_ticket_composicion',
    ]
    print()
    for nombre in colecciones:
        count = mongo[nombre].count_documents({})
        print('     {:<30} {:>6,} docs'.format(nombre, count))
    print()
    mongo.client.close()


def separador():
    print('  ' + '─' * 45)


def main():
    #  Header 
    print('\n' + '*-' * 30)
    print('    DATENGEIST — Demo Ventas')
    if RAPIDO:
        print('  Modo RÁPIDO activado')
    MESES_ES = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    fecha_str = f'{DEMO_FECHA.day} de {MESES_ES[DEMO_FECHA.month]} de {DEMO_FECHA.year}'
    print(f'    {fecha_str} — tarde')
    print('═' * 55 + '\n')

    engine = create_engine(PG_CONN, pool_pre_ping=True)

    # Verificar que hay datos de productos
    precios = cargar_precios(engine)
    if not precios:
        print('    Error: no hay productos en datengeist_demo.')
        print('       Ejecuta primero: python setup_demo.py')
        sys.exit(1)

    # Simulamos ventas 
    totales_sesion   = []
    sabores_vendidos = []
    metodos_usados   = []

    for num, venta in enumerate(VENTAS_DEMO, start=1):
        ticket_id = siguiente_ticket_id(engine)

        # Cliente entra
        print(f'    Cliente #{num} entrando a la tienda...')
        print(f'       {venta["descripcion_cli"]}')
        print(f'    Pidió: {venta["pedido_str"]}')
        print(f'    Pagando con: {venta["payment_method"]}')

        # Registrar en PostgreSQL
        total = insertar_venta(engine, ticket_id, venta, precios)
        totales_sesion.append(total)
        sabores_vendidos += [pid for pid, _, _, _ in venta['items']]
        metodos_usados.append(venta['payment_method'])

        print(f'    Venta #{ticket_id} registrada — ${total:,.2f} MXN')
        print(f'       Cliente: {venta["cliente_nombre"]} ({venta["segmento"]})')

        # ETL
        print('    Actualizando base de datos...')
        if not RAPIDO:
            # En modo normal, correr ETL completo después de cada venta
            ok = ejecutar_etl()
            print('    Dashboard actualizado' if ok else '     ETL con advertencia — continúa')
        else:
            # En modo rápido, solo confirmar que el ticket quedó en PostgreSQL
            print('    Ticket guardado en PostgreSQL')

        separador()

    # En modo rapido, un solo ETL al final
    if RAPIDO:
        print('\n    Ejecutando ETL final...')
        ok = ejecutar_etl()
        print('    MongoDB actualizado' if ok else '     ETL con advertencia')

    engine.dispose()

    # Verificación MongoDB 
    try:
        verificar_mongo()
    except Exception as e:
        print(f'  Advertencia: no se pudo conectar a MongoDB: {e}')

    # Resumen de la sesion 
    total_sesion = sum(totales_sesion)
    metodo_top   = max(set(metodos_usados), key=metodos_usados.count)

    # Sabor mas vendido: buscar nombre en catalogo
    SABORES_DEMO = ['Vainilla', 'Chocolate', 'Fresa', 'Mango', 'Limón',
                    'Pistache', 'Nuez', 'Cajeta', 'Tamarindo', 'Coco']
    N_CATS = 5

    def sabor_de_producto(pid):
        return SABORES_DEMO[(pid - 1) // N_CATS]

    conteo_sabores = {}
    for pid, qty, _, _ in [item for v in VENTAS_DEMO for item in v['items']]:
        s = sabor_de_producto(pid)
        conteo_sabores[s] = conteo_sabores.get(s, 0) + qty
    sabor_top = max(conteo_sabores, key=conteo_sabores.get)

    print('\n' + '*-' * 30)
    print('    Total de ventas inyectadas en esta sesión demo:')
    print('  ' + '─' * 51)
    print(f'    Ventas registradas:    {len(VENTAS_DEMO)}')
    print(f'    Total recaudado:       ${total_sesion:>10,.2f} MXN')
    print(f'    Sabor más vendido:     {sabor_top}')
    print(f'    Método más usado:      {metodo_top}')
    print(f'    Fecha de la sesión:    {DEMO_FECHA.strftime("%d/%m/%Y")}')
    print('  ' + '─' * 51)
    print()
    print('  ⟶  Para repetir la demo:')
    print('       python reset_demo.py')
    print('*-' * 30 + '\n')


if __name__ == '__main__':
    main()
