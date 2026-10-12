(() => {
  'use strict';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // A few world clocks echo the reference's sense of global movement.
  const clocks = [...document.querySelectorAll('[data-clock]')];
  const updateClocks = () => {
    const now = new Date();
    clocks.forEach((clock) => {
      try {
        clock.textContent = new Intl.DateTimeFormat('en-GB', {
          timeZone: clock.dataset.clock,
          hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
        }).format(now);
      } catch (_) { clock.textContent = '--:--:--'; }
    });
  };
  if (clocks.length) { updateClocks(); window.setInterval(updateClocks, 1000); }

  // Switch the visual lens on the journey preview; this is a client-side preview only.
  const lensTabs = [...document.querySelectorAll('[data-lens]')];
  const lensValue = document.querySelector('[data-lens-value]');
  const lensCopy = document.querySelector('[data-lens-copy]');
  const lensContent = {
    time: ['One trip. More perspective.', 'Compare journey times across the ways you can travel.'],
    cost: ['Know what the journey costs.', 'See estimated fares and driving costs side by side.'],
    impact: ['Choose a lighter way there.', 'Understand the estimated emissions behind each option.']
  };
  lensTabs.forEach((tab) => tab.addEventListener('click', () => {
    lensTabs.forEach((item) => {
      const active = item === tab;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-selected', String(active));
    });
    const panel = document.querySelector('.lens-readout');
    if (panel) panel.classList.add('is-changing');
    window.setTimeout(() => {
      const content = lensContent[tab.dataset.lens];
      if (content && lensValue && lensCopy) {
        lensValue.textContent = content[0];
        lensCopy.textContent = content[1];
      }
      if (panel) panel.classList.remove('is-changing');
    }, 140);
  }));

  const revealSelector = '.reveal-on-scroll, .card, .transport-card, .stat-card, .dashboard-card, .page-intro, .trip-item, .pdf-download-section, .calculator-sidebar, .map-container, .feature-row, .history-table tbody tr, .settings-tabs .tab';
  const revealItems = [...document.querySelectorAll(revealSelector)];
  if (!reduceMotion && 'IntersectionObserver' in window && revealItems.length) {
    revealItems.forEach((item) => item.classList.add('motion-reveal'));
    document.body.classList.add('motion-ready');
    const observer = new IntersectionObserver((entries, currentObserver) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          currentObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -30px 0px' });
    revealItems.forEach((item) => observer.observe(item));
    const resultsGrid = document.querySelector('#results-grid');
    if (resultsGrid) {
      const contentObserver = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
          if (!(node instanceof HTMLElement)) return;
          const candidates = [node, ...node.querySelectorAll(revealSelector)];
          candidates.forEach((item) => {
            if (item.matches?.(revealSelector) && !item.classList.contains('motion-reveal')) {
              item.classList.add('motion-reveal');
              observer.observe(item);
            }
          });
        }));
      });
      contentObserver.observe(resultsGrid, { childList: true, subtree: true });
    }
  }

  // Restrained pointer response: a soft highlight, never a distracting 3D tilt.
  if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    document.querySelectorAll('.card, .transport-card').forEach((card) => {
      card.classList.add('has-spotlight');
      card.addEventListener('pointermove', (event) => {
        const bounds = card.getBoundingClientRect();
        card.style.setProperty('--spot-x', `${event.clientX - bounds.left}px`);
        card.style.setProperty('--spot-y', `${event.clientY - bounds.top}px`);
      }, { passive: true });
    });
  }

  const nav = document.querySelector('.navbar');
  if (nav) {
    const updateNav = () => nav.classList.toggle('is-scrolled', window.scrollY > 24);
    updateNav();
    window.addEventListener('scroll', updateNav, { passive: true });
  }


  // Search and filter the rendered trip log without a page reload.
  const historySearch = document.querySelector('[data-history-search]');
  const historyMode = document.querySelector('[data-history-mode]');
  if (historySearch || historyMode) {
    const rows = [...document.querySelectorAll('.history-table tbody tr')].filter((row) => row.querySelector('.transport-badge'));
    const count = document.querySelector('[data-history-count]');
    const empty = document.querySelector('[data-history-empty]');
    const filterHistory = () => {
      const query = (historySearch?.value || '').trim().toLowerCase();
      const mode = historyMode?.value || 'all';
      let visible = 0;
      rows.forEach((row) => {
        const rowMode = row.querySelector('.transport-badge')?.textContent.trim().toLowerCase() || '';
        const matches = row.textContent.toLowerCase().includes(query) && (mode === 'all' || rowMode === mode);
        row.hidden = !matches;
        if (matches) visible += 1;
      });
      if (count) count.textContent = `${visible} ${visible === 1 ? 'trip' : 'trips'}`;
      if (empty) empty.hidden = rows.length === 0 || visible !== 0;
    };
    historySearch?.addEventListener('input', filterHistory);
    historyMode?.addEventListener('change', filterHistory);
  }

  // Route chips are input shortcuts; the normal route calculator remains in control.
  document.querySelectorAll('[data-route-origin][data-route-destination]').forEach((chip) => {
    chip.addEventListener('click', () => {
      const origin = document.getElementById('origin');
      const destination = document.getElementById('destination');
      if (!origin || !destination) return;
      origin.value = chip.dataset.routeOrigin;
      destination.value = chip.dataset.routeDestination;
      document.querySelectorAll('[data-route-origin]').forEach((item) => item.classList.toggle('is-selected', item === chip));
      destination.focus({ preventScroll: true });
    });
  });

})();
