"""
generador.py es un script que permite generar datos sinteticos
para nuestro proyecto Datengeist 

Info relevante:
  FECHA_INI  : 2021-01-01  (4 anios de datos)
  N_CLIENTES : 3_000       
  VENTAS_BASE: 700       
Resultado esperado: aprox. 1.2 M tickets (1 GB en MongoDB)
"""

import pandas as pd
import numpy as np
from faker import Faker
from tqdm import tqdm
import random, math, os, shutil
from datetime import date, timedelta, datetime
from sqlalchemy import create_engine, text

SEED       = 42
FECHA_INI  = date(2021, 1, 1)   
FECHA_FIN  = date(2024, 12, 31)
N_CLIENTES = 3_000            
OUTPUT_DIR = './csv_output' 

random.seed(SEED)
np.random.seed(SEED)
fake = Faker('es_MX')
Faker.seed(SEED)

# Limpia el directorio de salida para evitar duplicados si existen re-ejecuciones
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR)
fechas = pd.date_range(FECHA_INI, FECHA_FIN, freq='D')

# Funciones auxiliares para la estacionalidad
def temperatura_diaria(fecha):
    dia = fecha.timetuple().tm_yday
    base = 20 + 7 * math.sin(2 * math.pi * (dia - 30) / 365)
    lluvia = -4 * max(0, math.sin(2 * math.pi * (dia - 150) / 150))
    return round(max(8.0, min(35.0, base + lluvia + np.random.normal(0, 1.2))), 2)

def precipitacion_diaria(fecha):
    mes = fecha.month
    if mes in (6, 7, 8, 9):
        if random.random() < 0.60:
            return round(np.random.exponential(scale=12), 2)
    elif mes in (5, 10):
        if random.random() < 0.15:
            return round(np.random.exponential(scale=4), 2)
    return 0.0

# Lo siguiente es para considerar festividades mexicanas
FESTIVOS = {
    (1,1):'Año Nuevo',(2,5):'Día de la Constitución',(3,21):'Natalicio de Juárez',
    (4,30):'Día del Niño',(5,1):'Día del Trabajo',(5,10):'Día de las Madres',
    (5,15):'Día del Maestro',(9,15):'Víspera de Independencia',
    (9,16):'Día de Independencia',(10,31):'Halloween',
    (11,1):'Día de Muertos',(11,2):'Día de Muertos',
    (11,20):'Revolución Mexicana',(12,12):'Virgen de Guadalupe',
    (12,24):'Nochebuena',(12,25):'Navidad',(12,31):'Fin de Año'}

SEMANA_SANTA = {
    2021: [date(2021,3,29),date(2021,3,30),date(2021,3,31),date(2021,4,1),date(2021,4,2)],
    2022: [date(2022,4,11),date(2022,4,12),date(2022,4,13),date(2022,4,14),date(2022,4,15)],
    2023: [date(2023,4,3),date(2023,4,4),date(2023,4,5),date(2023,4,6),date(2023,4,7)],
    2024: [date(2024,3,25),date(2024,3,26),date(2024,3,27),date(2024,3,28),date(2024,3,29)]}
SS_SET = set(d for lst in SEMANA_SANTA.values() for d in lst)

def evento_festivo(fecha):
    if fecha in SS_SET: return 'Semana Santa'
    return FESTIVOS.get((fecha.month, fecha.day), '')

def multiplicador_ventas(temp, precip, festivo, dia_semana):
    factor = 1.0
    factor *= 1 + max(0, (temp - 20) * 0.03)
    if precip > 25:   factor *= 0.60
    elif precip > 10: factor *= 0.80
    if festivo:       factor *= random.uniform(1.5, 2.2)
    if dia_semana in (5, 6): factor *= 1.30
    elif dia_semana == 4:    factor *= 1.15
    return factor

# 1. Variables Externas
print(' Generando Variables_Externas...')
vars_ext = []
for f in tqdm(fechas):
    fdate = f.date()
    temp  = temperatura_diaria(fdate)
    prec  = precipitacion_diaria(fdate)
    vars_ext.append({'Fecha':fdate,'Temperatura':temp,'Precipitacion':prec,
                     'Eventos_Festivos_Locales':evento_festivo(fdate)})
df_vars = pd.DataFrame(vars_ext)
df_vars.to_csv(f'{OUTPUT_DIR}/Variables_Externas.csv', index=False)
print(f'    {len(df_vars)} filas → Variables_Externas.csv')

