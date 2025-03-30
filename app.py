from flask import Flask, request, jsonify, send_file
import os
import subprocess
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Dossiers pour stocker les fichiers
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
TRANSITION_DIR = "videos_transition"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TRANSITION_DIR, exist_ok=True)

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
        "-i", "template.mp4",
        "-i", voice_path,
        "-i", "music.mp3",
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
        "-crf", "28",            # qualité un peu réduite pour alléger
        "-vsync", "vfr",         # évite l’excès de frames
        "-r", "24",              # framerate plus raisonnable
        "-c:a", "aac",
        "-b:a", "192k",
        "-y", output_path
    ]

    print("Running ffmpeg for /generate...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("FFmpeg stderr:", result.stderr.decode())

    if result.returncode != 0:
        return jsonify({"error": "ffmpeg failed", "details": result.stderr.decode()}), 500

    return send_file(output_path, as_attachment=True)

@app.route('/generatetransition', methods=['POST'])
def generate_transition():
    for f in os.listdir(TRANSITION_DIR):
        os.remove(os.path.join(TRANSITION_DIR, f))

    filenames = []
    for i, f in enumerate(request.files.getlist('videos')):
        filename = secure_filename(f"video{i}.mp4")
        path = os.path.join(TRANSITION_DIR, filename)
        f.save(path)
        filenames.append(path)

    if len(filenames) < 2:
        return jsonify({'error': 'At least 2 videos are required'}), 400

    inputs = " ".join(f"-i {f}" for f in filenames)

    filter_parts = []
    for i in range(len(filenames) - 1):
        filter_parts.append(
            f"[{i}:v][{i}:a][{i+1}:v][{i+1}:a]xfade=transition=fade:duration=0.5:offset={i * 4}[v{i+1}a{i+1}]"
        )
    filter_complex = ";".join(filter_parts)
    last = f"v{len(filenames)-1}a{len(filenames)-1}"

    output_file = f"output_transition_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_file)

    cmd = f"""
    ffmpeg {inputs} -filter_complex "{filter_complex}" \
    -map "[{last}:v]" -map "[{last}:a]" -c:v libx264 -c:a aac -b:a 192k -preset veryfast -vsync vfr -r 24 -crf 28 -y "{output_path}"
    """

    print("Running ffmpeg for /generatetransition...")
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("FFmpeg stderr:", result.stderr.decode())

    if result.returncode != 0:
        return jsonify({"error": "transition ffmpeg failed", "details": result.stderr.decode()}), 500

    return send_file(output_path, as_attachment=True)

# Optionnel pour Render
@app.route('/healthz')
def health_check():
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
