from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import models
from .models import Rating, WatchHistory


@receiver(post_save, sender=Rating)
@receiver(post_delete, sender=Rating)
def recalculate_movie_average_rating(sender, instance, **kwargs):
    """ Signal to update the average rating of a movie whenever a new rating is created, updated or deleted """
    movie = instance.movie
    ratings = Rating.objects.filter(movie=movie)
    average_rating = ratings.aggregate(average=models.Avg('score'))['average'] or 0
    movie.average_rating = round(average_rating, 2)
    movie.save()