# Deployment Guide for PeerPulse

This guide covers deploying your Flask application to production.

## Pre-Deployment Checklist

### 1. Update app.py for Production

**CRITICAL:** Add these changes to your `app.py`:

```python
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Change this line:
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production')

# At the bottom, change debug mode:
if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_ENV') != 'production')
```

### 2. Security Updates Needed

**Important security changes to make:**

1. **Generate a secure secret key:**
   ```python
   import secrets
   print(secrets.token_hex(32))
   ```
   Use this output as your `FLASK_SECRET_KEY` in production.

2. **Add HTTPS enforcement** (optional but recommended):
   ```python
   @app.before_request
   def enforce_https():
       if os.environ.get('FORCE_HTTPS') == '1' and not request.is_secure:
           url = request.url.replace('http://', 'https://', 1)
           return redirect(url, code=301)
   ```

3. **Add rate limiting** to prevent abuse (install `flask-limiter`):
   ```python
   from flask_limiter import Limiter
   from flask_limiter.util import get_remote_address

   limiter = Limiter(
       app=app,
       key_func=get_remote_address,
       default_limits=["200 per day", "50 per hour"]
   )
   ```

### 3. Database Considerations

Your app uses SQLite, which works for small-to-medium traffic. For production:

**Option A: Keep SQLite (Simple)**
- Works fine for < 100 concurrent users
- Make sure to backup `ratings.db` regularly
- Consider adding a backup script

**Option B: Migrate to PostgreSQL (Recommended for scale)**
- Better for concurrent users
- Most hosting platforms support it
- Requires code changes to use PostgreSQL instead of SQLite

---

## Deployment Options

### Option 1: Render (Recommended - Easy & Free Tier)

**Pros:** Free tier, automatic deployments, easy setup
**Cons:** Free tier spins down after inactivity

**Steps:**

1. Create a Git repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. Push to GitHub:
   - Create a new repository on GitHub
   - Follow GitHub's instructions to push your code

