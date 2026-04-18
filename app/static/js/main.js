/* ── Slidin GH — main.js ─────────────────── */

// ── Menu overlay ──────────────────────────
const menuOverlay = document.getElementById('menu-overlay');
const menuOpen    = document.getElementById('menu-open');
const menuClose   = document.getElementById('menu-close');

if (menuOpen)  menuOpen.addEventListener('click',  () => menuOverlay?.classList.add('open'));
if (menuClose) menuClose.addEventListener('click', () => menuOverlay?.classList.remove('open'));
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') menuOverlay?.classList.remove('open');
});

// ── Cart drawer ───────────────────────────
const cartOverlay = document.getElementById('cart-overlay');
const cartDrawer  = document.getElementById('cart-drawer');
const cartOpen    = document.querySelectorAll('[data-cart-open]');
const cartClose   = document.getElementById('cart-close');

function openCart()  { cartOverlay?.classList.add('open'); cartDrawer?.classList.add('open'); }
function closeCart() { cartOverlay?.classList.remove('open'); cartDrawer?.classList.remove('open'); }

cartOpen.forEach(btn => btn.addEventListener('click', openCart));
if (cartClose) cartClose.addEventListener('click', closeCart);
if (cartOverlay) cartOverlay.addEventListener('click', e => { if (e.target === cartOverlay) closeCart(); });

// ── Toast ──────────────────────────────────
const toastEl = document.getElementById('toast');
let toastTimer;
function showToast(msg) {
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2800);
}

// ── Cart count update ──────────────────────
function setCartCount(n) {
  document.querySelectorAll('[data-cart-count]').forEach(el => {
    el.textContent = n;
    el.style.display = n > 0 ? 'flex' : 'none';
  });
}

// ── Add to cart (PDP) ─────────────────────
const addToCartBtn = document.getElementById('add-to-cart');
if (addToCartBtn) {
  addToCartBtn.addEventListener('click', async () => {
    const productId = addToCartBtn.dataset.productId;
    const variantId = document.getElementById('selected-variant')?.value || null;
    const qty = parseInt(document.getElementById('qty-input')?.value || '1');

    if (!variantId) {
      showToast('Please select a size');
      return;
    }

    addToCartBtn.disabled = true;
    addToCartBtn.textContent = '—';

    try {
      const res = await fetch('/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, variant_id: variantId, quantity: qty }),
      });
      const data = await res.json();
      if (data.success) {
        setCartCount(data.cart_count);
        addToCartBtn.textContent = 'Added';
        setTimeout(() => { addToCartBtn.disabled = false; addToCartBtn.textContent = 'Add to Bag'; }, 1800);
        showToast('Added to bag');
      } else {
        showToast(data.error || 'Error adding to bag');
        addToCartBtn.disabled = false;
        addToCartBtn.textContent = 'Add to Bag';
      }
    } catch {
      showToast('Network error');
      addToCartBtn.disabled = false;
      addToCartBtn.textContent = 'Add to Bag';
    }
  });
}

// ── PDP: size + color selectors ───────────
const sizeButtons  = document.querySelectorAll('.size-btn[data-size]');
const colorButtons = document.querySelectorAll('.color-btn[data-color]');
const selectedVariantInput = document.getElementById('selected-variant');
const selectedColorInput   = document.getElementById('selected-color');
const variantPriceEl       = document.getElementById('variant-price');

let selectedSize  = null;
let selectedColor = null;

async function fetchVariant() {
  const productId = addToCartBtn?.dataset.productId;
  if (!productId || !selectedSize || !selectedColor) return;
  const res = await fetch(`/api/variant-stock?product_id=${productId}&size=${encodeURIComponent(selectedSize)}&color=${encodeURIComponent(selectedColor)}`);
  const data = await res.json();
  if (selectedVariantInput) selectedVariantInput.value = data.variant_id || '';
  if (variantPriceEl && data.price) {
    variantPriceEl.textContent = formatPrice(data.price);
  }
  if (addToCartBtn) {
    addToCartBtn.disabled = !data.variant_id || data.quantity === 0;
    if (data.quantity === 0 && data.variant_id) addToCartBtn.textContent = 'Out of Stock';
    else addToCartBtn.textContent = 'Add to Bag';
  }
}

sizeButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    sizeButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedSize = btn.dataset.size;
    fetchVariant();
  });
});

colorButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    colorButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedColor = btn.dataset.color;
    if (selectedColorInput) selectedColorInput.value = selectedColor;
    fetchVariant();
  });
});

// Auto-select first available color
if (colorButtons.length) {
  colorButtons[0].click();
}

// ── PDP: gallery thumbs ───────────────────
const galleryMain   = document.getElementById('gallery-main');
const galleryThumbs = document.querySelectorAll('.pdp__thumb');

galleryThumbs.forEach(thumb => {
  thumb.addEventListener('click', () => {
    galleryThumbs.forEach(t => t.classList.remove('active'));
    thumb.classList.add('active');
    if (galleryMain) galleryMain.src = thumb.dataset.src;
  });
});

// ── Qty input ─────────────────────────────
const qtyMinus = document.getElementById('qty-minus');
const qtyPlus  = document.getElementById('qty-plus');
const qtyInput = document.getElementById('qty-input');

if (qtyMinus) qtyMinus.addEventListener('click', () => {
  const v = parseInt(qtyInput.value);
  if (v > 1) qtyInput.value = v - 1;
});
if (qtyPlus) qtyPlus.addEventListener('click', () => {
  qtyInput.value = parseInt(qtyInput.value) + 1;
});

// ── Cart drawer: remove + qty ─────────────
document.addEventListener('click', async e => {
  const removeBtn = e.target.closest('[data-remove-key]');
  if (removeBtn) {
    const key = removeBtn.dataset.removeKey;
    const res = await fetch('/cart/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key }),
    });
    const data = await res.json();
    if (data.success) {
      removeBtn.closest('.cart-item')?.remove();
      setCartCount(data.cart_count);
      updateCartSubtotal();
      if (data.cart_count === 0) showEmptyCart();
    }
  }

  const qtyBtn = e.target.closest('[data-qty-key]');
  if (qtyBtn) {
    const key = qtyBtn.dataset.qtyKey;
    const delta = parseInt(qtyBtn.dataset.delta);
    const qtyEl = qtyBtn.closest('.cart-item')?.querySelector('[data-qty-display]');
    const newQty = parseInt(qtyEl?.textContent || '1') + delta;
    const res = await fetch('/cart/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, quantity: newQty }),
    });
    const data = await res.json();
    if (data.success) {
      if (newQty < 1) {
        qtyBtn.closest('.cart-item')?.remove();
        if (data.cart_count === 0) showEmptyCart();
      } else {
        if (qtyEl) qtyEl.textContent = newQty;
      }
      setCartCount(data.cart_count);
      updateCartSubtotal(data.subtotal);
    }
  }
});

function updateCartSubtotal(subtotal) {
  const el = document.getElementById('cart-subtotal');
  if (el && subtotal !== undefined) el.textContent = formatPrice(subtotal);
}

function showEmptyCart() {
  const body = document.getElementById('cart-body');
  if (body) body.innerHTML = '<p class="cart-drawer__empty">Your bag is empty.</p>';
  const footer = document.getElementById('cart-footer');
  if (footer) footer.style.display = 'none';
}

// ── Helpers ────────────────────────────────
function formatPrice(n) {
  return 'GH₵' + parseFloat(n).toLocaleString('en-GH', { minimumFractionDigits: 2 });
}