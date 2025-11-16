"""
Root-level Flask app entrypoint for Vercel deployment.

This imports the Flask app from src/app.py to make it discoverable by Vercel.
Vercel looks for the app in standard locations including the root app.py.
"""

from src.app import app

if __name__ == '__main__':
    app.run(debug=True)
