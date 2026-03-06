# Dashboard Games Monitor

Aplicación web en Django para monitorear tu biblioteca de **Steam**: horas jugadas, backlog, logros, gasto y actividad reciente en un dashboard con filtros y gráficas.

## 1. Qué hace la aplicación

- Sincroniza juegos desde Steam usando `STEAM_API_KEY` y `STEAM_ID`.
- Guarda catálogo y metadatos por juego (género, publisher, portada, URL de tienda, precio estimado).
- Combina tiempo importado de Steam + tiempo manual + sesiones manuales.
- Muestra KPIs y analítica visual (horas, gasto, estados, actividad reciente).
- Muestra resumen social de Steam (perfil y amigos) y noticias de juegos.
- Permite CRUD manual de juegos y registro de sesiones.

## 2. Stack técnico

- Backend: Django 5
- Base de datos: SQLite (default) o PostgreSQL por variables de entorno
- Frontend: Django Templates + CSS + Chart.js
- Integración externa: Steam Web API + Steam Store API
- Contenedores: Docker / Docker Compose

## 3. Variables de entorno

Copia el archivo de ejemplo:

```bash
cp .env.example .env
```

Variables principales:

- `DJANGO_SECRET_KEY`: llave de Django
- `DJANGO_DEBUG`: `True`/`False`
- `DJANGO_ALLOWED_HOSTS`: hosts permitidos, separados por coma
- `DJANGO_CSRF_TRUSTED_ORIGINS`: orígenes CSRF confiables (opcional)
- `TIME_ZONE`: zona horaria (default `America/Bogota`)
- `APP_DEFAULT_CURRENCY`: moneda por defecto (ej. `USD`)
- `STEAM_API_KEY`: Web API Key de Steam
- `STEAM_ID`: SteamID64 numérico
- `STEAM_INCLUDE_ACHIEVEMENTS_ON_SYNC`: `True`/`False` para incluir logros al sincronizar

Opcionales de PostgreSQL:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## 4. Ejecutar local (sin Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8003
```

App: `http://localhost:8003`

## 5. Ejecutar con Docker

```bash
docker compose up --build
```

La app corre en `http://localhost:8003` y aplica migraciones al iniciar.

## 6. Uso funcional

### Dashboard (`/`)

- Botón `Sincronizar Steam`
- Filtros por búsqueda, estado, año, género, compañía, propiedad, horas mínimas, portada y orden
- KPIs: juegos (jugados/no jugados), horas, actividad reciente, backlog/jugando, amigos, logros, gasto
- Bloque social: `GetPlayerSummaries` + `GetFriendList`
- Bloque de noticias: `GetNewsForApp` sobre el juego más jugado del filtro actual
- Gráficas: horas por año, horas por género y compras por compañía
- Tablas: top por tiempo, top por gasto, últimos jugados, compras recientes
- Galería de juegos con portada y acceso a tienda

### Biblioteca (`/games/`)

- Lista tabular de juegos
- Filtros por nombre, estado y año
- Acciones por fila: editar juego y registrar sesión

### Alta/edición de juegos

- Crear juego: `/games/new/`
- Editar juego: `/games/<id>/edit/`
- Registrar sesión: `/games/<id>/session/`

## 7. Sincronización Steam

### Desde la web

- Entra al dashboard y presiona `Sincronizar Steam`.

### Desde línea de comandos

```bash
python manage.py sync_steam
python manage.py sync_steam --achievements
```

### Qué trae la sincronización

- Biblioteca propia (`GetOwnedGames`)
- Juegos recientes (`GetRecentlyPlayedGames`)
- Logros por juego (opcional)
- Perfil del jugador (`GetPlayerSummaries`)
- Lista de amigos (`GetFriendList`) + cálculo de online/en juego
- Noticias por app (`GetNewsForApp`) para el juego más jugado
- Metadatos de tienda para enriquecer analítica (género, publisher, precio estimado, portada)

Además, detecta juegos solo recientes (ej. préstamo familiar) y los marca con propiedad `RECENT_ONLY`.

## 8. Modelo de datos (resumen)

- `GameRecord`: juego, estado, tiempos (importado/manual), logros, precios, portada, URLs, timestamps
- `PlaySession`: sesiones manuales con inicio/fin y minutos calculados automáticamente

Notas de cálculo:

- `total_minutes = imported_minutes + manual_minutes + sum(sessions.minutes)`
- `total_hours = total_minutes / 60`

## 9. Comandos administrativos

- Migrar DB: `python manage.py migrate`
- Crear superusuario: `python manage.py createsuperuser`
- Admin: `http://localhost:8003/admin`

## 10. Estructura principal del proyecto

- `game_tracker/`: settings y configuración Django
- `tracker/models.py`: entidades principales
- `tracker/views.py`: dashboard, CRUD, sincronización Steam
- `tracker/services/steam.py`: lógica de integración con Steam
- `tracker/management/commands/sync_steam.py`: comando CLI de sincronización
- `tracker/templates/tracker/`: vistas HTML
- `tracker/static/tracker/styles.css`: estilos
- `tracker/migrations/`: historial de migraciones
- `docs/api_research.md`: notas de investigación de API

## 11. Troubleshooting

Si falla con `401 Unauthorized`:

- Revisa que `STEAM_API_KEY` sea válida
- Verifica que `STEAM_ID` sea SteamID64 numérico
- Asegura perfil de Steam público
- Reinicia proceso/contenedor tras cambiar `.env`

Si no aparecen algunos juegos por préstamo familiar:

- Steam Web API no siempre expone toda la biblioteca prestada
- La app mezcla `OwnedGames` + `RecentlyPlayedGames` para cubrir más casos
- Steam solo expone juegos prestados si aparecen como recientes; no hay endpoint público para listar el inventario completo prestado

## 12. Archivos legacy

Se conservan `steam_data.py` y `get_data.py` como referencia histórica, pero la aplicación activa es la de Django.
