import graphene
from movies.schema import Query as MoviesQuery


class Query(MoviesQuery, graphene.ObjectType):
    pass

schema = graphene.Schema(query=Query)
