from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
import os
import sqlite3
import tempfile

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db import connections
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from tracker.forms import GameRecordForm, PlaySessionForm
from tracker.models import GameRecord, PlaySession
from tracker.services.steam import (
    fetch_app_news,
    fetch_friend_list,
    fetch_own_player_summary,
    fetch_player_summaries_for_ids,
    sync_steam_games,
)


def _games_with_session_minutes():
    return GameRecord.objects.annotate(session_minutes=Coalesce(Sum("sessions__minutes"), 0))


def _total_minutes(game: GameRecord) -> int:
    return int(game.imported_minutes + game.manual_minutes + int(game.session_minutes or 0))


def _parse_min_hours(raw_value: str) -> float:
    try:
        value = float(raw_value)
        return max(value, 0)
    except (TypeError, ValueError):
        return 0.0


def _with_calculated_time(games: list[GameRecord]) -> list[GameRecord]:
    for game in games:
        game.total_minutes_calc = _total_minutes(game)
        game.total_hours_calc = round(game.total_minutes_calc / 60, 2)
        game.effective_spend_calc = game.purchase_price if game.purchase_price is not None else (game.estimated_price or Decimal("0"))
    return games


STATUS_FILTER_CHOICES = [
    (GameRecord.Status.PLAYING, "Jugando"),
    (GameRecord.Status.BACKLOG, "Backlog"),
]

PERSONA_STATE_LABELS = {
    0: "Desconectado",
    1: "En linea",
    2: "Ocupado",
    3: "Ausente",
    4: "Snooze",
    5: "Quiere intercambiar",
    6: "Quiere jugar",
}

SQLITE_HEADER = b"SQLite format 3\x00"
SQLITE_REQUIRED_TABLES = {
    "django_migrations",
    "django_session",
    "tracker_gamerecord",
    "tracker_playsession",
}


def _get_sqlite_db_path() -> Path | None:
    db_settings = connections["default"].settings_dict
    if db_settings.get("ENGINE") != "django.db.backends.sqlite3":
        return None

    raw_name = db_settings.get("NAME")
    if not raw_name:
        return None

    return Path(raw_name)


def _validate_sqlite_backup(db_path: Path) -> None:
    with db_path.open("rb") as uploaded_file:
        if uploaded_file.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            raise ValueError("El archivo cargado no es una base SQLite valida.")

    try:
        with sqlite3.connect(str(db_path)) as connection:
            quick_check = connection.execute("PRAGMA quick_check").fetchone()
            if not quick_check or quick_check[0] != "ok":
                raise ValueError("La base SQLite cargada esta corrupta o incompleta.")

            found_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
    except sqlite3.DatabaseError as exc:
        raise ValueError("No fue posible leer la base SQLite cargada.") from exc

    missing_tables = SQLITE_REQUIRED_TABLES - found_tables
    if missing_tables:
        raise ValueError(
            "La base SQLite cargada no parece ser una copia completa de esta aplicacion."
        )


