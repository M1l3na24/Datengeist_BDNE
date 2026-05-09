db.createCollection("ventas_completas");
db.ventas_completas.createIndex({ id_ticket: 1 },          { unique: true });
db.ventas_completas.createIndex({ timestamp: 1 });
db.ventas_completas.createIndex({ anio: 1 });
db.ventas_completas.createIndex({ mes: 1 });
db.ventas_completas.createIndex({ cliente_segmento: 1 });
db.ventas_completas.createIndex({ cliente_giro: 1 });
db.ventas_completas.createIndex({ id_cliente: 1 });
db.ventas_completas.createIndex({ temperatura: 1 });
db.ventas_completas.createIndex({ eventos_festivos_locales: 1 });
db.ventas_completas.createIndex({ payment_method: 1 });
print("ventas_completas lista");

db.createCollection("catalogo_productos");
db.catalogo_productos.createIndex({ id_producto: 1 }, { unique: true });
db.catalogo_productos.createIndex({ categoria: 1 });
db.catalogo_productos.createIndex({ rentabilidad_pct: -1 });
db.catalogo_productos.createIndex({ margen_bruto: -1 });
print("catalogo_productos lista");

db.createCollection("clientes_perfil");
db.clientes_perfil.createIndex({ id_cliente: 1 },             { unique: true });
db.clientes_perfil.createIndex({ segmento: 1 });
db.clientes_perfil.createIndex({ giro: 1 });
db.clientes_perfil.createIndex({ ticket_prom: -1 });
db.clientes_perfil.createIndex({ "resumen.total_gastado": -1 });
print("clientes_perfil lista");

db.createCollection("kpi_ventas_temporales");
db.kpi_ventas_temporales.createIndex({ tipo: 1, periodo: 1 }, { unique: true });
db.kpi_ventas_temporales.createIndex({ tipo: 1 });
db.kpi_ventas_temporales.createIndex({ total_ventas: -1 });
print("kpi_ventas_temporales lista");

db.createCollection("kpi_horarios_afluencia");
db.kpi_horarios_afluencia.createIndex({ hora: 1, dia_semana: 1 }, { unique: true });
db.kpi_horarios_afluencia.createIndex({ avg_tickets: -1 });
db.kpi_horarios_afluencia.createIndex({ clasificacion: 1 });
print("kpi_horarios_afluencia lista");

db.createCollection("kpi_productos_sabores");
db.kpi_productos_sabores.createIndex({ id_producto: 1 },      { unique: true });
db.kpi_productos_sabores.createIndex({ ranking_ventas: 1 });
db.kpi_productos_sabores.createIndex({ rentabilidad_lt: -1 });
db.kpi_productos_sabores.createIndex({ ingresos_totales: -1 });
print("kpi_productos_sabores lista");

db.createCollection("kpi_segmentacion");
db.kpi_segmentacion.createIndex({ segmento: 1 },              { unique: true });
db.kpi_segmentacion.createIndex({ total_ingresos: -1 });
db.kpi_segmentacion.createIndex({ ticket_prom: -1 });
print("kpi_segmentacion lista");

db.createCollection("kpi_metodos_pago");
db.kpi_metodos_pago.createIndex({ metodo: 1 },                { unique: true });
db.kpi_metodos_pago.createIndex({ num_transacciones: -1 });
db.kpi_metodos_pago.createIndex({ monto_total: -1 });
print("kpi_metodos_pago lista");