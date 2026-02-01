from django.db.models import F, FloatField, ExpressionWrapper, Count, Q
from .models import Movie, Genre, Rating
from django.db import models
from django.core.cache import cache


def calc_popularity_score(qs):
    """ Annotate queryset with popularity score """
    return qs.annotate(
        popularity_score=ExpressionWrapper(
            F('average_rating') * 0.7 + F('watch_count') * 0.3,
            output_field=FloatField()
        )
    )


def liked_genres(liked_movies):
    """ Return the top liked genres with count of liked movies in each genre """
    return (
        Genre.objects
        .filter(movies__in=liked_movies)
        .annotate(liked_movies_count=Count('movies', filter=models.Q(movies__in=liked_movies)))
        .order_by('-liked_movies_count')
    )


def top_movies_for_genre(user, genre, num_to_pick):
    """ Return a number of most popular movies for a genre excluding already rated movies by user """
    # Get all movies in this genre
    movies_in_genre = Movie.objects.filter(genres=genre)
    # Exclude movies already watched by the user
    # Every rated movie are in watched but not all watched movies are rated
    # So excluding watched movies covers rated movies
    unwatched_movies = movies_in_genre.exclude(watched_by__user=user)
    # Annotate with popularity score field
    movies_with_score = calc_popularity_score(unwatched_movies)
    # Order by popularity score and pick top N
    genre_movies = movies_with_score.order_by('-popularity_score').distinct()[:num_to_pick]

    return genre_movies


def invalidate_user_recommendation_cache(user_id):
    """ Function to invalidate the cache for the recommended view for the user """
    cache_key = f"recommended_movies_user_{user_id}"
    cache.delete(cache_key)
