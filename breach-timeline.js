// Sort tabs by year extracted from their text content
  const tabNav = document.querySelector('.incident-tabs');
  const tabs = Array.from(tabNav.querySelectorAll('.itab'));

  tabs.sort((a, b) => {
    return parseInt(a.dataset.year || 0) - parseInt(b.dataset.year || 0);
  });

  // Re-append in sorted order
  tabs.forEach(tab => tabNav.appendChild(tab));

  // Tab click switching
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.itab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.incident-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const panel = document.getElementById(tab.dataset.panel);
      if (panel) panel.classList.add('active');
    });
  });