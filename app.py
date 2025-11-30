from flask import Flask, request, jsonify, render_template, send_file
import yt_dlp
import os
import threading
import time
import logging
from urllib.parse import unquote

# إعداد التطبيق
app = Flask(__name__)

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# مجلد التحميلات
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# تخزين حالة التحميلات
download_status = {}

class DownloadThread(threading.Thread):
    def __init__(self, url, quality, download_id):
        threading.Thread.__init__(self)
        self.url = url
        self.quality = quality
        self.download_id = download_id

    def run(self):
        try:
            download_status[self.download_id] = {
                'status': 'downloading',
                'progress': '0%',
                'filename': '',
                'error': None
            }
            
            # إعداد خيارات yt-dlp
            ydl_opts = {
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'progress_hooks': [self.progress_hook],
            }
            
            # إعداد الجودة المطلوبة
            if self.quality == 'audio':
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            elif self.quality == '720p':
                ydl_opts['format'] = 'best[height<=720]'
            elif self.quality == '1080p':
                ydl_opts['format'] = 'best[height<=1080]'
            else:  # best quality
                ydl_opts['format'] = 'best'
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                filename = ydl.prepare_filename(info)
                
                # إذا كان تحميل صوت، غير الامتداد إلى mp3
                if self.quality == 'audio':
                    filename = os.path.splitext(filename)[0] + '.mp3'
                
                download_status[self.download_id] = {
                    'status': 'completed',
                    'progress': '100%',
                    'filename': filename,
                    'title': info.get('title', ''),
                    'error': None
                }
                
        except Exception as e:
            download_status[self.download_id] = {
                'status': 'error',
                'progress': '0%',
                'filename': '',
                'error': str(e)
            }
            logger.error(f"Download error: {str(e)}")

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            if 'total_bytes' in d and d['total_bytes']:
                percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
                progress = f"{percent:.1f}%"
            elif 'total_bytes_estimate' in d and d['total_bytes_estimate']:
                percent = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                progress = f"{percent:.1f}%"
            else:
                progress = f"{d.get('_percent_str', '0%')}"
            
            download_status[self.download_id]['progress'] = progress

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_video_info():
    """الحصول على معلومات الفيديو"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'الرجاء إدخال رابط'}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            video_info = {
                'title': info.get('title', ''),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', ''),
                'thumbnail': info.get('thumbnail', ''),
                'formats': []
            }
            
            # إضافة الخيارات المتاحة
            formats = []
            has_audio = False
            has_720 = False
            has_1080 = False
            
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':  # فيديو+صوت
                    height = f.get('height', 0)
                    if height >= 1080:
                        has_1080 = True
                    elif height >= 720:
                        has_720 = True
                elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':  # صوت فقط
                    has_audio = True
            
            formats.append({'id': 'best', 'name': 'أفضل جودة'})
            if has_1080:
                formats.append({'id': '1080p', 'name': '1080p'})
            if has_720:
                formats.append({'id': '720p', 'name': '720p'})
            if has_audio:
                formats.append({'id': 'audio', 'name': 'صوت فقط (MP3)'})
            
            video_info['formats'] = formats
            
            return jsonify(video_info)
            
    except Exception as e:
        logger.error(f"Info error: {str(e)}")
        return jsonify({'error': f'خطأ في جلب المعلومات: {str(e)}'}), 500

@app.route('/api/download', methods=['POST'])
def start_download():
    """بدء التحميل"""
    try:
        data = request.get_json()
        url = data.get('url')
        quality = data.get('quality', 'best')
        
        if not url:
            return jsonify({'error': 'الرجاء إدخال رابط'}), 400
        
        download_id = f"dl_{int(time.time())}_{hash(url)}"
        
        # بدء التحميل في thread منفصل
        download_thread = DownloadThread(url, quality, download_id)
        download_thread.start()
        
        return jsonify({
            'download_id': download_id,
            'message': 'بدأ التحميل'
        })
        
    except Exception as e:
        logger.error(f"Download start error: {str(e)}")
        return jsonify({'error': f'خطأ في بدء التحميل: {str(e)}'}), 500

@app.route('/api/status/<download_id>')
def get_download_status(download_id):
    """الحصول على حالة التحميل"""
    status = download_status.get(download_id, {
        'status': 'unknown',
        'progress': '0%',
        'filename': '',
        'error': None
    })
    
    return jsonify(status)

@app.route('/api/download-file/<filename>')
def download_file(filename):
    """تحميل الملف"""
    try:
        filename = unquote(filename)
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        
        if os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=filename
            )
        else:
            return jsonify({'error': 'الملف غير موجود'}), 404
            
    except Exception as e:
        logger.error(f"File download error: {str(e)}")
        return jsonify({'error': f'خطأ في تحميل الملف: {str(e)}'}), 500

@app.route('/api/cleanup', methods=['POST'])
def cleanup_files():
    """تنظيف الملفات المحملة"""
    try:
        for filename in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        
        download_status.clear()
        return jsonify({'message': 'تم تنظيف الملفات'})
        
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")
        return jsonify({'error': f'خطأ في التنظيف: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'الصفحة غير موجودة'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'خطأ داخلي في الخادم'}), 500

# التشغيل
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
