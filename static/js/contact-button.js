/* Updated by Claude AI on 2026-10-23 */
// Reveals a circle's contact email on demand rather than shipping it in the
// page HTML, so scrapers don't find it. Buttons use class show-contact-btn and
// an optional data-slug; without one, the current site's circle (body data-circle).

function initializeContactButtons() {
    document.querySelectorAll('.show-contact-btn').forEach(function(button) {
        button.addEventListener('click', function() {
            const slug = button.dataset.slug || document.body.dataset.circle;
            button.disabled = true;

            fetch(`/api/circles/${encodeURIComponent(slug)}/contact`)
                .then(function(response) {
                    if (!response.ok) {
                        throw new Error('Request failed');
                    }
                    return response.json();
                })
                .then(function(data) {
                    const link = document.createElement('a');
                    link.href = `mailto:${data.contact}`;
                    link.textContent = data.contact;
                    button.replaceWith(link);
                })
                .catch(function() {
                    button.disabled = false;
                    button.textContent = 'Unable to load - try again';
                });
        });
    });
}
