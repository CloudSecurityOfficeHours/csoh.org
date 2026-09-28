/* Stamps data-theme on <html> from localStorage.
 *
 * Loaded with `defer` from <head>: runs after the document is parsed but
 * before DOMContentLoaded, removing it as a parser-blocking resource.
 *
 * style.css handles the no-preference case without JavaScript: the dark tokens
 * live under `@media (prefers-color-scheme: dark) { :root:not([data-theme]) }`,
 * so a visitor who has never touched the toggle paints correctly with no JS.
 * This file is for the visitor whose stored choice differs from their OS; they
 * may see a brief flash of the wrong theme before defer fires, but the window
 * is very short (the file is ~1 KB and cached with `immutable` after first load).
 *
 * Deliberately does nothing when there is no stored preference: leaving the
 * attribute off is what lets the media query keep control, so a visitor who
 * changes their OS theme with the page open still follows it.
 *
 * main.js owns the toggle button and re-reads the same key; it does not need
 * to repeat this initial stamp, though doing it twice would be harmless.
 */
(function () {
    try {
        var saved = localStorage.getItem('theme');
        if (saved === 'dark' || saved === 'light') {
            document.documentElement.setAttribute('data-theme', saved);
        }
    } catch (e) {
        /* Storage can throw in private mode or with cookies blocked. The media
           query is a perfectly good fallback, so there is nothing to do. */
    }
})();