def dashboard(request: HttpRequest) -> HttpResponse:
    min_dt = datetime.min.replace(tzinfo=dt_timezone.utc)

    filters = {
        "search": request.GET.get("search", "").strip(),
        "status": request.GET.get("status", "").strip(),
        "year": request.GET.get("year", "").strip(),
        "genre": request.GET.get("genre", "").strip(),
        "company": request.GET.get("company", "").strip(),
        "ownership": request.GET.get("ownership", "").strip(),
        "sort": request.GET.get("sort", "last_played_desc").strip() or "last_played_desc",
        "min_hours": request.GET.get("min_hours", "").strip(),
        "has_cover": request.GET.get("has_cover", "").strip(),
    }

    all_games = _with_calculated_time(list(_games_with_session_minutes()))
    company_choices = sorted({game.publisher for game in all_games if game.publisher})
    genre_choices = sorted({part for game in all_games for part in [piece.strip() for piece in game.genre.split(",")] if part})
    available_years = sorted({game.last_played_at.year for game in all_games if game.last_played_at}, reverse=True)
    filtered_games = list(all_games)

    if filters["search"]:
        term = filters["search"].lower()
        filtered_games = [game for game in filtered_games if term in game.title.lower()]
    if filters["status"]:
        filtered_games = [game for game in filtered_games if game.status == filters["status"]]
    if filters["year"].isdigit():
        selected_year = int(filters["year"])
        filtered_games = [game for game in filtered_games if game.last_played_at and game.last_played_at.year == selected_year]
    if filters["genre"]:
        genre_term = filters["genre"].lower()
        filtered_games = [
            game
            for game in filtered_games
            if any(piece.strip().lower() == genre_term for piece in game.genre.split(",") if piece.strip())
        ]
    if filters["company"]:
        company_term = filters["company"].lower()
        filtered_games = [game for game in filtered_games if game.publisher and game.publisher.lower() == company_term]
    if filters["ownership"]:
        filtered_games = [game for game in filtered_games if game.ownership_type == filters["ownership"]]

    min_hours = _parse_min_hours(filters["min_hours"])
    if min_hours > 0:
        filtered_games = [game for game in filtered_games if game.total_hours_calc >= min_hours]

    if filters["has_cover"] == "1":
        filtered_games = [game for game in filtered_games if game.cover_url]

    sort_options = [
        ("last_played_desc", "Ultimo jugado"),
        ("hours_desc", "Mas horas"),
        ("hours_asc", "Menos horas"),
        ("title_asc", "Nombre A-Z"),
        ("spend_desc", "Mayor gasto"),
    ]

    if filters["sort"] == "hours_desc":
        filtered_games.sort(key=lambda game: game.total_minutes_calc, reverse=True)
    elif filters["sort"] == "hours_asc":
        filtered_games.sort(key=lambda game: game.total_minutes_calc)
    elif filters["sort"] == "title_asc":
        filtered_games.sort(key=lambda game: game.title.lower())
    elif filters["sort"] == "spend_desc":
        filtered_games.sort(key=lambda game: game.effective_spend_calc, reverse=True)
    else:
        filtered_games.sort(key=lambda game: game.last_played_at or min_dt, reverse=True)
        filters["sort"] = "last_played_desc"

    global_total_games = len(all_games)
    metric_games = filtered_games
    total_games = len(metric_games)
    played_games = sum(1 for game in metric_games if game.total_minutes_calc > 0)
    unplayed_games = max(total_games - played_games, 0)
    total_minutes = sum(game.total_minutes_calc for game in metric_games)
    total_hours = round(total_minutes / 60, 2)
    avg_hours_per_game = round(total_hours / total_games, 2) if total_games else 0

    playing_games = sum(1 for game in metric_games if game.status == GameRecord.Status.PLAYING)
    backlog_games = sum(1 for game in metric_games if game.status == GameRecord.Status.BACKLOG)

    achievements_total = sum(int(game.achievements_total or 0) for game in metric_games)
    achievements_unlocked = sum(
        min(int(game.achievements_unlocked or 0), int(game.achievements_total or 0)) for game in metric_games
    )
    achievements_rate = round((achievements_unlocked / achievements_total) * 100, 1) if achievements_total else 0

    spent_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for game in metric_games:
        if game.effective_spend_calc > 0:
            spent_totals[game.currency] += game.effective_spend_calc
    spent_by_currency = [{"currency": currency, "total": total} for currency, total in sorted(spent_totals.items())]

    today = timezone.localdate()
    month_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for game in metric_games:
        if game.purchase_price and game.purchase_date and game.purchase_date.year == today.year and game.purchase_date.month == today.month:
            month_totals[game.currency] += game.purchase_price
    current_month_spend = [{"currency": currency, "total": total} for currency, total in sorted(month_totals.items())]

    steam_recent_minutes = sum(game.recent_minutes for game in metric_games if game.platform == GameRecord.Platform.STEAM)
    last_30_days = timezone.now() - timedelta(days=30)
    selected_ids = [game.id for game in metric_games]
    session_minutes_30_days = (
        PlaySession.objects.filter(game_id__in=selected_ids, ended_at__gte=last_30_days)
        .aggregate(total=Coalesce(Sum("minutes"), 0))
        .get("total", 0)
    )
    recent_activity_hours = round((steam_recent_minutes + int(session_minutes_30_days or 0)) / 60, 2)

    status_labels = dict(GameRecord.Status.choices)
    status_counts = Counter(game.status for game in metric_games)

    status_distribution = [
        {
            "label": status_labels.get(code, code),
            "total": count,
            "pct": round((count / total_games) * 100, 1) if total_games else 0,
        }
        for code, count in status_counts.most_common()
    ]

    top_played = metric_games[:12]
    top_spent = [game for game in sorted(metric_games, key=lambda game: game.effective_spend_calc, reverse=True) if game.effective_spend_calc > 0][:8]

    recent_games = [
        game
        for game in sorted(metric_games, key=lambda game: game.last_played_at or min_dt, reverse=True)
        if game.last_played_at
    ][:10]
    recent_purchases = [
        game
        for game in sorted(metric_games, key=lambda game: game.purchase_date or date.min, reverse=True)
        if game.purchase_date
    ][:10]

    year_hours: dict[str, float] = defaultdict(float)
    genre_hours: dict[str, float] = defaultdict(float)

    for game in metric_games:
        if game.last_played_at:
            year_hours[str(game.last_played_at.year)] += float(game.total_hours_calc)

        if game.genre:
            parts = [piece.strip() for piece in game.genre.split(",") if piece.strip()]
            if not parts:
                continue
            weight = float(game.total_hours_calc) / float(len(parts))
            for part in parts:
                genre_hours[part] += weight

    chart_hours_year = {
        "labels": sorted(year_hours.keys()),
        "values": [round(year_hours[year], 2) for year in sorted(year_hours.keys())],
    }

    top_genres = sorted(genre_hours.items(), key=lambda item: item[1], reverse=True)[:10]
    chart_hours_genre = {
        "labels": [item[0] for item in top_genres],
        "values": [round(item[1], 2) for item in top_genres],
    }

    company_purchase_counts: dict[str, int] = defaultdict(int)
    for game in metric_games:
        if game.effective_spend_calc > 0:
            label = game.publisher if game.publisher else "Sin compañía"
            company_purchase_counts[label] += 1
    company_top = sorted(company_purchase_counts.items(), key=lambda item: item[1], reverse=True)[:12]
    chart_company_purchases = {
        "labels": [item[0] for item in company_top],
        "values": [item[1] for item in company_top],
    }

    steam_profile: dict = {}
    steam_profile_state_label = "No disponible"
    steam_friends_total = 0
    steam_friends_online = 0
    steam_friends_in_game = 0
    steam_news: list[dict] = []
    steam_news_source_game = ""
    steam_profile_visibility = "No disponible"
    steam_profile_country = "No disponible"
    steam_profile_created_at = None
    steam_profile_last_logoff = None

    if settings.STEAM_API_KEY and settings.STEAM_ID:
        profile_cache_key = f"steam_profile_{settings.STEAM_ID}"
        friends_cache_key = f"steam_friend_stats_{settings.STEAM_ID}"

        try:
            steam_profile = cache.get(profile_cache_key)
            if steam_profile is None:
                steam_profile = fetch_own_player_summary(
                    api_key=settings.STEAM_API_KEY,
                    steam_id=settings.STEAM_ID,
                )
                cache.set(profile_cache_key, steam_profile, 300)

            visibility_state = int(steam_profile.get("communityvisibilitystate", 0) or 0)
            steam_profile_visibility = "Publico" if visibility_state == 3 else "Privado/Limitado"

            country_code = str(steam_profile.get("loccountrycode", "")).strip()
            state_code = str(steam_profile.get("locstatecode", "")).strip()
            city_id = steam_profile.get("loccityid")
            location_parts = [part for part in [country_code, state_code] if part]
            if city_id:
                location_parts.append(str(city_id))
            if location_parts:
                steam_profile_country = " - ".join(location_parts)

            created_raw = steam_profile.get("timecreated")
            if created_raw:
                steam_profile_created_at = datetime.fromtimestamp(int(created_raw), tz=dt_timezone.utc)

            last_logoff_raw = steam_profile.get("lastlogoff")
            if last_logoff_raw:
                steam_profile_last_logoff = datetime.fromtimestamp(int(last_logoff_raw), tz=dt_timezone.utc)

            raw_persona_state = steam_profile.get("personastate", 0)
            steam_profile_state_label = PERSONA_STATE_LABELS.get(int(raw_persona_state), "Desconocido")
        except Exception:
            steam_profile = {}
            steam_profile_state_label = "No disponible"

        try:
            friend_stats = cache.get(friends_cache_key)
            if friend_stats is None:
                friends = fetch_friend_list(api_key=settings.STEAM_API_KEY, steam_id=settings.STEAM_ID)
                friend_ids = [str(friend.get("steamid", "")).strip() for friend in friends if friend.get("steamid")]
                friend_stats = {
                    "total": len(friend_ids),
                    "online": 0,
                    "in_game": 0,
                }

                if friend_ids:
                    friend_summaries = fetch_player_summaries_for_ids(
                        api_key=settings.STEAM_API_KEY,
                        steam_ids=friend_ids,
                    )
                    friend_stats["online"] = sum(
                        1 for friend in friend_summaries if int(friend.get("personastate", 0) or 0) > 0
                    )
                    friend_stats["in_game"] = sum(1 for friend in friend_summaries if friend.get("gameid"))
                cache.set(friends_cache_key, friend_stats, 300)

            steam_friends_total = int(friend_stats.get("total", 0))
            steam_friends_online = int(friend_stats.get("online", 0))
            steam_friends_in_game = int(friend_stats.get("in_game", 0))
        except Exception:
            steam_friends_total = 0
            steam_friends_online = 0
            steam_friends_in_game = 0

        steam_news_game_candidates = [
            game
            for game in metric_games
            if game.platform == GameRecord.Platform.STEAM and game.external_id and game.external_id.isdigit()
        ]
        if steam_news_game_candidates:
            steam_news_game = max(
                steam_news_game_candidates,
                key=lambda game: (game.total_minutes_calc, game.recent_minutes),
            )
            steam_news_source_game = steam_news_game.title
            try:
                news_cache_key = f"steam_news_{steam_news_game.external_id}"
                steam_news = cache.get(news_cache_key)
                if steam_news is None:
                    steam_news = fetch_app_news(
                        api_key=settings.STEAM_API_KEY,
                        app_id=int(steam_news_game.external_id),
                        count=4,
                        max_length=260,
                    )
                    cache.set(news_cache_key, steam_news, 300)
            except Exception:
                steam_news = []

    context = {
        "total_games": total_games,
        "played_games": played_games,
        "unplayed_games": unplayed_games,
        "global_total_games": global_total_games,
        "filtered_games": len(metric_games),
        "total_hours": total_hours,
        "avg_hours_per_game": avg_hours_per_game,
        "playing_games": playing_games,
        "backlog_games": backlog_games,
        "achievements_total": achievements_total,
        "achievements_unlocked": achievements_unlocked,
        "achievements_rate": achievements_rate,
        "recent_activity_hours": recent_activity_hours,
        "recent_activity_steam_minutes": steam_recent_minutes,
        "recent_activity_sessions_minutes": int(session_minutes_30_days or 0),
        "spent_by_currency": spent_by_currency,
        "current_month_spend": current_month_spend,
        "status_distribution": status_distribution,
        "top_played": top_played,
        "top_spent": top_spent,
        "recent_games": recent_games,
        "recent_purchases": recent_purchases,
        "gallery_games": metric_games[:24],
        "chart_hours_year": chart_hours_year,
        "chart_hours_genre": chart_hours_genre,
        "chart_company_purchases": chart_company_purchases,
        "steam_ready": bool(settings.STEAM_API_KEY and settings.STEAM_ID),
        "sqlite_backup_available": _get_sqlite_db_path() is not None,
        "steam_profile": steam_profile,
        "steam_profile_state_label": steam_profile_state_label,
        "steam_profile_visibility": steam_profile_visibility,
        "steam_profile_country": steam_profile_country,
        "steam_profile_created_at": steam_profile_created_at,
        "steam_profile_last_logoff": steam_profile_last_logoff,
        "steam_friends_total": steam_friends_total,
        "steam_friends_online": steam_friends_online,
        "steam_friends_in_game": steam_friends_in_game,
        "steam_news": steam_news,
        "steam_news_source_game": steam_news_source_game,
        "filters": filters,
        "status_choices": STATUS_FILTER_CHOICES,
        "available_years": available_years,
        "genre_choices": genre_choices,
        "company_choices": company_choices,
        "ownership_choices": GameRecord.OwnershipType.choices,
        "sort_choices": sort_options,
    }
    return render(request, "tracker/dashboard.html", context)


