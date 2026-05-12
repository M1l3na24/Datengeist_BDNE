"""
setup_demo.py — Datengeist Demo
Crea el entorno de demostración desde cero:
  - PostgreSQL: base datengeist_demo con 6 tablas, ~1,800 tickets (Oct 2024–Mar 2025)
  - 5 clientes, 10 sabores, 6 meses de datos estacionales
Ejecutar: python setup_demo.py
"""

import random, math
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

random.seed(2024)
np.random.seed(2024)

# Conexiones ────────────────────────────────────────────────────────────────
PG_ADMIN = 'postgresql+psycopg2://admin:cuyos123@127.0.0.1:5433/postgres'
PG_DEMO  = 'postgresql+psycopg2://admin:cuyos123@127.0.0.1:5433/datengeist_demo'

# Constantes del demo 
FECHA_INI = date(2024, 10, 1)
FECHA_FIN = date(2025, 3, 31)
FECHAS    = [FECHA_INI + timedelta(days=i)
             for i in range((FECHA_FIN - FECHA_INI).days + 1)]

SABORES_DEMO = [
    'Vainilla', 'Chocolate', 'Fresa', 'Mango', 'Limón',
    'Pistache', 'Nuez', 'Cajeta', 'Tamarindo', 'Coco',
]
CATS = [
    ('Artesanal',    18.0, 45.0),
    ('Premium',      25.0, 65.0),
    ('Bajo en azúcar', 22.0, 55.0),
    ('Niños',        12.0, 30.0),
    ('Temporada',    20.0, 50.0),
]
INGREDIENTES = {
    'Vainilla':   'leche, crema, azúcar, vainilla natural, yemas de huevo',
    'Chocolate':  'leche, crema, cacao 70%, azúcar, lecitina de soya',
    'Fresa':      'leche, crema, fresa fresca, azúcar, jugo de limón',
    'Mango':      'leche, crema, pulpa de mango ataulfo, azúcar',
    'Limón':      'leche, crema, jugo de limón, ralladura, azúcar',
    'Pistache':   'leche, crema, pasta de pistache, azúcar, sal de mar',
    'Nuez':       'leche, crema, nuez pecana tostada, caramelo, azúcar',
    'Cajeta':     'leche de cabra, azúcar, canela, vainilla',
    'Tamarindo':  'leche, crema, concentrado de tamarindo, chile piquín, azúcar',
    'Coco':       'leche de coco, crema, coco rallado, azúcar, vainilla',
}

CLIENTES_DEMO = [
    (1, 'Restaurante El Sabor',     'Restaurante', 'VIP',       'Semanal',    450.0, 'Tamarindo', 'Colonia Centro'),
    (2, 'María González',           'Familiar',    'Frecuente', 'Quincenal',  220.0, 'Vainilla',  'Colonia Roma'),
    (3, 'Pastelería La Dulce Vida', 'Cafetería',   'Frecuente', 'Semanal',    310.0, 'Chocolate', 'Polanco'),
    (4, 'Colegio Benito Juárez',    'Corporativo', 'Ocasional', 'Mensual',    180.0, 'Fresa',     'Naucalpan'),
    (5, 'Juan Ramírez',             'Particular',  'Nuevo',     'Esporádico',  95.0, 'Mango',     'Xochimilco'),
]

# Pesos de seleccion por cliente en ventas (cuanto compra cada uno)
PESOS_CLIENTES = [0.30, 0.25, 0.25, 0.12, 0.08]

FESTIVOS_DEMO = {
    (10, 31): 'Halloween',
    (11,  1): 'Día de Muertos',
    (11,  2): 'Día de Muertos',
    (11, 20): 'Revolución Mexicana',
    (12, 12): 'Virgen de Guadalupe',
    (12, 24): 'Nochebuena',
    (12, 25): 'Navidad',
    (12, 31): 'Fin de Año',
    ( 1,  1): 'Año Nuevo',
    ( 2,  3): 'Día de la Constitución',
    ( 3, 17): 'Natalicio de Benito Juárez',
}
METODOS_PAGO = ['Efectivo', 'Tarjeta débito', 'Tarjeta crédito', 'Transferencia', 'QR']
TIPOS_VENTA  = ['Mostrador', 'Para llevar', 'Pedido online', 'Mayoreo']

