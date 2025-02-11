import os
import tempfile
from flask import Flask, request, render_template_string, send_file, redirect, url_for, flash, after_this_request
import yt_dlp

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change to a more secure key in production

# Use the system temporary directory so files are not stored permanently.
DOWNLOAD_FOLDER = tempfile.gettempdir()

# HTML template with multiple stages:
# - stage="input": Input URL and select download format.
# - stage="choose_video": Display video info and a dropdown for available resolutions.
# - stage="choose_mp3": Display video info to confirm MP3 download.
# - stage="download": Display the download link when the file is ready.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YouTube Downloader</title>
  <!-- Bootstrap CSS -->
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { background-color: #f8f9fa; }
    .container { margin-top: 50px; max-width: 600px; }
    .card { margin-top: 20px; }
    .video-thumbnail { max-width: 100%; height: auto; }
    .back-button { margin-top: 10px; }
  </style>
</head>
<body>
  <div class="container">
    <h2 class="text-center mb-4">YouTube Downloader</h2>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <div class="alert alert-danger">
          {% for message in messages %}
            <div>{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    
    {% if stage == "input" %}
      <!-- Stage 1: Input URL and select download format -->
      <form method="POST">
        <div class="form-group">
          <label for="url">Video URL:</label>
          <input type="text" class="form-control" id="url" name="url" placeholder="Enter YouTube URL" value="{{ url|default('') }}" required>
        </div>
        <div class="form-group">
          <label>Select Download Format:</label>
          <div class="form-check">
            <input class="form-check-input" type="radio" name="download_type" id="video" value="video" checked>
            <label class="form-check-label" for="video">Video (choose resolution)</label>
          </div>
          <div class="form-check">
            <input class="form-check-input" type="radio" name="download_type" id="mp3" value="mp3">
            <label class="form-check-label" for="mp3">Audio (MP3)</label>
          </div>
        </div>
        <button type="submit" class="btn btn-primary btn-block">Check Video</button>
      </form>
    
    {% elif stage == "choose_video" %}
      <!-- Stage 2a: Display video info and resolution choices -->
      <div class="card">
        <div class="card-body">
          <h5 class="card-title">{{ video_title }}</h5>
          {% if thumbnail %}
            <img src="{{ thumbnail }}" alt="Thumbnail" class="video-thumbnail mb-3">
          {% endif %}
          <form method="POST">
            <!-- Pass URL and download type as hidden inputs -->
            <input type="hidden" name="url" value="{{ url }}">
            <input type="hidden" name="download_type" value="video">
            <div class="form-group">
              <label for="resolution">Select Resolution:</label>
              <select class="form-control" id="resolution" name="resolution">
                {% for res in available_resolutions %}
                  <option value="{{ res }}">{{ res }}p</option>
                {% endfor %}
              </select>
            </div>
            <button type="submit" class="btn btn-primary btn-block">Download Video</button>
          </form>
          <!-- Back button returns to input stage preserving the URL -->
          <a href="{{ url_for('index') }}?url={{ url }}" class="btn btn-primary btn-block back-button">Back</a>
        </div>
      </div>
    
    {% elif stage == "choose_mp3" %}
      <!-- Stage 2b: Display video info for MP3 download confirmation -->
      <div class="card">
        <div class="card-body">
          <h5 class="card-title">{{ video_title }}</h5>
          {% if thumbnail %}
            <img src="{{ thumbnail }}" alt="Thumbnail" class="video-thumbnail mb-3">
          {% endif %}
          <form method="POST">
            <!-- Pass URL and download type as hidden inputs -->
            <input type="hidden" name="url" value="{{ url }}">
            <input type="hidden" name="download_type" value="mp3">
            <input type="hidden" name="confirm_mp3" value="1">
            <button type="submit" class="btn btn-primary btn-block">Download MP3</button>
          </form>
          <!-- Back button -->
          <a href="{{ url_for('index') }}?url={{ url }}" class="btn btn-primary btn-block back-button">Back</a>
        </div>
      </div>
    
    {% elif stage == "download" %}
      <!-- Stage 3: Download ready, display the download link -->
      <div class="card">
        <div class="card-body text-center">
          <h5 class="card-title">Download Ready!</h5>
          <p class="card-text">Click the button below to download your file. The file will be deleted from the server after download.</p>
          <a href="{{ url_for('download_file', filename=filename) }}" class="btn btn-primary btn-block">Download File</a>
          <!-- Back button -->
          <a href="{{ url_for('index') }}?url={{ url }}" class="btn btn-primary btn-block back-button">Back</a>
        </div>
      </div>
    
    {% endif %}
  </div>
  
  <!-- Bootstrap JS and dependencies -->
  <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.1/dist/umd/popper.min.js"></script>
  <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        # On refresh or initial GET, always display the input stage.
        url_value = request.args.get("url", "")
        return render_template_string(HTML_TEMPLATE, stage="input", url=url_value)
    else:
        # Handle POST requests.
        if "resolution" in request.form:
            # Process video download.
            url = request.form.get("url").strip()
            try:
                resolution = int(request.form.get("resolution"))
            except Exception:
                flash("Invalid resolution.")
                return redirect(url_for("index"))
            ydl_opts = {
                "format": f"bestvideo[height={resolution}]+bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
            }
            # Check if file exists (based on metadata).
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                # If file does not exist, download it.
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
            return render_template_string(HTML_TEMPLATE,
                                          stage="download",
                                          filename=os.path.basename(filename),
                                          url=url)
        elif "confirm_mp3" in request.form:
            # Process MP3 download.
            url = request.form.get("url").strip()
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                filename = ydl.prepare_filename(info)
                filename = os.path.splitext(filename)[0] + ".mp3"
            if not os.path.exists(filename):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    filename = os.path.splitext(filename)[0] + ".mp3"
            return render_template_string(HTML_TEMPLATE,
                                          stage="download",
                                          filename=os.path.basename(filename),
                                          url=url)
        else:
            # Stage 1: Validate URL and fetch video metadata.
            url = request.form.get("url", "").strip()
            download_type = request.form.get("download_type", "video")
            if not url:
                flash("Please enter a video URL.")
                return render_template_string(HTML_TEMPLATE, stage="input", url="")
            try:
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as e:
                flash("Error fetching video info: " + str(e))
                return render_template_string(HTML_TEMPLATE, stage="input", url="")
            video_title = info.get("title", "Video")
            thumbnail = info.get("thumbnail", "")
            if download_type == "video":
                # Collect available video resolutions.
                resolutions = set()
                for fmt in info.get("formats", []):
                    if fmt.get("vcodec", "none") != "none" and fmt.get("height"):
                        resolutions.add(fmt.get("height"))
                if not resolutions:
                    flash("No valid video format available for download.")
                    return render_template_string(HTML_TEMPLATE, stage="input", url="")
                available_resolutions = sorted(list(resolutions), reverse=True)
                return render_template_string(HTML_TEMPLATE,
                                              stage="choose_video",
                                              url=url,
                                              video_title=video_title,
                                              thumbnail=thumbnail,
                                              available_resolutions=available_resolutions)
            elif download_type == "mp3":
                return render_template_string(HTML_TEMPLATE,
                                              stage="choose_mp3",
                                              url=url,
                                              video_title=video_title,
                                              thumbnail=thumbnail)
            else:
                flash("Invalid download type.")
                return render_template_string(HTML_TEMPLATE, stage="input", url="")

@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        @after_this_request
        def remove_file(response):
            try:
                os.remove(file_path)
            except Exception as e:
                app.logger.error("Failed to remove file %s: %s", file_path, e)
            return response
        return send_file(file_path, as_attachment=True)
    else:
        flash("File not found.")
        return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