def game_list(request: HttpRequest) -> HttpResponse:
    status = request.GET.get("status", "")
    year = request.GET.get("year", "")
    search = request.GET.get("search", "")

    games = _games_with_session_minutes()

    if status:
        games = games.filter(status=status)
    if year.isdigit():
        games = games.filter(last_played_at__year=int(year))
    if search:
        games = games.filter(title__icontains=search)

    games = list(games.order_by("title"))
    for game in games:
        game.total_minutes_calc = game.imported_minutes + game.manual_minutes + int(game.session_minutes or 0)
        game.effective_spend_calc = game.purchase_price if game.purchase_price is not None else (game.estimated_price or Decimal("0"))

    available_years = sorted(
        {
            game.last_played_at.year
            for game in _with_calculated_time(list(_games_with_session_minutes()))
            if game.last_played_at
        },
        reverse=True,
    )

    context = {
        "games": games,
        "status_choices": STATUS_FILTER_CHOICES,
        "available_years": available_years,
        "filters": {"status": status, "year": year, "search": search},
    }
    return render(request, "tracker/game_list.html", context)


def game_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = GameRecordForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Juego creado correctamente.")
            return redirect("game_list")
    else:
        form = GameRecordForm(initial={"currency": settings.APP_DEFAULT_CURRENCY})

    return render(request, "tracker/game_form.html", {"form": form, "mode": "Crear"})


