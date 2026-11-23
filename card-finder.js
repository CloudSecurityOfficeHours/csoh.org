// Card finder: one box holding a search field and an index of a page's
// cards (rendered by tools/card_finder.py). Typing filters the index and the
// cards together. An external file because the site's CSP
// (`script-src 'self'`) blocks inline <script>.
//
// The field ships with .is-hidden and is revealed here, so a reader without
// scripts never sees a box that cannot work. The index is plain in-page links
// and works either way.
//
// No per-page code: the cards are the targets of the index links,
// data-finder-text names the parts of a card that are searched, anything
// inside [data-finder-skip] is left out, and data-finder-noun(s) word the
// status line.
//
// Optional, both rendered by tools/card_finder.py:
// - Buttons carrying data-finder-query sit in the search bar. Pressing one
//   puts its query in the field; pressing it again clears the field. The
//   button whose query is what the field holds is marked aria-pressed, so
//   typing "finance" lights the Finance button too. While a button is lit,
//   only the part of each card named by data-finder-filter is matched, as a
//   whole word: the Crypto button finds the cards tagged Crypto, not a card
//   whose summary says "cryptographically". Any other typing searches the
//   whole card as usual.
// - data-finder-synonyms on the finder holds "word=term" pairs. A synonym
//   typed on its own acts as its industry's button: "bank" lights Finance
//   and finds the cards tagged Finance. Beside other words, a synonym
//   matches a card holding it as a whole word, or tagged with its industry.
//   Synonyms are matched as whole words, so "hospital" does not find
//   "Hospitality" and "law" does not find "flaw".
(function () {
    // Lower-cased, accents dropped, and every run of punctuation turned into
    // one space, so "shai hulud" finds "Shai-Hulud" and "tj actions" finds
    // "tj-actions/changed-files".
    const fold = s => s.normalize('NFKD').replace(/[̀-ͯ]/g, '')
        .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

    function setUp(finder) {
        const bar = finder.querySelector('.card-finder-filter');
        const input = finder.querySelector('.card-finder-input');
        const status = finder.querySelector('.card-finder-count');
        const clearBtn = finder.querySelector('.card-finder-clear');
        const index = finder.querySelector('.card-finder-index');
        const textSelector = finder.dataset.finderText;
        const filterSelector = finder.dataset.finderFilter;
        const noun = finder.dataset.finderNoun || 'card';
        const nouns = finder.dataset.finderNouns || noun + 's';
        if (!bar || !input || !status || !clearBtn || !index || !textSelector) return;

        const synonyms = {};
        (finder.dataset.finderSynonyms || '').split(/\s+/).forEach(pair => {
            const eq = pair.indexOf('=');
            if (eq > 0) synonyms[pair.slice(0, eq)] = pair.slice(eq + 1);
        });
        const buttons = Array.from(finder.querySelectorAll('[data-finder-query]'));

        // A searched node's text without any skipped parts nested inside it,
        // such as the "Industries hit:" label in a card's industries line.
        const searchedText = n => {
            if (!n.querySelector('[data-finder-skip]')) return n.textContent;
            const copy = n.cloneNode(true);
            copy.querySelectorAll('[data-finder-skip]').forEach(s => s.remove());
            return copy.textContent;
        };

        const entries = [];
        index.querySelectorAll('a[href^="#"]').forEach(link => {
            const card = document.getElementById(decodeURIComponent(link.getAttribute('href').slice(1)));
            if (!card) return;
            const text = Array.from(card.querySelectorAll(textSelector))
                .filter(n => !n.closest('[data-finder-skip]'))
                .map(searchedText)
                .join(' ');
            const filterText = filterSelector
                ? Array.from(card.querySelectorAll(filterSelector)).map(searchedText).join(' ')
                : '';
            entries.push({ card, item: link.closest('li'), text: ' ' + fold(text) + ' ',
                filterText: ' ' + fold(filterText) + ' ' });
        });
        if (!entries.length) return;
        const groups = Array.from(index.querySelectorAll('.card-finder-group'));
        const total = entries.length;

        // Where a card's industry is looked for: its filter part when the
        // page names one, otherwise the whole card.
        const tagged = (e, term) => (filterSelector ? e.filterText : e.text).includes(' ' + term + ' ');

        function refresh() {
            // Every word must appear somewhere in the card, in any order.
            const query = fold(input.value);
            const terms = query.split(' ').filter(Boolean);
            // A lone synonym asks for its industry, as that industry's button does.
            const wanted = terms.length === 1 && synonyms[query] !== undefined ? synonyms[query] : query;
            const lit = query !== '' && buttons.find(b => fold(b.dataset.finderQuery) === wanted);
            let shown = 0;
            entries.forEach(e => {
                const match = lit
                    ? tagged(e, wanted)
                    : terms.every(t => synonyms[t] !== undefined
                        ? e.text.includes(' ' + t + ' ') || tagged(e, synonyms[t])
                        : e.text.includes(t));
                e.card.classList.toggle('is-hidden', !match);
                if (e.item) e.item.classList.toggle('is-hidden', !match);
                if (match) shown++;
            });
            groups.forEach(g => g.classList.toggle('is-hidden', !g.querySelector('li:not(.is-hidden)')));
            index.classList.toggle('is-hidden', shown === 0);
            clearBtn.classList.toggle('is-hidden', terms.length === 0);
            buttons.forEach(b => b.setAttribute('aria-pressed', String(b === lit)));
            if (!terms.length) {
                status.textContent = '';
            } else if (shown === 0) {
                status.textContent = 'No ' + noun + ' matches that search.';
            } else {
                status.textContent = 'Showing ' + shown + ' of ' + total + ' ' + nouns + '.';
            }
        }

        function clear() {
            input.value = '';
            refresh();
            input.focus();
        }

        let timer = null;
        input.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(refresh, 100);
        });
        // On the whole bar, so Escape also clears while focus is on a button.
        bar.addEventListener('keydown', e => {
            if (e.key === 'Escape' && input.value) {
                e.preventDefault();
                clear();
            }
        });
        clearBtn.addEventListener('click', clear);
        // Focus stays on the button, so a keyboard reader can press the next
        // one or press this one again to clear.
        buttons.forEach(b => b.addEventListener('click', () => {
            clearTimeout(timer);
            input.value = b.getAttribute('aria-pressed') === 'true' ? '' : b.dataset.finderQuery;
            refresh();
        }));

        bar.classList.remove('is-hidden');
        // A browser that restores form fields on back/forward fills the box
        // before this runs, so apply whatever is already there.
        refresh();
    }

    document.querySelectorAll('.card-finder').forEach(setUp);
})();
