# -*- coding: utf-8 -*-
"""
KHANDHARS CHAT - Database Migrations
Run: flask db init && flask db migrate && flask db upgrade
"""
from flask.cli import FlaskGroup
from app import create_app, db
from app.models import *

app = create_app()

@app.cli.command('create-admin')
def create_admin():
    """Create default admin account."""
    import click
    username = click.prompt('Admin username', default='admin')
    email = click.prompt('Admin email', default='admin@khandharschat.com')
    password = click.prompt('Admin password', hide_input=True, confirmation_prompt=True)

    from app.models import Admin
    import uuid
    existing = Admin.query.filter_by(email=email).first()
    if existing:
        click.echo('Admin with that email already exists.')
        return

    admin = Admin(id=str(uuid.uuid4()), username=username, email=email, role='superadmin')
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo(f'✅ Admin {username} created successfully!')


@app.cli.command('seed-db')
def seed_db():
    """Seed database with default data."""
    import click
    from app import _seed_defaults
    _seed_defaults(app)
    click.echo('✅ Database seeded!')


@app.cli.command('reset-db')
def reset_db():
    """Drop and recreate all tables (DANGEROUS!)."""
    import click
    if click.confirm('⚠️ This will DELETE ALL DATA. Are you sure?'):
        db.drop_all()
        db.create_all()
        click.echo('✅ Database reset complete.')


if __name__ == '__main__':
    app.run()
