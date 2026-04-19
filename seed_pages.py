"""Seed CMS static pages: About, Contact, Shipping, Returns, Privacy, Terms, FAQ.

Run: python seed_pages.py
"""
from app import create_app, db
from app.models import Page

PAGES = [
    ('about', 'About Slidein GH',
     '<h2>Born in Ghana. Built for sneakerheads.</h2>'
     '<p>Slidein GH curates premium sneakers for Ghana\u2019s style-forward generation. '
     'Every pair is verified authentic and delivered fast.</p>'
     '<p>We started with one goal: make it effortless to get the drops you want, '
     'without the overseas markups or fakes.</p>'),
    ('contact', 'Contact Us',
     '<p>Questions, returns, partnerships \u2014 reach out any time.</p>'
     '<ul>'
     '<li><strong>WhatsApp:</strong> chat us for fastest replies</li>'
     '<li><strong>Email:</strong> hello@slidein.gh</li>'
     '<li><strong>Hours:</strong> Mon\u2013Sat, 9am\u20136pm GMT</li>'
     '</ul>'),
    ('shipping', 'Shipping &amp; Delivery',
     '<h2>Delivery in Ghana</h2>'
     '<ul>'
     '<li><strong>Accra:</strong> same-day or next-day, GH\u20B530</li>'
     '<li><strong>Kumasi / Takoradi / Cape Coast:</strong> 1\u20132 business days, GH\u20B530</li>'
     '<li><strong>Other regions:</strong> 2\u20134 business days, GH\u20B530</li>'
     '<li><strong>Free delivery</strong> on all orders over GH\u20B5500</li>'
     '</ul>'
     '<p>You\u2019ll get an SMS with your tracking info as soon as your order is confirmed.</p>'),
    ('returns', 'Returns &amp; Exchanges',
     '<h2>7-day return policy</h2>'
     '<p>If your sneakers aren\u2019t right, return them within 7 days of delivery for a full refund or exchange.</p>'
     '<ul>'
     '<li>Item must be unworn, in original packaging, with all tags</li>'
     '<li>Return shipping is on us for defects; GH\u20B550 for change-of-mind</li>'
     '<li>Message us on WhatsApp to start a return</li>'
     '</ul>'),
    ('privacy', 'Privacy Policy',
     '<p>We only collect what we need to deliver your order: name, phone, email, and delivery address. '
     'We never sell your data. Cookies are used only for your cart and analytics.</p>'
     '<p>To request deletion of your records, contact us.</p>'),
    ('terms', 'Terms of Service',
     '<p>By placing an order you agree to pay cash on delivery and accept items in the condition shown.</p>'
     '<p>Prices are in Ghanaian Cedi (GH\u20B5) and include VAT where applicable.</p>'
     '<p>Slidein GH reserves the right to cancel orders where stock is unavailable or fraud is suspected.</p>'),
    ('faq', 'Frequently Asked Questions',
     '<h3>Are your sneakers authentic?</h3>'
     '<p>Yes \u2014 every pair is sourced from authorised retailers or verified sellers. We authenticate on receipt.</p>'
     '<h3>How do I pay?</h3>'
     '<p>Cash on delivery is standard. Mobile money will follow shortly.</p>'
     '<h3>Can I cancel an order?</h3>'
     '<p>Yes, contact us before it ships.</p>'
     '<h3>Do you restock?</h3>'
     '<p>We do \u2014 hit the \u201Cnotify me\u201D button on sold-out pages.</p>'),
]


def run():
    app = create_app()
    with app.app_context():
        db.create_all()
        created = 0
        for slug, title, content in PAGES:
            existing = Page.query.filter_by(slug=slug).first()
            if existing:
                continue
            db.session.add(Page(
                slug=slug, title=title, content=content,
                status='published',
                seo_title=f'{title} \u2014 Slidein GH',
                seo_description=f'{title} page for Slidein GH.',
            ))
            created += 1
        db.session.commit()
        print(f'Seeded {created} page(s).')


if __name__ == '__main__':
    run()
