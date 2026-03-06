from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import requests

from tracker.models import GameRecord

OWNED_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
RECENTLY_PLAYED_URL = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/"
PLAYER_SUMMARIES_URL = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
FRIEND_LIST_URL = "https://api.steampowered.com/ISteamUser/GetFriendList/v1/"
APP_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
ACHIEVEMENTS_URL = "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
ACHIEVEMENT_SCHEMA_URL = "https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/"
STORE_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"


class SteamSyncError(RuntimeError):
    pass


def _http_error_message(status_code: int) -> str:
    if status_code == 401:
        return (
            "Steam API respondio 401 (Unauthorized). Revisa `STEAM_API_KEY` y `STEAM_ID` en `.env`:\n"
            "1) `STEAM_API_KEY` debe ser una Web API Key valida.\n"
            "2) `STEAM_ID` debe ser tu SteamID64 numerico.\n"
            "3) El perfil de Steam debe estar publico para consultar juegos."
        )
    if status_code == 403:
        return "Steam API respondio 403 (Forbidden). Verifica permisos de clave/perfil."
    if status_code == 429:
        return "Steam API respondio 429 (Too Many Requests). Espera un momento e intenta de nuevo."
    if status_code >= 500:
        return "Steam API presento error del servidor. Intenta nuevamente en unos minutos."
    return f"Steam API respondio {status_code}. Verifica credenciales y parametros."


def _fetch_json(url: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise SteamSyncError("Timeout al conectar con Steam API.") from exc
    except requests.ConnectionError as exc:
        raise SteamSyncError("No fue posible conectar con Steam API (error de red).") from exc
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else 0
        raise SteamSyncError(_http_error_message(status_code)) from exc
    except requests.RequestException as exc:
        raise SteamSyncError(f"Error inesperado consultando Steam API: {exc}") from exc

    return response.json()


def _steam_store_url(app_id: str) -> str:
    return f"https://store.steampowered.com/app/{app_id}/"


def _steam_cover_url(app_id: str) -> str:
    return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"


def _steam_logo_url(app_id: str, logo_hash: str) -> str:
    return f"https://media.steampowered.com/steamcommunity/public/images/apps/{app_id}/{logo_hash}.jpg"


def _decimal_from_cents(value: Any) -> Decimal | None:
    try:
        cents = int(value)
    except (TypeError, ValueError):
        return None
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))


def fetch_owned_games(api_key: str, steam_id: str) -> list[dict[str, Any]]:
    params = {
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": True,
        "include_played_free_games": True,
    }
    data = _fetch_json(OWNED_GAMES_URL, params)
    return data.get("response", {}).get("games", [])


def fetch_recently_played_games(api_key: str, steam_id: str) -> list[dict[str, Any]]:
    params = {
        "key": api_key,
        "steamid": steam_id,
        # Steam docs: 0/unset requests all recently played entries available.
        "count": 0,
    }
    data = _fetch_json(RECENTLY_PLAYED_URL, params)
    return data.get("response", {}).get("games", [])


