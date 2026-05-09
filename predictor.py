'''
predictor.py es un script que nos permitira realizar la prediccion de ventas 
para nuestro cliente: empresa de helados.

La intencion es poder responder a las preguntas de analisis que requieren ML:
  4b. ¿Cuanto se debe producir hoy para maximizar la frescura?
  7a. ¿Cual es la proyeccion de ventas semanales y mensuales de los proximos 3 meses?

Proceso:
  1. Lee kpi_ventas_temporales (historico mensual) desde MongoDB
  2. Entrena un modelo de regresion lineal con features de estacionalidad y lag
  3. Predice los proximos 3 meses de ingresos y tickets
  4. Calcula recomendacion de produccion diaria por producto/sabor
  5. Guarda resultados en MongoDB:
       predicciones_ventas      → proyección mensual de ingresos y tickets
       predicciones_produccion  → unidades sugeridas por producto para el mes siguiente

Debe ejecutarse despues de etl.py con 'python3 predictor.py'
'''

import numpy as np
import pandas as pd
from pymongo import MongoClient
from sklearn.linear_model import LinearRegression
from datetime import date
import calendar

MONGO_URI = 'mongodb://admin:cuyos123@localhost:27017/?authSource=admin'
MONGO_DB  = 'datengeist'

mongo = MongoClient(MONGO_URI)[MONGO_DB]


def upsert_collection(name, docs):
    coll = mongo[name]
    coll.delete_many({})
    if docs:
        coll.insert_many(docs)
    print('  -> {:<32} {:>6,} docs'.format(name, len(docs)))


# 1. Cargamos el historico mensual
print(' Cargando histórico desde MongoDB...')
raw = list(mongo['kpi_ventas_temporales'].find({'tipo': 'mensual'}, {'_id': 0}))
df = pd.DataFrame(raw).sort_values(['anio', 'mes']).reset_index(drop=True)

# Verificamos que en efecto exista suficiente informacion para una prediccion
if len(df) < 12:
    print(' Se necesitan al menos 12 meses de histórico para predecir.')
    exit(1)

print('   {} meses de histórico cargados ({} – {})'.format(
    len(df),
    '{}-{:02d}'.format(df['anio'].iloc[0], df['mes'].iloc[0]),
    '{}-{:02d}'.format(df['anio'].iloc[-1], df['mes'].iloc[-1])))

# 2. Feature engineering 

# Creamos las features para indice de tiempo, seno/coseno de la estacionalidad anual, lag 1 y lag 12
# Representa el paso del tiempo en linea recta. Permite detectar si las   
# ventas tienen una tendencia general hacia arriba o hacia abajo a lo largo de los 4 anios. 
df['t']      = np.arange(len(df))
# Las ventas de una heladeria teoricamente suben en verano y bajan en invierno 
# Una linea recta no puede capturar eso, pero seno y coseno si.
df['sin12']  = np.sin(2 * np.pi * df['mes'] / 12)
df['cos12']  = np.cos(2 * np.pi * df['mes'] / 12)
# Captura ventas del mes anterior
df['lag1']   = df['total_ventas'].shift(1)
# Captura ventas del mismo mes del anio anterior
df['lag12']  = df['total_ventas'].shift(12)

# Conjunto de entrenamiento
df_train = df.dropna(subset=['lag1', 'lag12']).copy()

FEATURES = ['t', 'sin12', 'cos12', 'lag1', 'lag12']
X = df_train[FEATURES].values
y_ventas  = df_train['total_ventas'].values
y_tickets = df_train['num_tickets'].values

model_ventas  = LinearRegression().fit(X, y_ventas)
model_tickets = LinearRegression().fit(X, y_tickets)

r2_v = model_ventas.score(X, y_ventas)
r2_t = model_tickets.score(X, y_tickets)
print('   R² ventas={:.3f}  R² tickets={:.3f}'.format(r2_v, r2_t))

# 3. Predecimos los proximos 3 meses 
ultimo_anio = int(df['anio'].iloc[-1])
ultimo_mes  = int(df['mes'].iloc[-1])
ultimo_t    = int(df['t'].iloc[-1])

pred_docs = []
ventas_hist  = list(df['total_ventas'])
tickets_hist = list(df['num_tickets'])

