(() => {
  'use strict';
  const version = '2026-10-03-balanced-motion-v11';
  if (!window.gsap || window.__ylMotion?.version === version) return;
  window.__ylMotion?.dispose();
  const g = window.gsap, root = document.documentElement;
  const seen = new WeakSet(), events = [], pending = new Set();
  let frame = 0, observer, media, reduced = false;
  const cards = '.home-feature,.home-flow-item,[class*="st-key-entry_"],.metric-card,.route-board,.note-panel,[class*="st-key-order_"]';
  const entrance = `${cards},.home-hero-copy,.home-journey,h1,.motion-focus,.motion-reveal,.home-reveal,.page-subtitle,[data-testid="stHeading"],[data-testid="stMetric"],[data-testid="stAlert"],.delivery-track-fill`;
  const controls = '[data-testid="stButton"] button,[data-testid="stPageLink-NavLink"], [data-testid="stDownloadButton"] button';
  const fine = () => matchMedia('(hover: hover) and (pointer: fine)').matches;
  const watched = new WeakSet();
  const view = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { view.unobserve(entry.target); animate([entry.target]); }
  }), {threshold: 0.06});
  function animate(nodes) {
    const fresh = nodes.filter(el => el.isConnected && !seen.has(el) && !el.closest('[data-testid="stHtml"],iframe'));
    fresh.forEach(el => seen.add(el));
    if (reduced) return;
    fresh.forEach((el, i) => {
      if (el.matches('.home-feature')) {
        const line = el.querySelector('.feature-line');
        if (line) g.fromTo(line, {scaleX: 0.25}, {scaleX: 1, transformOrigin: 'left center', duration: 0.65, ease: 'power2.out', overwrite: 'auto'});
      }
      const fill = el.matches('.delivery-track-fill');
      g.fromTo(el, fill ? {scaleX: 0.92, transformOrigin: 'left center'} : {y: 6, opacity: 0.88},
        {...(fill ? {scaleX: 1} : {y: 0, opacity: 1}), duration: fill ? 0.5 : 0.32,
         delay: Math.min(i * 0.025, 0.12), ease: 'power2.out', overwrite: 'auto', clearProps: 'transform,opacity'});
    });
  }
  function scan(node) {
    if (node.nodeType !== 1) return;
    if (node.matches(entrance)) pending.add(node);
    node.querySelectorAll(entrance).forEach(el => pending.add(el));
    if (!frame) frame = requestAnimationFrame(() => {
      frame = 0;
      pending.forEach(el => { if (!watched.has(el)) { watched.add(el); view.observe(el); } });
      pending.clear();
    });
  }
  function on(type, handler) { document.addEventListener(type, handler); events.push([type, handler]); }
  function target(event) {
    const el = event.target.closest(`${controls},${cards}`);
    return el && !el.matches(':disabled,[aria-disabled="true"]') &&
      !(event.target.closest('input,textarea,select,[role="combobox"]')) &&
      (el.matches(controls) || !el.matches(':focus-within')) ? el : null;
  }
  media = g.matchMedia();
  media.add({reduce: '(prefers-reduced-motion: reduce)', normal: '(prefers-reduced-motion: no-preference)'}, context => {
    reduced = context.conditions.reduce;
    root.dataset.ylMotionReduced = String(reduced);
    if (reduced) {
      g.killTweensOf(entrance + ',' + controls + ',.feature-line');
      g.set(document.querySelectorAll(entrance + ',' + controls + ',.feature-line'), {clearProps: 'transform,opacity'});
    }
  });
  root.dataset.ylMotion = version;
  on('pointerover', event => {
    const el = target(event);
    if (!el || reduced || !fine() || el.contains(event.relatedTarget)) return;
    g.to(el, {y: -2, duration: 0.18, ease: 'power2.out', overwrite: 'auto'});
    if (el.matches('.home-feature')) {
      const line = el.querySelector('.feature-line');
      if (line) g.fromTo(line, {scaleX: 0.55}, {scaleX: 1, duration: 0.45, ease: 'power2.out', overwrite: 'auto'});
    }
  });
  on('pointerout', event => {
    const el = target(event);
    if (!el || reduced || el.contains(event.relatedTarget)) return;
    g.to(el, {y: 0, scale: 1, duration: 0.2, ease: 'power2.out', overwrite: 'auto', clearProps: 'transform'});
  });
  on('pointerdown', event => {
    const el = target(event);
    if (el?.matches(controls) && !reduced) g.to(el, {scale: 0.985, y: 0, duration: 0.1, overwrite: 'auto'});
  });
  const release = () => { if (!reduced) g.to(document.querySelectorAll(controls), {scale: 1, duration: 0.16, overwrite: 'auto', clearProps: 'transform'}); };
  on('pointerup', release); on('pointercancel', release);
  on('focusin', event => {
    const card = event.target.closest(cards);
    if (card) { g.killTweensOf(card); g.set(card, {clearProps: 'transform,opacity'}); }
  });
  observer = new MutationObserver(records => records.forEach(record => {
    record.addedNodes.forEach(scan);
    record.removedNodes.forEach(node => {
      if (node.nodeType !== 1) return;
      [node, ...node.querySelectorAll(entrance)].forEach(el => {view.unobserve(el); pending.delete(el); g.killTweensOf(el);});
    });
  }));
  observer.observe(document.body, {childList: true, subtree: true});
  scan(document.body);
  window.__ylMotion = {version, dispose() {
    observer.disconnect(); view.disconnect(); cancelAnimationFrame(frame); media.revert();
    events.forEach(([type, handler]) => document.removeEventListener(type, handler));
    g.killTweensOf(entrance + ',' + controls + ',.feature-line');
    g.set(document.querySelectorAll(entrance + ',' + controls + ',.feature-line'), {clearProps: 'transform,opacity'});
    delete root.dataset.ylMotion;
  }};
})();
