# Required Updates to app.py for Production

Apply these changes to your `app.py` before deploying:

## 1. Add environment variable support (at the top of app.py, after imports)

```python
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
```

## 2. Update secret key (replace line 26)

**Current:**
```python
app.secret_key = 'your-secret-key-change-in-production'
```

**Replace with:**
```python
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production')
```

## 3. Update debug mode (replace line 1964)

**Current:**
```python
if __name__ == '__main__':
    app.run(debug=True)
```

**Replace with:**
```python
if __name__ == '__main__':
    # Debug mode OFF in production
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug_mode, host='0.0.0.0')
```

## 4. Optional: Add HTTPS enforcement (add after app initialization)

```python
@app.before_request
def enforce_https():
    """Redirect HTTP to HTTPS in production"""
    if os.environ.get('FORCE_HTTPS') == '1':
        if not request.is_secure and not request.headers.get('X-Forwarded-Proto') == 'https':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)
```

## 5. Optional: Add security headers (add after app initialization)

```python
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if os.environ.get('FORCE_HTTPS') == '1':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response
```

---

## Complete Example of Changes

Here's what the top of your app.py should look like:

```python
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from database import *
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production')

@app.before_request
def enforce_https():
    """Redirect HTTP to HTTPS in production"""
    if os.environ.get('FORCE_HTTPS') == '1':
        if not request.is_secure and not request.headers.get('X-Forwarded-Proto') == 'https':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if os.environ.get('FORCE_HTTPS') == '1':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ... rest of your routes ...
```

And at the bottom:

```python
if __name__ == '__main__':
    # Debug mode OFF in production
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug_mode, host='0.0.0.0')
```

---

## Generate Secret Key

Run this to generate a secure secret key:

```python
import secrets
print(secrets.token_hex(32))
```

Copy the output and use it as your `FLASK_SECRET_KEY` environment variable in production.
