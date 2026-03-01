const API_BASE_URL = localStorage.getItem('apiBaseUrl') || 'http://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev';

let currentQuery = '';
let currentOffset = 0;
const LIMIT = 10;
let totalResults = 0;

const searchInput = document.getElementById('search-input');
const searchBtn = document.getElementById('search-btn');
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const resultsInfoEl = document.getElementById('results-info');
const resultsCountEl = document.getElementById('results-count');
const resultsEl = document.getElementById('results');
const paginationEl = document.getElementById('pagination');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const pageInfoEl = document.getElementById('page-info');

searchBtn.addEventListener('click', () => performSearch());
searchInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') performSearch();
});
prevBtn.addEventListener('click', () => changePage(-1));
nextBtn.addEventListener('click', () => changePage(1));

console.log('Movie Search UI loaded. API endpoint:', API_BASE_URL);

async function performSearch(offset = 0) {
  const query = searchInput.value.trim();

  if (!query) {
    showError('Please enter a search query');
    return;
  }

  currentQuery = query;
  currentOffset = offset;

  showLoading(true);
  hideError();

  try {
    const url = new URL(`${API_BASE_URL}/search`);
    url.searchParams.set('q', query);
    url.searchParams.set('limit', LIMIT);
    url.searchParams.set('offset', offset);

    const response = await fetch(url);
    const data = await response.json();

    if (!data.success) {
      throw new Error(data.error || 'Search failed');
    }

    totalResults = data.data.total;
    renderResults(data.data);
    updatePagination();

  } catch (error) {
    showError(`Search failed: ${error.message}`);
    clearResults();
    paginationEl.classList.add('hidden');
    resultsInfoEl.classList.add('hidden');
  } finally {
    showLoading(false);
  }
}

function clearResults() {
  while (resultsEl.firstChild) {
    resultsEl.removeChild(resultsEl.firstChild);
  }
}

function renderResults(data) {
  const { results, total } = data;
  clearResults();

  if (results.length === 0) {
    const emptyState = document.createElement('div');
    emptyState.className = 'empty-state';

    const h3 = document.createElement('h3');
    h3.textContent = 'No movies found';
    emptyState.appendChild(h3);

    const p = document.createElement('p');
    p.textContent = 'Try a different search term';
    emptyState.appendChild(p);

    resultsEl.appendChild(emptyState);
    resultsInfoEl.classList.add('hidden');
    paginationEl.classList.add('hidden');
    return;
  }

  resultsCountEl.textContent = `Found ${total} movie${total !== 1 ? 's' : ''}`;
  resultsInfoEl.classList.remove('hidden');

  results.forEach(movie => {
    const card = createMovieCard(movie);
    resultsEl.appendChild(card);
  });
}

function formatRuntime(seconds) {
  if (!seconds) return null;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

function createMovieCard(movie) {
  const card = document.createElement('div');
  card.className = 'movie-card';

  const posterDiv = document.createElement('div');
  posterDiv.className = 'movie-poster';

  if (movie.image_url) {
    const img = document.createElement('img');
    img.src = movie.image_url;
    img.alt = movie.title;
    img.onerror = function() {
      this.parentElement.innerHTML = '<span class="movie-poster-placeholder">🎬</span>';
    };
    posterDiv.appendChild(img);
  } else {
    posterDiv.innerHTML = '<span class="movie-poster-placeholder">🎬</span>';
  }

  card.appendChild(posterDiv);

  const contentDiv = document.createElement('div');
  contentDiv.className = 'movie-content';

  const header = document.createElement('div');
  header.className = 'movie-header';

  const titleDiv = document.createElement('div');

  const title = document.createElement('span');
  title.className = 'movie-title';
  title.textContent = movie.title;
  titleDiv.appendChild(title);

  const year = document.createElement('span');
  year.className = 'movie-year';
  year.textContent = `(${movie.year || 'N/A'})`;
  titleDiv.appendChild(year);

  const runtime = formatRuntime(movie.running_time_secs);
  if (runtime) {
    const runtimeSpan = document.createElement('span');
    runtimeSpan.className = 'movie-runtime';
    runtimeSpan.textContent = `• ${runtime}`;
    titleDiv.appendChild(runtimeSpan);
  }

  header.appendChild(titleDiv);

  if (movie.rating) {
    const rating = document.createElement('span');
    rating.className = 'movie-rating';
    rating.textContent = `★ ${movie.rating.toFixed(1)}`;
    header.appendChild(rating);
  }

  contentDiv.appendChild(header);

  if (movie.genres && movie.genres.length > 0) {
    const genres = document.createElement('div');
    genres.className = 'movie-genres';
    movie.genres.forEach(g => {
      const tag = document.createElement('span');
      tag.className = 'genre-tag';
      tag.textContent = g;
      genres.appendChild(tag);
    });
    contentDiv.appendChild(genres);
  }

  const highlight = document.createElement('div');
  highlight.className = 'movie-highlight';
  if (movie.highlight) {
    const sanitizedHighlight = sanitizeHighlight(movie.highlight);
    const parser = new DOMParser();
    const doc = parser.parseFromString(sanitizedHighlight, 'text/html');
    Array.from(doc.body.childNodes).forEach(node => {
      highlight.appendChild(node.cloneNode(true));
    });
  } else if (movie.plot) {
    highlight.textContent = movie.plot;
  } else {
    highlight.textContent = 'No description available';
  }
  contentDiv.appendChild(highlight);

  const meta = document.createElement('div');
  meta.className = 'movie-meta';

  if (movie.directors && movie.directors.length > 0) {
    const directorSpan = document.createElement('span');
    directorSpan.textContent = `Director: ${movie.directors.join(', ')}`;
    meta.appendChild(directorSpan);
  }

  if (movie.actors && movie.actors.length > 0) {
    const actorSpan = document.createElement('span');
    actorSpan.textContent = `Cast: ${movie.actors.slice(0, 3).join(', ')}`;
    meta.appendChild(actorSpan);
  }

  contentDiv.appendChild(meta);
  card.appendChild(contentDiv);

  return card;
}

function sanitizeHighlight(text) {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  return escaped
    .replace(/&lt;mark&gt;/g, '<mark>')
    .replace(/&lt;\/mark&gt;/g, '</mark>');
}

function updatePagination() {
  if (totalResults <= LIMIT) {
    paginationEl.classList.add('hidden');
    return;
  }

  paginationEl.classList.remove('hidden');

  const currentPage = Math.floor(currentOffset / LIMIT) + 1;
  const totalPages = Math.ceil(totalResults / LIMIT);

  pageInfoEl.textContent = `Page ${currentPage} of ${totalPages}`;
  prevBtn.disabled = currentOffset === 0;
  nextBtn.disabled = currentOffset + LIMIT >= totalResults;
}

function changePage(direction) {
  const newOffset = currentOffset + (direction * LIMIT);
  if (newOffset >= 0 && newOffset < totalResults) {
    performSearch(newOffset);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function showLoading(show) {
  loadingEl.classList.toggle('hidden', !show);
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.classList.remove('hidden');
}

function hideError() {
  errorEl.classList.add('hidden');
}

window.setApiUrl = function(url) {
  localStorage.setItem('apiBaseUrl', url);
  location.reload();
};
