from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from tracker.services.steam import sync_steam_games


class Command(BaseCommand):
    help = "Sincroniza la librería de Steam con GameRecord"

    def add_arguments(self, parser):
        parser.add_argument(
            "--achievements",
            action="store_true",
            help="Incluye consulta de logros por juego (más lenta).",
        )

    def handle(self, *args, **options):
        try:
            result = sync_steam_games(
                api_key=settings.STEAM_API_KEY,
                steam_id=settings.STEAM_ID,
                default_currency=settings.APP_DEFAULT_CURRENCY,
                include_achievements=options["achievements"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Steam sincronizado. Total: {result['total_games']}, "
                f"propios: {result['owned_games']}, recientes: {result['recent_games']}, "
                f"posible préstamo: {result['recent_only']}, "
                f"creados: {result['created']}, actualizados: {result['updated']}"
            )
        )