def game_edit(request: HttpRequest, pk: int) -> HttpResponse:
    game = get_object_or_404(GameRecord, pk=pk)

    if request.method == "POST":
        form = GameRecordForm(request.POST, instance=game)
        if form.is_valid():
            form.save()
            messages.success(request, "Juego actualizado correctamente.")
            return redirect("game_list")
    else:
        form = GameRecordForm(instance=game)

    return render(request, "tracker/game_form.html", {"form": form, "mode": "Editar", "game": game})


def session_create(request: HttpRequest, pk: int) -> HttpResponse:
    game = get_object_or_404(GameRecord, pk=pk)

    if request.method == "POST":
        form = PlaySessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.game = game
            session.save()
            messages.success(request, f"Sesion registrada: {session.minutes} minutos.")
            return redirect("game_list")
    else:
        form = PlaySessionForm()

    return render(request, "tracker/session_form.html", {"form": form, "game": game})


def sync_steam(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("dashboard")

    try:
        result = sync_steam_games(
            api_key=settings.STEAM_API_KEY,
            steam_id=settings.STEAM_ID,
            default_currency=settings.APP_DEFAULT_CURRENCY,
            include_achievements=settings.STEAM_INCLUDE_ACHIEVEMENTS_ON_SYNC,
        )
    except Exception as exc:
        messages.error(request, f"Error sincronizando Steam: {exc}")
        return redirect("dashboard")

    extra = ""
    if result["recent_only"] > 0:
        extra = f" | Posible prestamo familiar detectado: {result['recent_only']}"

    messages.success(
        request,
        (
            "Steam sincronizado correctamente. "
            f"Total: {result['total_games']} | Propios: {result['owned_games']} | "
            f"Recientes: {result['recent_games']} | Creados: {result['created']} | "
            f"Actualizados: {result['updated']}{extra}"
        ),
    )
    return redirect("dashboard")


def export_sqlite_database(request: HttpRequest) -> HttpResponse:
    db_path = _get_sqlite_db_path()
    if db_path is None:
        messages.error(request, "La exportacion solo esta disponible cuando la app usa SQLite.")
        return redirect("dashboard")

    default_connection = connections["default"]
    temp_file_path: str | None = None

    try:
        default_connection.ensure_connection()
        sqlite_connection = default_connection.connection
        if sqlite_connection is None:
            raise RuntimeError("No fue posible abrir la conexion SQLite actual.")

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".sqlite3",
            prefix="game_tracker_backup_",
            delete=False,
        )
        temp_file_path = temp_file.name
        temp_file.close()

        with sqlite3.connect(temp_file_path) as backup_connection:
            sqlite_connection.backup(backup_connection)

        with open(temp_file_path, "rb") as backup_file:
            payload = backup_file.read()

        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        response = HttpResponse(payload, content_type="application/vnd.sqlite3")
        response["Content-Disposition"] = (
            f'attachment; filename="game_tracker_backup_{timestamp}.sqlite3"'
        )
        response["Content-Length"] = str(len(payload))
        return response
    except Exception as exc:
        messages.error(request, f"No fue posible exportar la base SQLite: {exc}")
        return redirect("dashboard")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def import_sqlite_database(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("dashboard")

    db_path = _get_sqlite_db_path()
    if db_path is None:
        messages.error(request, "La importacion solo esta disponible cuando la app usa SQLite.")
        return redirect("dashboard")

    uploaded_database = request.FILES.get("database_file")
    if uploaded_database is None:
        messages.error(request, "Selecciona un archivo SQLite para importar.")
        return redirect("dashboard")

    temp_file_path: str | None = None

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".sqlite3",
            prefix=f"{db_path.stem}_import_",
            dir=db_path.parent,
            delete=False,
        )
        temp_file_path = temp_file.name

        for chunk in uploaded_database.chunks():
            temp_file.write(chunk)
        temp_file.close()

        _validate_sqlite_backup(Path(temp_file_path))
        connections.close_all()

        os.replace(temp_file_path, db_path)
        temp_file_path = None

        for suffix in ("-wal", "-shm"):
            sidecar_path = f"{db_path}{suffix}"
            if os.path.exists(sidecar_path):
                os.remove(sidecar_path)

        messages.success(request, "Base SQLite importada correctamente.")
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"No fue posible importar la base SQLite: {exc}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    return redirect("dashboard")
