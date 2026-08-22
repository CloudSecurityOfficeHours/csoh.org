// 404 redirect-hint: detect a few common old-URL patterns and offer the
// new URL. Runs purely on the client because the server returns this
// static 404 page - we don't have access to server logs from here.
// The original URL the user tried lives in document.referrer (if they
// followed a link) or window.location.search (if a 301-from-X landing
// page passed it through). Both are best-effort hints.
(function () {
  const hint = document.getElementById('redirect-hint');
  const link = document.getElementById('redirect-link');
  if (!hint || !link) return;

  // Prefer the hash from the location the user requested. We can't see
  // the original requested path on a static 404, so we rely on
  // window.location.hash if Apache is configured to forward it, and on
  // a `?from=` query string if a server-side rewrite passes the
  // original path. Both are graceful no-ops if absent.
  const params = new URLSearchParams(location.search);
  const oldPath = params.get('from') || '';
  const oldHash = location.hash || '';

  let target = null;

  // Old: breach-timeline.html#capital-one  →  /breaches/capital-one.html
  if (oldPath.includes('breach-timeline') || /breach-timeline/i.test(document.referrer)) {
    const slug = (oldHash.replace('#', '') || '').toLowerCase();
    const knownBreaches = [
      'capital-one','solarwinds','uber','lastpass','storm-0558',
      'microsoft-sas-leak','scattered-spider-mgm','promptware',
      'snowflake-unc5537','mitnick-novell',
    ];
    if (knownBreaches.includes(slug)) {
      target = '/breaches/' + slug + '.html';
    } else {
      target = '/breach-timeline.html';
    }
  }

  // Old: meetings.html#meeting-2026-04-17  →  /meetings/2026-04-17.html
  if (!target && (oldPath.includes('meetings') || /meetings\.html/i.test(document.referrer))) {
    const m = oldHash.match(/meeting-(\d{4}-\d{2}-\d{2})/);
    if (m) target = '/meetings/' + m[1] + '.html';
    else if (oldPath.includes('meetings')) target = '/meetings.html';
  }

  if (target) {
    link.href = target;
    link.textContent = '→ ' + target;
    hint.style.display = 'block';   // was ''; the default is now .is-hidden in CSS
  }
})();
