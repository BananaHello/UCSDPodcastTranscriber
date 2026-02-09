# Quick Start Guide

## One-Command Startup 🚀

From anywhere, just run:

```bash
cd "/Users/atjon/Desktop/Code/projects/Transcription Tool" && ./start-webapp.sh
```

Or if you're already in the directory:

```bash
./start-webapp.sh
```

That's it! The script will:
1. ✅ Navigate to the correct directory
2. ✅ Activate your virtual environment (venv-webapp)
3. ✅ Start the Flask server on port 8080

Then open your browser to: **http://localhost:8080**

---

## Manual Startup (if needed)

If you prefer to do it step-by-step:

### Step 1: Navigate to the project
```bash
cd "/Users/atjon/Desktop/Code/projects/Transcription Tool"
```

### Step 2: Activate virtual environment
```bash
source venv-webapp/bin/activate
```

### Step 3: Run the app
```bash
python3 app.py
```

### Step 4: Open browser
Go to: **http://localhost:8080**

---

## Stopping the Server

Press `Ctrl+C` in the terminal to stop the server.

---

## First Time Setup

Only needed once:

```bash
cd "/Users/atjon/Desktop/Code/projects/Transcription Tool"
python3 -m venv venv-webapp
source venv-webapp/bin/activate
pip install -r requirements-webapp.txt
```

After that, just use `./start-webapp.sh` every time!

---

## Troubleshooting

**"Port already in use"**: The app uses port 8080. If it's taken, edit `app.py` line 322 to use a different port.

**"Permission denied"**: Run `chmod +x start-webapp.sh` to make the script executable.

**"Module not found"**: Make sure you're in the virtual environment and run `pip install -r requirements-webapp.txt`
