from flask import Flask, request, jsonify, send_file
import os
import subprocess
from datetime import datetime

app = Flask(__name__)

BASE_DIR = "/Users/ulrichsame/Downloads/CITATIONSAFRICAINESAUTOVIDEOS"
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route('/generate', methods=['POST'])
def generate_video():
    image = request.files.get('image')
    voiceover = request.files.get('voiceover')
    subtitle = request.files.get('subtitle')

    if not image or not voiceover or not subtitle:
        return jsonify({"error": "Missing image, voiceover or subtitle"}), 400

    image_path = os.path.join(UPLOAD_DIR, "image.png")
    voice_path = os.path.join(UPLOAD_DIR, "voiceover.mp3")
    subtitle_path = os.path.join(UPLOAD_DIR, "subtitle.srt")

    image.save(image_path)
    voiceover.save(voice_path)
    subtitle.save(subtitle_path)

    output_file = f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_file)

    cmd = [
        "ffmpeg",
        "-loop", "1", "-t", "3", "-i", image_path,
        "-i", os.path.join(BASE_DIR, "template.mp4"),
        "-i", voice_path,
        "-i", os.path.join(BASE_DIR, "music.mp3"),
        "-sub_charenc", "UTF-8",
        "-i", subtitle_path,
        "-filter_complex",
        "[3:a]volume=0.1[musique_basse];"
        "[1:a]adelay=3000|3000[video_audio];"
        "[2:a][musique_basse][video_audio]amix=inputs=3:duration=longest:dropout_transition=2[mix_audio];"
        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p,"
        "fade=t=out:st=2.8:d=0.2[img_fade];"
        "[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p,"
        "fade=t=in:st=0:d=0.2[vid_fade];"
        "[img_fade][vid_fade]concat=n=2:v=1:a=0[base];"
        f"[base]subtitles='{subtitle_path}':force_style='FontName=Arial,FontSize=10,"
        "PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BorderStyle=1,Outline=2,"
        "Alignment=2,MarginV=50,TextTransform=Upper'[outv]",
        "-map", "[outv]",
        "-map", "[mix_audio]",
        "-t", "24",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-y", output_path
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        return jsonify({"error": "ffmpeg failed", "details": result.stderr.decode()}), 500

    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
