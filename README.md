# AlmaStock – Fase 3

Sistema de control de inventario construido con Python, Flask, Flask-SQLAlchemy y SQLite.

## Instalación en Windows (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```
Abre http://127.0.0.1:5000.

## Funciones
- Registro e inicio de sesión con contraseñas protegidas.
- Roles de administrador y operario.
- Gestión de productos con stock mínimo configurable.
- Alertas de existencias bajas en el panel y en inventario.
- Búsqueda de inventario por nombre, SKU y categoría.
- Entradas y salidas con validación transaccional.
- Historial filtrable por producto, tipo y fechas.
- Auditoría básica: usuario que registró cada movimiento.
- Reportes resumidos y exportación de movimientos a CSV (compatible con Excel) y PDF.

## Actualización desde Fase 2
1. Haz una copia de seguridad de `instance/almastock.db`.
2. Copia los archivos de esta versión sobre el proyecto anterior, sin reemplazar la carpeta `instance`.
3. Activa el entorno virtual e instala dependencias:
   `python -m pip install -r requirements.txt`
4. Ejecuta `python run.py`. Se agregan automáticamente las columnas nuevas `products.min_stock` y `movements.user_id`.

## Administrador
Para convertir una cuenta existente en administradora:
```powershell
flask --app run.py promote-admin correo@ejemplo.com
```

## Seguridad
Proyecto para desarrollo local y portafolio. Antes de desplegarlo públicamente configura una `SECRET_KEY` aleatoria, HTTPS, `COOKIE_SECURE=1`, desactiva `debug`, aplica migraciones formales y ejecuta pruebas automatizadas. No publiques `.venv`, `instance` ni archivos `.db`.