print('\n Generando predicciones...')
for i in range(1, 4):
    # Calculamos a que mes y anio corresponde cada iteracion
    mes_pred  = (ultimo_mes + i - 1) % 12 + 1
    anio_pred = ultimo_anio + (ultimo_mes + i - 1) // 12
    # Construimos las features del mes a predecir
    t_pred    = ultimo_t + i
    # cada mes usa el anterior como insumo en lugar de inventarse un valor
    lag1      = ventas_hist[-1]
    lag12     = ventas_hist[-12] if len(ventas_hist) >= 12 else ventas_hist[0]

    # Predecimos y garantizamos que no salgan negativos
    x_pred = np.array([[t_pred,
                         np.sin(2 * np.pi * mes_pred / 12),
                         np.cos(2 * np.pi * mes_pred / 12),
                         lag1, lag12]])

    pred_v = max(0.0, float(model_ventas.predict(x_pred)[0]))
    pred_t = max(0,   int(model_tickets.predict(x_pred)[0]))

    # Agregamos la prediccion al historial
    ventas_hist.append(pred_v)
    tickets_hist.append(pred_t)

    dias_mes     = calendar.monthrange(anio_pred, mes_pred)[1]
    ticket_prom  = round(pred_v / pred_t, 2) if pred_t else 0.0

    MESES_NOM = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio',
                 'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

    pred_docs.append({
        'tipo': 'mensual',
        'periodo':      '{}-{:02d}'.format(anio_pred, mes_pred),
        'anio':         anio_pred,
        'mes':          mes_pred,
        'mes_nombre':   MESES_NOM[mes_pred],
        'total_ventas': round(pred_v, 2),
        'num_tickets':  pred_t,
        'ticket_prom':  ticket_prom,
        'dias_mes':     dias_mes,
        'ventas_diarias_estimadas': round(pred_v / dias_mes, 2),
        'tickets_diarios_estimados': round(pred_t / dias_mes, 1),
        'r2_modelo':    round(r2_v, 4),
    })
    print('   {} → ${:,.0f} ingresos | {:,} tickets'.format(
        '{}-{:02d}'.format(anio_pred, mes_pred), pred_v, pred_t))

upsert_collection('predicciones_ventas', pred_docs)

# 4. Recomendacion de produccion diaria (proximo mes) 

# Calculamos las unidades diarias sugeridas por producto basandonos en:
# mix historico de cada producto en el total de unidades vendidas
# por tickets diarios estimados del proximo mes

print('\n Calculando recomendaciones de producción...')

raw_prod = list(mongo['kpi_productos_sabores'].find({}, {'_id': 0}))
if not raw_prod: # Verificamos que existan los datos
    print(' kpi_productos_sabores vacío.')
    exit(1)

df_prod = pd.DataFrame(raw_prod)
total_unidades = float(df_prod['unidades_vendidas'].sum())
df_prod['mix_pct'] = df_prod['unidades_vendidas'] / total_unidades

# Proximo mes
siguiente = pred_docs[0]
tickets_dia = siguiente['tickets_diarios_estimados']
# Promedio historico de unidades por ticket
avg_u_ticket = float(
    pd.DataFrame(list(mongo['kpi_ticket_composicion'].find({'tipo': 'resumen_global'}, {'_id': 0})))
    ['unidades_prom'].iloc[0]
) if mongo['kpi_ticket_composicion'].count_documents({'tipo': 'resumen_global'}) else 2.0

unidades_dia_total = tickets_dia * avg_u_ticket

prod_docs = []
for _, r in df_prod.iterrows():
    unidades_dia = round(float(r['mix_pct']) * unidades_dia_total, 1)
    prod_docs.append({
        'periodo':          siguiente['periodo'],
        'id_producto':      int(r['id_producto']),
        'sabor':            r['sabor'],
        'categoria':        r['categoria'],
        'ranking_ventas':   int(r['ranking_ventas']),
        'mix_pct':          round(float(r['mix_pct']) * 100, 2),
        'unidades_dia_sugeridas': unidades_dia,
        'base_calculo': {
            'tickets_dia_estimados': tickets_dia,
            'unidades_prom_ticket': avg_u_ticket,
        },
    })

prod_docs.sort(key=lambda x: x['ranking_ventas'])
upsert_collection('predicciones_produccion', prod_docs)

# Resumen de las predicciones
print('\n' + '*-'*30)
print('  RESUMEN — predictor.py')
print('*-'*30)
print('  Colecciones generadas:')
print('    predicciones_ventas     → proyección 3 meses')
print('    predicciones_produccion → unidades/día por producto')
print('\n  Top 5 productos a producir mañana:')
top5 = sorted(prod_docs, key=lambda x: x['unidades_dia_sugeridas'], reverse=True)[:5]
for p in top5:
    print('    {:<12} {:<20} {:.1f} unidades/día'.format(
        p['sabor'], '(' + p['categoria'] + ')', p['unidades_dia_sugeridas']))
print('\n Predicciones listas en MongoDB :)')
