import { APIGatewayProxyEvent, APIGatewayProxyResult } from "aws-lambda";
import { Pool } from "pg";
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";

interface Movie {
  id: string;
  title: string;
  year?: number;
  genres?: string[];
  rating?: number;
  directors?: string[];
  actors?: string[];
  plot?: string;
  release_date?: string;
  rank?: number;
  running_time_secs?: number;
  image_url?: string;
}

const pool = new Pool({
  host: process.env.PARADEDB_HOST || "paradedb.localhost.localstack.cloud",
  port: parseInt(process.env.PARADEDB_PORT || "4566"),
  database: process.env.PARADEDB_DATABASE || "mydatabase",
  user: process.env.PARADEDB_USER || "myuser",
  password: process.env.PARADEDB_PASSWORD || "mypassword",
});

const S3_ENDPOINT = process.env.S3_ENDPOINT || "http://s3.localhost.localstack.cloud:4566";
const DATA_BUCKET = process.env.DATA_BUCKET || "movie-search-data";

const s3Client = new S3Client({
  endpoint: S3_ENDPOINT,
  region: "us-east-1",
  forcePathStyle: true,
  credentials: {
    accessKeyId: "test",
    secretAccessKey: "test",
  },
});

function successResponse(data: unknown): APIGatewayProxyResult {
  return {
    statusCode: 200,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
    body: JSON.stringify({ success: true, data }),
  };
}

function errorResponse(
  statusCode: number,
  message: string
): APIGatewayProxyResult {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
    body: JSON.stringify({ success: false, error: message }),
  };
}

