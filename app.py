from flask import Flask, render_template, request, send_file
import yt_dlp

# تعريف تطبيق Flask
app = Flask(__name__)

# الصفحة الرئيسية
@app.route('/')
def home():
    return render_template('index.html')

# صفحة التحميل
@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    quality = request.form.get('quality')

    # إعداد خيارات yt-dlp حسب الجودة
    if quality.isdigit():
        ydl_opts = {
            'format': f'bestvideo[height<={quality}]+bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s'
        }
    elif quality == "best":
        ydl_opts = {
            'format': 'best',
            'outtmpl': 'downloads/%(title)s.%(ext)s'
        }
    elif quality == "worst":
        ydl_opts = {
            'format': 'worst',
            'outtmpl': 'downloads/%(title)s.%(ext)s'
        }
    else:
        ydl_opts = {
            'format': 'best',
            'outtmpl': 'downloads/%(title)s.%(ext)s'
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url)
        filename = ydl.prepare_filename(info)

    return send_file(filename, as_attachment=True)

# تشغيل التطبيق
if __name__ == "__main__":
    app.run(debug=True)
