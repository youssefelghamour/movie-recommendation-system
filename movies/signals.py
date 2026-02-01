from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import models
from .models import Rating, WatchHistory
from django.core.cache import cache
from .utils import invalidate_user_recommendation_cache


@receiver(post_save, sender=Rating)
@receiver(post_delete, sender=Rating)
def recalculate_movie_average_rating(sender, instance, **kwargs):
    """ Signal to update the average rating of a movie whenever a new rating is created, updated or deleted """
    movie = instance.movie
    ratings = Rating.objects.filter(movie=movie)
    average_rating = ratings.aggregate(average=models.Avg('score'))['average'] or 0
    movie.average_rating = round(average_rating, 2)
    movie.save()

    # Invalidate this user's recommendations
    invalidate_user_recommendation_cache(instance.user.user_id)


@receiver(post_save, sender=WatchHistory)
@receiver(post_delete, sender=WatchHistory)
def recalculate_movie_watch_count(sender, instance, **kwargs):
    """ Signal to update the watch count of a movie whenever a new watch history is created or deleted """
    movie = instance.movie
    movie.watch_count = WatchHistory.objects.filter(movie=movie).count()
    movie.save()

    # Invalidate this user's recommendations
    invalidate_user_recommendation_cache(instance.user.user_id)
