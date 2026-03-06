import requests
import pandas as pd
from datetime import datetime

# Leer token de Steam desde archivo Excel
token_steam = pd.read_excel('/Users/andresmauriciotrianareina/Documents/Desarrollos/token_steam.xlsx')

# Validar que las columnas existan en el archivo Excel
if 'token' not in token_steam.columns or 'is_user' not in token_steam.columns:
    raise ValueError("El archivo Excel debe contener las columnas 'token' y 'is_user'.")

# Obtener los valores y convertirlos a string
API_KEY = str(token_steam['token'].iloc[0])  # Usar iloc para mayor claridad
STEAM_ID = str(token_steam['is_user'].iloc[0])  # Usar iloc para mayor claridad

# Imprimir los valores para verificar
print(f"API_KEY: {API_KEY}")
print(f"STEAM_ID: {STEAM_ID}")

# Función para obtener la lista de juegos y horas jugadas
def obtener_juegos(api_key, steam_id):
    url = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": True,
        "include_played_free_games": True
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get("response", {}).get("games", [])
    else:
        print("Error al obtener la lista de juegos:", response.status_code)
        return []

# Función para obtener logros por juego (con manejo de errores)
def obtener_logros(api_key, steam_id, app_id):
    url = f"http://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
    params = {
        "key": api_key,
        "steamid": steam_id,
        "appid": app_id
    }
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        achievements = response.json().get("playerstats", {}).get("achievements", [])
        total = len(achievements)
        desbloqueados = sum(1 for logro in achievements if logro.get("achieved") == 1)
        return total, desbloqueados
    elif response.status_code == 400:
        print(f"El juego con AppID {app_id} no tiene logros disponibles o no hay datos.")
        return 0, 0
    else:
        print(f"Error al obtener logros para AppID {app_id}: {response.status_code}")
        return 0, 0

# Procesar los datos de los juegos
juegos = obtener_juegos(API_KEY, STEAM_ID)
datos_juegos = []

for juego in juegos:
    app_id = juego.get("appid")
    nombre = juego.get("name")
    horas_totales = round(juego.get("playtime_forever", 0) / 60, 2)
    horas_recientes = round(juego.get("playtime_2weeks", 0) / 60, 2)
    ultima_jugada = datetime.fromtimestamp(juego.get("rtime_last_played", 0)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Obtener logros
    logros_totales, logros_desbloqueados = obtener_logros(API_KEY, STEAM_ID, app_id)

    # Agregar los datos al listado
    datos_juegos.append({
        "AppID": app_id,
        "Nombre": nombre,
        "Horas Totales": horas_totales,
        "Horas Últimas 2 Semanas": horas_recientes,
        "Última Vez Jugado": ultima_jugada,
        "Logros Totales": logros_totales,
        "Logros Desbloqueados": logros_desbloqueados
    })

# Convertir a DataFrame
df_juegos = pd.DataFrame(datos_juegos)

# Guardar el DataFrame en un archivo CSV
df_juegos.to_csv('data_steam.csv', index=False)

# Calcular estadísticas clave
# numero_juegos = len(df_juegos)
# total_horas = df_juegos["Horas Totales"].sum()
# total_logros = df_juegos["Logros Desbloqueados"].sum()

# print(f"Número de Juegos: {numero_juegos}")
# print(f"Total de Horas Jugadas: {total_horas}")
# print(f"Total de Logros Desbloqueados: {total_logros}")