# Distribucion de horas pico a las 13-15h y 17-19h
_horas_raw = [0]*8 + [0.01]*2 + [0.04,0.07,0.10,0.12,0.10,0.09,0.08,0.10,0.10,0.09,0.06,0.03,0.01,0]
_suma_h    = sum(_horas_raw)
HORAS_PROB = [p / _suma_h for p in _horas_raw]


def banner(texto):
    print('\n' + '*-' * 30)
    print(f'  {texto}')
    print('*-' * 30)


def ok(texto):
    print(f'  ok:  {texto}')


def step(texto):
    print(f'\n  ⟶  {texto}')


# Funciones de clima 
def temperatura(fecha):
    dia   = fecha.timetuple().tm_yday
    base  = 20 + 7 * math.sin(2 * math.pi * (dia - 30) / 365)
    lluvia = -4 * max(0, math.sin(2 * math.pi * (dia - 150) / 150))
    return round(max(8.0, min(35.0, base + lluvia + np.random.normal(0, 1.2))), 2)


def precipitacion(fecha):
    mes = fecha.month
    if mes in (6, 7, 8, 9) and random.random() < 0.60:
        return round(np.random.exponential(scale=12), 2)
    if mes in (5, 10) and random.random() < 0.15:
        return round(np.random.exponential(scale=4), 2)
    return 0.0


def mult_ventas(temp, prec, festivo, dia_semana):
    f = 1.0
    f *= 1 + max(0, (temp - 20) * 0.03)
    if prec > 25:    f *= 0.60
    elif prec > 10:  f *= 0.80
    if festivo:      f *= random.uniform(1.5, 2.2)
    if dia_semana in (5, 6): f *= 1.30
    elif dia_semana == 4:    f *= 1.15
    return f


