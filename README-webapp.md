# UCSD Podcast Transcriber - Web Interface

A modern web application for transcribing UCSD lecture podcasts using OpenAI Whisper.

![UCSD Colors](https://img.shields.io/badge/Navy-%23182B49-blue?style=flat-square)
![UCSD Gold](https://img.shields.io/badge/Gold-%23C69214-yellow?style=flat-square)

## Features

- Clean, modern web interface with UCSD branding
- Real-time progress tracking
- Multiple Whisper model options (tiny to large)
- Automatic hallucination cleanup
- Download transcripts as text files
- Handles UCSD's Kaltura streaming system

## Architecture

```
┌─────────────────────────────────────────┐
│         Frontend (HTML/Tailwind)       │
│  - URL input & model selection         │
│  - Progress bar & status display       │
│  - Download button                     │
└──────────────┬──────────────────────────┘
               │ REST API
┌──────────────▼──────────────────────────┐
│         Flask Backend (Python)          │
│  - Job queue & management              │
│  - Progress tracking                   │
│  - Transcript storage                  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│    ucsd_podcast_transcriber.py          │
│  - Selenium for video capture          │
│  - FFmpeg for audio download           │
│  - Whisper for transcription           │
│  - Hallucination cleanup               │
└─────────────────────────────────────────┘
```

## Prerequisites

Before running the web app, you need:

### 1. System Dependencies

**FFmpeg** (required for audio download):
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

**Google Chrome** (required for Selenium):
- The app uses headless Chrome to capture video streams
- Make sure Chrome is installed on your system

### 2. Python 3.8+

Check your Python version:
```bash
python3 --version
```

## Installation

### 1. Clone or download this repository

### 2. Install Python dependencies

```bash
pip install -r requirements-webapp.txt
```

This will install:
- `openai-whisper` - AI transcription model
- `selenium` - Browser automation
- `webdriver-manager` - Chrome driver management
- `Flask` - Web framework
- `flask-cors` - CORS support

### 3. Verify installation

```bash
python3 -c "import whisper; import selenium; import flask; print('All dependencies installed!')"
```

## Running the Web App

### Start the server

```bash
python3 app.py
```

You should see:
```
============================================================
🎓 UCSD Podcast Transcriber - Web Interface
============================================================

Starting Flask server...
Open your browser to: http://localhost:5000

Press Ctrl+C to stop the server
============================================================
```

### Access the web interface

Open your browser to:
```
http://localhost:5000
```

## Usage

1. **Paste URL**: Copy a UCSD podcast URL like:
   ```
   https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6
   ```

2. **Select Model**: Choose a Whisper model based on your needs:
   - **Tiny**: Fastest (~10-15 min/hour) - Good for quick tests
   - **Base**: Balanced (~20-30 min/hour) - Recommended
   - **Small**: Accurate (~45-60 min/hour) - Better quality
   - **Medium**: Very accurate (~2-3 hours/hour) - High quality
   - **Large**: Best quality (~4-6 hours/hour) - Highest quality

3. **Transcribe**: Click the "Transcribe" button

4. **Monitor Progress**: Watch real-time status updates:
   - Capturing video stream
   - Downloading audio
   - Transcribing audio
   - Cleaning up transcript

5. **Download**: Once complete, preview and download your transcript

## API Endpoints

The Flask backend provides a REST API:

### POST `/api/transcribe`
Start a new transcription job.

**Request:**
```json
{
  "url": "https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6",
  "model": "base"
}
```

**Response:**
```json
{
  "job_id": "uuid-string"
}
```

### GET `/api/status/<job_id>`
Get the status of a transcription job.

**Response:**
```json
{
  "job_id": "uuid-string",
  "status": "transcribing",
  "progress": 65,
  "eta_minutes": 12,
  "transcript_preview": null,
  "error": null
}
```

**Status values:**
- `queued` - Job is waiting to start
- `capturing` - Capturing video stream
- `downloading` - Downloading audio
- `transcribing` - Transcribing audio with Whisper
- `cleaning` - Cleaning up hallucinations
- `complete` - Job finished successfully
- `error` - Job failed (check `error` field)

### GET `/api/download/<job_id>`
Download the transcript file.

**Response:** Plain text file

### GET `/api/transcript/<job_id>`
Get the full transcript as JSON.

**Response:**
```json
{
  "job_id": "uuid-string",
  "transcript": "Full transcript text...",
  "url": "https://podcast.ucsd.edu/...",
  "model": "base"
}
```

## File Structure

```
ucsd-podcast-transcriber/
├── app.py                          # Flask backend server
├── ucsd_podcast_transcriber.py     # Core transcription logic
├── requirements-webapp.txt         # Python dependencies
├── static/
│   └── index.html                  # Frontend UI
├── transcripts/                    # Saved transcripts (created automatically)
├── audio_temp/                     # Temporary audio files (created automatically)
└── README-webapp.md                # This file
```

## How It Works

### 1. Video Stream Capture
- Uses Selenium with headless Chrome to load the UCSD podcast page
- Monitors network requests to capture the m3u8 video stream URL
- Handles UCSD's Kaltura streaming system

### 2. Audio Download
- Uses FFmpeg to download audio from the m3u8 stream
- Converts to MP3 format for efficient processing

### 3. Transcription
- Loads the selected Whisper model
- Transcribes the audio file
- First-time model downloads may take a few minutes

### 4. Cleanup
- Removes Whisper hallucinations (gibberish at start/end)
- Identifies lecture start/end patterns
- Removes repetitive phrases like "Thank you. Thank you. Thank you."
- Removes non-English text that appears during silence

## Troubleshooting

### "FFmpeg not found"
Install FFmpeg using the instructions in Prerequisites.

### "Chrome driver failed"
Make sure Google Chrome is installed and up to date.

### "Could not find video stream URL"
- Check if the podcast URL is correct
- The video might require UCSD authentication
- Try logging into UCSD in your browser first

### Transcription is slow
- Use a smaller model (tiny or base)
- Make sure you have adequate RAM
- GPU acceleration will speed up transcription significantly

### "Missing Python dependencies"
Run:
```bash
pip install -r requirements-webapp.txt
```

## Production Deployment

For production use, consider:

1. **Use a production WSGI server** instead of Flask's development server:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

2. **Use Redis for job storage** instead of in-memory storage:
   - Install Redis
   - Modify `app.py` to use Redis for the `jobs` dictionary

3. **Add authentication** to protect the API

4. **Set up HTTPS** for secure communication

5. **Use a task queue** like Celery for better job management

## UCSD Brand Guidelines

The interface uses official UCSD colors:
- **Navy**: #182B49
- **Gold**: #C69214
- **Light Blue**: #006A96

## License

This tool is for educational purposes. Please respect UCSD's content policies when using it.

## Credits

- Built with [OpenAI Whisper](https://github.com/openai/whisper)
- Uses [Flask](https://flask.palletsprojects.com/) for the web framework
- Styled with [Tailwind CSS](https://tailwindcss.com/)
