from rest_framework import serializers
from .models import User, Movie, Genre, Rating, WatchHistory


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['user_id', 'username', 'first_name', 'last_name', 'email', 'password']

    # Override create and update to handle password hashing
    def create(self, validated_data):
        """ Create user with hashed password by explicitly using set_password
            otherwise password would be stored in plain text
        """
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)  # hash password
        user.save()
        return user

    def update(self, instance, validated_data):
        """Update user and hash password if it's being updated"""
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)  # hash password
        instance.save()
        return instance


class MovieSerializer(serializers.ModelSerializer):
    """Serializer for Movie model"""
    genres = serializers.PrimaryKeyRelatedField(
        queryset=Genre.objects.all(),
        many=True,
        write_only=True
    )

    genre_names = serializers.StringRelatedField(
        source='genres',
        many=True,
        read_only=True
    )

    # Calculated fields from ratings and watch history & updated with signals
    average_rating = serializers.FloatField(read_only=True)
    watch_count = serializers.IntegerField(read_only=True)

    # only for popular view
    popularity_score = serializers.FloatField(read_only=True)

    class Meta:
        model = Movie
        fields = ['movie_id', 'title', 'description', 'release_date', 'duration',
                  'cast', 'director', 'language', 'country', 'average_rating',
                  'watch_count', 'genres', 'genre_names', 'popularity_score']

    def to_representation(self, instance):
        """ Round popularity_score to 2 decimal places in the output """
        data = super().to_representation(instance)
        if data.get('popularity_score') is not None:
            data['popularity_score'] = round(float(data['popularity_score']), 2)
        return data


class GenreSerializer(serializers.ModelSerializer):
    """Serializer for Genre model"""

    class Meta:
        model = Genre
        fields = ['genre_id', 'name']


class RatingSerializer(serializers.ModelSerializer):
    """Serializer for Rating model"""
    user_id = serializers.ReadOnlyField(source='user.user_id')
    username = serializers.ReadOnlyField(source='user.username')
    movie_id = serializers.ReadOnlyField(source='movie.movie_id')
    movie_title = serializers.ReadOnlyField(source='movie.title')

    class Meta:
        model = Rating
        fields = ['rating_id', 'user_id', 'username', 'movie_id', 'movie_title', 'score', 'review_text']

    def validate_score(self, value):
        """Ensurethe score is between 1 and 5 stars"""
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Score must be between 1 and 5 stars")
        return value


class WatchHistorySerializer(serializers.ModelSerializer):
    """Serializer for WatchHistory model"""
    user_id = serializers.ReadOnlyField(source='user.user_id')
    username = serializers.ReadOnlyField(source='user.username')
    movie_id = serializers.ReadOnlyField(source='movie.movie_id')
    movie_title = serializers.ReadOnlyField(source='movie.title')

    class Meta:
        model = WatchHistory
        fields = ['history_id', 'user_id', 'username', 'movie_id', 'movie_title', 'watched_on']
