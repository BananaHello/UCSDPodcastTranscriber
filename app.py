#!/usr/bin/env python3
"""
Flask backend for UCSD Podcast Transcriber Web App
"""

import os
import sys
import uuid
import threading
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import the transcriber functions
from ucsd_podcast_transcriber import (
    transcribe_podcast,
    check_dependencies,
    download_audio,
    transcribe_audio,
    clean_transcript,
    save_transcript
)

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Store job status in memory (in production, use Redis or database)
jobs = {}
transcripts = {}

# Create output directory for transcripts
OUTPUT_DIR = Path("transcripts")
OUTPUT_DIR.mkdir(exist_ok=True)

AUDIO_DIR = Path("audio_temp")
AUDIO_DIR.mkdir(exist_ok=True)


class TranscriptionJob:
    """Represents a transcription job with progress tracking."""

    def __init__(self, job_id, url, model, output_folder=None):
        self.job_id = job_id
        self.url = url
        self.model = model
        self.output_folder = output_folder  # Custom output folder path
        self.status = "queued"  # queued, capturing, downloading, transcribing, cleaning, complete, error
        self.progress = 0  # 0-100
        self.eta_minutes = None
        self.error = None
        self.transcript_path = None
        self.transcript_preview = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None

    def to_dict(self):
        """Convert job to dictionary for JSON response."""
        return {
            "job_id": self.job_id,
            "url": self.url,
            "model": self.model,
            "status": self.status,
            "progress": self.progress,
            "eta_minutes": self.eta_minutes,
            "error": self.error,
            "transcript_preview": self.transcript_preview,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def estimate_time(model, audio_duration_minutes=60):
    """
    Estimate transcription time based on model.
    Returns minutes per hour of audio.
    """
    estimates = {
        "tiny": 12.5,    # 10-15 min per hour
        "base": 25,      # 20-30 min per hour
        "small": 52.5,   # 45-60 min per hour
        "medium": 150,   # 2-3 hours per hour
        "large": 300     # 4-6 hours per hour
    }
    return estimates.get(model, 25)


def run_transcription(job_id):
    """
    Run the transcription in a background thread.
    Updates job status throughout the process.
    """
    job = jobs.get(job_id)
    if not job:
        return

    try:
        job.started_at = datetime.now()
        job.status = "capturing"
        job.progress = 5

        # Step 1: Download audio
        job.status = "downloading"
        job.progress = 10
        job.eta_minutes = estimate_time(job.model)

        audio_path = download_audio(job.url, str(AUDIO_DIR))

        job.progress = 30

        # Step 2: Transcribe
        job.status = "transcribing"
        job.progress = 40

        transcript = transcribe_audio(audio_path, job.model)

        job.progress = 80

        # Step 3: Clean transcript
        job.status = "cleaning"
        job.progress = 85

        transcript = clean_transcript(transcript)

        # Step 4: Save transcript
        job.progress = 90
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"transcript_{timestamp}_{job_id[:8]}.txt"

        # Use custom output folder if specified, otherwise use default
        if job.output_folder:
            output_dir = Path(job.output_folder)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / output_filename
            print(f"[DEBUG] Saving transcript to custom folder: {output_path}", file=sys.stderr)
        else:
            output_path = OUTPUT_DIR / output_filename
            print(f"[DEBUG] Saving transcript to default folder: {output_path}", file=sys.stderr)

        save_transcript(transcript, str(output_path))
        print(f"[DEBUG] Transcript successfully saved to: {output_path}", file=sys.stderr)

        # Clean up audio file
        try:
            os.remove(audio_path)
        except:
            pass

        # Store results
        job.status = "complete"
        job.progress = 100
        job.eta_minutes = 0
        job.transcript_path = str(output_path)
        job.transcript_preview = transcript[:500] if len(transcript) > 500 else transcript
        job.completed_at = datetime.now()

        # Cache the full transcript
        transcripts[job_id] = transcript

    except Exception as e:
        job.status = "error"
        job.error = str(e)
        job.progress = 0
        print(f"Error in transcription job {job_id}: {e}", file=sys.stderr)


@app.route('/')
def index():
    """Serve the main HTML page."""
    return send_from_directory('static', 'index.html')


@app.route('/api/check-dependencies', methods=['GET'])
def api_check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        check_dependencies()
        return jsonify({"status": "ok", "message": "All dependencies are installed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/transcribe', methods=['POST'])
def api_transcribe():
    """
    Start a new transcription job.

    Request body:
    {
        "url": "https://podcast.ucsd.edu/...",
        "model": "base",  # optional, defaults to "base"
        "output_folder": "/path/to/folder"  # optional, custom output folder
    }

    Returns:
    {
        "job_id": "uuid"
    }
    """
    data = request.get_json()

    if not data or 'url' not in data:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    url = data['url']
    model = data.get('model', 'base')
    output_folder = data.get('output_folder', '').strip()

    # Validate model
    valid_models = ['tiny', 'base', 'small', 'medium', 'large']
    if model not in valid_models:
        return jsonify({"error": f"Invalid model. Must be one of: {', '.join(valid_models)}"}), 400

    # Validate URL
    if not url.startswith('http'):
        return jsonify({"error": "Invalid URL format"}), 400

    # Validate output folder if provided
    if output_folder:
        try:
            # Expand user path (e.g., ~/Documents becomes /home/user/Documents)
            output_folder = os.path.expanduser(output_folder)
            # Validate that the path is safe (basic check)
            output_folder_path = Path(output_folder).resolve()
            # Create directory if it doesn't exist to verify we have permissions
            output_folder_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return jsonify({"error": f"Invalid output folder: {str(e)}"}), 400
    else:
        output_folder = None

    # Create job
    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id, url, model, output_folder)
    jobs[job_id] = job

    # Start transcription in background thread
    thread = threading.Thread(target=run_transcription, args=(job_id,))
    thread.daemon = True
    thread.start()

    return jsonify({"job_id": job_id})


@app.route('/api/status/<job_id>', methods=['GET'])
def api_status(job_id):
    """
    Get the status of a transcription job.

    Returns:
    {
        "status": "queued|capturing|downloading|transcribing|cleaning|complete|error",
        "progress": 0-100,
        "eta_minutes": 15,
        "transcript_preview": "...",
        "error": "error message if failed"
    }
    """
    job = jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(job.to_dict())


@app.route('/api/download/<job_id>', methods=['GET'])
def api_download(job_id):
    """
    Download the transcript file.
    """
    job = jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status != "complete":
        return jsonify({"error": "Transcription not complete yet"}), 400

    if not job.transcript_path or not os.path.exists(job.transcript_path):
        return jsonify({"error": "Transcript file not found"}), 404

    return send_file(
        job.transcript_path,
        as_attachment=True,
        download_name=f"transcript_{job_id[:8]}.txt",
        mimetype='text/plain'
    )


@app.route('/api/transcript/<job_id>', methods=['GET'])
def api_get_transcript(job_id):
    """
    Get the full transcript text as JSON.
    """
    job = jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status != "complete":
        return jsonify({"error": "Transcription not complete yet"}), 400

    transcript = transcripts.get(job_id)

    if not transcript:
        # Try to read from file
        if job.transcript_path and os.path.exists(job.transcript_path):
            with open(job.transcript_path, 'r', encoding='utf-8') as f:
                transcript = f.read()
                transcripts[job_id] = transcript
        else:
            return jsonify({"error": "Transcript not found"}), 404

    return jsonify({
        "job_id": job_id,
        "transcript": transcript,
        "url": job.url,
        "model": job.model
    })


@app.route('/api/jobs', methods=['GET'])
def api_list_jobs():
    """
    List all jobs (for debugging/admin).
    """
    return jsonify({
        "jobs": [job.to_dict() for job in jobs.values()]
    })


@app.route('/api/browse-folders', methods=['POST'])
def api_browse_folders():
    """
    Browse folders on the local file system.

    Request body:
    {
        "path": "/path/to/directory"  # optional, defaults to user home
    }

    Returns:
    {
        "current_path": "/current/path",
        "parent_path": "/parent/path",
        "folders": [{"name": "folder1", "path": "/path/to/folder1"}, ...]
    }
    """
    data = request.get_json() or {}
    requested_path = data.get('path', '').strip()

    # Default to user's home directory
    if not requested_path:
        requested_path = str(Path.home())
    else:
        # Expand user path
        requested_path = os.path.expanduser(requested_path)

    try:
        current_path = Path(requested_path).resolve()

        # Security check: ensure path exists and is a directory
        if not current_path.exists():
            return jsonify({"error": "Path does not exist"}), 400

        if not current_path.is_dir():
            return jsonify({"error": "Path is not a directory"}), 400

        # Get parent path
        parent_path = str(current_path.parent) if current_path.parent != current_path else None

        # List folders in current directory
        folders = []
        try:
            for item in sorted(current_path.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    folders.append({
                        "name": item.name,
                        "path": str(item)
                    })
        except PermissionError:
            return jsonify({"error": "Permission denied to read this directory"}), 403

        # Add common locations for quick access
        quick_access = []
        home = Path.home()
        common_folders = ['Documents', 'Desktop', 'Downloads']
        for folder_name in common_folders:
            folder_path = home / folder_name
            if folder_path.exists() and folder_path.is_dir():
                quick_access.append({
                    "name": folder_name,
                    "path": str(folder_path)
                })

        return jsonify({
            "current_path": str(current_path),
            "parent_path": parent_path,
            "folders": folders,
            "quick_access": quick_access
        })

    except Exception as e:
        return jsonify({"error": f"Error browsing folders: {str(e)}"}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("🎓 UCSD Podcast Transcriber - Web Interface")
    print("=" * 60)
    print()
    print("Starting Flask server...")
    print("Open your browser to: http://localhost:8080")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    print()

    app.run(debug=True, host='0.0.0.0', port=8080, threaded=True)
