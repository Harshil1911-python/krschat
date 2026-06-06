# 💬 KHANDHARS CHAT
### Production-Ready SaaS Messaging Platform

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

A complete, production-ready, end-to-end encrypted messaging platform built with Flask, WebSockets, PostgreSQL, and a stunning Purple/Black/White design system.

---

## ✨ Features

### 💬 Messaging
- Real-time WebSocket messaging
- One-to-One & Group Chats (up to 256 members)
- Read receipts & delivery status
- Typing indicators
- Message reactions (emoji)
- Reply, edit, delete, forward messages
- Pin messages
- Archive chats
- Message search
- Voice notes
- File sharing (images, videos, PDFs, audio, documents)

### 🔐 Security
- End-to-End Encryption (E2EE via WebCrypto)
- Argon2 password hashing (NEVER plaintext)
- JWT + Session authentication
- CSRF protection
- XSS prevention
- SQL injection protection
- Rate limiting
- Brute force protection (account lockout)
- Secure cookies
- Audit logging
- Security headers (HSTS, CSP, X-Frame-Options)

### 👤 Users
- Phone + Email + Username login
- Multi-device support
- QR code login
- Profile pictures (Cloudinary)
- Bio, username, display name
- Online/offline status
- Privacy controls
- Block & Report users
- Account verification badges

### 👥 Groups
- Create groups
- Admin roles
- Invite links
- Group permissions
- Up to 256 members

### 🛡️ Admin Panel
- Full dashboard with analytics
- User management (ban, suspend, verify, delete)
- CMS page editor (WYSIWYG)
- Landing page editor
- Announcement system
- Advertisement manager
- **Contact settings** (helpline, email, Gmail, phone — all editable without code)
- SMTP configuration
- Theme & branding controls
- Audit logs
- Report management

### 📱 PWA
- Install as native app
- Offline support
- Push notifications
- Mobile-first responsive design

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis (optional, for rate limiting)

### 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/khandhars-chat.git
cd khandhars-chat
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
nano .env
```

**Minimum required settings:**
```env
SECRET_KEY=your-super-secret-key-minimum-32-chars
DATABASE_URL=postgresql://user:password@localhost:5432/khandhars_chat
FLASK_ENV=development
```

### 3. Database Setup

```bash
# Create the database
createdb khandhars_chat

# Initialize migrations
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 4. Run Development Server

```bash
python wsgi.py
```

Visit: `http://localhost:5000`

**Default Admin Credentials:**
- URL: `http://localhost:5000/admin/login`
- Username: `admin`
- Password: Set via `ADMIN_PASSWORD` in `.env` (default: `ChangeMe123!`)

---

## 🌐 Deploy to Render

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit - Khandhars Chat"
git remote add origin https://github.com/YOUR_USERNAME/khandhars-chat.git
git push -u origin main
```

### 2. Deploy on Render

1. Go to [render.com](https://render.com) and sign up
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Render will auto-detect the `render.yaml` configuration
5. Set your environment variables in Render dashboard:
   - `SECRET_KEY` — generate a strong random key
   - `JWT_SECRET_KEY` — generate another strong random key
   - `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` (for file uploads)
   - `MAIL_USERNAME`, `MAIL_PASSWORD` (for email features)
   - `ADMIN_EMAIL`, `ADMIN_PASSWORD` (change from defaults!)

6. Render will provision a PostgreSQL database automatically via `render.yaml`
7. Deploy! 🎉

### 3. Post-Deploy Setup

After deployment, visit your admin panel at `https://YOUR-APP.onrender.com/admin` and:
- Update contact details (helpline, support email, Gmail)
- Configure SMTP for email sending
- Upload your logo and favicon
- Edit landing page content
- Set your app name and URL in settings

---

## ⚙️ Configuration Reference

### Core Settings (`.env`)

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key (min 32 chars) | ✅ |
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `JWT_SECRET_KEY` | JWT signing key | ✅ |
| `REDIS_URL` | Redis for rate limiting | Optional |

### File Storage

| Variable | Description |
|----------|-------------|
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret |

### Email (SMTP)

