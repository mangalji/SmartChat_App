# SmartChat 🚀

A real-time AI-assisted chat application built with Django + Channels + Gemini AI.

---

## Tech Stack
- **Backend**: Python 3.12, Django 4.2, Django Channels 4, Daphne
- **Database**: MySQL
- **Auth**: Session-based, OTP via email (console backend)
- **AI**: Google Gemini 1.5 Flash
- **Frontend**: Django Templates, Bootstrap 5.3, Vanilla JS

---

## Features
- ✅ Custom user model (email login)
- ✅ OTP-based signup & login (5-min expiry, 30s resend cooldown)
- ✅ Real-time 1-on-1 chat (WebSockets)
- ✅ Group chat with admin controls
- ✅ Typing indicators + online presence
- ✅ Media sharing (images + files, 10 MB max, lightbox viewer)
- ✅ Media gallery per conversation
- ✅ AI Suggest Reply (Gemini, EN + HI)
- ✅ Standalone AI Assistant page
- ✅ Scheduler app skeleton (Phase 7)

---

## Setup

### 1. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure MySQL
```sql
CREATE DATABASE smartchat_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env — set DB_PASSWORD and GEMINI_API_KEY
```

### 5. Run migrations
```bash
python manage.py makemigrations accounts chat scheduler
python manage.py migrate
```

### 6. Create superuser
```bash
python manage.py createsuperuser
```

### 7. Run server
```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000

> **OTP appears in the terminal** (console email backend).

---

## Environment Variables (.env)

| Variable        | Description                        |
|-----------------|------------------------------------|
| `SECRET_KEY`    | Django secret key                  |
| `DEBUG`         | True for local dev                 |
| `DB_NAME`       | MySQL database name                |
| `DB_USER`       | MySQL username                     |
| `DB_PASSWORD`   | MySQL password                     |
| `DB_HOST`       | MySQL host (127.0.0.1)             |
| `DB_PORT`       | MySQL port (3306)                  |
| `GEMINI_API_KEY`| Google Gemini API key              |

---

## URL Structure

| URL                        | Page                        |
|----------------------------|-----------------------------|
| `/`                        | Redirect to chat            |
| `/accounts/signup/`        | Sign up                     |
| `/accounts/login/`         | Login                       |
| `/accounts/verify-otp/`    | OTP verification            |
| `/chat/`                   | Chat home                   |
| `/chat/dm/<id>/`           | 1-on-1 chat room            |
| `/chat/dm/<id>/media/`     | Shared media gallery        |
| `/chat/groups/`            | Group list                  |
| `/chat/groups/create/`     | Create group                |
| `/chat/groups/<id>/`       | Group chat room             |
| `/chat/groups/<id>/media/` | Group media gallery         |
| `/ai/`                     | AI Assistant                |
| `/admin/`                  | Django admin                |

---

## Project Structure

```
smartchat/
├── manage.py
├── requirements.txt
├── .env
├── smartchat/          # Project config
├── accounts/           # Auth (User, OTP)
├── chat/               # Chat + WebSockets
├── scheduler/          # Scheduled messages (Phase 7)
├── ai_assist/          # Gemini AI
├── templates/          # All HTML templates
├── static/             # CSS + JS
└── media/              # Uploaded files
```
