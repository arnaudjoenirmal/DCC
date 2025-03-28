from fastapi import FastAPI, File, UploadFile
import os
import subprocess
from pathlib import Path

app = FastAPI()

# Output resolutions and formats
RESOLUTIONS = {
    "1080p": "1920x1080",
    "720p": "1280x720",
    "480p": "854x480",
    "360p": "640x360"
}
FORMATS = ["mp4", "avi", "mkv", "webm"]

# Create an output directory
OUTPUT_DIR = "converted_videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def convert_video(input_path: str, output_name: str):
    """
    Converts a video to different resolutions and formats using FFmpeg.
    Returns a list of output file paths.
    """
    output_files = []
    for res_name, res_size in RESOLUTIONS.items():
        for fmt in FORMATS:
            output_path = f"{OUTPUT_DIR}/{output_name}_{res_name}.{fmt}"
            cmd = [
                "ffmpeg", "-i", input_path,
                "-vf", f"scale={res_size}",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                output_path
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output_files.append(output_path)
    return output_files

@app.post("/convert")
async def upload_video(file: UploadFile = File(...)):
    """
    API endpoint to upload a video and convert it to multiple resolutions and formats.
    """
    input_path = f"{OUTPUT_DIR}/{file.filename}"
    
    # Save input file
    with open(input_path, "wb") as f:
        f.write(await file.read())

    # Convert video
    output_files = convert_video(input_path, Path(file.filename).stem)

    return {"message": "Conversion complete", "files": output_files}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
