/* ═══════════════════════════════════════════════
   Slidein GH — main.js
   All shared + page-specific JS in one place.
   Initialise by detecting elements on the page
   so this single file works on every page.
═══════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', function () {

  initMobileMenu();

  if (document.getElementById('site-header'))   initHeaderScroll();
  if (document.getElementById('hero-vid'))       initHero();
  if (document.querySelector('.size-btn'))       initCollectionFilters();
  if (document.querySelector('.size-select-btn')) initProductSelectors();
  if (document.getElementById('fav-btn'))        initFavorite();
  if (document.getElementById('subscribe-btn'))  initSubscribe();
  if (document.getElementById('cart-overlay'))   initCheckout();
  if (document.getElementById('pay-btn'))        initPayButton();

  initQuickAdd();
  initOrderChevrons();
  initSizeGuide();
  initPriceSlider();

});


/* ─────────────────────────────────────────────
   1. MOBILE MENU
   Slides in from left on all pages.
   Requires: #mobile-menu, #menu-overlay,
             #menu-close, .menu-btn
───────────────────────────────────────────── */
function initMobileMenu() {
  var menu    = document.getElementById('mobile-menu');
  var overlay = document.getElementById('menu-overlay');
  var closeBtn = document.getElementById('menu-close');

  if (!menu) return;

  function openMenu() {
    menu.classList.add('open');
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  function closeMenu() {
    menu.classList.remove('open');
    overlay.classList.remove('open');
    document.body.style.overflow = '';
  }

  document.querySelectorAll('.menu-btn').forEach(function (btn) {
    btn.addEventListener('click', openMenu);
  });
  if (closeBtn)  closeBtn.addEventListener('click', closeMenu);
  if (overlay)   overlay.addEventListener('click', closeMenu);
}


/* ─────────────────────────────────────────────
   2. HEADER SCROLL  (The_Showroom only)
   Adds .scrolled class after 80px.
───────────────────────────────────────────── */
function initHeaderScroll() {
  var header = document.getElementById('site-header');
  window.addEventListener('scroll', function () {
    header.classList.toggle('scrolled', window.scrollY > 80);
  }, { passive: true });
}


/* ─────────────────────────────────────────────
   3. HERO VIDEO  (The_Showroom)
   Auto-switches to video if src is set.
   Controls: #btn-play / #btn-mute
───────────────────────────────────────────── */
function initHero() {
  var vid      = document.getElementById('hero-vid');
  var img      = document.getElementById('hero-img');
  var controls = document.getElementById('vid-controls');

  if (vid.src && vid.src !== window.location.href) {
    img.classList.add('hidden');
    vid.classList.remove('hidden');
    controls.classList.remove('hidden');
    controls.classList.add('flex');
  }
}

/* Called from onclick in HTML (kept on element so
   they work even before DOMContentLoaded) */
window.heroPlayPause = function () {
  var vid  = document.getElementById('hero-vid');
  var icon = document.querySelector('#btn-play .material-symbols-outlined');
  if (vid.paused) { vid.play();  icon.textContent = 'pause'; }
  else            { vid.pause(); icon.textContent = 'play_arrow'; }
};

window.heroMute = function () {
  var vid  = document.getElementById('hero-vid');
  var icon = document.querySelector('#btn-mute .material-symbols-outlined');
  vid.muted = !vid.muted;
  icon.textContent = vid.muted ? 'volume_off' : 'volume_up';
};


/* ─────────────────────────────────────────────
   4. COLLECTION FILTERS  (Collections page)
   Classes needed on buttons:
     size buttons  → .size-btn
     color buttons → .color-btn
     clear button  → #clear-filters
───────────────────────────────────────────── */
function initCollectionFilters() {

  document.querySelectorAll('.size-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      btn.closest('.grid').querySelectorAll('.size-btn').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
    });
  });

  document.querySelectorAll('.color-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.color-btn').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
    });
  });

  var clearBtn = document.getElementById('clear-filters');
  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      document.querySelectorAll('.size-btn').forEach(function (b) {
        b.classList.remove('active');
      });
      document.querySelectorAll('.color-btn').forEach(function (b) {
        b.classList.remove('active');
      });
    });
  }
}


/* ─────────────────────────────────────────────
   5. PRODUCT SELECTORS  (Product_Details page)
   Classes needed:
     size buttons  → .size-select-btn
     color buttons → .color-select-btn
     unavailable   → .unavailable (skip click)
───────────────────────────────────────────── */
function initProductSelectors() {

  document.querySelectorAll('.size-select-btn:not(.unavailable)').forEach(function (btn) {
    btn.addEventListener('click', function () {
      btn.closest('.grid').querySelectorAll('.size-select-btn').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
    });
  });

  document.querySelectorAll('.color-select-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      btn.closest('.flex').querySelectorAll('.color-select-btn').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
    });
  });
}


