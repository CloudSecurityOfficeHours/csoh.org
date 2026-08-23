/* CSOH site search frontend.
 *
 * Lazy-loads /search-index.json on first keystroke, builds an in-memory
 * MiniSearch index, runs the query with field weights + prefix + fuzzy
 * matching, expands tokens through a synonyms map, and renders results
 * that deep-link to the matching #section anchor.
 *
 * Loaded after /vendor/minisearch-7.1.2.min.js via two <script defer>
 * tags in /search.html, so the global `MiniSearch` is available here.
 *
 * Kept out of /main.js because main.js loads on every page; search only
 * matters on /search.html and pre-loading the bundle elsewhere would
 * waste bandwidth.
 */
(function () {
    'use strict';

    if (typeof MiniSearch === 'undefined') {
        // Defensive: vendor script failed to load (network, ad-blocker,
        // mis-deploy). Leave the page alone - the noscript fallback
        // explains how to navigate without search.
        return;
    }

    var container = document.getElementById('csoh-search');
    if (!container) return;

    // ----- DOM scaffolding ---------------------------------------------
    // Building these in JS rather than HTML keeps the markup in
    // search.html minimal and lets us re-skin the UI without touching
    // the page template.
    container.innerHTML = [
        '<div class="csoh-search-controls">',
        '  <label class="csoh-search-label" for="csoh-search-input">Search across every page on csoh.org</label>',
        '  <input id="csoh-search-input" type="search" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="e.g. NHI, IRSA, OAuth, blast radius…" aria-describedby="csoh-search-status">',
        '  <div class="csoh-search-filters" role="group" aria-label="Filter results by type">',
        '    <button type="button" data-filter="all" class="csoh-filter-chip is-active" aria-pressed="true">All</button>',
        '    <button type="button" data-filter="guide" class="csoh-filter-chip" aria-pressed="false">Guides</button>',
        '    <button type="button" data-filter="resource" class="csoh-filter-chip" aria-pressed="false">Resources</button>',
        '    <button type="button" data-filter="glossary" class="csoh-filter-chip" aria-pressed="false">Glossary</button>',
        '    <button type="button" data-filter="faq" class="csoh-filter-chip" aria-pressed="false">FAQ</button>',
        '    <button type="button" data-filter="feed" class="csoh-filter-chip" aria-pressed="false">News / Sessions</button>',
        '    <button type="button" data-filter="breach" class="csoh-filter-chip" aria-pressed="false">Breaches</button>',
        '    <button type="button" data-filter="meeting" class="csoh-filter-chip" aria-pressed="false">Recaps</button>',
        '  </div>',
        '</div>',
        '<p id="csoh-search-status" class="csoh-search-status" role="status" aria-live="polite">Start typing to search.</p>',
        '<ol id="csoh-search-results" class="csoh-search-results" aria-label="Search results"></ol>'
    ].join('');

    var input = document.getElementById('csoh-search-input');
    var status = document.getElementById('csoh-search-status');
    var resultsList = document.getElementById('csoh-search-results');
    var filterButtons = container.querySelectorAll('.csoh-filter-chip');

    var currentFilter = 'all';
    var indexState = 'unloaded'; // 'unloaded' | 'loading' | 'ready' | 'failed'
    var miniSearch = null;
    var synonyms = {};
    // Cache loaded docs by id so we can render snippets without re-fetching.
    var docsById = {};

    // ----- Index loading -----------------------------------------------
    function loadIndex() {
        if (indexState !== 'unloaded') return;
        indexState = 'loading';
        status.textContent = 'Loading search index…';
        fetch('/search-index.json', { credentials: 'omit' })
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (payload) {
                synonyms = payload.synonyms || {};
                buildIndex(payload.docs || []);
                indexState = 'ready';
                // If the user already typed something while we were
                // loading, run the search now.
                if (input.value.trim()) runSearch(input.value);
                else status.textContent = 'Start typing to search.';
            })
            .catch(function (err) {
                indexState = 'failed';
                status.textContent = 'Search index failed to load. Try refreshing the page.';
                if (window.console && console.warn) console.warn('search-init: index load failed', err);
            });
    }

    // ----- Index construction ------------------------------------------
    // termProcessor: lowercases everything and, when a token has a
    // synonym group, returns the canonical key prefixed so MiniSearch
    // matches across synonyms at both index- and query-time.
    //
    // Why prefix the canonical form into the indexed string rather than
    // adding alternate fields: MiniSearch deduplicates tokens per doc,
    // and the simplest way to make {"nhi", "non-human", "machine identity"}
    // all hit the same doc is to expand every alias into the same token
    // bag. The expansion happens in expandTokens() below; this processor
    // is just the lowercase + light cleanup pass.
    function termProcessor(term) {
        if (!term) return term;
        // Strip surrounding punctuation but keep internal hyphens
        // ("iam:passrole", "non-human", "in-transit").
        return term.toLowerCase().replace(/^[^\w-]+|[^\w-]+$/g, '');
    }

    function expandTokens(text) {
        // Pull tokens out of text, then add synonym aliases inline.
        // Used at index-build time on each doc's text field.
        var out = [text];
        var tokens = text.toLowerCase().match(/[\w][\w-]*(?:[ ][\w][\w-]*){0,2}/g) || [];
        // Dedup tokens cheaply.
        var seen = {};
        for (var i = 0; i < tokens.length; i++) {
            var t = tokens[i];
            if (seen[t]) continue;
            seen[t] = 1;
            if (synonyms[t]) {
                out.push(synonyms[t].join(' '));
            }
        }
        return out.join(' ');
    }

    function buildIndex(docs) {
        miniSearch = new MiniSearch({
            // Fields searched. Order doesn't matter; weights are in
            // searchOptions.boost below.
            fields: ['title', 'heading', 'page', 'text'],
            // Fields returned with each result for rendering.
            storeFields: ['url', 'page', 'section', 'heading', 'title', 'text', 'type'],
            idField: 'id',
            // Process every term through the same pipeline at index AND
            // query time. MiniSearch is strict about this - using
            // different processors causes "matched at index time but
            // not at query time" bugs that are hard to debug.
            processTerm: termProcessor,
            tokenize: function (str) {
                // Default tokenizer plus: keep tokens with internal
                // colons (iam:passrole) and hyphens (non-human).
                return str.split(/[\s.,;:!?"()[\]{}<>]+/).filter(Boolean);
            }
        });

        // Pre-process each doc's text to inline synonym expansions.
        // The cost is one walk over the corpus at load time; the
        // benefit is that "nhi" naturally matches every doc tagged
        // with "non-human identity" without query-time juggling.
        var prepped = docs.map(function (d) {
            docsById[d.id] = d;
            return {
                id: d.id,
                title: d.title,
                heading: d.heading,
                page: d.page,
                text: expandTokens(d.text || ''),
                url: d.url,
                section: d.section,
                type: d.type
            };
        });
        miniSearch.addAll(prepped);
    }

    // ----- Search execution --------------------------------------------
    function runSearch(rawQuery) {
        var q = (rawQuery || '').trim();
        if (!q) {
            resultsList.innerHTML = '';
            status.textContent = 'Start typing to search.';
            return;
        }
        if (indexState !== 'ready') {
            // Will be retried automatically when the index finishes loading.
            return;
        }

        // Expand the query through the synonyms map so user types "nhi"
        // and we OR-match against "non-human identity" etc. as well.
        var expanded = q;
        var lower = q.toLowerCase();
        if (synonyms[lower]) {
            expanded = q + ' ' + synonyms[lower].join(' ');
        } else {
            // Per-word lookup for multi-word queries.
            var words = lower.split(/\s+/);
            for (var i = 0; i < words.length; i++) {
                if (synonyms[words[i]]) {
                    expanded += ' ' + synonyms[words[i]].join(' ');
                }
            }
        }

        var results = miniSearch.search(expanded, {
            boost: { title: 4, heading: 3, page: 2, text: 1 },
            // Prefix lets "kuber" match "kubernetes". Fuzzy threshold
            // 0.2 catches typos without producing nonsense hits.
            prefix: function (term) { return term.length > 2; },
            fuzzy: function (term) { return term.length > 3 ? 0.2 : false; },
            // OR-combine - any token match contributes; AND would be
            // too restrictive for short queries that hit the synonym
            // expansion ("nhi" expanded to 6 alternates).
            combineWith: 'OR'
        });

        if (currentFilter !== 'all') {
            results = results.filter(function (r) { return (r.type || 'guide') === currentFilter; });
        }

        // Collapse multiple hits within the same URL - only the
        // best-scoring section per URL wins, with a secondary list of
        // other section matches shown beneath the primary result.
        // Exception: glossary terms each get their own result because
        // every term is a standalone definition, not a "section of the
        // glossary page." Collapsing them would hide direct definition
        // hits behind unrelated terms that happen to score higher.
        var byUrl = {};
        var order = [];
        for (var j = 0; j < results.length; j++) {
            var r = results[j];
            var key = r.type === 'glossary' && r.url.indexOf('#') > 0
                ? r.url
                : r.url.split('#')[0];
            if (!byUrl[key]) {
                byUrl[key] = { primary: r, others: [] };
                order.push(key);
            } else {
                byUrl[key].others.push(r);
            }
        }
        var grouped = order.map(function (k) { return byUrl[k]; });
        grouped.sort(function (a, b) { return b.primary.score - a.primary.score; });

        renderResults(grouped, q);
    }

    // ----- Rendering ---------------------------------------------------
    function renderResults(groups, q) {
        if (!groups.length) {
            resultsList.innerHTML = '';
            // `textContent`, so NOT escapeHtml(q): the assignment already
            // treats the string as literal text. Escaping first double-escapes,
            // and a search for `a<b` renders as `a&lt;b` on screen. The escape
            // is only needed on the innerHTML paths below.
            status.textContent = 'No results for "' + q + '". Try a related term, an acronym, or its expansion.';
            return;
        }
        status.textContent = groups.length + (groups.length === 1 ? ' page' : ' pages') + ' matched.';

        var max = Math.min(groups.length, 40);
        var html = '';
        for (var i = 0; i < max; i++) {
            var g = groups[i];
            html += renderGroup(g, q);
        }
        resultsList.innerHTML = html;
    }

    function renderGroup(group, q) {
        var primary = group.primary;
        var doc = docsById[primary.id] || primary;
        var snippet = snippetFor(doc.text || '', q);
        var typeBadge = typeLabel(primary.type);
        var pageLine = '';
        if (primary.section) {
            pageLine = '<span class="csoh-result-breadcrumb">' +
                escapeHtml(doc.page) + ' › ' + escapeHtml(doc.section) + '</span>';
        } else {
            pageLine = '<span class="csoh-result-breadcrumb">' + escapeHtml(doc.page) + '</span>';
        }
        var others = '';
        if (group.others.length) {
            others = '<ul class="csoh-result-others" aria-label="More sections on this page">';
            var shown = Math.min(group.others.length, 4);
            for (var i = 0; i < shown; i++) {
                var o = group.others[i];
                var od = docsById[o.id] || o;
                // Resource cards share their category anchor, so listing
                // od.section would repeat the same category name. The card
                // name is what distinguishes them.
                var label = od.type === 'resource'
                    ? (od.heading || od.section)
                    : (od.section || od.heading);
                others += '<li><a href="' + escapeHtml(od.url) + '">' +
                    escapeHtml(label) + '</a></li>';
            }
            if (group.others.length > shown) {
                others += '<li class="csoh-result-others-more">+' + (group.others.length - shown) + ' more</li>';
            }
            others += '</ul>';
        }
        return [
            '<li class="csoh-result">',
            '  <a class="csoh-result-link" href="', escapeHtml(doc.url), '">',
            '    <span class="csoh-result-type-badge csoh-type-', escapeHtml(primary.type || 'guide'), '">', typeBadge, '</span>',
            '    <span class="csoh-result-title">', highlight(doc.heading || doc.title, q), '</span>',
            '    ', pageLine,
            '    <p class="csoh-result-snippet">', snippet, '</p>',
            '  </a>',
            others,
            '</li>'
        ].join('');
    }

    function typeLabel(t) {
        switch (t) {
            case 'glossary': return 'Glossary';
            case 'faq': return 'FAQ';
            case 'resource': return 'Resource';
            case 'feed': return 'News';
            case 'site': return 'Site';
            case 'breach': return 'Breach';
            case 'meeting': return 'Recap';
            default: return 'Guide';
        }
    }

    // Build a ~220-char snippet around the first match of any query
    // token. Falls back to the doc lead if nothing matches (which can
    // happen when the only hit was via a synonym expansion).
    function snippetFor(text, q) {
        if (!text) return '';
        var lower = text.toLowerCase();
        var tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
        var idx = -1;
        for (var i = 0; i < tokens.length; i++) {
            var t = tokens[i];
            var found = lower.indexOf(t);
            if (found >= 0 && (idx === -1 || found < idx)) idx = found;
        }
        var start, end;
        if (idx === -1) {
            start = 0;
            end = Math.min(text.length, 220);
        } else {
            start = Math.max(0, idx - 80);
            end = Math.min(text.length, idx + 160);
        }
        var snip = text.slice(start, end);
        if (start > 0) snip = '…' + snip;
        if (end < text.length) snip = snip + '…';
        return highlight(snip, q);
    }

    function highlight(text, q) {
        var safe = escapeHtml(text);
        var tokens = q.toLowerCase().split(/\s+/).filter(function (t) { return t.length > 1; });
        if (!tokens.length) return safe;
        // Escape regex metachars in user input before assembling the alternation.
        var pattern = tokens.map(function (t) {
            return t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        }).join('|');
        try {
            var re = new RegExp('(' + pattern + ')', 'gi');
            return safe.replace(re, '<mark>$1</mark>');
        } catch (_) {
            return safe;
        }
    }

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // ----- Event wiring ------------------------------------------------
    var searchTimer = null;
    input.addEventListener('input', function (e) {
        loadIndex();
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () { runSearch(e.target.value); }, 80);
    });
    input.addEventListener('focus', loadIndex, { once: true });

    filterButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            currentFilter = btn.getAttribute('data-filter');
            filterButtons.forEach(function (b) {
                var active = b === btn;
                b.classList.toggle('is-active', active);
                b.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
            runSearch(input.value);
        });
    });

    // ----- Deep-link & autofocus ---------------------------------------
    // Support ?q=foo for shareable search URLs.
    var params = new URLSearchParams(window.location.search);
    var preset = params.get('q');
    if (preset) {
        input.value = preset;
        loadIndex();
        // runSearch will fire as soon as the index loads.
    }
    input.focus();
})();
