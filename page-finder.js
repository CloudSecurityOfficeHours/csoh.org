// Page finder: a "Find on this page" field inside a long guide's "On this
// page" box (.toc), or at the top of a breach kill chain (.kill-chain).
// tools/sync_page_finder.py stamps the field into those pages. An external
// file because the site's CSP (`script-src 'self'`) blocks inline <script>.
//
// Typing highlights every match in the article and, in a guide, narrows the
// box's list to the sections holding one, each with its count. Enter or the
// down arrow steps to the next match, Shift+Enter or the up arrow to the
// previous one, and choosing a section in the narrowed list jumps to its
// first match. Escape clears. The first step goes to the first match below
// the top of the window, as a browser's own find does. While a search is on,
// the field carries .is-finding, which pins it under the header on a kill
// chain (breach-timeline.css), where no box lists the steps.
//
// Matching ignores case and starts at the beginning of a word, so "sso" finds
// "SSO" but not "lesson". The words of a query match as a phrase with any
// spacing or punctuation between them, so "tj actions" finds "tj-actions",
// but a phrase never runs from one paragraph, heading or cell into the next.
//
// Highlights use the CSS Custom Highlight API (::highlight in style.css), so
// the page's markup is never rewritten. In a browser without it the list
// still narrows and the arrows still scroll; nothing is painted.
//
// The field is in the page's HTML and visible from the first paint, so the
// script running moves nothing. noscript.css hides it from readers without
// scripts, for whom it could do nothing.
(function () {
    const finder = document.querySelector('.page-finder');
    if (!finder) return;
    // Null on a kill chain, which has no contents box to narrow.
    const toc = finder.closest('.toc');
    const input = finder.querySelector('.page-finder-input');
    const status = finder.querySelector('.page-finder-count');
    const prevBtn = finder.querySelector('.page-finder-prev');
    const nextBtn = finder.querySelector('.page-finder-next');
    const root = document.querySelector('main');
    if (!input || !status || !prevBtn || !nextBtn || !root) return;

    const canPaint = typeof Highlight === 'function' && window.CSS && CSS.highlights;
    // Enough for any real query; a two-letter one on the longest guide stays
    // well under it. Past it, painting and stepping are not worth the cost.
    const MAX = 2000;

    // Text a reader does not see as part of the article: the contents box,
    // the field itself, navigation (a kill chain's previous/next links),
    // controls, drawings, and anything hidden.
    const SKIP = 'script, style, noscript, template, svg, nav, button, select, textarea, .toc,'
        + ' .page-finder, .visually-hidden, [hidden], .is-hidden, [aria-hidden="true"]';
    // Elements that end a run of text. A phrase never matches across one.
    const BLOCK = /^(ADDRESS|ARTICLE|ASIDE|BLOCKQUOTE|CAPTION|DD|DETAILS|DIV|DL|DT|FIGCAPTION|FIGURE|FOOTER|H[1-6]|HEADER|LI|MAIN|NAV|OL|P|PRE|SECTION|SUMMARY|TABLE|TD|TH|TR|UL)$/;
    const SEP = '\u0000';

    // One entry per link in the box, in page order, with its <li>.
    const entries = [];
    const box = toc || finder;
    box.querySelectorAll('li > a[href^="#"]').forEach(a => {
        const target = document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
        if (target) entries.push({ a, li: a.parentElement, target, count: 0, first: -1, badge: null });
    });
    entries.sort((x, y) => (x.target.compareDocumentPosition(y.target) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
    const items = Array.from(box.querySelectorAll('li'));
    const lists = Array.from(box.querySelectorAll('ol, ul'));

    let matches = [];   // { range, entry }
    let current = -1;   // index into matches of the one stepped to, or -1
    let over = false;   // more than MAX matches

    // A pattern for the query, or null while it is too short to search.
    function pattern(query) {
        const words = query.match(/[\p{L}\p{N}]+/gu);
        if (!words || words.join('').length < 2) return null;
        const body = words.join('[^\\p{L}\\p{N}' + SEP + ']+');
        try {
            return new RegExp('(?<![\\p{L}\\p{N}])' + body, 'giu');
        } catch (e) {
            // A browser without lookbehind matches anywhere in a word instead.
            return new RegExp(body, 'giu');
        }
    }

    // The article's visible text as one string, a separator at every block
    // boundary, with each text node's offset into it.
    function collect() {
        const nodes = [];
        const seen = new Map();
        const visible = el => {
            if (!el.checkVisibility) return true;
            let v = seen.get(el);
            if (v === undefined) {
                // A closed <details> hides its body until it opens, and
                // stepping to a match inside one opens it.
                v = el.checkVisibility() || !!el.closest('details:not([open])');
                seen.set(el, v);
            }
            return v;
        };
        const blockOf = n => {
            let el = n.parentElement;
            while (el && el !== root && !BLOCK.test(el.tagName)) el = el.parentElement;
            return el;
        };
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
            acceptNode(n) {
                if (n.nodeType === Node.ELEMENT_NODE) {
                    return n.matches(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_SKIP;
                }
                return visible(n.parentElement) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
            }
        });
        let text = '';
        let block = null;
        for (let n = walker.nextNode(); n; n = walker.nextNode()) {
            const b = blockOf(n);
            if (b !== block) {
                text += SEP;
                block = b;
            }
            nodes.push({ node: n, start: text.length });
            text += n.nodeValue;
        }
        return { text, nodes };
    }

    // The text node and offset at a position in the collected string. An end
    // that falls on a node boundary stays in the earlier node.
    function locate(nodes, pos, isEnd) {
        let lo = 0;
        let hi = nodes.length - 1;
        while (lo < hi) {
            const mid = (lo + hi + 1) >> 1;
            if (isEnd ? nodes[mid].start < pos : nodes[mid].start <= pos) lo = mid;
            else hi = mid - 1;
        }
        const e = nodes[lo];
        return [e.node, Math.max(0, Math.min(pos - e.start, e.node.nodeValue.length))];
    }

    // The box entry a match belongs to: the innermost section holding it, or,
    // where the box links headings rather than sections, the last heading
    // before it. k is the last entry that starts before the match.
    function ownerOf(node, k) {
        for (let j = k; j >= 0; j--) {
            if (entries[j].target.contains(node)) return entries[j];
        }
        return k >= 0 && /^H[1-6]$/.test(entries[k].target.tagName) ? entries[k] : null;
    }

    function search() {
        matches = [];
        current = -1;
        over = false;
        entries.forEach(e => { e.count = 0; e.first = -1; });
        const re = pattern(input.value);
        if (!re) return false;
        const { text, nodes } = collect();
        if (!nodes.length) return true;
        let k = -1;
        let m;
        while ((m = re.exec(text))) {
            if (matches.length === MAX) {
                over = true;
                break;
            }
            const [sn, so] = locate(nodes, m.index, false);
            const [en, eo] = locate(nodes, m.index + m[0].length, true);
            const range = document.createRange();
            range.setStart(sn, so);
            range.setEnd(en, eo);
            while (k + 1 < entries.length
                && entries[k + 1].target.compareDocumentPosition(sn) & Node.DOCUMENT_POSITION_FOLLOWING) k++;
            const entry = ownerOf(sn, k);
            if (entry) {
                if (entry.first < 0) entry.first = matches.length;
                entry.count++;
            }
            matches.push({ range, entry });
        }
        return true;
    }

    function paint() {
        if (!canPaint) return;
        if (matches.length) CSS.highlights.set('page-finder', new Highlight(...matches.map(x => x.range)));
        else CSS.highlights.delete('page-finder');
        if (current >= 0) {
            const h = new Highlight(matches[current].range);
            h.priority = 1;
            CSS.highlights.set('page-finder-current', h);
        } else {
            CSS.highlights.delete('page-finder-current');
        }
    }

    // While a search is on, the box lists only the sections holding a match,
    // each with its count; a parent stays when one of its children does.
    // Without a box there is nothing to narrow, only the field to flag.
    function narrow(searching) {
        finder.classList.toggle('is-finding', searching);
        if (!toc) return;
        const keep = new Set();
        entries.forEach(e => {
            if (!searching || !e.count) {
                if (e.badge) e.badge.classList.add('is-hidden');
                return;
            }
            for (let li = e.li; li && toc.contains(li); li = li.parentElement.closest('li')) keep.add(li);
            if (!e.badge) {
                e.badge = document.createElement('span');
                e.badge.className = 'page-finder-hits';
                e.a.after(e.badge);
            }
            e.badge.textContent = '';
            e.badge.append(String(e.count));
            const sr = document.createElement('span');
            sr.className = 'visually-hidden';
            sr.textContent = e.count === 1 ? ' match' : ' matches';
            e.badge.append(sr);
            e.badge.classList.remove('is-hidden');
        });
        toc.classList.toggle('is-finding', searching);
        items.forEach(li => li.classList.toggle('is-hidden', searching && !keep.has(li)));
        lists.forEach(l => l.classList.toggle('is-hidden', searching && !l.querySelector(':scope > li:not(.is-hidden)')));
    }

    function report(searching) {
        const n = matches.length;
        const plural = (count, one, many) => count + ' ' + (count === 1 ? one : many);
        prevBtn.classList.toggle('is-hidden', !n);
        nextBtn.classList.toggle('is-hidden', !n);
        if (!searching) {
            status.textContent = '';
        } else if (!n) {
            status.textContent = 'No matches on this page.';
        } else if (current >= 0) {
            status.textContent = 'Match ' + (current + 1) + ' of ' + n + (over ? '+' : '') + '.';
        } else if (over) {
            status.textContent = 'More than ' + MAX + ' matches. Add a word to narrow it.';
        } else {
            const sections = entries.filter(e => e.count).length;
            status.textContent = plural(n, 'match', 'matches')
                + (sections ? ' in ' + plural(sections, 'section', 'sections') : '') + '.';
        }
    }

    function refresh() {
        clearTimeout(timer);
        timer = null;
        const searching = search();
        paint();
        narrow(searching);
        report(searching);
    }

    // Where a match is on screen. A match inside a closed <details> has no
    // box of its own, so use the outermost closed one's.
    function topOf(range) {
        const r = range.getBoundingClientRect();
        if (r.width || r.height) return r.top;
        let shut = null;
        for (let d = range.startContainer.parentElement.closest('details:not([open])'); d;
            d = d.parentElement && d.parentElement.closest('details:not([open])')) shut = d;
        return shut ? shut.getBoundingClientRect().top : r.top;
    }

    // The first match below the top of the window, or the first on the page.
    function fromHere() {
        for (let i = 0; i < matches.length; i++) {
            if (topOf(matches[i].range) >= 0) return i;
        }
        return 0;
    }

    function reveal(range) {
        const el = range.startContainer.parentElement;
        for (let d = el.closest('details:not([open])'); d; d = el.closest('details:not([open])')) d.open = true;
        // Wide code blocks and tables scroll sideways in their own box.
        for (let box = el; box && box !== root; box = box.parentElement) {
            if (box.scrollWidth > box.clientWidth && /auto|scroll/.test(getComputedStyle(box).overflowX)) {
                const r = range.getBoundingClientRect();
                const b = box.getBoundingClientRect();
                if (r.left < b.left || r.right > b.right) box.scrollLeft += r.left - b.left - box.clientWidth / 3;
                break;
            }
        }
        // Glide to a match a screen or two away, so the reader keeps their
        // place; jump to one further off, as a browser's own find does,
        // rather than scroll past pages of text.
        const r = range.getBoundingClientRect();
        const top = Math.max(0, window.scrollY + r.top - (window.innerHeight - r.height) / 2);
        const near = Math.abs(top - window.scrollY) < 2 * window.innerHeight;
        const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        window.scrollTo({ top, behavior: near && !still ? 'smooth' : 'instant' });
    }

    function go(i) {
        if (!matches.length) return;
        current = (i + matches.length) % matches.length;
        reveal(matches[current].range);
        paint();
        report(true);
    }

    function step(back) {
        if (timer) refresh();
        if (!matches.length) return;
        if (current < 0) go(back ? fromHere() - 1 : fromHere());
        else go(current + (back ? -1 : 1));
    }

    function clear() {
        input.value = '';
        refresh();
    }

    let timer = null;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(refresh, 150);
    });
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            step(e.shiftKey);
        } else if (e.key === 'Escape' && input.value) {
            e.preventDefault();
            clear();
        }
    });
    prevBtn.addEventListener('click', () => step(true));
    nextBtn.addEventListener('click', () => step(false));
    // Choosing a section in the narrowed list goes to its first match rather
    // than the top of the section. Capturing on the box runs this before
    // main.js's smooth-scroll handler on the link, and stopping the event
    // here keeps that handler from scrolling back to the section's top.
    if (toc) toc.addEventListener('click', e => {
        const a = e.target.closest('a[href^="#"]');
        const entry = a && entries.find(x => x.a === a);
        if (!entry || entry.first < 0) return;
        e.preventDefault();
        e.stopPropagation();
        go(entry.first);
    }, true);

    // A browser that restores form fields on back/forward fills the field
    // before this runs, so apply whatever is already there.
    if (input.value) refresh();
})();
