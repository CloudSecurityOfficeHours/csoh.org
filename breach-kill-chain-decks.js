// breach-kill-chain-decks.html: one search box filters the deck index and
// the deck cards together. An external file because the site's CSP
// (`script-src 'self'`) blocks inline <script>.
//
// The search box ships with .is-hidden and is revealed here, so a reader
// without scripts never sees a box that cannot work. The index is plain
// in-page links and works either way.
(function () {
    const bar = document.getElementById('deckFilter');
    const input = document.getElementById('deckSearch');
    const status = document.getElementById('deckFilterStatus');
    const clearBtn = document.getElementById('clearDeckSearch');
    const index = document.querySelector('.deck-index');
    const cards = Array.from(document.querySelectorAll('.resource-card--deck[id^="deck-"]'));
    if (!bar || !input || !status || !clearBtn || !cards.length) return;

    // Lower-cased, accents dropped, and every run of punctuation turned into
    // one space, so "shai hulud" finds "Shai-Hulud" and "tj actions" finds
    // "tj-actions/changed-files".
    const fold = s => s.normalize('NFKD').replace(/[̀-ͯ]/g, '')
        .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

    // A card is searched by its title, summary, year and platform. The action
    // links are the same on every card, and every card carries an "As of"
    // date, so a search for this year's number would otherwise match them all.
    const META_TAG = /^\d+ slides?$|^As of /;
    const decks = cards.map(card => {
        const parts = Array.from(card.querySelectorAll('h3, p, .resource-tags .tag'))
            .map(n => n.textContent.trim())
            .filter(t => !META_TAG.test(t));
        const link = index ? index.querySelector('a[href="#' + card.id + '"]') : null;
        return { card, item: link ? link.closest('li') : null, text: ' ' + fold(parts.join(' ')) + ' ' };
    });
    const groups = index ? Array.from(index.querySelectorAll('.deck-index-group')) : [];
    const total = decks.length;

    function refresh() {
        // Every word must appear somewhere in the card, in any order.
        const terms = fold(input.value).split(' ').filter(Boolean);
        let shown = 0;
        decks.forEach(d => {
            const match = terms.every(t => d.text.includes(t));
            d.card.classList.toggle('is-hidden', !match);
            if (d.item) d.item.classList.toggle('is-hidden', !match);
            if (match) shown++;
        });
        groups.forEach(g => g.classList.toggle('is-hidden', !g.querySelector('li:not(.is-hidden)')));
        if (index) index.classList.toggle('is-hidden', shown === 0);
        clearBtn.classList.toggle('is-hidden', terms.length === 0);
        if (!terms.length) {
            status.textContent = '';
        } else if (shown === 0) {
            status.textContent = 'No deck matches that search.';
        } else {
            status.textContent = 'Showing ' + shown + ' of ' + total + ' decks.';
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
    input.addEventListener('keydown', e => {
        if (e.key === 'Escape' && input.value) {
            e.preventDefault();
            clear();
        }
    });
    clearBtn.addEventListener('click', clear);

    bar.classList.remove('is-hidden');
    // A browser that restores form fields on back/forward fills the box
    // before this runs, so apply whatever is already there.
    refresh();
})();
