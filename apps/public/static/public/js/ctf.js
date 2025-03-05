document.addEventListener('DOMContentLoaded', function() {
    const challengeContainer = document.getElementById('challenge-container');
    const challengeList = document.getElementById('challenge-list');
    const filterLinks = document.querySelectorAll('[data-filter]');

    function updateActiveStatus(filter, value) {
        const links = document.querySelectorAll(`[data-filter="${filter}"]`);
        links.forEach(link => {
            if (link.dataset.value === value) {
                link.classList.add('active-type');
            } else {
                link.classList.remove('active-type');
            }
        });
    }
    function updateUI(url) {
        const params = new URLSearchParams(url.search);
        updateActiveStatus('type', params.get('type') || '');
        updateActiveStatus('difficulty', params.get('difficulty') || '');
        updateActiveStatus('status', params.get('status') || '');
        updateActiveStatus('author', params.get('author') || '');
    }
    filterLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const filter = this.dataset.filter;
            const value = this.dataset.value;

            const url = new URL(window.location);
            
            url.searchParams.delete('q');
            url.searchParams.delete('tag');

            if (value === '') {
                url.searchParams.delete(filter);
            } else {
                url.searchParams.set(filter, value);
            }
            fetch(url)
                .then(response => response.text())
                .then(html => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const newChallengeList = doc.getElementById('challenge-list');

                    if (challengeList && newChallengeList) {
                        challengeList.innerHTML = newChallengeList.innerHTML;
                    }
                    history.pushState({}, '', url);
                    updateUI(url);
                })
                .catch(error => {
                    console.error('Error:', error);
                });
        });
    });
});