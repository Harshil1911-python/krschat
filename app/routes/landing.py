"""
KHANDHARS CHAT - Landing / Public Routes
"""
from flask import Blueprint, render_template, redirect, url_for, abort
from flask_login import current_user
from ..models import CMSPage, SiteSettings, Advertisement

landing_bp = Blueprint('landing', __name__)


@landing_bp.route('/')
def index():
    ads = Advertisement.query.filter_by(is_active=True, placement='landing').all()
    return render_template('landing/index.html', ads=ads)


@landing_bp.route('/p/<slug>')
def cms_page(slug):
    page = CMSPage.query.filter_by(slug=slug, is_published=True).first_or_404()
    return render_template('landing/cms_page.html', page=page)


@landing_bp.route('/privacy-policy')
def privacy():
    page = CMSPage.query.filter_by(slug='privacy-policy').first()
    return render_template('landing/cms_page.html', page=page)


@landing_bp.route('/terms-of-service')
def terms():
    page = CMSPage.query.filter_by(slug='terms-of-service').first()
    return render_template('landing/cms_page.html', page=page)


@landing_bp.route('/contact')
def contact():
    page = CMSPage.query.filter_by(slug='contact').first()
    return render_template('landing/contact.html', page=page)


@landing_bp.route('/about')
def about():
    page = CMSPage.query.filter_by(slug='about').first()
    return render_template('landing/cms_page.html', page=page)
