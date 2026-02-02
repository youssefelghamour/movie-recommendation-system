# Movie Recommendation System

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Django](https://img.shields.io/badge/django-%23092e20.svg?style=for-the-badge&logo=django&logoColor=white)
![DjangoREST](https://img.shields.io/badge/DJANGO-REST-ff1709?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Swagger](https://img.shields.io/badge/-Swagger-%23Clojure?style=for-the-badge&logo=swagger&logoColor=white)

A movie recommendation API built with Django Rest Framework. It tracks user watch history and ratings to provide a personalized movie discovery experience.

## Recommendation Logic

The recommendation engine uses a **Weighted Genre Proportional Algorithm**. Instead of just looking at your favorite genre, it looks at the balance of everything you enjoy to create a diverse but relevant list.

### How the process works:

1.  **Filtering Likes:** First, the system finds all movies you have rated **3 stars or higher**. We consider these your "liked" movies.
2.  **Genre Analysis:** The system looks at every genre attached to those liked movies.
3.  **Calculating Weights:** It counts how many of your liked movies belong to each genre.
    *   *Example:* If you liked 10 movies total, and 5 are "Action," 3 are "Comedy," and 2 are "Horror," your weights are Action (50%), Comedy (30%), and Horror (20%).
4.  **Determining Quantity:** The app aims to suggest **20 movies**. It uses your weights to decide how many to pick from each category.
    *   *Example:* 10 Action movies (50% of 20), 6 Comedy movies (30% of 20), and 4 Horror movies (20% of 20).
5.  **Picking the Best:** For each genre, it looks for movies you **haven't watched yet**. It picks the top-ranked ones based on their global **Popularity Score**.
6.  **Combining & Cleaning:** Since a movie can belong to both "Action" and "Comedy", which means it can be picked by both genres, the system merges these lists and removes any duplicates.
7.  **Final Polish:** The list is re-sorted by popularity and trimmed to exactly 20 results.

> **Fallback Logic:** If you haven't rated any movies yet, the system defaults to showing you the overall most popular movies on the platform so you aren't left with an empty screen.

## Scoring & Popularity

The app tracks "Quality" and "Quantity" to decide what is trending:

- **Top Rated:** Lists movies with an average rating of 3.0 or higher.
- **Most Watched:** Lists movies based strictly on how many people have watched them.
- **Popular (Hybrid):** This is our main metric. It uses a specific formula:

### Popularity Score

This score is used for the "Popular" list and to rank movies within recommendations.

**Formula:** `(Average Rating * 0.7) + (Watch Count * 0.3)`

*   **Average Rating (70% weight):** We prioritize movies that people actually liked.
*   **Watch Count (30% weight):** We also give credit to movies that are being watched frequently.

## Caching

Because the recommendation logic and popularity math can be heavy, we use **Redis** to store results.

| View/Action | Cache Logic | Expiry |
| :--- | :--- | :--- |
| **Global Lists** | Cached per URL (Popular, Top Rated, etc.) | 15 Minutes |
| **Genres** | Cached globally (Rarely changes) | 1 Hour |
| **Recommendations** | Cached **per User ID** (Unique to you) | 10 Minutes |

**Memory Refresh (Signals):**

We use Django Signals to keep the cache accurate. Whenever you rate a movie or mark one as watched:
1.  The system recalculates the movie's average rating and watch count.
2.  The system **deletes your specific recommendation cache**.
3.  The next time you visit the recommended page, the logic runs fresh to include your latest preferences.

### Live Demo
The API is currently deployed and accessible at: [**Movie Recommendation API on PythonAnywhere**](https://youssefelghamour.pythonanywhere.com/api/)

### API Documentation
The API is fully documented with interactive explorers:
*   **Swagger UI:** [/api/docs/swagger/](https://youssefelghamour.pythonanywhere.com/api/docs/swagger/) (Best for testing)
*   **ReDoc:** [/api/docs/redoc/](https://youssefelghamour.pythonanywhere.com/api/docs/redoc/) (Best for reading)

## Installation & Setup

### Method 1: Using Docker

This method automatically sets up your Python environment, PostgreSQL database, and Redis cache.

1.  **Environment Setup:** Create a `.env` file in the project root:
    ```env
    DB_NAME=movie_db
    DB_USER=postgres
    DB_PASSWORD=password
    DB_HOST=db
    DB_PORT=5432
    ```
2.  **Build and Run:**
    ```bash
    docker-compose up --build
    ```
3.  **Initialize Data:** Open a new terminal and run:
    ```bash
    docker exec -it movies_web_container python manage.py seed
    ```

### Method 2: Manual Setup

Use this if you prefer to run the components separately. Ensure **PostgreSQL** and **Redis** are running on your machine.

1.  **Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
2.  **Requirements:**
    ```bash
    pip install -r requirements.txt
    ```
3. **Configure the Database:** Create a PostgreSQL database and update your environment variables or settings.py to match your local credentials.
4.  **Database Config:**
    Update your `settings.py` or `.env` with your local DB credentials, then migrate:
    ```bash
    python manage.py migrate
    ```
5.  **Seed Data:**
    This command creates test users and imports movies from the provided `movies.csv`, and creates ratings and a watch history for all users.
    ```bash
    python manage.py seed
    ```
6.  **Start Server:**
    ```bash
    python manage.py runserver
    ```

## API Endpoints

### Movie
| Method | Endpoint | Description | Permission |
| :--- | :--- | :--- | :--- |
| GET | `/api/movies/` | List all movies (Supports search/filters) | Public |
| POST | `/api/movies/` | Add a new movie | Admin Only |
| GET | `/api/movies/<id>/` | Get full details of a specific movie | Public |
| PUT/PATCH | `/api/movies/<id>/` | Update movie details | Admin Only |
| DELETE | `/api/movies/<id>/` | Remove a movie from the platform | Admin Only |
| GET | `/api/movies/<id>/ratings/` | See all user ratings for this movie | Public |

### Interactive Movie Actions
| Method | Endpoint | Description | Permission |
| :--- | :--- | :--- | :--- |
| POST | `/api/movies/<id>/rate/` | Rate 1-5 stars. Also marks the movies as watched. | Authenticated |
| POST | `/api/movies/<id>/watch/` | Manually mark a movie as watched | Authenticated |
| POST | `/api/movies/<id>/unwatch/` | Remove from history (only if not rated) | Authenticated |

### Discovery & Rankings
| Method | Endpoint | Description | Permission |
| :--- | :--- | :--- | :--- |
| GET | `/api/movies/recommended/` | Your personal "Weighted Genre" suggestions | Authenticated |
| GET | `/api/movies/popular/` | Top movies by the Popularity Score formula | Public |
| GET | `/api/movies/top-rated/` | Highest average ratings (minimum 3 stars) | Public |
| GET | `/api/movies/most-watched/` | Movies with the highest watch counts | Public |

### User Accounts
| Method | Endpoint | Description | Permission |
| :--- | :--- | :--- | :--- |
| POST | `/api/users/` | Signup for a new account | Public |
| GET | `/api/users/` | List users (Admins see all, Users see self) | Authenticated |
| GET | `/api/users/<id>/` | View user profile details | Auth (Self/Admin) |
| PUT/PATCH | `/api/users/<id>/` | Update profile or change password | Auth (Self) |
| DELETE | `/api/users/<id>/` | Close account | Auth (Self/Admin) |

### Ratings & History
| Method | Endpoint | Description | Permission |
| :--- | :--- | :--- | :--- |
| GET | `/api/ratings/` | List all ratings across the site | Public |
| GET | `/api/ratings/<id>/` | View a specific rating | Public |
| PUT/PATCH | `/api/ratings/<id>/` | Update your rating score or review text | Owner Only |
| DELETE | `/api/ratings/<id>/` | Remove your rating | Owner/Admin |
| GET | `/api/watch-history/` | View your list of watched movies | Authenticated |
| GET | `/api/watch-history/<id>/` | View a specific history entry | Auth (Owner) |

### Genres
| Method | Endpoint | Description | Permission |
| :--- | :--- | :--- | :--- |
| GET | `/api/genres/` | List all available movie genres | Public |
| POST | `/api/genres/` | Create a new genre category | Admin Only |
| GET | `/api/genres/<id>/` | View a specific genre | Public |
| PUT/PATCH | `/api/genres/<id>/` | Update genre name | Admin Only |
| DELETE | `/api/genres/<id>/` | Remove a genre | Admin Only |

### Next Steps
*   **Advanced Security:** Implement a dedicated Django app for IP tracking/blocking with management commands and middlewares, automated blacklisting, detecting anomalies with Celery tasks, and rate limiting.
*   **GraphQL Integration:** Add a GraphQL layer to allow clients to query specific movie metadata without over-fetching, and to include all movie-related data without under-fetching.
*   **Background Tasks:** Integrate **Celery & Celery Beat with RabbitMQ** for scheduled security audits, detecting and flagging suspicious IPs, database and cache cleanup, and automated logging.
*   **Orchestration:** Transition from Docker Compose to **Kubernetes (K8s)** for automated scaling and high availability.
