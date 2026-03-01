# ParadeDB Movie Search Sample App

A CDK application demonstrating ParadeDB's full-text search capabilities with LocalStack.

## Overview

This sample app deploys a serverless movie search application using:

- **AWS Lambda** - Handles search and data operations
- **Amazon API Gateway** - REST API endpoints
- **Amazon S3** - Stores movie dataset
- **ParadeDB** - Full-text search engine (runs as LocalStack extension)

### Dataset

Uses the official [AWS OpenSearch sample movies dataset](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/samples/sample-movies.zip) containing **5,000 movies** with metadata including:

- Title, year, genres, rating
- Directors and actors
- Plot descriptions
- Movie poster images
- Runtime duration

### Features Demonstrated

| Feature | Description |
|---------|-------------|
| **BM25 Ranking** | Industry-standard relevance scoring |
| **Fuzzy Matching** | Handles typos (e.g., "Godfater" finds "Godfather") |
| **Highlighting** | Returns matched text with highlighted terms |
| **Movie Posters** | Rich UI with movie poster images |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/search?q=<query>` | Search movies with BM25 ranking |
| GET | `/movies/{id}` | Get movie details by ID |
| POST | `/admin/init` | Initialize database schema |
| POST | `/admin/seed` | Load movie data from S3 |

## Prerequisites

- [LocalStack](https://localstack.cloud/) installed and running
- [Node.js](https://nodejs.org/) 18+ installed
- [AWS CDK Local](https://github.com/localstack/aws-cdk-local) (`npm install -g aws-cdk-local`)
- [AWS CLI](https://aws.amazon.com/cli/) configured
- ParadeDB extension installed in LocalStack

## Setup

### 1. Start LocalStack with ParadeDB Extension

```bash
# Install the ParadeDB extension
localstack extensions install localstack-extension-paradedb

# Start LocalStack
localstack start
```

### 2. Install Dependencies and Download Dataset

```bash
cd paradedb/sample-movie-search
make install
make download-data
```

The `download-data` target downloads the AWS sample movies dataset (~5000 movies) and preprocesses it for ParadeDB ingestion.

### 3. Deploy the Stack

```bash
make deploy
```

Or manually:

```bash
cdklocal bootstrap
cdklocal deploy
```

After deployment, you'll see output similar to:

```
Outputs:
MovieSearchStack.ApiEndpoint = https://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev/
MovieSearchStack.DataBucketName = movie-search-data
MovieSearchStack.InitEndpoint = https://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev/admin/init
MovieSearchStack.MovieSearchApiEndpointB25066EC = https://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev/
MovieSearchStack.MoviesEndpoint = https://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev/movies/{id}
MovieSearchStack.SearchEndpoint = https://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev/search
MovieSearchStack.SeedEndpoint = https://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev/admin/seed
```

### 4. Initialize Database

Create the movies table and BM25 search index:

```bash
make init
```

### 5. Seed Data

Load movie data from S3 into ParadeDB:

```bash
make seed
```

## Usage

### Search Movies

```bash
# Basic search
curl "http://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev/search?q=redemption"

# With pagination
curl "http://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev/search?q=dark%20knight&limit=5&offset=0"

# Fuzzy search (handles typos)
curl "http://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev/search?q=godfater"
```

### Get Movie Details

```bash
curl "http://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev/movies/tt0111161"
```

### Example Response

```json
{
  "success": true,
  "data": {
    "id": "tt0111161",
    "title": "The Shawshank Redemption",
    "year": 1994,
    "genres": [
      "Crime",
      "Drama"
    ],
    "rating": 9.3,
    "directors": [
      "Frank Darabont"
    ],
    "actors": [
      "Tim Robbins",
      "Morgan Freeman",
      "Bob Gunton"
    ],
    "plot": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.",
    "image_url": "https://m.media-amazon.com/images/M/MV5BODU4MjU4NjIwNl5BMl5BanBnXkFtZTgwMDU2MjEyMDE@._V1_SX400_.jpg",
    "release_date": "1994-09-10T00:00:00.000Z",
    "rank": 80,
    "running_time_secs": 8520
  }
}
```

## Web UI

A web UI with movie posters is included in the `web/` directory.

### Quick Start

```bash
make web-ui
```

This starts a local web server at http://localhost:3000. The UI automatically connects to the API Gateway at `http://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev`.

<img width="2880" height="1402" alt="image" src="https://gist.github.com/user-attachments/assets/63986bfe-709b-4bde-bac8-4df2b15bd41a" />

## How It Works

1. **Dataset Preparation**: Download and preprocess the AWS OpenSearch sample movies dataset

2. **Deployment**: CDK creates Lambda functions, API Gateway, and S3 bucket with movie data (bulk format)

3. **Initialization**: The init Lambda creates the movies table and ParadeDB BM25 index:
   ```sql
   CREATE INDEX movies_search_idx ON movies
   USING bm25 (id, title, plot)
   WITH (key_field = 'id');
   ```

4. **Data Loading**: The seed Lambda reads `movies.bulk` from S3 (newline-delimited JSON) and inserts 5000 movies into ParadeDB

5. **Search**: Queries use ParadeDB's BM25 search with fuzzy matching:
   ```sql
   SELECT id, title, year, genres, rating, directors, actors, image_url, running_time_secs,
          pdb.snippet(plot, start_tag => '<mark>', end_tag => '</mark>') as highlight,
          pdb.score(id) as score
   FROM movies
   WHERE title ||| $1::pdb.fuzzy(1) OR plot ||| $1::pdb.fuzzy(1)
   ORDER BY score DESC
   ```

## References

- [ParadeDB Documentation](https://docs.paradedb.com/)
- [LocalStack Extensions](https://docs.localstack.cloud/aws/tooling/extensions/)
- [AWS CDK Local](https://github.com/localstack/aws-cdk-local)
