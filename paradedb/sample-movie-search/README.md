# ParadeDB Movie Search Sample App

A CDK application demonstrating ParadeDB's full-text search capabilities with LocalStack.

## Overview

This sample app deploys a serverless movie search application using:

- **AWS Lambda** - Handles search and data operations
- **Amazon API Gateway** - REST API endpoints
- **Amazon S3** - Stores movie dataset
- **ParadeDB** - Full-text search engine (runs as LocalStack extension)

### Features Demonstrated

| Feature | Description |
|---------|-------------|
| **BM25 Ranking** | Industry-standard relevance scoring |
| **Fuzzy Matching** | Handles typos (e.g., "Godfater" finds "Godfather") |
| **Highlighting** | Returns matched text with highlighted terms |

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

### 2. Install Dependencies

```bash
cd paradedb/sample-movie-search
make install
```

Or manually:

```bash
npm install
cd lambda && npm install
```

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
curl "https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/search?q=redemption"

# With pagination
curl "https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/search?q=dark%20knight&limit=5&offset=0"

# Fuzzy search (handles typos)
curl "https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/search?q=godfater"
```

### Get Movie Details

```bash
curl "https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/movies/tt0111161"
```

### Example Response

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "id": "tt0111161",
        "title": "The Shawshank Redemption",
        "year": 1994,
        "genres": ["Drama"],
        "rating": 9.3,
        "directors": ["Frank Darabont"],
        "actors": ["Tim Robbins", "Morgan Freeman", "Bob Gunton"],
        "highlight": "...finding solace and eventual <mark>redemption</mark> through acts of common decency."
      }
    ],
    "total": 1,
    "limit": 10,
    "offset": 0
  }
}
```

## Web UI

A minimal web UI is included in the `web/` directory. To use it:

1. Open `web/index.html` in a browser
2. Set the API URL by opening the browser console and running:

```javascript
setApiUrl('https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev')
```

3. Start searching!

## How It Works

1. **Deployment**: CDK creates Lambda functions, API Gateway, and S3 bucket with movie data

2. **Initialization**: The init Lambda creates the movies table and ParadeDB BM25 index:
   ```sql
   CALL paradedb.create_bm25(
     index_name => 'movies_search_idx',
     table_name => 'movies',
     key_field => 'id',
     text_fields => paradedb.field('title') || paradedb.field('plot')
   );
   ```

3. **Data Loading**: The seed Lambda reads `movies.json` from S3 and inserts into ParadeDB

4. **Search**: Queries use ParadeDB's BM25 search with fuzzy matching:
   ```sql
   SELECT *, paradedb.snippet(plot) as highlight
   FROM movies
   WHERE id @@@ paradedb.parse('title:query~1 OR plot:query~1')
   ORDER BY paradedb.score(id) DESC
   ```

## References

- [ParadeDB Documentation](https://docs.paradedb.com/)
- [LocalStack Extensions](https://docs.localstack.cloud/aws/tooling/extensions/)
- [AWS CDK Local](https://github.com/localstack/aws-cdk-local)