# Script principal 
def main():
    banner(' Datengeist — Configurando Entorno Demo')

    # Creamos base de datos 
    step('Creando base de datos datengeist_demo en PostgreSQL...')
    engine_admin = create_engine(PG_ADMIN, isolation_level='AUTOCOMMIT')
    with engine_admin.connect() as conn:
        conn.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = 'datengeist_demo' AND pid <> pg_backend_pid()"
        ))
        conn.execute(text('DROP DATABASE IF EXISTS datengeist_demo'))
        conn.execute(text('CREATE DATABASE datengeist_demo'))
    engine_admin.dispose()
    ok('Base de datos creada')

    # Creamos tablas 
    step('Creando las 6 tablas...')
    engine = create_engine(PG_DEMO, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE Dim_Productos_y_Sabores (
            ID_Producto   INT PRIMARY KEY,
            Categoria     VARCHAR(50),
            costo_prod_lt DECIMAL(10,2),
            precio_sug    DECIMAL(10,2),
            ingredientes  TEXT
        );
        CREATE TABLE Dim_Clientes_y_Segmentos (
            ID_Cliente        INT PRIMARY KEY,
            Nombre            VARCHAR(100),
            Giro              VARCHAR(50),
            Segmento          VARCHAR(50),
            frecuencia_compra VARCHAR(50),
            ticket_prom       DECIMAL(10,2),
            sabor_preferido   VARCHAR(50),
            ubicacion         VARCHAR(255)
        );
        CREATE TABLE Ventas (
            ID_Ticket      INT PRIMARY KEY,
            Timestamp      TIMESTAMP,
            ID_Cliente     INT REFERENCES Dim_Clientes_y_Segmentos(ID_Cliente),
            payment_method VARCHAR(50),
            total          DECIMAL(10,2)
        );
        CREATE TABLE Detalle_ventas (
            ID_Ticket       INT REFERENCES Ventas(ID_Ticket),
            ID_Producto     INT REFERENCES Dim_Productos_y_Sabores(ID_Producto),
            ID_Sabor        INT,
            Cantidad        INT,
            Precio_Unitario DECIMAL(10,2),
            Tipo_Venta      VARCHAR(50),
            PRIMARY KEY (ID_Ticket, ID_Producto, ID_Sabor)
        );
        CREATE TABLE Operaciones_y_Personal (
            Fecha          DATE,
            Turno          VARCHAR(20),
            Num_empleados  INT,
            payment_method VARCHAR(50),
            costo_hora     DECIMAL(10,2),
            PRIMARY KEY (Fecha, Turno)
        );
        CREATE TABLE Variables_Externas (
            Fecha                    DATE PRIMARY KEY,
            Temperatura              DECIMAL(5,2),
            Precipitacion            DECIMAL(5,2),
            Eventos_Festivos_Locales TEXT
        );
        """))
    ok('6 tablas creadas')

    # Variables externas 
    step(f'Generando datos climáticos ({len(FECHAS)} días: Oct 2024–Mar 2025)...')
    vars_rows = []
    for f in FECHAS:
        temp  = temperatura(f)
        prec  = precipitacion(f)
        fest  = FESTIVOS_DEMO.get((f.month, f.day), '')
        vars_rows.append({
            'fecha': f, 'temperatura': temp,
            'precipitacion': prec, 'eventos_festivos_locales': fest,
        })
    pd.DataFrame(vars_rows).to_sql('variables_externas', engine, if_exists='append', index=False)
    festivos_con_datos = sum(1 for r in vars_rows if r['eventos_festivos_locales'])
    ok(f'{len(vars_rows)} fechas · {festivos_con_datos} fechas con festivo')

    # Clientes 
    step('Insertando 5 clientes demo...')
    cli_rows = [
        {
            'id_cliente': cid, 'nombre': nom, 'giro': giro,
            'segmento': seg, 'frecuencia_compra': freq,
            'ticket_prom': tp, 'sabor_preferido': sab, 'ubicacion': ubic,
        }
        for cid, nom, giro, seg, freq, tp, sab, ubic in CLIENTES_DEMO
    ]
    pd.DataFrame(cli_rows).to_sql(
        'dim_clientes_y_segmentos', engine, if_exists='append', index=False)
    nombres = ' · '.join(r['nombre'].split()[0] for r in cli_rows)
    ok(f'Clientes: {nombres}')

    # Productos 
    step(f'Insertando {len(SABORES_DEMO) * len(CATS)} productos (10 sabores × 5 categorías)...')
    prod_rows = []
    pid = 1
    for sabor in SABORES_DEMO:
        for cat, costo_base, precio_base in CATS:
            prod_rows.append({
                'id_producto':   pid,
                'categoria':     cat,
                'costo_prod_lt': round(costo_base + random.uniform(-2, 2), 2),
                'precio_sug':    round(precio_base + random.uniform(-3, 3), 2),
                'ingredientes':  INGREDIENTES.get(sabor, 'leche, crema, azúcar'),
            })
            pid += 1
    df_prod = pd.DataFrame(prod_rows)
    df_prod.to_sql('dim_productos_y_sabores', engine, if_exists='append', index=False)
    ok(f'{len(prod_rows)} productos listos')

    # Ventas y Detalle 
    step('Generando ~1,800 tickets de venta (Oct 2024–Mar 2025)...')
    producto_ids  = df_prod['id_producto'].tolist()
    cliente_ids   = [r['id_cliente'] for r in cli_rows]
    vars_lookup   = {r['fecha']: r for r in vars_rows}
    precio_lookup = {r['id_producto']: r['precio_sug'] for r in prod_rows}

    ventas_rows, detalle_rows = [], []
    ticket_id = 1

    for f in FECHAS:
        r         = vars_lookup[f]
        temp      = r['temperatura']
        prec      = r['precipitacion']
        festivo   = r['eventos_festivos_locales']
        dia_sem   = f.weekday()
        mult      = mult_ventas(temp, prec, festivo, dia_sem)
        n_tickets = max(3, int(np.random.poisson(9 * mult)))

        for _ in range(n_tickets):
            hora   = int(np.random.choice(range(24), p=HORAS_PROB))
            ts     = datetime(f.year, f.month, f.day,
                              hora, random.randint(0, 59), random.randint(0, 59))
            cli_id = random.choices(cliente_ids, weights=PESOS_CLIENTES)[0]
            pago   = random.choices(
                METODOS_PAGO, weights=[0.35, 0.25, 0.20, 0.10, 0.10])[0]

            # Es un pedido de mayoreo si es el colegio o el restaurante con alta prob
            es_mayoreo = cli_id in (1, 4) and random.random() < 0.30
            tipo_v     = 'Mayoreo' if es_mayoreo else random.choices(
                ['Mostrador', 'Para llevar', 'Pedido online'],
                weights=[0.60, 0.28, 0.12])[0]

            n_prods = random.choices([1, 2, 3, 4], weights=[0.45, 0.30, 0.17, 0.08])[0]
            prods_t = random.sample(producto_ids, min(n_prods, len(producto_ids)))
            total   = 0.0

            for prod_id in prods_t:
                sabor_idx  = (prod_id - 1) // len(CATS)  # 0-9
                cantidad   = random.choices([1, 2, 3, 4], weights=[0.55, 0.28, 0.12, 0.05])[0]
                precio_u   = round(precio_lookup[prod_id] * random.uniform(0.95, 1.05), 2)
                total     += precio_u * cantidad
                detalle_rows.append({
                    'id_ticket':       ticket_id,
                    'id_producto':     prod_id,
                    'id_sabor':        sabor_idx + 1,
                    'cantidad':        cantidad,
                    'precio_unitario': precio_u,
                    'tipo_venta':      tipo_v,
                })

            ventas_rows.append({
                'id_ticket':      ticket_id,
                'timestamp':      ts,
                'id_cliente':     cli_id,
                'payment_method': pago,
                'total':          round(total, 2),
            })
            ticket_id += 1

    df_ventas  = pd.DataFrame(ventas_rows)
    df_detalle = pd.DataFrame(detalle_rows)
    df_ventas.to_sql('ventas',          engine, if_exists='append', index=False)
    df_detalle.to_sql('detalle_ventas', engine, if_exists='append', index=False)
    ok(f'{len(ventas_rows):,} tickets y {len(detalle_rows):,} líneas de detalle')

    # Operaciones y personal 
    step('Insertando operaciones y personal...')
    TURNOS   = ['Matutino', 'Vespertino', 'Nocturno']
    ops_rows = []
    for f in FECHAS:
        r       = vars_lookup[f]
        temp    = r['temperatura']
        festivo = r['eventos_festivos_locales']
        finde   = f.weekday() in (5, 6)
        for turno in TURNOS:
            base = 4 if turno == 'Vespertino' else 3
            if finde or festivo: base += random.randint(1, 2)
            if temp > 28:        base += 1
            ops_rows.append({
                'fecha':          f,
                'turno':          turno,
                'num_empleados':  max(2, base + random.randint(-1, 1)),
                'payment_method': random.choices(
                    METODOS_PAGO, weights=[0.35, 0.25, 0.20, 0.10, 0.10])[0],
                'costo_hora':     round(random.uniform(42.0, 65.0), 2),
            })
    pd.DataFrame(ops_rows).to_sql(
        'operaciones_y_personal', engine, if_exists='append', index=False)
    ok(f'{len(ops_rows)} registros de operaciones ({len(FECHAS)} días × 3 turnos)')

    engine.dispose()

    # Resumen 
    banner('  Entorno demo listo')
    print(f'  Base de datos:  datengeist_demo (PostgreSQL 5433)')
    print(f'  Período:        1 Oct 2024 → 31 Mar 2025 ({len(FECHAS)} días)')
    print(f'  Tickets:        {len(ventas_rows):,}')
    print(f'  Clientes:       5   (VIP · Frecuente ×2 · Ocasional · Nuevo)')
    print(f'  Sabores:        10')
    print(f'  Festivos:       {festivos_con_datos} fechas especiales')
    print()
    print('*-' * 30)


if __name__ == '__main__':
    main()
