# API Research (Steam)

Verificado el 2026-03-06.

## Steam Web API (oficial)

Referencia oficial:
- https://partner.steamgames.com/doc/webapi/IPlayerService

Endpoints clave:
- `IPlayerService/GetOwnedGames` (biblioteca propia)
- `IPlayerService/GetRecentlyPlayedGames` (actividad reciente)
- `ISteamUser/GetPlayerSummaries` (perfil jugador)
- `ISteamUser/GetFriendList` (amigos)
- `ISteamNews/GetNewsForApp` (noticias por juego)
- `ISteamUserStats/GetPlayerAchievements` + `GetSchemaForGame` (logros)

Notas:
- `GetOwnedGames` devuelve juegos "owned" del usuario (segun visibilidad/privacidad).
- Para prestamo familiar no siempre veras todo en `GetOwnedGames`.
- `GetRecentlyPlayedGames` solo aporta juegos jugados recientemente (no inventario completo historico).

Licencia familiar (SDK/API nativa):
- https://partner.steamgames.com/doc/api/ISteamApps#BIsSubscribedFromFamilySharing

Ese endpoint nativo documenta:
- `BIsSubscribedFromFamilySharing()` para saber si el usuario juega con licencia familiar temporal.
- `GetAppOwner()` para identificar al dueno original de la licencia.

Limite importante para esta app:
- No hay endpoint Web API publico para enumerar toda la biblioteca prestada por Steam Family Sharing/Steam Families.
- Lo mas cercano en Web API son juegos propios (`GetOwnedGames`) y jugados recientemente (`GetRecentlyPlayedGames`).

## CheckAppOwnership (ISteamUser)

- `CheckAppOwnership` existe, pero requiere `publisher authentication key`.
- Con una key Web API publica de usuario responde `403 Forbidden`.
- Es util para validar propiedad de un `appid` concreto dentro de contexto publisher, no para listar toda biblioteca prestada de terceros.

## Otros endpoints utiles (siguiente iteracion)

- `ISteamUser/GetPlayerBans`: estado de VAC/Game bans para listas de SteamID.
- `ISteamUser/ResolveVanityURL`: convertir vanity URL a SteamID64.
- `IPlayerService/GetSteamLevel`: nivel de cuenta Steam para un usuario.
- `IPlayerService/GetBadges`: insignias y progreso de badges.
