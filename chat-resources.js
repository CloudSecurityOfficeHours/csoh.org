// CSOH Chat Resources - Interactive JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const showAllBtn = document.getElementById('showAllBtn');
    const cards = document.querySelectorAll('.card-link');
    const filterBtns = document.querySelectorAll('.filter-btn');
    let activeFilter = null;
    let activeDateFilter = { type: 'none', startDate: null, endDate: null };

    function filterCards() {
        const query = searchInput.value.toLowerCase();
        cards.forEach(function(card) {
            var text = card.textContent.toLowerCase();
            var cardEl = card.querySelector('.resource-card');
            var cat = cardEl.dataset.category;
            var person = cardEl.dataset.person;
            var cardDate = cardEl.dataset.date;

            var matchesSearch = !query || text.includes(query);
            var matchesFilter = !activeFilter;

            if (activeFilter) {
                if (activeFilter.startsWith('person-')) {
                    matchesFilter = person === activeFilter;
                } else {
                    matchesFilter = cat === activeFilter;
                }
            }

            var matchesDate = checkDateFilter(cardDate);

            card.style.display = (matchesSearch && matchesFilter && matchesDate) ? '' : 'none';
        });
    }

    function debounce(func, wait) {
        var timeout;
        return function() {
            var context = this;
            var args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(function() {
                func.apply(context, args);
            }, wait);
        };
    }

    function initSearchSuggestions() {
        if (!searchInput || searchInput.dataset.suggestionsInit === 'true') {
            return;
        }

        var wrapper = document.createElement('div');
        wrapper.className = 'search-wrapper';
        searchInput.parentNode.insertBefore(wrapper, searchInput);
        wrapper.appendChild(searchInput);

        var dropdown = document.createElement('div');
        dropdown.className = 'search-suggestions';
        dropdown.setAttribute('role', 'listbox');
        dropdown.id = 'searchSuggestions';
        wrapper.appendChild(dropdown);

        searchInput.setAttribute('role', 'combobox');
        searchInput.setAttribute('aria-autocomplete', 'list');
        searchInput.setAttribute('aria-controls', 'searchSuggestions');
        searchInput.setAttribute('aria-expanded', 'false');
        searchInput.dataset.suggestionsInit = 'true';

        var suggestions = buildSuggestionIndex();
        var highlightIndex = -1;

        var debouncedSuggest = debounce(function() {
            var query = searchInput.value.trim().toLowerCase();
            if (query.length < 2) {
                closeSuggestions();
                return;
            }

            var matches = suggestions.filter(function(item) {
                return item.text.toLowerCase().includes(query);
            }).slice(0, 8);

            if (matches.length === 0) {
                closeSuggestions();
                return;
            }

            dropdown.innerHTML = '';
            matches.forEach(function(match) {
                var div = document.createElement('div');
                div.className = 'search-suggestion';
                div.setAttribute('role', 'option');
                div.dataset.value = match.text;

                var text = document.createElement('span');
                text.textContent = match.text;

                var type = document.createElement('span');
                type.className = 'suggestion-type';
                type.textContent = match.type;

                div.appendChild(text);
                div.appendChild(type);

                div.addEventListener('mousedown', function(e) {
                    e.preventDefault();
                    searchInput.value = match.text;
                    closeSuggestions();
                    filterCards();
                });

                dropdown.appendChild(div);
            });

            highlightIndex = -1;
            dropdown.classList.add('visible');
            searchInput.setAttribute('aria-expanded', 'true');
        }, 100);

        searchInput.addEventListener('input', debouncedSuggest);

        searchInput.addEventListener('keydown', function(e) {
            var items = dropdown.querySelectorAll('.search-suggestion');
            if (!dropdown.classList.contains('visible') || items.length === 0) {
                return;
            }

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                highlightIndex = Math.min(highlightIndex + 1, items.length - 1);
                updateHighlight(items, highlightIndex);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                highlightIndex = Math.max(highlightIndex - 1, 0);
                updateHighlight(items, highlightIndex);
            } else if (e.key === 'Enter' && highlightIndex >= 0) {
                e.preventDefault();
                searchInput.value = items[highlightIndex].dataset.value;
                closeSuggestions();
                filterCards();
            } else if (e.key === 'Escape') {
                closeSuggestions();
            }
        });

        searchInput.addEventListener('blur', function() {
            setTimeout(closeSuggestions, 150);
        });

        function closeSuggestions() {
            dropdown.classList.remove('visible');
            dropdown.innerHTML = '';
            highlightIndex = -1;
            searchInput.setAttribute('aria-expanded', 'false');
        }

        function updateHighlight(items, index) {
            items.forEach(function(item) {
                item.classList.remove('highlighted');
            });

            if (index >= 0 && index < items.length) {
                items[index].classList.add('highlighted');
                items[index].scrollIntoView({ block: 'nearest' });
            }
        }
    }

    function buildSuggestionIndex() {
        var seen = new Set();
        var suggestions = [];

        cards.forEach(function(cardLink) {
            var card = cardLink.querySelector('.resource-card');
            if (!card) return;

            var titleEl = card.querySelector('h3');
            var title = titleEl ? titleEl.textContent.trim() : '';
            if (title && !seen.has(title.toLowerCase())) {
                seen.add(title.toLowerCase());
                suggestions.push({ text: title, type: 'Resource' });
            }

            card.querySelectorAll('.tag').forEach(function(tagEl) {
                var tag = tagEl.textContent.trim();
                if (tag && !seen.has(tag.toLowerCase())) {
                    seen.add(tag.toLowerCase());
                    suggestions.push({ text: tag, type: 'Tag' });
                }
            });
        });

        return suggestions;
    }

    function checkDateFilter(cardDate) {
        if (activeDateFilter.type === 'none' || cardDate === 'unknown') {
            return true;
        }

        var filterType = activeDateFilter.type;
        var startDate = activeDateFilter.startDate;
        var endDate = activeDateFilter.endDate;

        if (filterType === 'before' && startDate) {
            return cardDate < startDate;
        } else if (filterType === 'after' && startDate) {
            return cardDate > startDate;
        } else if (filterType === 'range' && startDate && endDate) {
            return cardDate >= startDate && cardDate <= endDate;
        }

        return true;
    }

    searchInput.addEventListener('input', filterCards);
    initSearchSuggestions();

    showAllBtn.addEventListener('click', function() {
        searchInput.value = '';
        activeFilter = null;
        filterBtns.forEach(function(b) { b.classList.remove('active'); });

        activeDateFilter = { type: 'none', startDate: null, endDate: null };
        var dateFilterType = document.getElementById('dateFilterType');
        var singleDateInput = document.getElementById('singleDate');
        var startDateInput = document.getElementById('startDate');
        var endDateInput = document.getElementById('endDate');
        if (dateFilterType) {
            dateFilterType.value = 'none';
            singleDateInput.value = '';
            startDateInput.value = '';
            endDateInput.value = '';
            document.getElementById('startDateContainer').style.display = 'none';
            document.getElementById('endDateContainer').style.display = 'none';
            document.getElementById('singleDateContainer').style.display = 'none';
            document.getElementById('applyDateFilter').style.display = 'none';
            document.getElementById('clearDateFilter').style.display = 'none';
        }

        filterCards();
    });

    filterBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            var filter = this.dataset.filter;
            if (activeFilter === filter) {
                activeFilter = null;
                this.classList.remove('active');
            } else {
                activeFilter = filter;
                filterBtns.forEach(function(b) { b.classList.remove('active'); });
                this.classList.add('active');
            }
            filterCards();
        });
    });

    // Handle Show All Contributors button
    var showAllContributorsBtn = document.getElementById('showAllContributorsBtn');
    if (showAllContributorsBtn) {
        showAllContributorsBtn.addEventListener('click', function() {
            var allContributorsDiv = document.getElementById('allContributors');
            if (allContributorsDiv.style.display === 'none') {
                allContributorsDiv.style.display = '';
                this.textContent = 'Hide Additional Contributors';
            } else {
                allContributorsDiv.style.display = 'none';
                this.textContent = 'Show All Contributors';
            }
        });
    }

    // Handle Date Filter
    var dateFilterType = document.getElementById('dateFilterType');
    var startDateContainer = document.getElementById('startDateContainer');
    var endDateContainer = document.getElementById('endDateContainer');
    var singleDateContainer = document.getElementById('singleDateContainer');
    var startDateInput = document.getElementById('startDate');
    var endDateInput = document.getElementById('endDate');
    var singleDateInput = document.getElementById('singleDate');
    var applyDateFilter = document.getElementById('applyDateFilter');
    var clearDateFilter = document.getElementById('clearDateFilter');

    dateFilterType.addEventListener('change', function() {
        var filterType = this.value;

        startDateContainer.style.display = 'none';
        endDateContainer.style.display = 'none';
        singleDateContainer.style.display = 'none';
        applyDateFilter.style.display = 'none';
        clearDateFilter.style.display = 'none';

        if (filterType === 'before' || filterType === 'after') {
            singleDateContainer.style.display = 'block';
            applyDateFilter.style.display = 'block';
            clearDateFilter.style.display = 'block';
        } else if (filterType === 'range') {
            startDateContainer.style.display = 'block';
            endDateContainer.style.display = 'block';
            applyDateFilter.style.display = 'block';
            clearDateFilter.style.display = 'block';
        }
    });

    applyDateFilter.addEventListener('click', function() {
        var filterType = dateFilterType.value;

        if (filterType === 'before' || filterType === 'after') {
            var dateValue = singleDateInput.value;
            if (dateValue) {
                activeDateFilter = {
                    type: filterType,
                    startDate: dateValue,
                    endDate: null
                };
                filterCards();
            }
        } else if (filterType === 'range') {
            var sd = startDateInput.value;
            var ed = endDateInput.value;
            if (sd && ed) {
                activeDateFilter = {
                    type: 'range',
                    startDate: sd,
                    endDate: ed
                };
                filterCards();
            }
        }
    });

    clearDateFilter.addEventListener('click', function() {
        activeDateFilter = { type: 'none', startDate: null, endDate: null };
        dateFilterType.value = 'none';
        singleDateInput.value = '';
        startDateInput.value = '';
        endDateInput.value = '';
        startDateContainer.style.display = 'none';
        endDateContainer.style.display = 'none';
        singleDateContainer.style.display = 'none';
        applyDateFilter.style.display = 'none';
        clearDateFilter.style.display = 'none';
        filterCards();
    });

    // Dark mode toggle
    const saved = localStorage.getItem('theme');
    if (saved === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }

    function updateToggleIcon(btn) {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        btn.textContent = isDark ? '☀️' : '🌙';
        btn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
    }

    const themeToggle = document.querySelector('.theme-toggle');
    if (themeToggle) {
        updateToggleIcon(themeToggle);
        themeToggle.addEventListener('click', function() {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
            localStorage.setItem('theme', isDark ? 'light' : 'dark');
            updateToggleIcon(this);
        });
    }

    // Hamburger menu toggle
    const hamburger = document.querySelector('.hamburger');
    if (hamburger) {
        hamburger.addEventListener('click', function() {
            const header = this.closest('.header-content');
            const isOpen = document.body.classList.toggle('nav-open');
            if (header) header.classList.toggle('nav-open', isOpen);
            this.setAttribute('aria-expanded', String(isOpen));
            this.textContent = isOpen ? '✕' : '☰';
        });
    }
});
