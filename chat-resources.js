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
});
