/**
 * Quick Navigation (⌘K / Ctrl+K) command palette
 * and scroll progress bar for the Wealth Analysis dashboard.
 *
 * Reads page data from #cmd-palette-data (JSON rendered by GUI.py).
 * All interaction is handled client-side — no Dash callbacks required.
 */
document.addEventListener('DOMContentLoaded', function () {
    /* ── Read page data ── */
    var dataEl = document.getElementById('cmd-palette-data');
    if (!dataEl) return;
    var pages;
    try { pages = JSON.parse(dataEl.textContent); } catch (e) { return; }

    /* ── Build overlay DOM ── */
    var overlay = document.createElement('div');
    overlay.className = 'cmd-palette-overlay';
    overlay.style.display = 'none';

    var inner = document.createElement('div');
    inner.className = 'cmd-palette-inner';

    var input = document.createElement('input');
    input.className = 'cmd-palette-input';
    input.placeholder = 'Jump to page\u2026';
    input.type = 'text';
    input.autocomplete = 'off';

    var results = document.createElement('div');
    results.className = 'cmd-palette-results';

    inner.appendChild(input);
    inner.appendChild(results);
    overlay.appendChild(inner);
    document.body.appendChild(overlay);

    var activeIdx = 0;
    var items = [];

    /* ── Render results list ── */
    function renderResults(filter) {
        results.innerHTML = '';
        activeIdx = 0;
        items = [];
        var lc = (filter || '').toLowerCase();

        for (var href in pages) {
            var p = pages[href];
            var search = (p.section + ' ' + p.name).toLowerCase();
            if (lc && search.indexOf(lc) === -1) continue;
            items.push({ href: href, section: p.section, name: p.name, icon: p.icon });
        }

        items.forEach(function (item, i) {
            var div = document.createElement('div');
            div.className = 'cmd-result' + (i === 0 ? ' active' : '');

            var iconSpan = document.createElement('span');
            iconSpan.className = 'cmd-result-icon';
            iconSpan.textContent = item.icon;

            div.appendChild(iconSpan);

            if (item.section) {
                var secSpan = document.createElement('span');
                secSpan.className = 'cmd-result-section';
                secSpan.textContent = item.section + ' \u203A ';
                div.appendChild(secSpan);
            }

            var nameSpan = document.createElement('span');
            nameSpan.className = 'cmd-result-name';
            nameSpan.textContent = item.name;
            div.appendChild(nameSpan);

            (function (idx, h) {
                div.addEventListener('click', function () { navigate(h); });
                div.addEventListener('mouseenter', function () { setActive(idx); });
            })(i, item.href);

            results.appendChild(div);
        });
    }

    /* ── Highlight active item ── */
    function setActive(index) {
        var els = results.querySelectorAll('.cmd-result');
        for (var i = 0; i < els.length; i++) {
            if (i === index) els[i].classList.add('active');
            else els[i].classList.remove('active');
        }
        activeIdx = index;
    }

    /* ── Navigate using Dash SPA routing ── */
    function navigate(href) {
        closePalette();
        window.history.pushState({}, '', href);
        window.dispatchEvent(new PopStateEvent('popstate'));
    }

    /* ── Open / close helpers ── */
    function openPalette() {
        overlay.style.display = 'flex';
        input.value = '';
        renderResults('');
        setTimeout(function () { input.focus(); }, 30);
    }

    function closePalette() {
        overlay.style.display = 'none';
        input.value = '';
    }

    /* ── Global keyboard listener ── */
    document.addEventListener('keydown', function (e) {
        // ⌘K / Ctrl+K toggle
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            if (overlay.style.display === 'none') openPalette();
            else closePalette();
            return;
        }
        // Escape closes
        if (e.key === 'Escape' && overlay.style.display !== 'none') {
            closePalette();
        }
    });

    /* ── Input filtering + arrow key navigation ── */
    input.addEventListener('input', function () {
        renderResults(input.value);
    });

    input.addEventListener('keydown', function (e) {
        var els = results.querySelectorAll('.cmd-result');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActive(Math.min(activeIdx + 1, els.length - 1));
            if (els[activeIdx]) els[activeIdx].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive(Math.max(activeIdx - 1, 0));
            if (els[activeIdx]) els[activeIdx].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (items[activeIdx]) navigate(items[activeIdx].href);
        }
    });

    /* ── Click outside to close ── */
    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) closePalette();
    });

    /* ── ⌘K hint button in header opens palette ── */
    var hint = document.getElementById('cmd-hint');
    if (hint) {
        hint.addEventListener('click', function () { openPalette(); });
    }

    /* ── Scroll progress bar ── */
    var progressBar = document.getElementById('scroll-progress-bar');
    if (progressBar) {
        var ticking = false;
        window.addEventListener('scroll', function () {
            if (!ticking) {
                window.requestAnimationFrame(function () {
                    var scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                    var docHeight = document.documentElement.scrollHeight - window.innerHeight;
                    if (docHeight > 0) {
                        progressBar.style.width = ((scrollTop / docHeight) * 100) + '%';
                    }
                    ticking = false;
                });
                ticking = true;
            }
        });
    }
});