# 2. Dim_Productos_y_Sabores 
print(' Generando Dim_Productos_y_Sabores...')
SABORES = ['Vainilla','Chocolate','Fresa','Mango','Limón','Pistache','Nuez',
           'Cajeta','Guanábana','Mamey','Tamarindo','Coco','Frambuesa','Elote','Tequila']
CATS = [('Artesanal',18.0,45.0),('Premium',25.0,65.0),('Bajo en azúcar',22.0,55.0),
        ('Niños',12.0,30.0),('Temporada',20.0,50.0)]
INGREDIENTES = {
    'Vainilla':'leche, crema, azúcar, vainilla natural, yemas de huevo',
    'Chocolate':'leche, crema, cacao 70%, azúcar, lecitina de soya',
    'Fresa':'leche, crema, fresa fresca, azúcar, jugo de limón',
    'Mango':'leche, crema, pulpa de mango ataulfo, azúcar',
    'Limón':'leche, crema, jugo de limón, ralladura, azúcar',
    'Pistache':'leche, crema, pasta de pistache, azúcar, sal de mar',
    'Nuez':'leche, crema, nuez pecana tostada, caramelo, azúcar',
    'Cajeta':'leche de cabra, azúcar, canela, vainilla',
    'Guanábana':'leche, crema, pulpa de guanábana, azúcar, limón',
    'Mamey':'leche, crema, pulpa de mamey, azúcar, canela',
    'Tamarindo':'leche, crema, concentrado de tamarindo, chile piquín, azúcar',
    'Coco':'leche de coco, crema, coco rallado, azúcar, vainilla',
    'Frambuesa':'leche, crema, frambuesa, azúcar, pectina natural',
    'Elote':'leche, crema, elote dulce, azúcar, mantequilla',
    'Tequila':'leche, crema, tequila reposado, limón, sal de gusano, azúcar'}

productos, pid = [], 1
for sabor in SABORES:
    for cat, costo, precio in CATS:
        productos.append({'ID_Producto':pid,'Categoria':cat,
                          'costo_prod_lt':round(costo+random.uniform(-2,2),2),
                          'precio_sug':round(precio+random.uniform(-3,3),2),
                          'ingredientes':INGREDIENTES.get(sabor,'leche, crema, azúcar')})
        pid += 1
df_prod = pd.DataFrame(productos)
df_prod.to_csv(f'{OUTPUT_DIR}/Dim_Productos_y_Sabores.csv', index=False)
print(f'    {len(df_prod)} filas → Dim_Productos_y_Sabores.csv')

# 3. Dim_Clientes_y_Segmentos 
print(' Generando Dim_Clientes_y_Segmentos...')
GIROS = ['Familiar','Corporativo','Revendedor','Cafetería','Restaurante','Particular']
SEGS  = ['VIP','Frecuente','Ocasional','Nuevo']
FREQS = ['Semanal','Quincenal','Mensual','Esporádico']
UBICS = ['Colonia Centro','Colonia Roma','Colonia Condesa','Polanco',
         'Coyoacán','Xochimilco','Tlalpan','Iztapalapa','Naucalpan','Ecatepec',
         'Tlalnepantla','Toluca','Querétaro Centro','Aguascalientes Norte','León Guanajuato']
SEG_TICKET = {'VIP':(300,800),'Frecuente':(150,400),'Ocasional':(80,250),'Nuevo':(50,150)}

clientes = []
for cid in range(1, N_CLIENTES + 1):
    seg  = random.choices(SEGS,  weights=[0.10,0.30,0.40,0.20])[0]
    giro = random.choices(GIROS, weights=[0.35,0.15,0.10,0.15,0.10,0.15])[0]
    t_min, t_max = SEG_TICKET[seg]
    clientes.append({
        'ID_Cliente': cid,
        'Nombre': fake.company() if giro in ('Corporativo','Cafetería','Restaurante','Revendedor') else fake.name(),
        'Giro': giro, 'Segmento': seg,
        'frecuencia_compra': random.choices(FREQS, weights=[0.20,0.25,0.35,0.20])[0],
        'ticket_prom': round(random.uniform(t_min, t_max), 2),
        'sabor_preferido': random.choice(SABORES),
        'ubicacion': random.choice(UBICS)})
