/* Stamps data-theme on <html> before the first paint.
 *
 * This has to be a separate file loaded synchronously from <head>, and not a
 * few lines inside main.js, because of two constraints that only bite together:
 *
 *   - main.js is deferred, so it runs after the document has already painted.
 *   - The CSP is `script-src 'self'` with no 'unsafe-inline', no nonce and no
 *     hash, so the usual one-line inline snippet in <head> is dropped on the
 *     floor in production. localhost sends no CSP, which is exactly why this is
 *     easy to miss locally.
 *
 * style.css already handles the no-preference case on its own: the dark tokens
 * live under `@media (prefers-color-scheme: dark) { :root:not([data-theme]) }`,
 * so a visitor who has never touched the toggle paints correctly with no
 * JavaScript at all. The flash was for the visitor whose stored choice differs
 * from their OS - light OS with the site set to dark is the common one. They
 * painted light, then flipped when the deferred script ran.
 *
 * Deliberately does nothing when there is no stored preference: leaving the
 * attribute off is what lets the media query keep control, so a visitor who
 * changes their OS theme with the page open still follows it.
 *
 * main.js owns the toggle button and re-reads the same key; it no longer needs
 * to do this initial stamp, but doing it twice would be harmless.
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
