# GraphQL API Guide

The app supports **GraphQL** via `graphene-django`. This allows clients to fetch exactly the data they need in a single request, avoiding the "over-fetching" common in REST APIs.

![GraphQL](https://img.shields.io/badge/-GraphQL-E10098?style=for-the-badge&logo=graphql&logoColor=white)


## Key Features

*   **Smart Pagination:** All list queries include `totalCount`, `limit`, and `offset`.
*   **Context-Aware Fields:** Fields like `myRating` and `watchedByMe` automatically detect the logged-in user.
*   **Dynamic Popularity:** The `popularityScore` is calculated on-the-fly using our hybrid formula.
*   **Deep Filtering:** Support for genre filtering, text search, and watcher-specific history.


## Movie Queries

### 1. Single Movie Detail
Get everything about a specific movie, including its watchers and your own interaction status.

```graphql
query {
  movie(movieId: "<MOVIE_ID>") {
    title
    description
    averageRating
    watchCount
    popularityScore
    genres {
      name
    }
    watchers {
      username
    }
    myRating      # Returns your rating if logged in
    watchedByMe   # Returns true/false based on history
  }
}
```

### 2. All Movies (With Pagination)
Standard list view with total count for frontend pagination.

```graphql
query {
  movies(limit: 10, offset: 0) {
    totalCount
    limit
    offset
    items {
      movieId
      title
      averageRating
      genres {
        name
      }
    }
  }
}
```

### 3. Advanced Search & Filtering
Search by text, filter by genre, and order by specific metrics like `-average_rating`.

```graphql
query {
  movies(
    genre: "Action",
    search: "Avengers",
    orderBy: "-average_rating",
    limit: 5
  ) {
    items {
      movieId
      title
      description
      averageRating
      popularityScore
    }
    totalCount
    limit
    offset
  }
}
```


## User & Personalization

### 1. Current User (`me`)
Check authentication status and get profile info.

```graphql
query {
  me {
    userId
    username
    email
    firstName
    lastName
  }
}
```

### 2. User Watch History
Get all movies watched by a specific user ID.

```graphql
query {
  movies(watcherId: "<USER_ID>") {
    items {
      movieId
      title
      myRating
      watchedByMe # Useful to see if YOU also watched it
    }
  }
}
```


## Ratings & Reviews

### 1. All Ratings (Site-wide)
Great for building a "Recent Activity" feed.

```graphql
query {
  ratings(limit: 10) {
    totalCount
    limit
    offset
    items {
      score
      reviewText
      user {
        username
      }
      movie {
        title
      }
    }
  }
}
```

### 2. Ratings for a Specific Movie
Fetch only the reviews for one film.

```graphql
query {
  ratings(movieId: "<MOVIE_ID>") {
    totalCount
    limit
    offset
    items {
      score
      user {
        username
      }
    }
  }
}
```

### 3. Ratings by a Specific User
Fetch all reviews written by a single person.

```graphql
query {
  ratings(userId: "<USER_ID>") {
    items {
      score
      movie {
        title
      }
    }
  }
}
```


### Authorization
*   **Public Fields:** Anyone can query movie lists, genres, and public ratings.
*   **Private Fields:** `myRating` and `watchedByMe` will return `null` or `false` respectively if the request is not authenticated.
*   **The `me` Query:** Returns `null` if the user is not logged in.

### Endpoint
Access the interactive GraphiQL explorer at:  
[**youssefelghamour.pythonanywhere.com/graphql/**](https://youssefelghamour.pythonanywhere.com/graphql/)