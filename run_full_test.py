from app import app
from flask import session

# Quick smoke test for full() rendering with default sort and with q filter
with app.test_request_context('/full'):
    # simulate logged-in user
    session['user_id'] = 1
    session['username'] = 'admin'
    resp = app.view_functions['full']()
    print('Rendered /full (default):', isinstance(resp, str) or hasattr(resp, 'data'))

with app.test_request_context('/full?q=claire'):
    session['user_id'] = 1
    session['username'] = 'admin'
    resp = app.view_functions['full']()
    print('Rendered /full?q=claire:', isinstance(resp, str) or hasattr(resp, 'data'))
