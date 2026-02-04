import graphene
from graphene_django import DjangoObjectType
from .models import Movie, Genre, Rating, WatchHistory, User
from django.db.models import Q


# ────────────── TYPES ──────────────

class GenreType(DjangoObjectType):
    class Meta:
        model = Genre
        fields = "__all__"

class RatingType(DjangoObjectType):
    class Meta:
        model = Rating
        fields = ["score", "review_text", "user", "movie"]

class UserType(DjangoObjectType):
    class Meta:
        model = User
        fields = "__all__"

class MovieType(DjangoObjectType):
    # All ratings of all users for this movie
    ratings = graphene.List(RatingType)
    genres = graphene.List(GenreType)
    # All the users who watched this movies
    watchers = graphene.List(UserType)
    # The rating given to this movie by the current logged in use
    my_rating = graphene.Int()
    # Whether this movie is watched by the current user or not
    watched_by_me = graphene.Boolean()
    popularity_score = graphene.Float()

    class Meta:
        model = Movie
        fields = "__all__"

    def resolve_ratings(self, info):
        return self.ratings.all()

    def resolve_genres(self, info):
        return self.genres.all()

    def resolve_watchers(self, info):
        return [watch_hist.user for watch_hist in self.watched_by.all()]

    def resolve_my_rating(self, info):
        user = info.context.user
        if user.is_anonymous:
            return None
        rating = Rating.objects.filter(user=user, movie=self).first()
        return rating.score if rating else None

    def resolve_watched_by_me(self, info):
        user = info.context.user
        if user.is_anonymous:
            return False
        return WatchHistory.objects.filter(user=user, movie=self).exists()

    def resolve_popularity_score(self, info):
        return round(self.average_rating * 0.7 + self.watch_count * 0.3, 2)


# ────────────── TYPES ──────────────

class MovieListType(graphene.ObjectType):
    items = graphene.List(MovieType)
    total_count = graphene.Int()
    limit = graphene.Int()
    offset = graphene.Int()

class RatingListType(graphene.ObjectType):
    items = graphene.List(RatingType)
    total_count = graphene.Int()
    limit = graphene.Int()
    offset = graphene.Int()


# ────────────── QUERY ──────────────

class Query(graphene.ObjectType):
    movies = graphene.Field(
        MovieListType,
        genre=graphene.String(required=False), # Optional filter by genre name
        watcher_id=graphene.String(required=False),
        limit=graphene.Int(),
        offset=graphene.Int(),
        order_by=graphene.String(), # e.g. "-average_rating" or by "popularity_score"
        search=graphene.String(),
    )

    movie = graphene.Field(
        MovieType,
        movie_id=graphene.UUID(required=True)
    )

    me = graphene.Field(UserType)
    
    ratings = graphene.Field(
        RatingListType,
        user_id=graphene.String(required=False),
        movie_id=graphene.String(required=False),
        limit=graphene.Int(),
        offset=graphene.Int()
    )

    # ────────── RESOLVERS ──────────

    def resolve_movies(self, info, genre=None, watcher_id=None, limit=20, offset=0, order_by=None, search=None):
        """ Return all movies
            - Filter by genre if genre name
            - Filter by watcher user id to only return movies the user watched
        """
        qs = Movie.objects.all()

        if genre:
            qs = qs.filter(genres__name__iexact=genre)
        if watcher_id:
            qs = qs.filter(watched_by__user_id=watcher_id)
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))
        if order_by:
            qs = qs.order_by(order_by)

        total_count = qs.count()
        qs = qs[offset:offset+limit]

        return MovieListType(
            items=qs,
            total_count=total_count,
            limit=limit,
            offset=offset
        )

    def resolve_movie(self, info, movie_id):
        """ Return a single movie by ID """
        return Movie.objects.get(movie_id=movie_id)

    def resolve_me(self, info):
        """ return the current authenticated user """
        user = info.context.user
        if user.is_anonymous:
            return None
        return user
    
    def resolve_ratings(self, info, user_id=None, movie_id=None, limit=20, offset=0):
        """ Return all ratings
            - filter by user_id to get all ratings of a user
            - filter by movie_id to get all ratings for a movie
        """
        qs = Rating.objects.all()
        
        if user_id:
            qs = qs.filter(user__user_id=user_id)
        if movie_id:
            qs = qs.filter(movie__movie_id=movie_id)
        
        total_count = qs.count()
        qs = qs[offset:offset+limit]

        return RatingListType(
            items=qs,
            total_count=total_count,
            limit=limit,
            offset=offset
        )


schema = graphene.Schema(query=Query)
