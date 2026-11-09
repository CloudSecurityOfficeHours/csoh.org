// glossary.html search - filters dt/dd pairs and section headings
// based on a single search input. Lives in an external file because
// the site's strict CSP (`script-src 'self'`) blocks inline <script>.
(function () {
    const search = document.getElementById('glossarySearch');
    const noResults = document.getElementById('noGlossaryResults');
    const clearBtn = document.getElementById('clearGlossarySearch');
    const countEl = document.getElementById('visibleTerms');
    const lists = Array.from(document.querySelectorAll('.glossary-list'));
    if (!search || !lists.length) return;

    // Build pairs: each <dt> + the run of <dd>s that follow it (until next <dt>).
    const pairs = [];
    lists.forEach(list => {
        const children = Array.from(list.children);
        let current = null;
        children.forEach(node => {
            if (node.tagName === 'DT') {
                if (current) pairs.push(current);
                current = {
                    dt: node,
                    dds: [],
                    list,
                    text: node.textContent.toLowerCase(),
                };
            } else if (node.tagName === 'DD' && current) {
                current.dds.push(node);
                // The "Used on N pages" list names other pages. Matching its
                // text would show a term for every page title containing the
                // query, so it hides and shows with its term but is not searched.
                if (!node.classList.contains('term-usage')) {
                    current.text += ' ' + node.textContent.toLowerCase();
                }
            }
        });
        if (current) pairs.push(current);
        current = null;
    });

    // Track the section headings (h2[id]) so we can hide a whole section
    // when none of its terms match.
    const sectionHeadings = Array.from(document.querySelectorAll('main .content-section h2[id]'));
    const sectionPairs = sectionHeadings.map(h => {
        // The section's pairs are the ones whose list comes after this
        // heading and before the next h2[id].
        const next = sectionHeadings[sectionHeadings.indexOf(h) + 1] || null;
        const docPairs = pairs.filter(p => {
            const after = h.compareDocumentPosition(p.dt) & Node.DOCUMENT_POSITION_FOLLOWING;
            const before = !next || (next.compareDocumentPosition(p.dt) & Node.DOCUMENT_POSITION_PRECEDING);
            return after && before;
        });
        return { heading: h, pairs: docPairs };
    });

    const totalTerms = pairs.length;

    function setHidden(el, hidden) {
        el.classList.toggle('is-hidden', hidden);
    }

    function refresh() {
        const term = search.value.trim().toLowerCase();
        let visible = 0;

        pairs.forEach(p => {
            const match = !term || p.text.includes(term);
            setHidden(p.dt, !match);
            p.dds.forEach(dd => setHidden(dd, !match));
            if (match) visible++;
        });

        // Hide sections (and their h2) where no terms match.
        sectionPairs.forEach(s => {
            const anyVisible = !term || s.pairs.some(p => !p.dt.classList.contains('is-hidden'));
            setHidden(s.heading, !anyVisible);
            // Hide the dl too if entirely empty so the gap collapses.
            const list = s.pairs.length ? s.pairs[0].list : null;
            if (list) {
                const allHidden = s.pairs.every(p => p.dt.classList.contains('is-hidden'));
                setHidden(list, allHidden);
            }
        });

        if (countEl) countEl.textContent = String(visible);
        if (noResults) setHidden(noResults, visible !== 0);
    }

    let timer = null;
    search.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(refresh, 100);
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            search.value = '';
            refresh();
            search.focus();
        });
    }

    // Esc clears the search.
    search.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && search.value) {
            search.value = '';
            refresh();
        }
    });

    if (countEl) countEl.textContent = String(totalTerms);
    refresh();
})();