| Variable | Description |
|----------|-------------|
| `MAIL_SERVER` | SMTP server (e.g., smtp.gmail.com) |
| `MAIL_PORT` | Port (587 for TLS) |
| `MAIL_USERNAME` | Your Gmail or SMTP username |
| `MAIL_PASSWORD` | App password (not your main password) |

> **Gmail tip:** Enable 2FA → Generate App Password → Use that as `MAIL_PASSWORD`

### Contact (also editable via Admin Panel)

| Variable | Description |
|----------|-------------|
| `SUPPORT_EMAIL` | Support email address |
| `HELPLINE_NUMBER` | Helpline/emergency phone |
| `SUPPORT_PHONE` | General support phone |

---

## 📁 Project Structure

```
khandhars_chat/
├── app/
│   ├── __init__.py          # App factory
│   ├── models.py            # All database models
│   ├── routes/
│   │   ├── auth.py          # Authentication routes
│   │   ├── chat.py          # Chat interface routes
│   │   ├── api.py           # REST API endpoints
│   │   ├── admin.py         # Admin panel routes
│   │   ├── landing.py       # Public/landing routes
│   │   └── sockets.py       # WebSocket event handlers
│   ├── utils/
│   │   ├── helpers.py       # Utility functions
│   │   ├── file_upload.py   # File upload (Cloudinary)
│   │   └── encryption.py    # E2EE utilities
│   ├── static/
│   │   ├── css/main.css     # Complete design system
│   │   ├── js/chat.js       # Full chat client
│   │   ├── js/app.js        # Global utilities
│   │   ├── sw.js            # Service worker (PWA)
│   │   └── manifest.json    # PWA manifest
│   └── templates/
│       ├── base.html        # Base layout
│       ├── auth/            # Login, register, profile
│       ├── chat/            # Main chat interface
│       ├── admin/           # Admin panel
│       ├── landing/         # Landing & CMS pages
│       ├── emails/          # Email templates
│       └── errors/          # Error pages
├── config.py                # Configuration classes
├── wsgi.py                  # WSGI entry point
├── manage.py                # CLI commands
├── requirements.txt         # Python dependencies
├── Procfile                 # Gunicorn config
├── render.yaml              # Render deployment
├── runtime.txt              # Python version
└── .env.example             # Environment template
```

---

## 🔑 Admin Panel Features

Access at: `/admin/login`

### Contact & Helpline Management
Go to **Settings → Contact** tab to update:
- 🆘 Helpline Number
- 📧 Support Email
- 📱 Support Phone
- ✉️ Contact Gmail
- 📍 Office Address
- 💬 WhatsApp Number

All changes reflect instantly on the public site — no code changes needed.

### Landing Page
Go to **Admin → Landing Page** to edit:
- Hero title and subtitle
- Features section
- Footer text

### CMS Pages
Go to **Admin → CMS Pages** to create/edit:
- Privacy Policy
- Terms of Service
- About page
- Contact page
- Custom pages with full WYSIWYG editor

---

## 🛠️ CLI Commands

```bash
# Create admin account interactively
flask create-admin

# Seed default data
flask seed-db

# Reset database (DANGEROUS)
flask reset-db

# Database migrations
flask db init
flask db migrate -m "description"
flask db upgrade
flask db downgrade
```

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + Flask 3.0 |
| Real-time | Flask-SocketIO + WebSockets |
| Database | PostgreSQL + SQLAlchemy |
| Auth | Flask-Login + JWT |
| Passwords | Argon2 (never plaintext) |
| File Storage | Cloudinary (with local fallback) |
| Email | Flask-Mail (SMTP) |
| Rate Limiting | Flask-Limiter |
| Security | Flask-Talisman + WTF CSRF |
| Deployment | Render + Gunicorn + Gevent |
| PWA | Service Worker + Web Manifest |
| Design | Custom CSS (Purple/Black/White) |
| Fonts | Syne + DM Sans (Google Fonts) |

---

## 📞 Support

- **Email:** Set in admin settings
- **Helpline:** Set in admin settings
- **Admin Panel:** `/admin/login`

---

## 📄 License

MIT License — free to use and modify.

---

*Built with ❤️ — Khandhars Chat*