export async function searchHandler(
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> {
  try {
    const query = event.queryStringParameters?.q;
    const limit = parseInt(event.queryStringParameters?.limit || "10");
    const offset = parseInt(event.queryStringParameters?.offset || "0");

    if (!query) {
      return errorResponse(400, "Query parameter 'q' is required");
    }

    console.log(`Searching for: ${query} (limit: ${limit}, offset: ${offset})`);

    const searchQuery = `
      SELECT
        id,
        title,
        year,
        genres,
        rating,
        directors,
        actors,
        image_url,
        running_time_secs,
        plot,
        pdb.snippet(plot, start_tag => '<mark>', end_tag => '</mark>') as highlight,
        pdb.score(id) as score
      FROM movies
      WHERE title ||| $1::pdb.fuzzy(1) OR plot ||| $1::pdb.fuzzy(1)
      ORDER BY score DESC
      LIMIT $2 OFFSET $3
    `;

    const result = await pool.query(searchQuery, [query, limit, offset]);

    const countQuery = `
      SELECT COUNT(*) as total
      FROM movies
      WHERE title ||| $1::pdb.fuzzy(1) OR plot ||| $1::pdb.fuzzy(1)
    `;
    const countResult = await pool.query(countQuery, [query]);
    const total = parseInt(countResult.rows[0].total);

    return successResponse({
      results: result.rows.map((row) => ({
        id: row.id,
        title: row.title,
        year: row.year,
        genres: row.genres,
        rating: row.rating ? parseFloat(row.rating) : null,
        directors: row.directors,
        actors: row.actors,
        image_url: row.image_url,
        running_time_secs: row.running_time_secs,
        highlight: row.highlight,
        plot: row.plot,
      })),
      total,
      limit,
      offset,
    });
  } catch (error) {
    console.error("Search error:", error);
    return errorResponse(500, "Search failed");
  }
}

export async function movieDetailHandler(
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> {
  try {
    const movieId = event.pathParameters?.id;

    if (!movieId) {
      return errorResponse(400, "Movie ID is required");
    }

    console.log(`Fetching movie: ${movieId}`);

    const query = `
      SELECT id, title, year, genres, rating, directors, actors, plot,
             image_url, release_date, rank, running_time_secs
      FROM movies
      WHERE id = $1
    `;

    const result = await pool.query(query, [movieId]);

    if (result.rows.length === 0) {
      return errorResponse(404, "Movie not found");
    }

    const movie = result.rows[0];
    return successResponse({
      id: movie.id,
      title: movie.title,
      year: movie.year,
      genres: movie.genres,
      rating: movie.rating ? parseFloat(movie.rating) : null,
      directors: movie.directors,
      actors: movie.actors,
      plot: movie.plot,
      image_url: movie.image_url,
      release_date: movie.release_date,
      rank: movie.rank,
      running_time_secs: movie.running_time_secs,
    });
  } catch (error) {
    console.error("Movie detail error:", error);
    return errorResponse(500, "Failed to fetch movie");
  }
}

export async function initHandler(): Promise<APIGatewayProxyResult> {
  const client = await pool.connect();

  try {
    console.log("Initializing database schema...");

    await client.query(`
      CREATE TABLE IF NOT EXISTS movies (
        id VARCHAR(20) PRIMARY KEY,
        title TEXT NOT NULL,
        year INTEGER,
        genres TEXT[],
        rating NUMERIC(3,1),
        directors TEXT[],
        actors TEXT[],
        plot TEXT,
        image_url TEXT,
        release_date TIMESTAMPTZ,
        rank INTEGER,
        running_time_secs INTEGER
      )
    `);

    console.log("Movies table created");

    const indexCheck = await client.query(`
      SELECT 1 FROM pg_indexes WHERE indexname = 'movies_search_idx'
    `);

    if (indexCheck.rows.length === 0) {
      console.log("Creating BM25 search index...");

      await client.query(`
        CREATE INDEX movies_search_idx ON movies
        USING bm25 (id, title, plot)
        WITH (key_field = 'id')
      `);

      console.log("BM25 index created");
    } else {
      console.log("BM25 index already exists");
    }

    return successResponse({
      message: "Database initialized successfully",
      table: "movies",
      index: "movies_search_idx",
    });
  } catch (error) {
    console.error("Init error:", error);
    return errorResponse(500, "Initialization failed");
  } finally {
    client.release();
  }
}

export async function seedHandler(): Promise<APIGatewayProxyResult> {
  const client = await pool.connect();

  try {
    console.log(`Loading movie data from S3 bucket: ${DATA_BUCKET}`);

    const command = new GetObjectCommand({
      Bucket: DATA_BUCKET,
      Key: "movies.bulk",
    });

    const response = await s3Client.send(command);
    const bodyString = await response.Body?.transformToString();

    if (!bodyString) {
      return errorResponse(500, "Failed to read movie data from S3");
    }

    const lines = bodyString.trim().split("\n");
    const movies: Movie[] = [];

    for (const line of lines) {
      if (line.trim()) {
        try {
          const movie = JSON.parse(line) as Movie;
          movies.push(movie);
        } catch (e) {
          console.warn(`Skipping invalid JSON line: ${line.substring(0, 50)}...`);
        }
      }
    }

    console.log(`Parsed ${movies.length} movies from bulk file`);

    await client.query("BEGIN");

    try {
      await client.query("DELETE FROM movies");

      const batchSize = 100;
      let inserted = 0;

      for (let i = 0; i < movies.length; i += batchSize) {
        const batch = movies.slice(i, i + batchSize);

        const values: unknown[] = [];
        const placeholders: string[] = [];

        batch.forEach((movie, idx) => {
          const offset = idx * 12;
          placeholders.push(
            `($${offset + 1}, $${offset + 2}, $${offset + 3}, $${offset + 4}, $${offset + 5}, $${offset + 6}, $${offset + 7}, $${offset + 8}, $${offset + 9}, $${offset + 10}, $${offset + 11}, $${offset + 12})`
          );
          values.push(
            movie.id,
            movie.title,
            movie.year || null,
            movie.genres || [],
            movie.rating || null,
            movie.directors || [],
            movie.actors || [],
            movie.plot || null,
            movie.image_url || null,
            movie.release_date || null,
            movie.rank || null,
            movie.running_time_secs || null
          );
        });

        await client.query(
          `INSERT INTO movies (id, title, year, genres, rating, directors, actors, plot,
                               image_url, release_date, rank, running_time_secs)
           VALUES ${placeholders.join(", ")}
           ON CONFLICT (id) DO UPDATE SET
             title = EXCLUDED.title,
             year = EXCLUDED.year,
             genres = EXCLUDED.genres,
             rating = EXCLUDED.rating,
             directors = EXCLUDED.directors,
             actors = EXCLUDED.actors,
             plot = EXCLUDED.plot,
             image_url = EXCLUDED.image_url,
             release_date = EXCLUDED.release_date,
             rank = EXCLUDED.rank,
             running_time_secs = EXCLUDED.running_time_secs`,
          values
        );

        inserted += batch.length;
        console.log(`Inserted ${inserted}/${movies.length} movies...`);
      }

      await client.query("COMMIT");

      console.log(`Seeding complete: ${inserted} movies`);

      return successResponse({
        message: "Data seeded successfully",
        count: inserted,
      });
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    }
  } catch (error) {
    console.error("Seed error:", error);
    return errorResponse(500, "Seeding failed");
  } finally {
    client.release();
  }
}
