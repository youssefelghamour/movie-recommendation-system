from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter, OrderingFilter

from django.db import models
from django.db.models import F, FloatField, ExpressionWrapper, Count
from django_filters.rest_framework import DjangoFilterBackend

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
    authentication_classes = [SessionAuthentication, BasicAuthentication]
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
    authentication_classes = [SessionAuthentication, BasicAuthentication]
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
        if self.action in ["list", "retrieve", "top_rated", "most_watched", "popular"]:
            return [AllowAny()]
        return super().get_permissions()
    
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

        # Get the movies the user has rated >= 3
        liked_movies = Rating.objects.filter(user=user, score__gte=3).values_list('movie', flat=True)

        if not liked_movies.exists():
            # Fallback: return popular movies if user hasn't liked anything
            popular_movies = calc_popularity_score(Movie.objects).exclude(watched_by__user=user).order_by('-popularity_score')

            # Paginate
            page = self.paginate_queryset(popular_movies)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(popular_movies, many=True)
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
        
        # Final ordering to shuffle so we don't get all action movies first then all drama movies.. etc
        # Re-annotate and order by popularity score because after union the field score is lost
        recommended_list = calc_popularity_score(recommended_list).order_by('-popularity_score')

        page = self.paginate_queryset(recommended_list)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(recommended_list, many=True)
        return Response(serializer.data)


class GenreViewSet(viewsets.ModelViewSet):
    """ Viewset for Genre model """
    authentication_classes = [SessionAuthentication, BasicAuthentication]
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


class RatingViewSet(viewsets.ModelViewSet):
    """ Viewset for Rating model """
    authentication_classes = [SessionAuthentication, BasicAuthentication]
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
    authentication_classes = [SessionAuthentication, BasicAuthentication]
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
        """ Allow users to delete their watch history entries
            Since a watch history is created when a user rates a movie, (rated=watched)
            we prevent deletion if there are existing ratings for that user
        """
        history = self.get_object()
        movie = history.movie
        if Rating.objects.filter(user=request.user, movie=movie).exists():
            return Response(
                {"detail": "Cannot delete watch history while ratings exist. Please delete your ratings first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)
