# Vercel Deployment Guide

## What Was Added

### 1. `app.py` (Root Level)
- **Location**: `c:\DSProject\app.py`
- **Purpose**: Vercel entry point - Flask app that Vercel can discover
- **Content**: Imports the Flask app from `src/app.py`
- **Why Needed**: Vercel looks for Flask apps in root directory or specific locations

### 2. `vercel.json` (Configuration)
- **Location**: `c:\DSProject\vercel.json`
- **Purpose**: Vercel build and deployment configuration
- **Specifies**:
  - Build command: Install dependencies from `requirements.txt`
  - Framework: Flask
  - Rewrites: All requests route to the Flask app
  - Environment: Python unbuffered output

### 3. `.vercelignore` (Ignore File)
- **Location**: `c:\DSProject\.vercelignore`
- **Purpose**: Tell Vercel which files NOT to deploy
- **Excludes**: Cache, tests, notebooks, IDE files
- **Keeps**: Data files and models (needed for the app)

---

## Deployment Steps

### 1. Connect to Vercel
```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Deploy from project root
cd c:\DSProject
vercel
```

### 2. GitHub Integration (Recommended)
1. Push changes to GitHub
2. Connect GitHub repo to Vercel dashboard
3. Vercel auto-deploys on every push to `main`

### 3. Environment Variables (if needed)
Add to Vercel dashboard under project settings:
```
FLASK_ENV=production
PYTHONUNBUFFERED=1
```

---

## Project Structure for Vercel

```
DSProject/                          (root)
├── app.py                          ← Vercel entry point (NEW)
├── vercel.json                     ← Vercel config (NEW)
├── .vercelignore                   ← Ignore rules (NEW)
├── requirements.txt
├── src/
│   ├── app.py                      ← Your Flask app
│   ├── seir_model.py
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── css/
│       ├── js/
│       └── india_states.geojson
├── data/                           ← Data files (will be deployed)
├── models/                         ← ML models (will be deployed)
└── tests/
```

---

## How It Works

### Local Development
```bash
python app.py              # Runs from root
# or
python src/app.py          # Runs from src
```

### Vercel Deployment
```
1. Vercel clones your GitHub repo
2. Installs dependencies: pip install -r requirements.txt
3. Starts Flask app from app.py
4. Routes all requests to Flask
5. Your app is live at: https://your-project.vercel.app
```

---

## Error Resolution

### Before (Error)
```
Error: No flask entrypoint found. Define a valid application 
entrypoint in one of the following locations: app.py, src/app.py, ...
```

### Why It Failed
- Vercel looks for Flask app in root directory
- Your app was at `src/app.py`
- Vercel couldn't find it

### After (Fixed) ✅
- Root `app.py` imports from `src/app.py`
- Vercel finds the entry point
- Deployment succeeds

---

## Testing Locally

```bash
# Test root-level app works
cd c:\DSProject
python -c "from app import app; print('✓ Works')"

# Run the app
python app.py

# Visit http://localhost:5000
```

---

## Vercel Dashboard

1. Go to https://vercel.com/dashboard
2. Click "Add New" → "Project"
3. Import your GitHub repo
4. Vercel auto-detects Flask
5. Click "Deploy"

---

## Troubleshooting

### If deployment still fails
1. Check `requirements.txt` has all dependencies
2. Verify `vercel.json` is valid JSON
3. Ensure `.vercelignore` isn't excluding needed files
4. Check Vercel build logs for specific errors

### Common Issues
- **Missing dependencies**: Add to `requirements.txt`
- **Data not found**: Make sure `data/` and `models/` are in repo
- **Port issues**: Vercel automatically assigns ports (don't hardcode)

---

## Live Deployment Example

```
Your app will be available at:
https://disease-prediction-[random].vercel.app

API endpoints:
- GET  /                         → Main page
- POST /api/predict              → Risk prediction
- GET  /mobility-trends/<state>  → Mobility data
```

---

**Status**: ✅ Ready for Vercel deployment  
**Last Updated**: November 16, 2025
