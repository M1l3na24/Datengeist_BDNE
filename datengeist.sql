-- En este archivo creamos el esquema de la base de datos relacional

-- 1. Productos y Sabores
CREATE TABLE Dim_Productos_y_Sabores (
    ID_Producto INT PRIMARY KEY,
    Categoria VARCHAR(50),
    costo_prod_lt DECIMAL(10,2),
    precio_sug DECIMAL(10,2),
    ingredientes TEXT
);

-- 2. Clientes y Segmentos
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

-- 3. Tabla de Ventas
CREATE TABLE Ventas (
    ID_Ticket INT PRIMARY KEY,
    Timestamp TIMESTAMP,
    ID_Cliente INT REFERENCES Dim_Clientes_y_Segmentos(ID_Cliente),
    payment_method VARCHAR(50),
    total DECIMAL(10,2)
);

-- 4. Detalle de Ventas 
CREATE TABLE Detalle_ventas (
    ID_Ticket INT REFERENCES Ventas(ID_Ticket),
    ID_Producto INT REFERENCES Dim_Productos_y_Sabores(ID_Producto),
    ID_Sabor INT, 
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

-- 6. Variables Externas
CREATE TABLE Variables_Externas (
    Fecha DATE PRIMARY KEY,
    Temperatura DECIMAL(5,2),
    Precipitacion DECIMAL(5,2),
    Eventos_Festivos_Locales TEXT
);