df_cli = pd.DataFrame(clientes)
df_cli.to_csv(f'{OUTPUT_DIR}/Dim_Clientes_y_Segmentos.csv', index=False)
print(f'    {len(df_cli)} filas → Dim_Clientes_y_Segmentos.csv')

# 4. y 5. Ventas + Detalle_ventas 
print(' Generando Ventas y Detalle_ventas (tarda un poco)...')

METODOS = ['Efectivo','Tarjeta débito','Tarjeta crédito','Transferencia','QR']
TIPOS_V = ['Mostrador','Para llevar','Pedido online','Mayoreo']
SABOR_IDS   = list(range(1, len(SABORES) + 1))
PRODUCTO_IDS = df_prod['ID_Producto'].tolist()
CLIENTE_IDS  = df_cli['ID_Cliente'].tolist()
vars_lookup  = df_vars.set_index('Fecha')

VENTAS_BASE = 700   

# Distribucion de horarios con picos en 12-15h y 17-20h
horas_prob_raw = [0]*8 + [0.01]*2 + [0.04,0.07,0.10,0.12,0.10,
                  0.09,0.08,0.10,0.10,0.09,0.06,0.03,0.01] + [0]*1
suma_h = sum(horas_prob_raw)
horas_prob = [p/suma_h for p in horas_prob_raw]

ventas_rows, detalle_rows, ticket_id = [], [], 1
ventas_primera, detalle_primera = True, True

for f in tqdm(fechas):
    fdate      = f.date()
    row_ext    = vars_lookup.loc[fdate]
    temp       = float(row_ext['Temperatura'])
    precip     = float(row_ext['Precipitacion'])
    festivo    = str(row_ext['Eventos_Festivos_Locales'])
    dia_semana = f.dayofweek
    mult       = multiplicador_ventas(temp, precip, festivo, dia_semana)
    n_tickets  = max(50, int(np.random.poisson(VENTAS_BASE * mult)))

    for _ in range(n_tickets):
        hora = np.random.choice(range(24), p=horas_prob)
        ts   = datetime(fdate.year, fdate.month, fdate.day,
                        hora, random.randint(0,59), random.randint(0,59))
        cid  = random.choice(CLIENTE_IDS)
        pago = random.choices(METODOS, weights=[0.35,0.25,0.20,0.10,0.10])[0]
        n_prods = random.choices([1,2,3,4,5,6], weights=[0.40,0.30,0.15,0.08,0.04,0.03])[0]
        prods_t = random.sample(PRODUCTO_IDS, min(n_prods, len(PRODUCTO_IDS)))
        total   = 0.0
        for pid_t in prods_t:
            prod_row   = df_prod[df_prod['ID_Producto'] == pid_t].iloc[0]
            sabor_id   = random.choice(SABOR_IDS)
            cantidad   = random.choices([1,2,3,4], weights=[0.55,0.28,0.12,0.05])[0]
            precio_u   = round(prod_row['precio_sug'] * random.uniform(0.95, 1.05), 2)
            tipo_v     = random.choices(TIPOS_V, weights=[0.55,0.25,0.12,0.08])[0]
            subtotal   = round(precio_u * cantidad, 2)
            total     += subtotal
            detalle_rows.append({'ID_Ticket':ticket_id,'ID_Producto':pid_t,
                                  'ID_Sabor':sabor_id,'Cantidad':cantidad,
                                  'Precio_Unitario':precio_u,'Tipo_Venta':tipo_v})
        ventas_rows.append({'ID_Ticket':ticket_id,'Timestamp':ts,
                             'ID_Cliente':cid,'payment_method':pago,'total':round(total,2)})
        ticket_id += 1

    if len(ventas_rows) >= 90_000:
        pd.DataFrame(ventas_rows).to_csv(f'{OUTPUT_DIR}/Ventas.csv',
            mode='w' if ventas_primera else 'a', index=False, header=ventas_primera)
        ventas_primera = False
        ventas_rows = []
    if len(detalle_rows) >= 250_000:
        pd.DataFrame(detalle_rows).to_csv(f'{OUTPUT_DIR}/Detalle_ventas.csv',
            mode='w' if detalle_primera else 'a', index=False, header=detalle_primera)
        detalle_primera = False
        detalle_rows = []

