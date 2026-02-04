# ParadeDB Sample App: Movie Search

## Overview

A CDK application demonstrating integration with ParadeDB's full-text search capabilities running in LocalStack. This sample app showcases ParadeDB as a modern Elasticsearch replacement, using BM25 search with fuzzy matching and highlighting.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        LocalStack                                │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐ │
│  │              │     │              │     │                  │ │
│  │  API Gateway │────▶│    Lambda    │────▶│    ParadeDB      │ │
│  │              │     │              │     │   (pg_search)    │ │
│  └──────────────┘     └──────────────┘     └──────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│                       ┌──────────────┐                          │
│                       │      S3      │                          │
│                       │ (movie data) │                          │
│                       └──────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│   Static Web UI  │
│  (HTML/CSS/JS)   │
└──────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Infrastructure | AWS CDK (TypeScript) |
| Lambda Runtime | Node.js 22.x |
| Database | ParadeDB (PostgreSQL + pg_search) |
| Postgres Client | pg (node-postgres) |
| Data Storage | Amazon S3 |
| API | Amazon API Gateway (REST) |
| Frontend | Vanilla HTML/CSS/JS |

## AWS Services Used

- **AWS Lambda** - Handles search and data operations
- **Amazon API Gateway** - REST API endpoints
- **Amazon S3** - Stores movie dataset (JSON)
- **ParadeDB Extension** - Full-text search engine (runs in LocalStack)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/search?q=<query>` | Search movies with BM25 ranking |
| GET | `/movies/:id` | Get movie details by ID |

### Search Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | required | Search query (supports fuzzy matching) |
| `limit` | number | 10 | Max results to return |
| `offset` | number | 0 | Pagination offset |

### Search Response Shape

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
        "actors": ["Tim Robbins", "Morgan Freeman"],
        "highlight": "...two imprisoned men bond over a number of <mark>years</mark>..."
      }
    ],
    "total": 1,
    "limit": 10,
    "offset": 0
  }
}
```

### Movie Detail Response

```json
{
  "success": true,
  "data": {
    "id": "tt0111161",
    "title": "The Shawshank Redemption",
    "year": 1994,
    "genres": ["Drama"],
    "rating": 9.3,
    "directors": ["Frank Darabont"],
    "actors": ["Tim Robbins", "Morgan Freeman"],
    "plot": "Two imprisoned men bond over a number of years..."
  }
}
```

## Search Features Demonstrated

| Feature | Description |
|---------|-------------|
| **BM25 Ranking** | Relevance scoring using BM25 algorithm - the industry standard for text search |
| **Fuzzy Matching** | Handles typos (e.g., "Godfater" finds "Godfather") |
| **Highlighting** | Returns matched text snippets with search terms wrapped in `<mark>` tags |

## Database Schema

```sql
CREATE TABLE movies (
  id VARCHAR(20) PRIMARY KEY,
  title TEXT NOT NULL,
  year INTEGER,
  genres TEXT[],
  rating NUMERIC(3,1),
  directors TEXT[],
  actors TEXT[],
  plot TEXT
);

-- ParadeDB BM25 search index
CALL paradedb.create_bm25(
  index_name => 'movies_search_idx',
  table_name => 'movies',
  key_field => 'id',
  text_fields => paradedb.field('title') || paradedb.field('plot')
);
```

## Dataset

- **Source**: AWS sample-movies dataset (transformed from OpenSearch format)
- **Size**: ~100 movies (curated subset for fast loading)
- **Format**: JSON stored in S3
- **Fields**: id, title, year, genres, rating, directors, actors, plot

## Project Structure

```
paradedb/sample-movie-search/
├── README.md                 # Setup & usage instructions
├── idea.md                   # This document
├── Makefile                  # Development commands
├── package.json              # CDK dependencies
├── tsconfig.json             # TypeScript config
├── cdk.json                  # CDK config
├── bin/
│   └── app.ts                # CDK app entry point
├── lib/
│   └── movie-search-stack.ts # CDK stack definition
├── lambda/
│   ├── package.json          # Lambda dependencies
│   ├── search.ts             # Search handler
│   ├── movie-detail.ts       # Movie detail handler
│   ├── init.ts               # Schema/index creation
│   └── seed.ts               # Data loading from S3
├── data/
│   └── movies.json           # Transformed movie dataset
└── web/
    ├── index.html            # Main HTML page
    ├── style.css             # Styling
    └── script.js             # Search functionality
```

## Setup Flow

### 1. Start LocalStack with ParadeDB Extension

```bash
localstack extensions install localstack-extension-paradedb
localstack start
```

### 2. Deploy Infrastructure

```bash
cd paradedb/sample-movie-search
npm install
cdklocal bootstrap
cdklocal deploy
```

### 3. Initialize Database

```bash
make init
```

This triggers a Lambda that:
- Creates the `movies` table
- Creates the BM25 search index using pg_search

### 4. Seed Data

```bash
make seed
```

This triggers a Lambda that:
- Reads `movies.json` from S3
- Inserts all movies into ParadeDB

### 5. Test the API

```bash
# Search for movies
curl "https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/search?q=redemption"

# Get movie details
curl "https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/movies/tt0111161"
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install all dependencies |
| `make deploy` | Deploy CDK stack to LocalStack |
| `make init` | Create database schema and BM25 index |
| `make seed` | Load movie data from S3 into ParadeDB |
| `make destroy` | Tear down the stack |

## Web UI Features

The minimal web UI provides:

- **Search Box**: Text input with search button
- **Results List**: Movie cards displaying:
  - Title
  - Year
  - Genres (as tags)
  - Rating (stars)
  - Highlighted plot snippet

The UI is served as static files and connects to the API Gateway endpoint.

## ParadeDB Connection

The Lambda connects to ParadeDB via LocalStack's internal networking:

```
PARADEDB_HOST=paradedb.localhost.localstack.cloud
PARADEDB_PORT=5432
PARADEDB_DATABASE=postgres
PARADEDB_USER=postgres
PARADEDB_PASSWORD=postgres
```

## Error Handling

API returns minimal error responses for security:

```json
{
  "success": false,
  "error": "Search failed"
}
```

## What This Demo Shows

1. **ParadeDB as Elasticsearch Replacement**: Full-text search with BM25 ranking directly in Postgres
2. **LocalStack Extension Integration**: Running ParadeDB alongside AWS services in LocalStack
3. **Serverless Search Architecture**: Lambda + API Gateway pattern for search APIs
4. **Data Pipeline**: S3 → Lambda → ParadeDB ingestion flow
5. **Modern TypeScript Stack**: CDK + Node.js 22 + TypeScript throughout

## Not Included (By Design)

- Faceted search / aggregations
- Analytics queries (pg_analytics)
- Automated tests
- Production error handling
- Authentication/authorization
- Caching layer

## References

- [ParadeDB Documentation](https://docs.paradedb.com/)
- [LocalStack Extensions](https://docs.localstack.cloud/aws/tooling/extensions/)
- [AWS CDK Local](https://github.com/localstack/aws-cdk-local)
- [WireMock Sample App](../wiremock/sample-app-runner/) (similar pattern)
- [TypeDB Sample App](https://github.com/typedb-osi/typedb-localstack-demo) (similar pattern)
