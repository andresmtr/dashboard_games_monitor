from django.urls import path

from tracker import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("games/", views.game_list, name="game_list"),
    path("games/new/", views.game_create, name="game_create"),
    path("games/<int:pk>/edit/", views.game_edit, name="game_edit"),
    path("games/<int:pk>/session/", views.session_create, name="session_create"),
    path("sync/steam/", views.sync_steam, name="sync_steam"),
]
