/* resources.html hub behaviour: cross-category search, and forwarding for the
   deep links the category split left behind.

   Why a separate file rather than an inline <script>: the production CSP is
   `script-src 'self'` with no 'unsafe-inline', no nonce and no hash, so an
   inline block is dropped by the browser. localhost sends no CSP at all, so
   an inline version would work in every local check and exist only as a
   production bug. See CLAUDE.md.

   Both features read resources-index.json, a compact {slug, page, name, text}
   row per card that build_search_index.py writes beside search-index.json.
   The big index is ~3.7 MB and would be an absurd thing to fetch in order to
   answer a redirect; this one is fetched lazily, and only when something
   actually needs it. */
(function () {
    'use strict';

    var INDEX_URL = '/resources-index.json';
    var MAX_RESULTS = 60;
    var cards = null;
    var loading = null;

    function load() {
        if (cards) return Promise.resolve(cards);
        if (loading) return loading;
        loading = fetch(INDEX_URL, { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) throw new Error('resources-index.json: HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                cards = (data && data.cards) || [];
                return cards;
            })
            .catch(function (err) {
                // Leave `cards` null so a later attempt can retry rather than
                // caching the failure as "no resources exist".
                loading = null;
                throw err;
            });
        return loading;
    }

    /* ---- forwarding old /resources.html#card-<slug> links ---------------- */
    function forwardHash() {
        var hash = window.location.hash || '';
        if (hash.indexOf('#card-') !== 0) return;
        var slug = hash.slice('#card-'.length);
        if (!slug) return;
        load().then(function (rows) {
            for (var i = 0; i < rows.length; i++) {
                if (rows[i].s === slug) {
                    // replace() so Back returns where the reader came from
                    // rather than bouncing through the hub again.
                    window.location.replace('/' + rows[i].p + '#card-' + slug);
                    return;
                }
            }
        }).catch(function () { /* stay on the hub; the categories are right there */ });
    }

    /* ---- forwarding old /resources.html?category=<name> links ------------ */
    // Bookmarks, search results and other sites still carry the old
    // ?category= form; without this they land on the hub with the filter
    // silently ignored.
    var CATEGORY_PAGES = {
        'ctf': 'resources-ctf-challenges.html',
        'lab': 'resources-labs-training.html',
        'tool': 'resources-security-tools.html',
        'certification': 'resources-certifications.html',
        'ai-security': 'resources-ai-security.html',
        'job': 'resources-job-search.html',
        'newsletter': 'resources-newsletters.html'
    };

    function forwardCategory() {
        var params = new URLSearchParams(window.location.search);
        var page = CATEGORY_PAGES[params.get('category')];
        if (page) window.location.replace('/' + page);
    }

    /* ---- cross-category search ------------------------------------------ */
    var input = document.getElementById('resourceSearch');
    var results = document.getElementById('searchResults');
    var grid = document.getElementById('searchResultsGrid');
    var heading = document.getElementById('searchResultsHeading');
    var none = document.getElementById('noResults');
    var categories = document.getElementById('categoryGrid');

    function esc(t) {
        var d = document.createElement('div');
        d.textContent = t == null ? '' : String(t);
        return d.innerHTML;
    }

    function render(matches, term) {
        grid.textContent = '';
        for (var i = 0; i < matches.length; i++) {
            var c = matches[i];
            var a = document.createElement('a');
            a.className = 'card-link';
            a.href = '/' + c.p + '#card-' + c.s;
            a.innerHTML =
                '<div class="resource-card" data-icon="🔎">' +
                '<h3>' + esc(c.n) + '</h3>' +
                '<p>' + esc((c.t || '').slice(0, 160)) + '…</p>' +
                '</div>';
            grid.appendChild(a);
        }
        var n = matches.length;
        heading.textContent = n
            ? n + (n === MAX_RESULTS ? '+' : '') + ' result' + (n === 1 ? '' : 's') +
              ' for “' + term + '”'
            : 'No results for “' + term + '”';
        none.classList.toggle('is-hidden', n !== 0);
        results.classList.remove('is-hidden');
        categories.classList.add('is-hidden');
    }

    function clear() {
        results.classList.add('is-hidden');
        categories.classList.remove('is-hidden');
        grid.textContent = '';
    }

    function search(term) {
        var q = term.trim().toLowerCase();
        if (q.length < 2) { clear(); return; }
        load().then(function (rows) {
            var out = [];
            for (var i = 0; i < rows.length && out.length < MAX_RESULTS; i++) {
                var r = rows[i];
                if ((r.n + ' ' + r.t).toLowerCase().indexOf(q) !== -1) out.push(r);
            }
            render(out, term.trim());
        }).catch(function () {
            heading.textContent = 'Search is unavailable right now. Browse by category below.';
            none.classList.add('is-hidden');
            results.classList.remove('is-hidden');
            categories.classList.remove('is-hidden');
        });
    }

    if (input && results && grid && heading && none && categories) {
        var timer = null;
        input.addEventListener('input', function () {
            var v = input.value;
            clearTimeout(timer);
            timer = setTimeout(function () { search(v); }, 150);
        });
        // Warm the index on first focus so the first keystroke feels instant.
        input.addEventListener('focus', function () { load().catch(function () {}); },
                               { once: true });
    }

    forwardCategory();
    forwardHash();
    window.addEventListener('hashchange', forwardHash);
}());
