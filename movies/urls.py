from rest_framework import routers
from django.urls import path, include
from .views import UserViewSet, MovieViewSet, GenreViewSet, RatingViewSet, WatchHistoryViewSet

router = routers.DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'movies', MovieViewSet)
router.register(r'genres', GenreViewSet)
router.register(r'ratings', RatingViewSet)
router.register(r'watch-history', WatchHistoryViewSet)


urlpatterns = [
    path('', include(router.urls)),
]