3. Deploy on Render:
   - Go to [render.com](https://render.com)
   - Sign up with GitHub
   - Click "New +" → "Web Service"
   - Connect your repository
   - Configure:
     - **Name:** peerpulse (or your preferred name)
     - **Environment:** Python 3
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `gunicorn wsgi:app`
   - Add environment variables:
     - `FLASK_SECRET_KEY`: (your generated secret key)
     - `FLASK_ENV`: production
   - Click "Create Web Service"

4. Access your site at: `https://your-app-name.onrender.com`

---

### Option 2: Heroku (Easy but paid)

**Pros:** Reliable, easy deployment
**Cons:** No longer has free tier ($7/month minimum)

**Steps:**

1. Install Heroku CLI: [Download here](https://devcenter.heroku.com/articles/heroku-cli)

2. Login and create app:
   ```bash
   heroku login
   heroku create your-app-name
   ```

3. Set environment variables:
   ```bash
   heroku config:set FLASK_SECRET_KEY=your-secret-key
   heroku config:set FLASK_ENV=production
   ```

4. Deploy:
   ```bash
   git push heroku main
   ```

5. Access your site at: `https://your-app-name.herokuapp.com`

---

### Option 3: PythonAnywhere (Easiest, Free Tier Available)

**Pros:** Free tier with custom domain support, beginner-friendly
**Cons:** Limited resources on free tier

**Steps:**

1. Sign up at [pythonanywhere.com](https://www.pythonanywhere.com)

2. Upload your code:
   - Use "Files" tab to upload your project folder
   - Or use Git to clone your repository

3. Create a virtual environment:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 peerpulse
   pip install -r requirements.txt
   ```

4. Configure web app:
   - Go to "Web" tab → "Add a new web app"
   - Choose "Manual configuration" → Python 3.10
   - Set source code directory: `/home/yourusername/RatingsProject`
   - Edit WSGI configuration file to:
   ```python
   import sys
   path = '/home/yourusername/RatingsProject'
   if path not in sys.path:
       sys.path.append(path)

   from wsgi import app as application
   ```

5. Set environment variables:
   - Go to "Files" → Edit `.env` file
   - Add your environment variables

6. Reload web app and access at: `https://yourusername.pythonanywhere.com`

---

### Option 4: VPS (DigitalOcean, Linode) - Advanced

**Pros:** Full control, better performance
**Cons:** Requires Linux knowledge, more setup

**Steps (Ubuntu 22.04):**

1. Create a VPS and SSH in

2. Install dependencies:
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv nginx
   ```

3. Clone your repository:
   ```bash
   git clone https://github.com/yourusername/your-repo.git
   cd your-repo
   ```

4. Set up virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. Configure Gunicorn service (`/etc/systemd/system/peerpulse.service`):
   ```ini
   [Unit]
   Description=PeerPulse Flask App
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/path/to/your/app
   Environment="PATH=/path/to/your/app/venv/bin"
   ExecStart=/path/to/your/app/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:8000 wsgi:app

   [Install]
   WantedBy=multi-user.target
   ```

6. Configure Nginx (`/etc/nginx/sites-available/peerpulse`):
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }

       location /static {
           alias /path/to/your/app/static;
       }
   }
   ```

7. Enable and start services:
   ```bash
   sudo systemctl enable peerpulse
   sudo systemctl start peerpulse
   sudo systemctl enable nginx
   sudo systemctl start nginx
   ```

8. Set up SSL with Let's Encrypt:
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

---

## Post-Deployment Steps

### 1. Database Setup

On first deployment, you need to initialize the database:
- Upload your existing `ratings.db` file, OR
- Let the app create a new database automatically

### 2. Set Up Backups

**For SQLite:**
```bash
# Daily backup script
cp ratings.db backups/ratings-$(date +%Y%m%d).db
```

**For cloud platforms:**
- Use their backup features
- Or use cron jobs to backup to cloud storage

### 3. Monitor Your Application

- Set up error logging (consider Sentry.io)
- Monitor uptime (UptimeRobot.com)
- Check resource usage regularly

### 4. Custom Domain (Optional)

Most platforms allow custom domains:
1. Buy a domain (Namecheap, Google Domains, etc.)
2. Point DNS to your hosting platform
3. Configure SSL certificate

---

## Important Files Created

- **wsgi.py** - WSGI entry point for production servers
- **Procfile** - Heroku/Render deployment configuration
- **.env.example** - Template for environment variables
- **requirements.txt** - Updated with production dependencies

---

## Common Issues & Solutions

### Issue: Database locked errors
**Solution:** SQLite doesn't handle many concurrent writes well. Migrate to PostgreSQL.

### Issue: Static files not loading
**Solution:** Configure your web server to serve `/static` directory directly.

### Issue: App is slow
**Solution:**
- Add caching (Flask-Caching)
- Use CDN for static files
- Optimize database queries
- Consider upgrading hosting plan

### Issue: Database lost after deployment
**Solution:**
- SQLite databases need to be persisted
- Use platform's persistent storage
- Or migrate to hosted database (PostgreSQL)

---

## Security Checklist

- [ ] Secret key is random and secure
- [ ] Debug mode is OFF in production
- [ ] HTTPS is enforced
- [ ] Rate limiting is enabled
- [ ] Database backups are configured
- [ ] Environment variables are set (not hardcoded)
- [ ] `.env` file is in `.gitignore`
- [ ] SQL injection prevention is in place (using parameterized queries)
- [ ] XSS protection is enabled
- [ ] CSRF tokens are used for forms

---

## Quick Start (Render.com - Recommended)

1. Create account at render.com
2. Connect your GitHub repository
3. Create a new Web Service
4. Set environment variables:
   - `FLASK_SECRET_KEY`: (generate with `secrets.token_hex(32)`)
   - `FLASK_ENV`: production
5. Deploy!

**That's it!** Your app will be live at `https://your-app.onrender.com`

---

## Need Help?

- Check platform documentation
- Flask deployment guide: https://flask.palletsprojects.com/en/stable/deploying/
- Community: Reddit r/flask, Stack Overflow

Good luck with your deployment! 🚀