def fetch_friend_list(api_key: str, steam_id: str) -> list[dict[str, Any]]:
    params = {"key": api_key, "steamid": steam_id, "relationship": "friend"}
    data = _fetch_json(FRIEND_LIST_URL, params)
    return data.get("friendslist", {}).get("friends", [])


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def fetch_player_summaries_for_ids(api_key: str, steam_ids: list[str]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for chunk in _chunks(steam_ids, 100):
        params = {"key": api_key, "steamids": ",".join(chunk)}
        data = _fetch_json(PLAYER_SUMMARIES_URL, params)
        summaries.extend(data.get("response", {}).get("players", []))
    return summaries


def fetch_own_player_summary(api_key: str, steam_id: str) -> dict[str, Any]:
    summaries = fetch_player_summaries_for_ids(api_key=api_key, steam_ids=[steam_id])
    if summaries:
        return summaries[0]
    return {}


def fetch_app_news(api_key: str, app_id: int, count: int = 4, max_length: int = 320) -> list[dict[str, Any]]:
    params = {
        "key": api_key,
        "appid": app_id,
        "count": count,
        "maxlength": max_length,
    }
    data = _fetch_json(APP_NEWS_URL, params)
    items = data.get("appnews", {}).get("newsitems", [])

    normalized: list[dict[str, Any]] = []
    for item in items:
        raw_ts = item.get("date")
        try:
            published_at = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            published_at = None

        normalized.append(
            {
                "gid": str(item.get("gid") or ""),
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "author": str(item.get("author") or "").strip(),
                "published_at": published_at,
                "feedlabel": str(item.get("feedlabel") or "").strip(),
            }
        )
    return normalized


def fetch_achievement_schema_total(api_key: str, app_id: int) -> int:
    params = {"key": api_key, "appid": app_id}

    try:
        data = _fetch_json(ACHIEVEMENT_SCHEMA_URL, params)
    except SteamSyncError:
        return 0

    achievements = data.get("game", {}).get("availableGameStats", {}).get("achievements", [])
    return len(achievements or [])


def fetch_achievements(api_key: str, steam_id: str, app_id: int) -> tuple[int, int]:
    params = {"key": api_key, "steamid": steam_id, "appid": app_id}
    schema_total = fetch_achievement_schema_total(api_key=api_key, app_id=app_id)

    try:
        data = _fetch_json(ACHIEVEMENTS_URL, params)
    except SteamSyncError:
        return schema_total, 0

    achievements = data.get("playerstats", {}).get("achievements") or []
    unlocked = sum(1 for achievement in achievements if achievement.get("achieved") == 1)
    total = max(len(achievements), schema_total)
    return total, unlocked


def fetch_store_app_details(app_id: str) -> dict[str, Any]:
    try:
        payload = _fetch_json(
            STORE_APP_DETAILS_URL,
            {"appids": app_id, "l": "english", "cc": "US"},
            timeout=12,
        )
    except SteamSyncError:
        return {}

    details = payload.get(str(app_id), {})
    if not details.get("success"):
        return {}

    data = details.get("data", {})
    genres = [genre.get("description", "").strip() for genre in data.get("genres", []) if genre.get("description")]
    publishers = [publisher.strip() for publisher in data.get("publishers", []) if publisher]
    price = _decimal_from_cents((data.get("price_overview") or {}).get("final"))
    currency = (data.get("price_overview") or {}).get("currency") or ""

    return {
        "genre": ", ".join(genres),
        "publisher": publishers[0] if publishers else "",
        "estimated_price": price,
        "currency": currency,
        "cover_url": data.get("header_image") or "",
    }


def _merge_owned_and_recent(
    owned_games: list[dict[str, Any]],
    recent_games: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for game in owned_games:
        app_id = str(game.get("appid", "")).strip()
        if not app_id:
            continue
        merged[app_id] = {
            "appid": app_id,
            "name": (game.get("name") or "Sin nombre").strip(),
            "img_logo_url": game.get("img_logo_url") or "",
            "playtime_forever": int(game.get("playtime_forever", 0) or 0),
            "playtime_2weeks": int(game.get("playtime_2weeks", 0) or 0),
            "rtime_last_played": int(game.get("rtime_last_played", 0) or 0),
            "owned": True,
        }

    for game in recent_games:
        app_id = str(game.get("appid", "")).strip()
        if not app_id:
            continue

        if app_id in merged:
            merged[app_id]["playtime_2weeks"] = max(
                int(merged[app_id].get("playtime_2weeks", 0)), int(game.get("playtime_2weeks", 0) or 0)
            )
            merged[app_id]["rtime_last_played"] = max(
                int(merged[app_id].get("rtime_last_played", 0)), int(game.get("rtime_last_played", 0) or 0)
            )
            continue

        merged[app_id] = {
            "appid": app_id,
            "name": (game.get("name") or "Sin nombre").strip(),
            "img_logo_url": game.get("img_logo_url") or "",
            "playtime_forever": int(game.get("playtime_forever", 0) or 0),
            "playtime_2weeks": int(game.get("playtime_2weeks", 0) or 0),
            "rtime_last_played": int(game.get("rtime_last_played", 0) or 0),
            "owned": False,
        }

    return list(merged.values())


def sync_steam_games(
    api_key: str,
    steam_id: str,
    default_currency: str = "USD",
    include_achievements: bool = False,
) -> dict[str, int]:
    if not api_key or not steam_id:
        raise ValueError("Faltan STEAM_API_KEY y/o STEAM_ID en variables de entorno.")
    if api_key.strip().lower().startswith("your-") or api_key.strip().lower().startswith("replace"):
        raise ValueError("`STEAM_API_KEY` parece un valor placeholder. Reemplazalo por una clave real.")
    if not steam_id.strip().isdigit():
        raise ValueError("`STEAM_ID` debe ser numerico (SteamID64).")

    owned_games = fetch_owned_games(api_key=api_key, steam_id=steam_id)
    recent_games = fetch_recently_played_games(api_key=api_key, steam_id=steam_id)
    games = _merge_owned_and_recent(owned_games, recent_games)

    store_cache: dict[str, dict[str, Any]] = {}

    created_count = 0
    updated_count = 0
    recent_only_count = 0

    for game in games:
        app_id = str(game.get("appid", "")).strip()
        name = (game.get("name") or "Sin nombre").strip()
        logo_hash = str(game.get("img_logo_url") or "").strip()

        imported_minutes = int(game.get("playtime_forever", 0) or 0)
        recent_minutes = int(game.get("playtime_2weeks", 0) or 0)
        last_played_raw = int(game.get("rtime_last_played", 0) or 0)
        last_played = None

        if last_played_raw > 0:
            last_played = datetime.fromtimestamp(last_played_raw, tz=timezone.utc)

        status = GameRecord.Status.PLAYING if recent_minutes > 0 else GameRecord.Status.BACKLOG
        ownership_type = GameRecord.OwnershipType.OWNED if game.get("owned", False) else GameRecord.OwnershipType.RECENT_ONLY
        if ownership_type == GameRecord.OwnershipType.RECENT_ONLY:
            recent_only_count += 1

        record = None
        if app_id:
            record = GameRecord.objects.filter(platform=GameRecord.Platform.STEAM, external_id=app_id).first()
        if record is None:
            record = GameRecord.objects.filter(platform=GameRecord.Platform.STEAM, title__iexact=name).first()

        if app_id not in store_cache and app_id:
            needs_store_details = (
                record is None
                or not record.genre
                or not record.publisher
                or record.estimated_price is None
                or not record.cover_url
            )
            if needs_store_details:
                store_cache[app_id] = fetch_store_app_details(app_id=app_id)
            else:
                store_cache[app_id] = {}

        store_details = store_cache.get(app_id, {})
        cover_url = store_details.get("cover_url") or (_steam_cover_url(app_id) if app_id else "")
        store_url = _steam_store_url(app_id) if app_id else ""
        logo_url = _steam_logo_url(app_id, logo_hash) if app_id and logo_hash else ""

        defaults = {
            "title": name,
            "status": status,
            "ownership_type": ownership_type,
            "imported_minutes": imported_minutes,
            "recent_minutes": recent_minutes,
            "currency": store_details.get("currency") or default_currency,
            "last_played_at": last_played,
            "cover_url": cover_url,
            "logo_url": logo_url,
            "store_url": store_url,
            "genre": store_details.get("genre") or "",
            "publisher": store_details.get("publisher") or "",
            "estimated_price": store_details.get("estimated_price"),
        }

        created = record is None
        if created:
            record = GameRecord.objects.create(
                platform=GameRecord.Platform.STEAM,
                external_id=app_id,
                **defaults,
            )

        if created:
            created_count += 1
        else:
            updated_count += 1
            if app_id:
                record.external_id = app_id
            record.title = name
            record.imported_minutes = imported_minutes
            record.recent_minutes = recent_minutes
            record.status = status
            record.ownership_type = ownership_type
            if last_played:
                record.last_played_at = last_played
            if store_details.get("genre"):
                record.genre = store_details["genre"]
            if store_details.get("publisher"):
                record.publisher = store_details["publisher"]
            if store_details.get("estimated_price") is not None:
                record.estimated_price = store_details["estimated_price"]
            if store_details.get("currency") and not record.purchase_price:
                record.currency = store_details["currency"]
            if not record.currency:
                record.currency = default_currency
            if cover_url:
                record.cover_url = cover_url
            if logo_url:
                record.logo_url = logo_url
            if store_url:
                record.store_url = store_url

        if include_achievements and app_id.isdigit():
            total, unlocked = fetch_achievements(api_key=api_key, steam_id=steam_id, app_id=int(app_id))
            record.achievements_total = total
            record.achievements_unlocked = unlocked

        record.save()

    return {
        "total_games": len(games),
        "owned_games": len(owned_games),
        "recent_games": len(recent_games),
        "recent_only": recent_only_count,
        "created": created_count,
        "updated": updated_count,
    }
