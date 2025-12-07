# Quick Deployment Guide - 5 Minutes to Live!

## Fastest Path: Deploy to Render.com (FREE)

### Step 1: Prepare Your Code (2 minutes)

1. **Apply production updates to app.py:**
   - Read and apply changes from `app_production_updates.md`
   - Or run this quick script:

```bash
python -c "import secrets; print('Your secret key:', secrets.token_hex(32))"
```

Save that key for later!

2. **Create .env file** (copy from .env.example):
```
FLASK_SECRET_KEY=<paste-your-secret-key-here>
FLASK_ENV=production
```

### Step 2: Push to GitHub (1 minute)

```bash
git init
git add .
git commit -m "Ready for deployment"
```

Then:
- Go to github.com
- Create new repository "peerpulse"
- Follow the instructions to push your code

### Step 3: Deploy to Render (2 minutes)

1. Go to [render.com](https://render.com) - Sign up with GitHub
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Fill in:
   - **Name:** peerpulse
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn wsgi:app`
5. Click **"Advanced"** and add environment variables:
   - `FLASK_SECRET_KEY`: (your generated secret key)
   - `FLASK_ENV`: `production`
6. Click **"Create Web Service"**

**Done!** Your site will be live at `https://peerpulse.onrender.com` in ~5 minutes.

---

## Important Notes

- **Free tier sleeps after 15 mins of inactivity** (wakes up on first request)
- **Upgrade to paid ($7/month)** for always-on service
- **Database:** Your SQLite database will persist on Render

---

## After Deployment

1. **Visit your site** and test it
2. **Create your first user** (will be admin)
3. **Set up backups** (see DEPLOYMENT_GUIDE.md)

---

## Need a Custom Domain?

1. Buy domain from Namecheap/Google Domains
2. In Render, go to Settings → Custom Domains
3. Add your domain and follow DNS instructions
4. SSL certificate is automatic!

---

## Troubleshooting

**Site not loading?**
- Check Render logs (Logs tab in dashboard)
- Verify environment variables are set
- Check that app.py has production updates applied

**Database empty?**
- Upload your existing `ratings.db` file
- Or let it create a new database

**Need help?**
- Read full guide: `DEPLOYMENT_GUIDE.md`
- Check Render docs: https://render.com/docs

---

That's it! You're live! 🎉
