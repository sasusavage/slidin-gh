"""
Seed script for Slidin GH — run once to populate the DB with:
  - Site settings (announcement bar, hero, trust features, footer)
  - Categories (already exist, but will add if missing)
  - Products with variants (no images — upload via admin)
  - Banners

Usage:
  python seed.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wsgi import app
from app import db
from app.models import (Category, Product, ProductVariant,
                        SiteSettings, Banner)
import uuid, re
from datetime import datetime


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text


def gen_uuid():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
#  CATEGORIES
# ─────────────────────────────────────────────
CATEGORIES = [
    {'name': 'Sneakers',       'slug': 'sneakers',      'position': 1},
    {'name': 'Slides & Crocs', 'slug': 'slides-crocs',  'position': 2},
    {'name': 'Bags',           'slug': 'bags',           'position': 3},
    {'name': 'Apparel',        'slug': 'apparel',        'position': 4},
]


# ─────────────────────────────────────────────
#  PRODUCTS  (images to be uploaded by admin)
# ─────────────────────────────────────────────
PRODUCTS = [
    # ── Sneakers ──────────────────────────────
    {
        'name': 'Air Max Pulse',
        'category': 'sneakers',
        'price': 650.00,
        'compare_at': 780.00,
        'gender': 'unisex',
        'brand': 'Nike',
        'featured': True,
        'description': 'The Air Max Pulse draws inspiration from the London music scene. Visible Air cushioning under every step.',
        'sizes': ['40', '41', '42', '43', '44', '45'],
        'colors': [('White/Black', '#FFFFFF'), ('Black/Red', '#1a1a1a'), ('Grey Fog', '#9e9e9e')],
        'stock': 8,
    },
    {
        'name': 'Adidas Ultraboost 22',
        'category': 'sneakers',
        'price': 720.00,
        'compare_at': None,
        'gender': 'men',
        'brand': 'Adidas',
        'featured': True,
        'description': 'Responsive Boost midsole returns energy with every stride. Primeknit+ upper hugs the foot.',
        'sizes': ['41', '42', '43', '44', '45'],
        'colors': [('Core Black', '#111111'), ('Cloud White', '#F5F5F5')],
        'stock': 5,
    },
    {
        'name': 'New Balance 550',
        'category': 'sneakers',
        'price': 580.00,
        'compare_at': None,
        'gender': 'unisex',
        'brand': 'New Balance',
        'featured': True,
        'description': 'Basketball-inspired silhouette revived. Clean leather upper with retro court DNA.',
        'sizes': ['38', '39', '40', '41', '42', '43', '44'],
        'colors': [('White/Green', '#FFFFFF'), ('Cream/Navy', '#F5F0E0')],
        'stock': 10,
    },
    {
        'name': 'Jordan 1 Retro High OG',
        'category': 'sneakers',
        'price': 950.00,
        'compare_at': None,
        'gender': 'unisex',
        'brand': 'Jordan',
        'featured': True,
        'description': 'The shoe that started it all. Premium leather upper, Air-Sole unit, iconic Wings logo.',
        'sizes': ['40', '41', '42', '43', '44', '45'],
        'colors': [('Chicago', '#C41E3A'), ('Bred Toe', '#1a1a1a'), ('University Blue', '#4B9CD3')],
        'stock': 3,
    },
    {
        'name': 'Puma Suede Classic XXI',
        'category': 'sneakers',
        'price': 420.00,
        'compare_at': 520.00,
        'gender': 'unisex',
        'brand': 'Puma',
        'featured': False,
        'description': 'The suede that defined street style since 1968. Soft suede upper, cushioned sockliner.',
        'sizes': ['38', '39', '40', '41', '42', '43'],
        'colors': [('Puma Black', '#1a1a1a'), ('Whisper White', '#F5F5F5'), ('Peacoat Blue', '#1F3464')],
        'stock': 12,
    },
    {
        'name': 'Vans Old Skool',
        'category': 'sneakers',
        'price': 380.00,
        'compare_at': None,
        'gender': 'unisex',
        'brand': 'Vans',
        'featured': False,
        'description': 'The original skate shoe. Canvas and suede upper with the iconic sidestripe.',
        'sizes': ['37', '38', '39', '40', '41', '42', '43', '44'],
        'colors': [('Black/White', '#1a1a1a'), ('Navy/White', '#1F3464'), ('Checkerboard', '#808080')],
        'stock': 15,
    },

    # ── Slides & Crocs ────────────────────────
    {
        'name': 'Adidas Adilette Aqua',
        'category': 'slides-crocs',
        'price': 180.00,
        'compare_at': None,
        'gender': 'unisex',
        'brand': 'Adidas',
        'featured': False,
        'description': 'Pool-ready slides with a quick-dry bandage upper. Three iconic stripes.',
        'sizes': ['38', '40', '42', '44', '46'],
        'colors': [('Core Black', '#1a1a1a'), ('Cloud White', '#F5F5F5'), ('Blue Rush', '#4682B4')],
        'stock': 20,
    },
    {
        'name': 'Nike Offcourt Slide',
        'category': 'slides-crocs',
        'price': 220.00,
        'compare_at': 260.00,
        'gender': 'unisex',
        'brand': 'Nike',
        'featured': False,
        'description': 'Post-game comfort. Soft foam footbed with a jersey-lined strap.',
        'sizes': ['38', '40', '42', '44'],
        'colors': [('Black/White', '#1a1a1a'), ('Light Bone', '#D2C9A5')],
        'stock': 18,
    },
    {
        'name': 'Crocs Classic Clog',
        'category': 'slides-crocs',
        'price': 290.00,
        'compare_at': None,
        'gender': 'unisex',
        'brand': 'Crocs',
        'featured': False,
        'description': 'The iconic clog. Lightweight Croslite foam, ventilation ports, pivoting heel straps.',
        'sizes': ['37', '38', '39', '40', '41', '42', '43', '44', '45'],
        'colors': [('Black', '#1a1a1a'), ('White', '#FFFFFF'), ('Navy', '#1F3464'), ('Red', '#C41E3A')],
        'stock': 25,
    },

    # ── Bags ──────────────────────────────────
    {
        'name': 'Nike Brasilia Backpack',
        'category': 'bags',
        'price': 320.00,
        'compare_at': None,
        'gender': 'unisex',
        'brand': 'Nike',
        'featured': False,
        'description': 'Versatile 18L daypack. Padded back panel and shoulder straps, zip main compartment.',
        'sizes': ['One Size'],
        'colors': [('Black', '#1a1a1a'), ('Navy', '#1F3464'), ('Grey', '#808080')],
        'stock': 14,
    },
    {
        'name': 'Adidas Linear Duffel Bag',
        'category': 'bags',
        'price': 280.00,
        'compare_at': 350.00,
        'gender': 'unisex',
        'brand': 'Adidas',
        'featured': False,
        'description': '30L duffel with a separate base compartment. Removable, adjustable shoulder strap.',
        'sizes': ['One Size'],
        'colors': [('Black/White', '#1a1a1a'), ('Core Black', '#333333')],
        'stock': 10,
    },

    # ── Apparel ───────────────────────────────
    {
        'name': 'Nike Sportswear Club Fleece Hoodie',
        'category': 'apparel',
        'price': 350.00,
        'compare_at': None,
        'gender': 'unisex',
        'brand': 'Nike',
        'featured': False,
        'description': 'Classic pullover hoodie in soft brushed-back fleece. Kangaroo pocket, ribbed cuffs.',
        'sizes': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
        'colors': [('Black', '#1a1a1a'), ('White', '#FFFFFF'), ('Dark Grey', '#555555')],
        'stock': 20,
    },
    {
        'name': 'Adidas Essentials 3-Stripes Tee',
        'category': 'apparel',
        'price': 160.00,
        'compare_at': 200.00,
        'gender': 'men',
        'brand': 'Adidas',
        'featured': False,
        'description': 'Soft cotton jersey tee with three-stripe tape on the left sleeve. Regular fit.',
        'sizes': ['S', 'M', 'L', 'XL', 'XXL'],
        'colors': [('White', '#FFFFFF'), ('Black', '#1a1a1a'), ('Legend Ink', '#1F3464')],
        'stock': 30,
    },
]


# ─────────────────────────────────────────────
#  SITE SETTINGS
# ─────────────────────────────────────────────
SETTINGS = {
    'site_name': 'Slidin GH',
    'site_tagline': 'Premium Sneakers & Streetwear in Ghana',
    'contact_phone': '+233 55 000 0000',
    'contact_email': 'hello@slidingh.com',
    'contact_address': 'Accra Mall, Spintex Road, Accra',
    'currency': 'GHS',
    'currency_symbol': 'GH₵',
    'social_instagram': 'https://instagram.com/slidingh',
    'social_whatsapp': '+233550000000',
    'social_tiktok': 'https://tiktok.com/@slidingh',

    # Hero
    'hero_style': 'balenciaga',
    'hero_media_type': 'image',
    'hero_label': 'New Season — 2025',
    'hero_title': 'Step Into\nYour Story',
    'hero_subheadline': 'Authentic sneakers, same-day delivery across Accra.',
    'hero_cta_primary_text': 'Shop Now',
    'hero_cta_primary_url': '/shop',
    'hero_cta_secondary_text': 'New Arrivals',
    'hero_cta_secondary_url': '/shop?sort=newest',

    # Hero badge
    'hero_badge_label': 'Limited Time',
    'hero_badge_text': 'Free\nDelivery',
    'hero_badge_subtext': 'Orders over GH₵500',

    # Hero stats
    'hero_stat1_title': '2,000+',
    'hero_stat1_desc': 'Happy customers',
    'hero_stat2_title': '500+',
    'hero_stat2_desc': 'Products in stock',
    'hero_stat3_title': '100%',
    'hero_stat3_desc': 'Authentic gear',

    # Trust features
    'feature1_icon': 'ri-truck-line',
    'feature1_title': 'Fast Delivery',
    'feature1_desc': 'Same-day in Accra',
    'feature2_icon': 'ri-shield-check-line',
    'feature2_title': '100% Authentic',
    'feature2_desc': 'Every item verified',
    'feature3_icon': 'ri-refresh-line',
    'feature3_title': 'Easy Returns',
    'feature3_desc': '7-day return policy',
    'feature4_icon': 'ri-whatsapp-line',
    'feature4_title': 'WhatsApp Support',
    'feature4_desc': 'Chat us anytime',

    # Announcement bar
    'announcement_bar_text': '🔥 Free delivery on all orders over GH₵500 — Shop Now',
    'announcement_bar_active': 'true',

    # SEO
    'seo_title': 'Slidin GH — Authentic Sneakers in Ghana',
    'seo_description': 'Shop authentic Nike, Adidas, Jordan, Puma and more. Fast delivery across Ghana. 100% genuine products.',
    'seo_keywords': 'sneakers ghana, nike accra, adidas ghana, jordan shoes ghana, authentic sneakers',

    # Footer
    'footer_copyright_text': '© 2025 Slidin GH. All rights reserved.',
    'footer_show_newsletter': 'false',
    'footer_col1_title': 'Shop',
    'footer_col1_links_json': '[{"label":"All Sneakers","href":"/shop"},{"label":"New Arrivals","href":"/shop?sort=newest"},{"label":"Sale","href":"/shop?sort=price_asc"}]',
    'footer_col2_title': 'Help',
    'footer_col2_links_json': '[{"label":"Track Order","href":"/order/track"},{"label":"Returns Policy","href":"/p/returns"},{"label":"FAQ","href":"/p/faq"},{"label":"Contact Us","href":"/p/contact"}]',
    'footer_col3_title': 'Company',
    'footer_col3_links_json': '[{"label":"About Us","href":"/p/about"},{"label":"Privacy Policy","href":"/p/privacy"},{"label":"Terms","href":"/p/terms"}]',

    # Contact page
    'contact_hero_title': 'Get In Touch',
    'contact_hero_subtitle': 'We\'re here to help.',
    'contact_hours': 'Mon – Sat: 9am – 7pm',
    'contact_whatsapp_hours': 'Mon – Sun: 8am – 9pm',

    # About page
    'about_hero_title': 'Our Story',
    'about_hero_subtitle': 'Born in Ghana. Built for Sneakerheads.',
    'about_story_title': 'How Slidin Started',
    'about_story_content': 'Slidin GH was founded with one mission: bring authentic, quality sneakers and streetwear to Ghana at fair prices. No fakes, no compromises.',
    'about_cta_title': 'Ready to step up?',
    'about_cta_subtitle': 'Browse our latest drops and find your next favourite pair.',
}


# ─────────────────────────────────────────────
#  BANNERS
# ─────────────────────────────────────────────
BANNERS = [
    {
        'name': 'New Season Drop',
        'type': 'promotional',
        'title': 'New Season Is Here',
        'subtitle': 'Fresh drops from Nike, Jordan, Adidas & more',
        'button_text': 'Shop Now',
        'button_url': '/shop?sort=newest',
        'background_color': '#000000',
        'text_color': '#FFFFFF',
        'position': 'homepage',
        'sort_order': 0,
        'is_active': True,
    },
]


# ─────────────────────────────────────────────
#  SEED RUNNER
# ─────────────────────────────────────────────
def seed():
    with app.app_context():
        print("🌱 Seeding Slidin GH database…")

        # ── Categories ───────────────────────
        cat_map = {}
        for c in CATEGORIES:
            existing = Category.query.filter_by(slug=c['slug']).first()
            if existing:
                cat_map[c['slug']] = existing
                print(f"  Category exists: {c['name']}")
            else:
                cat = Category(
                    id=gen_uuid(),
                    name=c['name'],
                    slug=c['slug'],
                    position=c['position'],
                    is_active=True,
                )
                db.session.add(cat)
                db.session.flush()
                cat_map[c['slug']] = cat
                print(f"  ✓ Category created: {c['name']}")
        db.session.commit()

        # ── Products ─────────────────────────
        for p in PRODUCTS:
            slug = slugify(p['name'])
            existing = Product.query.filter_by(slug=slug).first()
            if existing:
                print(f"  Product exists: {p['name']}")
                continue

            cat = cat_map.get(p['category'])
            product = Product(
                id=gen_uuid(),
                name=p['name'],
                slug=slug,
                description=p['description'],
                price=p['price'],
                compare_at_price=p.get('compare_at'),
                category_id=cat.id if cat else None,
                gender=p.get('gender', 'unisex'),
                brand=p.get('brand', ''),
                featured=p.get('featured', False),
                status='active',
            )
            db.session.add(product)
            db.session.flush()

            # Variants: every size × every color
            for size in p.get('sizes', []):
                for color_name, color_hex in p.get('colors', [('Default', '#000000')]):
                    v = ProductVariant(
                        id=gen_uuid(),
                        product_id=product.id,
                        size=size,
                        color=color_name,
                        color_hex=color_hex,
                        quantity=p.get('stock', 5),
                    )
                    db.session.add(v)

            print(f"  ✓ Product created: {p['name']} ({len(p['sizes'])} sizes × {len(p['colors'])} colors)")

        db.session.commit()
        print(f"  Products done.")

        # ── Site Settings ────────────────────
        for key, value in SETTINGS.items():
            SiteSettings.set(key, value)
        db.session.commit()
        print(f"  ✓ Site settings seeded ({len(SETTINGS)} keys)")

        # ── Banners ──────────────────────────
        for b in BANNERS:
            existing = Banner.query.filter_by(name=b['name']).first()
            if existing:
                print(f"  Banner exists: {b['name']}")
                continue
            banner = Banner(id=gen_uuid(), **b)
            db.session.add(banner)
        db.session.commit()
        print(f"  ✓ Banners seeded")

        print("\n✅ Seed complete! Upload product images via /admin/products.")
        print("   Tip: Set a hero image at /admin/settings → Homepage tab.")


if __name__ == '__main__':
    seed()
