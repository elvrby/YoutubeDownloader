import os
import tempfile
from flask import Flask, request, render_template, send_file, redirect, url_for, flash, after_this_request
import yt_dlp

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Ubah dengan key yang lebih aman untuk produksi

# Menggunakan direktori temporary bawaan sistem, sehingga file tidak disimpan secara permanen.
DOWNLOAD_FOLDER = tempfile.gettempdir()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        url_value = request.args.get("url", "")
        return render_template("index.html", stage="input", url=url_value)
    else:
        # Menangani permintaan POST.
        if "resolution" in request.form:
            # Proses download video.
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
            # Cek apakah file sudah ada.
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                # Jika belum ada, download file.
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
            return render_template("index.html",
                                   stage="download",
                                   filename=os.path.basename(filename),
                                   url=url)
        elif "confirm_mp3" in request.form:
            # Proses download MP3.
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
            return render_template("index.html",
                                   stage="download",
                                   filename=os.path.basename(filename),
                                   url=url)
        else:
            # Tahap validasi video.
            url = request.form.get("url", "").strip()
            download_type = request.form.get("download_type", "video")
            if not url:
                flash("Please enter a video URL.")
                return render_template("index.html", stage="input", url="")
            try:
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as e:
                flash("Error fetching video info: " + str(e))
                return render_template("index.html", stage="input", url="")
            video_title = info.get("title", "Video")
            thumbnail = info.get("thumbnail", "")
            video_id = info.get("id", "")
            embed_url = f"https://www.youtube.com/embed/{video_id}" if video_id else ""
            
            if download_type == "video":
                # Kumpulkan resolusi yang tersedia.
                resolutions = set()
                for fmt in info.get("formats", []):
                    if fmt.get("vcodec", "none") != "none" and fmt.get("height"):
                        resolutions.add(fmt.get("height"))
                if not resolutions:
                    flash("No valid video format available for download.")
                    return render_template("index.html", stage="input", url="")
                available_resolutions = sorted(list(resolutions), reverse=True)
                return render_template("index.html",
                                       stage="choose_video",
                                       url=url,
                                       video_title=video_title,
                                       thumbnail=thumbnail,
                                       available_resolutions=available_resolutions,
                                       embed_url=embed_url)
            elif download_type == "mp3":
                return render_template("index.html",
                                       stage="choose_mp3",
                                       url=url,
                                       video_title=video_title,
                                       thumbnail=thumbnail)
            else:
                flash("Invalid download type.")
                return render_template("index.html", stage="input", url="")

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
