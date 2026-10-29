(function () {
  fetch('../versions.json')
    .then((r) => r.json())
    .then((versions) => {
      const current = window.location.pathname.split('/').filter(Boolean).slice(-2)[0];
      const select = document.createElement('select');
      select.id = 'version-switcher';

      versions.forEach((v) => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        if (v === current) opt.selected = true;
        select.appendChild(opt);
      });

      select.addEventListener('change', (e) => {
        const newVersion = e.target.value;
        // preserve the current page name (e.g. classes.html), just swap the version folder
        const parts = window.location.pathname.split('/');
        parts[parts.length - 2] = newVersion;
        window.location.pathname = parts.join('/');
      });

      const container = document.createElement('div');
      container.style.cssText = 'position:fixed;top:8px;right:12px;z-index:9999;';
      container.appendChild(select);
      document.body.appendChild(container);
    })
    .catch(() => {/* versions.json not reachable, fail silently */});
})();