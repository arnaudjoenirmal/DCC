import sqlite3
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import subprocess

app = FastAPI()

# Define output resolutions and formats
RESOLUTIONS = {
    "1080p": "1920x1080",
    "720p": "1280x720",
    "480p": "854x480",
    "360p": "640x360"
}
FORMATS = ["mp4", "avi", "mkv", "webm"]

# Directory where converted videos are stored
OUTPUT_DIR = "converted_videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Mount static files for video streaming
app.mount("/videos", StaticFiles(directory=OUTPUT_DIR), name="videos")

# SQLite Database Setup
DB_PATH = "videos.db"

def init_db():
    """Initialize the SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            original_filename TEXT,
            converted_urls TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_to_db(video_id, original_filename, urls):
    """Save video metadata to SQLite"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO videos (id, original_filename, converted_urls) VALUES (?, ?, ?)", 
                   (video_id, original_filename, ",".join(urls)))
    conn.commit()
    conn.close()

def convert_video(input_path: str, output_name: str):
    """
    Converts a video to different resolutions and formats using FFmpeg.
    Returns a list of output file paths.
    """
    output_files = []
    for res_name, res_size in RESOLUTIONS.items():
        for fmt in FORMATS:
            output_filename = f"{output_name}_{res_name}.{fmt}"
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", f"scale={res_size}",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                output_path
            ]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if process.returncode != 0:
                raise Exception(f"Error converting video {output_filename}: {process.stderr.decode()}")
            output_files.append(output_path)
    return output_files

@app.post("/convert")
async def convert_endpoint(file: UploadFile = File(...)):
    """
    Upload a video file, convert it, save metadata in SQLite, 
    and return a unique ID with streaming URLs.
    """
    # Generate unique ID
    video_id = str(uuid.uuid4())
    
    # Save uploaded file temporarily
    file_ext = Path(file.filename).suffix
    input_filename = f"{video_id}{file_ext}"
    input_path = os.path.join(OUTPUT_DIR, input_filename)
    with open(input_path, "wb") as f:
        f.write(await file.read())

    try:
        output_files = convert_video(input_path, video_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)

    # Construct streaming URLs
    base_url = "http://ec2-35-183-105-115.ca-central-1.compute.amazonaws.com:8080"
    urls = [f"{base_url}/videos/{os.path.basename(filepath)}" for filepath in output_files]

    # Save to SQLite
    save_to_db(video_id, file.filename, urls)

    return {"video_id": video_id, "urls": urls}

@app.get("/video/{video_id}")
async def get_video_info(video_id: str):
    """
    Retrieve video details using the unique ID.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT original_filename, converted_urls FROM videos WHERE id = ?", (video_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        raise HTTPException(status_code=404, detail="Video not found")

    original_filename, urls = result
    return {"video_id": video_id, "original_filename": original_filename, "urls": urls.split(",")}
