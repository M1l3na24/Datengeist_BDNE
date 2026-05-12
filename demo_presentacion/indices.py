"""
indices.py — Datengeist Demo
Crea los índices en todas las colecciones de MongoDB datengeist_demo.

Ejecutar después de oro.py:
  python indices.py
"""

from pymongo import MongoClient

MONGO_URI = 'mongodb://admin:cuyos123@localhost:27017/?authSource=admin'
MONGO_DB  = 'datengeist_demo'


def crear_indices(db, coleccion, indices):
    col = db[coleccion]
    for campos, opciones in indices:
        col.create_index(campos, **opciones)
    total = col.index_information()
    print('  {:<30} {} índices'.format(coleccion, len(total) - 1))  # -1 excluye _id


def main():
    print('\n' + '*-' * 30)
    print('   ÍNDICES — MongoDB datengeist_demo')
    print('*-' * 30 + '\n')

    mongo = MongoClient(MONGO_URI)
    db    = mongo[MONGO_DB]

    crear_indices(db, 'ventas_completas', [
        ([('id_ticket',                1)], {'unique': True}),
        ([('timestamp',                1)], {}),
        ([('anio',                     1)], {}),
        ([('mes',                      1)], {}),
        ([('cliente_segmento',         1)], {}),
        ([('cliente_giro',             1)], {}),
        ([('id_cliente',               1)], {}),
        ([('temperatura',              1)], {}),
        ([('eventos_festivos_locales', 1)], {}),
        ([('payment_method',           1)], {}),
    ])

    crear_indices(db, 'catalogo_productos', [
        ([('id_producto',    1)], {'unique': True}),
        ([('categoria',      1)], {}),
        ([('rentabilidad_pct', -1)], {}),
        ([('margen_bruto',  -1)], {}),
    ])

    crear_indices(db, 'clientes_perfil', [
        ([('id_cliente',             1)], {'unique': True}),
        ([('segmento',               1)], {}),
        ([('giro',                   1)], {}),
        ([('ticket_prom',           -1)], {}),
        ([('resumen.total_gastado', -1)], {}),
    ])

    crear_indices(db, 'kpi_ventas_temporales', [
        ([('tipo', 1), ('periodo', 1)], {'unique': True}),
        ([('tipo',          1)], {}),
        ([('total_ventas', -1)], {}),
    ])

    crear_indices(db, 'kpi_horarios_afluencia', [
        ([('hora', 1), ('dia_semana', 1)], {'unique': True}),
        ([('avg_tickets',  -1)], {}),
        ([('clasificacion', 1)], {}),
    ])

    crear_indices(db, 'kpi_productos_sabores', [
        ([('id_producto',       1)], {'unique': True}),
        ([('ranking_ventas',    1)], {}),
        ([('rentabilidad_lt',  -1)], {}),
        ([('ingresos_totales', -1)], {}),
    ])

    crear_indices(db, 'kpi_segmentacion', [
        ([('segmento',        1)], {'unique': True}),
        ([('total_ingresos', -1)], {}),
        ([('ticket_prom',    -1)], {}),
    ])

    crear_indices(db, 'kpi_metodos_pago', [
        ([('metodo',             1)], {'unique': True}),
        ([('num_transacciones', -1)], {}),
        ([('monto_total',       -1)], {}),
    ])

    crear_indices(db, 'kpi_mayoreo', [
        ([('tipo',    1)], {}),
        ([('ranking', 1)], {}),
    ])

    crear_indices(db, 'kpi_operaciones_personal', [
        ([('fecha', 1), ('turno', 1)], {'unique': True}),
        ([('num_empleados', -1)], {}),
    ])

    crear_indices(db, 'kpi_ticket_composicion', [
        ([('tipo', 1)], {}),
    ])

    mongo.close()

    print('\n' + '*-' * 30)
    print('   Índices creados en todas las colecciones')
    print('*-' * 30 + '\n')


if __name__ == '__main__':
    main()