/* ─────────────────────────────────────────────
   6. FAVOURITE TOGGLE  (Product_Details)
   Requires: id="fav-btn"
───────────────────────────────────────────── */
function initFavorite() {
  document.getElementById('fav-btn').addEventListener('click', function () {
    this.classList.toggle('loved');
  });
}


/* ─────────────────────────────────────────────
   7. NEWSLETTER SUBSCRIBE  (The_Showroom)
   Requires: id="subscribe-email", id="subscribe-btn"
───────────────────────────────────────────── */
function initSubscribe() {
  document.getElementById('subscribe-btn').addEventListener('click', function () {
    var email = document.getElementById('subscribe-email');
    if (email && email.value.trim()) {
      this.textContent = 'Subscribed!';
      this.disabled = true;
      this.classList.add('opacity-70');
    } else if (email) {
      email.focus();
    }
  });
}


/* ─────────────────────────────────────────────
   8. CHECKOUT / CART DRAWER
   Requires: id="cart-overlay", id="cart-drawer"
   Cart items need: class="cart-item"
   Delete btn: class="cart-delete"
   Qty:        class="qty-minus" / "qty-plus"
   Open toggle: id="cart-toggle"
───────────────────────────────────────────── */
function initCheckout() {
  var overlay  = document.getElementById('cart-overlay');
  var toggle   = document.getElementById('cart-toggle');

  if (toggle) {
    toggle.addEventListener('click', function () {
      overlay.classList.toggle('open');
    });
  }

  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) overlay.classList.remove('open');
  });

  var closeBtn = document.getElementById('cart-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', function () {
      overlay.classList.remove('open');
    });
  }

  document.querySelectorAll('.cart-delete').forEach(function (btn) {
    btn.addEventListener('click', function () {
      btn.closest('.cart-item').remove();
    });
  });

  document.querySelectorAll('.qty-minus').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var display = btn.nextElementSibling;
      var v = parseInt(display.textContent);
      if (v > 1) display.textContent = v - 1;
    });
  });

  document.querySelectorAll('.qty-plus').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var display = btn.previousElementSibling;
      display.textContent = parseInt(display.textContent) + 1;
    });
  });

  var checkoutNowBtn = document.getElementById('checkout-now-btn');
  if (checkoutNowBtn) {
    checkoutNowBtn.addEventListener('click', function () {
      overlay.classList.remove('open');
      var payBtn = document.getElementById('pay-btn');
      if (payBtn) payBtn.scrollIntoView({ behavior: 'smooth' });
    });
  }
}


/* ─────────────────────────────────────────────
   9. PAY BUTTON  (Checkout page)
   Requires: id="pay-btn"
───────────────────────────────────────────── */
function initPayButton() {
  document.getElementById('pay-btn').addEventListener('click', function () {
    this.textContent = '✓  Order Confirmed!';
    this.disabled = true;
    this.classList.add('opacity-70');
    setTimeout(function () { window.location = 'My_Account.html'; }, 1500);
  });
}


/* ─────────────────────────────────────────────
   10. QUICK ADD BUTTONS  (Collections page)
   Requires: class="quick-add-btn" on the + buttons
───────────────────────────────────────────── */
function initQuickAdd() {
  document.querySelectorAll('.quick-add-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      btn.innerHTML = '<span class="material-symbols-outlined">check</span>';
      btn.classList.add('bg-green-600');
      setTimeout(function () { window.location = 'Checkout.html'; }, 500);
    });
  });
}


/* ─────────────────────────────────────────────
   11. ORDER CHEVRONS  (My_Account page)
   Requires: class="order-chevron"
───────────────────────────────────────────── */
function initOrderChevrons() {
  document.querySelectorAll('.order-chevron').forEach(function (btn) {
    btn.addEventListener('click', function () {
      window.location = 'Checkout.html';
    });
  });
}


/* ─────────────────────────────────────────────
   12. SIZE GUIDE MODAL  (Product_Details page)
   Requires: id="size-guide-btn"
───────────────────────────────────────────── */
function initSizeGuide() {
  var btn = document.getElementById('size-guide-btn');
  if (!btn) return;
  btn.addEventListener('click', function () {
    var modal = document.getElementById('size-guide-modal');
    if (modal) modal.classList.remove('hidden');
  });
  var closeModal = document.getElementById('size-guide-close');
  if (closeModal) {
    closeModal.addEventListener('click', function () {
      document.getElementById('size-guide-modal').classList.add('hidden');
    });
  }
}


/* ─────────────────────────────────────────────
   13. PRICE SLIDER  (Collections page)
   Requires: id="price-slider", id="price-display"
───────────────────────────────────────────── */
function initPriceSlider() {
  var slider  = document.getElementById('price-slider');
  var display = document.getElementById('price-display');
  if (!slider || !display) return;
  slider.addEventListener('input', function () {
    display.textContent = '£' + slider.value;
  });
}
