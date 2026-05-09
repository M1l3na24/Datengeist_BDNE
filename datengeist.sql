-- 1. Catálogo de Productos y Sabores
CREATE TABLE Dim_Productos_y_Sabores (
    ID_Producto INT PRIMARY KEY,
    Categoria VARCHAR(50),
    costo_prod_lt DECIMAL(10,2),
    precio_sug DECIMAL(10,2),
    ingredientes TEXT
);

-- 2. Catálogo de Clientes y Segmentos
CREATE TABLE Dim_Clientes_y_Segmentos (
    ID_Cliente INT PRIMARY KEY,
    Nombre VARCHAR(100),
    Giro VARCHAR(50),
    Segmento VARCHAR(50),
    frecuencia_compra VARCHAR(50),
    ticket_prom DECIMAL(10,2),
    sabor_preferido VARCHAR(50),
    ubicacion VARCHAR(255)
);

-- 3. Tabla de Ventas (Encabezado)
CREATE TABLE Ventas (
    ID_Ticket INT PRIMARY KEY,
    Timestamp TIMESTAMP,
    ID_Cliente INT REFERENCES Dim_Clientes_y_Segmentos(ID_Cliente),
    payment_method VARCHAR(50),
    total DECIMAL(10,2)
);

-- 4. Detalle de Ventas (Relacional)
CREATE TABLE Detalle_ventas (
    ID_Ticket INT REFERENCES Ventas(ID_Ticket),
    ID_Producto INT REFERENCES Dim_Productos_y_Sabores(ID_Producto),
    ID_Sabor INT, -- Podrías crear una dim aparte para sabores si es necesario
    Cantidad INT,
    Precio_Unitario DECIMAL(10,2),
    Tipo_Venta VARCHAR(50),
    PRIMARY KEY (ID_Ticket, ID_Producto, ID_Sabor)
);

-- 5. Operaciones y Personal
CREATE TABLE Operaciones_y_Personal (
    Fecha DATE,
    Turno VARCHAR(20),
    Num_empleados INT,
    payment_method VARCHAR(50),
    costo_hora DECIMAL(10,2),
    PRIMARY KEY (Fecha, Turno)
);

-- 6. Variables Externas (Muy útil para el análisis de helados)
CREATE TABLE Variables_Externas (
    Fecha DATE PRIMARY KEY,
    Temperatura DECIMAL(5,2),
    Precipitacion DECIMAL(5,2),
    Eventos_Festivos_Locales TEXT
);

-- Para ver tablas
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE';

-- Para ver info
SELECT
    v.id_ticket,
    v.timestamp,
    v.total,
    v.payment_method,

    -- Cliente
    c.nombre,
    c.segmento,
    c.giro,
    c.ubicacion,

    -- Detalle
    d.cantidad,
    d.precio_unitario,
    d.tipo_venta,

    -- Producto
    p.categoria,
    p.precio_sug,
    p.ingredientes,

    -- Clima del día
    ve.temperatura,
    ve.precipitacion,
    ve.eventos_festivos_locales

FROM ventas v
    JOIN dim_clientes_y_segmentos c  ON v.id_cliente  = c.id_cliente
    JOIN detalle_ventas d            ON v.id_ticket   = d.id_ticket
    JOIN dim_productos_y_sabores p   ON d.id_producto = p.id_producto
    JOIN variables_externas ve       ON v.timestamp::date = ve.fecha

LIMIT 100;
