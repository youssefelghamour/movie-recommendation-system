from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter, OrderingFilter

from django.db import models
from django.db.models import F, FloatField, ExpressionWrapper, Count, Avg, Count, Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models.functions import Coalesce

from .models import User, Movie, Genre, Rating, WatchHistory
from .serializers import UserSerializer, MovieSerializer, GenreSerializer, RatingSerializer, WatchHistorySerializer
from .permissions import IsRatingOwner, DenyUpdate, IsHistoryOwner
from .filters import MovieFilter
from .utils import calc_popularity_score, liked_genres, top_movies_for_genre


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class UserViewSet(viewsets.ModelViewSet):
    """ Viewset for User model"""
    permission_classes = [IsAuthenticated]
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        """ Authenticated user can only see their own info """
        # Admin can see all the users
        if self.request.user.is_staff:
            return super().get_queryset()
        # The logged-in user
        return super().get_queryset().filter(user_id=self.request.user.user_id)

    def get_permissions(self):
        """Allow unauthenticated access to POST /users/ for signup"""
        if self.action == "create":  # signup
            return [AllowAny()]
        return super().get_permissions()


class MovieViewSet(viewsets.ModelViewSet):
    """ Viewset for Movie model with rating and watch actions
        and recommendation features

            - Public: list, retrieve, top_rated, most_watched, popular
            - Authenticated: rate, watch, recommended
            - Admin: create, update, delete
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = MovieFilter
    queryset = Movie.objects.all().order_by('-created_at')
    serializer_class = MovieSerializer

    # Text search
    search_fields = ['title', 'cast', 'director', 'description']

    # Sorting
    ordering_fields = ['average_rating', 'watch_count', 'release_date']
    ordering = ['-created_at']

    def get_permissions(self):
        """ Allow unauthenticated access to list and retrieve movies """
        if self.action in ['rate', 'watch', 'recommended']:
            return [IsAuthenticated()]
        if self.action in ["list", "retrieve", "top_rated", "most_watched", "popular", "trending"]:
            return [AllowAny()]
        return super().get_permissions()

    # Cache list of movies for 15 min
    @method_decorator(cache_page(60*15))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # Cache single movie retrieve for 15 min
    @method_decorator(cache_page(60*15))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='ratings', permission_classes=[AllowAny])
    def ratings(self, request, pk=None):
        """ Get the ratings of a movie """
        movie = self.get_object()
        ratings = movie.ratings.all().order_by('-created_at')

        page = self.paginate_queryset(ratings)
        if page is not None:
            serializer = RatingSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = RatingSerializer(ratings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def rate(self, request, pk=None):
        """ Action for an authenticated user to rate a movie """
        movie = self.get_object()

        # Make sure the user hasn't rated this movie already
        # If so they should do an update in RatingViewSet, not create
        user = request.user
        user_rating = Rating.objects.filter(user=user, movie=movie)

        if user_rating.exists():
            return Response(
                {"detail": "You have already rated this movie. Please update your rating instead in /ratings/<id>/."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = RatingSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(user=user, movie=movie)

            # If a user rates a movie, we mark it as watched by creating a watch history entry if it doesn't exist
            user_history = WatchHistory.objects.filter(user=user, movie=movie)
            if not user_history.exists():
                WatchHistory.objects.create(user=user, movie=movie)

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def watch(self, request, pk=None):
        """ Action for an authenticated user to mark a movie as watched """
        movie = self.get_object()
        user = request.user

        # Make sure the user doesn't mark this movie as watched twice
        user_history = WatchHistory.objects.filter(user=user, movie=movie)

        if user_history.exists():
            return Response(
                {"detail": "You have already watched this movie."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = WatchHistorySerializer(data={})
        if serializer.is_valid():
            serializer.save(user=user, movie=movie)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def unwatch(self, request, pk=None):
        """ Action for an authenticated user to unwatch a movie
            Allow users to delete their watch history entries
            Since a watch history is created when a user rates a movie, (rated=watched)
            we prevent deletion if there are existing ratings for that user
        """
        movie = self.get_object()
        user = request.user

        # Make sure the history exists, the movie is watched by this user
        history = WatchHistory.objects.filter(user=user, movie=movie).first()
        if not history:
            return Response({"detail": "You haven't watched this movie yet."}, status=404)

        if Rating.objects.filter(user=user, movie=movie).exists():
            return Response(
                {"detail": "Cannot delete watch history while ratings exist. Please delete your ratings first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        history.delete()
        return Response({"detail": "Movie removed from watch history."}, status=204)

    @method_decorator(cache_page(60 * 15))  # cache for 15min
    @action(detail=False, methods=['get'], url_path='top-rated')
    def top_rated(self, request):
        """ Action to get top rated movies with an average rating >= 3 """
        top_rated_movies = Movie.objects.filter(average_rating__gte=3).order_by('-average_rating')

        # [EDGE CASE]: In case there are no movies with average rating >=3, return top 10 anyway
        if not top_rated_movies.exists():
            top_rated_movies = Movie.objects.all().order_by('-average_rating')

        # manually paginate
        page = self.paginate_queryset(top_rated_movies)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(top_rated_movies, many=True)
        return Response(serializer.data)

    @method_decorator(cache_page(60 * 15))
    @action(detail=False, methods=['get'], url_path='most-watched')
    def most_watched(self, request):
        """ Action to get the most watched movies """
        most_watched_movies = Movie.objects.all().order_by('-watch_count')

        # manually paginate
        page = self.paginate_queryset(most_watched_movies)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(most_watched_movies, many=True)
        return Response(serializer.data)

    @method_decorator(cache_page(60 * 15))
    @action(detail=False, methods=['get'], url_path='popular')
    def popular(self, request):
        """ Action to get the most popular movies based on a calculation of
            popularity_score = (average_rating * 0.7) + (watch_count * 0.3)
            having the rating weigh more than watch count
        """
        popular_movies = Movie.objects.annotate(
            popularity_score = ExpressionWrapper(
                F('average_rating') * 0.7 + F('watch_count') * 0.3,
                output_field=FloatField()
            )
        ).order_by('-popularity_score')

        # manually paginate
        page = self.paginate_queryset(popular_movies)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(popular_movies, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='recommended', permission_classes=[IsAuthenticated])
    def recommended(self, request):
        """ Action to get recommended movies for the authenticated user
            based on the top genres from their liked movies (rated >=3)
        """
        """
            If the user liked 5 action movies but 1 drama movie, we should
            recommend more action movies than drama movies

            The recommendation algorithm works as follows:
            1. Get the movies the user has rated >= 3
            2. Filter the liked genres that include movies from the liked movies
            3. For each liked genre, count how many liked movies by the user are in that genre
            4. Order genres by the count of liked movies in descending order to get the most liked genres at the top
            5. For each genre, calculate the proportion of liked movies in that genre to the total liked movies
               e.g. if the user liked 5 action movies out of 10 total liked movies, action genre weight/proportion is 0.5
            6. Based on the proportion, determine how many movies to recommend from that genre out of a total of 20 movies
               e.g. for action genre with 50% proportion, we recommend 10 movies from that genre: 0.5*total
            7. From each genre, get the top movies not yer watched & rated ordered by popularity score
            8. Combine all the selected movies from each genre into a final recommended list
            9. Return the final recommended list ordered by popularity score
        """
        user = request.user
        cache_key = f"recommended_movies_user_{user.user_id}"

        # Check for cache hit
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        # Get the movies the user has rated >= 3
        liked_movies = Rating.objects.filter(user=user, score__gte=3).values_list('movie', flat=True)

        if not liked_movies.exists():
            # Fallback: return popular movies if user hasn't liked anything
            popular_movies = calc_popularity_score(Movie.objects).exclude(watched_by__user=user).order_by('-popularity_score')

            # Paginate
            page = self.paginate_queryset(popular_movies)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                data = serializer.data
                # cache for 10 min
                cache.set(cache_key, data, timeout=60 * 10)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(popular_movies, many=True)
            data = serializer.data
            # cache for 10 min
            cache.set(cache_key, data, timeout=60 * 10)
            return Response(serializer.data)

        # Get top liked genres with count of liked movies in each genre ordered desc
        ordered_liked_genres = liked_genres(liked_movies)

        # Get the number of movies liked by the user
        total_liked_movies = liked_movies.count()

        recommended_list = Movie.objects.none()
        for genre in ordered_liked_genres:
            # Get the weight of this genre
            proportion = genre.liked_movies_count / total_liked_movies

            # Number of movies to pick from this genre out of 20 total, at least 1 movie
            num_to_pick = max(1, int(proportion * 20))

            # Get the number of most popular movies in this genre that haven't been watched by this user
            genre_movies = top_movies_for_genre(user, genre, num_to_pick)

            # union querysets
            recommended_list = recommended_list | genre_movies

        """
            Since a movie can belong to many genres, that means it's counted for every genre as a liked movie
            Which inflates genre.liked_movies_count and the proportion
                We expect the sum of all liked_movies_count for all genres to = total_liked movies
                which isn't the case since we count a movie multiple times (once for every genre)
            Result is each genre picks the movie, so the proportion of each genre is slightly higher
            And we end up returning a result exceeding 20 movies
            That's why since we order by popularity score we can limit the result to 20 again
        """
        # Final ordering to shuffle so we don't get all action movies first then all drama movies.. etc
        # Re-annotate and order by popularity score because after union the field score is lost
        recommended_list = calc_popularity_score(recommended_list).order_by('-popularity_score')[:20]

        page = self.paginate_queryset(recommended_list)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            # cache for 10 min
            cache.set(cache_key, data, timeout=60 * 10)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(recommended_list, many=True)
        data = serializer.data
        # cache for 10 min
        cache.set(cache_key, data, timeout=60 * 10)
        return Response(serializer.data)

    @method_decorator(cache_page(60 * 30))  # cache for 30min
    @action(detail=False, methods=['get'], url_path='trending')
    def trending(self, request):
        """ Action to get the trending movies in the past time window the client chooses
            Logic:
                1. Annotate the movies list with fields for ratings they have received during this time period
                2. Likewise for the watch history
                3. Filter out movies that haven't been rated or watched in this time window
                4. Annotate the movies remaining with a trending score similar to popularity_score:
                    recent_avg_rating * 0.6 + recent_watch_count * 0.4
                5. Order and return the movies in descending order based on this score
        """
        try:
            # Get the time window from the client or default to 30 previous days
            days = int(request.query_params.get("days", 30))
        except ValueError:
            days = 30

        # Make sure the client doesn't go beyond the appropriate time window
        if days < 7 or days > 30:
            days = 30

        # The cutoff date so we only include movies after this date
        since = timezone.now() - timezone.timedelta(days=days)

        # Filter movies that have been best rated or watched the most during this time period
        trending_movies = Movie.objects.annotate(
            recent_avg_rating=Coalesce(Avg('ratings__score', filter=Q(ratings__created_at__gte=since)), 0.0),
            recent_watch_count=Coalesce(Count('watched_by', filter=Q(watched_by__watched_on__gte=since)), 0)
        ).filter(
            Q(recent_watch_count__gt=0) |
            Q(recent_avg_rating__gt=0)
        ).annotate(
            trending_score=ExpressionWrapper(
                (F('recent_avg_rating') * 0.6) + (F('recent_watch_count') * 0.4),
                output_field=FloatField()
            )
        ).order_by('-trending_score')

        page = self.paginate_queryset(trending_movies)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(trending_movies, many=True)
        return Response(serializer.data)

class GenreViewSet(viewsets.ModelViewSet):
    """ Viewset for Genre model """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer

    def get_permissions(self):
        """Allow unauthenticated access to list and retrieve genres
            Create, update, delete are admin only
        """
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return super().get_permissions()

    # Cache list of genres for 1 hour (they change very rarely)
    @method_decorator(cache_page(60*60))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # Cache single genre retrieve for 1 hour
    @method_decorator(cache_page(60*60))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class RatingViewSet(viewsets.ModelViewSet):
    """ Viewset for Rating model """
    permission_classes = [IsAuthenticated, IsRatingOwner]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

    filterset_fields = {
        'user__username': ['exact', 'icontains'],
        'movie__title': ['exact', 'icontains'],
        'score': ['exact', 'gte', 'lte'],
    }

    def create(self, request, *args, **kwargs):
        """ Create a rating is movie specific so it's handled in MovieViewSet rate action """
        return Response(
            {"detail": "Use /movies/<id>/rate/ instead to create a rating."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def get_permissions(self):
        """ Allow unauthenticated access to list and retrieve ratings """
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return super().get_permissions()


class WatchHistoryViewSet(viewsets.ModelViewSet):
    """ Viewset for WatchHistory model """
    permission_classes = [IsAuthenticated, DenyUpdate, IsHistoryOwner]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    queryset = WatchHistory.objects.all()
    serializer_class = WatchHistorySerializer

    filterset_fields = {
        'user__username': ['exact', 'icontains'],
        'movie__title': ['exact', 'icontains'],
    }

    def get_queryset(self):
        """ Authenticated user can only see their own watch history """
        # Admin can see all the watch history entries
        if self.request.user.is_staff:
            return super().get_queryset()
        # Only return watch history entries for the authenticated user for list and retrieve
        return super().get_queryset().filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """ Create a watch history is movie specific so it's handled in MovieViewSet watch action """
        return Response(
            {"detail": "Use /movies/<id>/watch/ instead to create a watch history."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def destroy(self, request, *args, **kwargs):
        """ Delete a watch history is movie specific so it's handled in MovieViewSet unwatch action """
        return Response(
            {"detail": "Use /movies/<id>/unwatch/ instead to delete a watch history (unwatch a movie)."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
