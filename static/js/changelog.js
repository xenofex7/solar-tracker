(function () {
  var btn = document.getElementById('open-changelog');
  var backdrop = document.getElementById('changelog-modal');
  var closeBtn = document.getElementById('changelog-close');
  var body = document.getElementById('changelog-body');
  if (!btn || !backdrop || !closeBtn || !body) return;

  var loaded = false;

  function open() {
    backdrop.classList.add('open');
    backdrop.setAttribute('aria-hidden', 'false');
    if (!loaded) {
      fetch('/api/changelog')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          body.innerHTML = data.html || '';
          loaded = true;
          body.scrollTop = 0;
        })
        .catch(function () {
          body.textContent = '—';
        });
    }
  }

  function close() {
    backdrop.classList.remove('open');
    backdrop.setAttribute('aria-hidden', 'true');
  }

  btn.addEventListener('click', open);
  closeBtn.addEventListener('click', close);
  backdrop.addEventListener('click', function (e) {
    if (e.target === backdrop) close();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && backdrop.classList.contains('open')) close();
  });
})();
