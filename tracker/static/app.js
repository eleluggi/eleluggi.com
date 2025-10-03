(function () {
  const scanInput = document.querySelector('[data-scan-input]');
  if (scanInput) {
    const focusScan = () => {
      setTimeout(() => {
        scanInput.focus();
        scanInput.select();
      }, 150);
    };
    focusScan();
    document.querySelectorAll('[data-reset-scan]').forEach((btn) => {
      btn.addEventListener('click', () => {
        scanInput.value = '';
        focusScan();
      });
    });
    window.addEventListener('pageshow', focusScan);
  }

  const kioskBtn = document.getElementById('kiosk-btn');
  if (kioskBtn && document.documentElement.requestFullscreen) {
    kioskBtn.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    });
  }

  let audioCtx;
  function beep(frequency, duration) {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    } catch (err) {
      return;
    }
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'square';
    osc.frequency.value = frequency;
    gain.gain.value = 0.08;
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    setTimeout(() => {
      osc.stop();
    }, duration);
  }

  document.querySelectorAll('[data-flash-category]').forEach((alert) => {
    const category = alert.getAttribute('data-flash-category');
    if (category === 'success') {
      beep(880, 180);
    } else if (category === 'danger' || category === 'error') {
      beep(220, 260);
    } else if (category === 'warning') {
      beep(440, 200);
    }
  });
})();