if ventas_rows:
    pd.DataFrame(ventas_rows).to_csv(f'{OUTPUT_DIR}/Ventas.csv',
        mode='w' if ventas_primera else 'a', index=False, header=ventas_primera)
if detalle_rows:
    pd.DataFrame(detalle_rows).to_csv(f'{OUTPUT_DIR}/Detalle_ventas.csv',
        mode='w' if detalle_primera else 'a', index=False, header=detalle_primera)

n_tickets_total = ticket_id - 1
print(f'    {n_tickets_total:,} tickets → Ventas.csv + Detalle_ventas.csv')

# 6. Operaciones_y_Personal 
print(' Generando Operaciones_y_Personal...')
TURNOS = ['Matutino','Vespertino','Nocturno']
ops_rows = []
for f in tqdm(fechas):
    fdate   = f.date()
    row_ext = vars_lookup.loc[fdate]
    temp    = float(row_ext['Temperatura'])
    festivo = str(row_ext['Eventos_Festivos_Locales'])
    es_finde = f.dayofweek in (5, 6)
    for turno in TURNOS:
        base_emp = 4 if turno == 'Vespertino' else 3
        if es_finde or festivo: base_emp += random.randint(1,3)
        if temp > 28: base_emp += 1
        ops_rows.append({'Fecha':fdate,'Turno':turno,
                          'Num_empleados':max(2, base_emp + random.randint(-1,1)),
                          'payment_method':random.choices(METODOS, weights=[0.35,0.25,0.20,0.10,0.10])[0],
                          'costo_hora':round(random.uniform(42.0,65.0),2)})
df_ops = pd.DataFrame(ops_rows)
df_ops.to_csv(f'{OUTPUT_DIR}/Operaciones_y_Personal.csv', index=False)
print(f'    {len(df_ops)} filas → Operaciones_y_Personal.csv')

# Resumen de los csv creados
print('\n' + '*-'*30)
print('  RESUMEN')
print('*-'*30)
archivos = ['Variables_Externas.csv','Dim_Productos_y_Sabores.csv',
            'Dim_Clientes_y_Segmentos.csv','Ventas.csv',
            'Detalle_ventas.csv','Operaciones_y_Personal.csv']
total_mb = 0
for arch in archivos:
    ruta = f'{OUTPUT_DIR}/{arch}'
    if os.path.exists(ruta):
        mb   = os.path.getsize(ruta) / 1_048_576
        filas = sum(1 for _ in open(ruta, encoding='utf-8')) - 1
        total_mb += mb
        print('  -  {:<35} {:>10,} filas   {:>6.1f} MB'.format(arch, filas, mb))
print('-'*55)
print('  TOTAL  {:>40.1f} MB'.format(total_mb))

# Cargamos a PostgreSQL 
print('\n Cargando CSVs en PostgreSQL...')
PG_CONN = 'postgresql+psycopg2://admin:cuyos123@127.0.0.1:5433/datengeist'
engine  = create_engine(PG_CONN)

# Truncamos en orden seguro para evitar errores (FK: detalle_ventas → ventas → dims)
with engine.begin() as conn:
    conn.execute(text(
        'TRUNCATE TABLE detalle_ventas, ventas, operaciones_y_personal, '
        'variables_externas, dim_clientes_y_segmentos, dim_productos_y_sabores CASCADE'
    ))

TABLAS = [
    (f'{OUTPUT_DIR}/Variables_Externas.csv',       'variables_externas'),
    (f'{OUTPUT_DIR}/Dim_Productos_y_Sabores.csv',  'dim_productos_y_sabores'),
    (f'{OUTPUT_DIR}/Dim_Clientes_y_Segmentos.csv', 'dim_clientes_y_segmentos'),
    (f'{OUTPUT_DIR}/Ventas.csv',                   'ventas'),
    (f'{OUTPUT_DIR}/Detalle_ventas.csv',            'detalle_ventas'),
    (f'{OUTPUT_DIR}/Operaciones_y_Personal.csv',   'operaciones_y_personal')]
for csv_path, table_name in TABLAS:
    print(f'   {table_name}...')
    for chunk in pd.read_csv(csv_path, chunksize=50_000):
        chunk.columns = chunk.columns.str.lower()
        chunk.to_sql(table_name, engine, if_exists='append', index=False)
    print(f'   {table_name} lista')

print('\n ¡Datos cargados en PostgreSQL!')
