import os
import subprocess
import tempfile
import traceback
import time
import json
from flask import Flask, request, render_template_string, send_file
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = "super_secret_key"

# Gemini API Setup
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# လှပသေသပ်သော အချောထည် UI (Tailwind CSS)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Subtitle Studio - Myanmar</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .loader { border-top-color: #3498db; -webkit-animation: spinner 1.5s linear infinite; animation: spinner 1.5s linear infinite; }
        @keyframes spinner { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-gray-100 font-sans leading-normal tracking-normal flex items-center justify-center min-h-screen">
    <div class="max-w-xl w-full bg-white rounded-lg shadow-lg p-8 m-4">
        <div class="text-center mb-8">
            <h1 class="text-3xl font-bold text-gray-800 mb-2">🎬 AI Subtitle Studio</h1>
            <p class="text-gray-600">နိုင်ငံခြားဇာတ်ကားများကို မြန်မာစာတန်းထိုး (.srt) အဖြစ် အလိုအလျောက် ပြောင်းလဲပေးမည့်စနစ်</p>
        </div>

        <form id="uploadForm" action="/upload" method="post" enctype="multipart/form-data" class="space-y-6">
            <div class="flex items-center justify-center w-full">
                <label class="flex flex-col w-full h-32 border-4 border-blue-200 border-dashed hover:bg-gray-50 hover:border-blue-300 rounded-lg cursor-pointer transition">
                    <div class="flex flex-col items-center justify-center pt-7">
                        <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-gray-400 group-hover:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        <p class="pt-1 text-sm tracking-wider text-gray-400 group-hover:text-gray-600">Video ဖိုင်ရွေးချယ်ပါ (MP4, AVI, etc.)</p>
                    </div>
                    <input type="file" name="video_file" class="opacity-0" accept="video/*" required id="fileInput" />
                </label>
            </div>
            
            <div id="fileNameDisplay" class="text-center text-sm text-blue-600 font-medium hidden"></div>

            <button type="submit" id="submitBtn" class="w-full flex justify-center items-center bg-blue-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-blue-700 transition duration-300">
                <span>စာတန်းထိုး ဖန်တီးရန် (Generate .srt)</span>
            </button>
        </form>

        <div id="loadingUI" class="hidden text-center mt-6">
            <div class="loader ease-linear rounded-full border-4 border-t-4 border-gray-200 h-12 w-12 mx-auto mb-4"></div>
            <h2 class="text-xl font-semibold text-gray-700">ခေတ္တစောင့်ဆိုင်းပါ...</h2>
            <p class="text-gray-500 text-sm mt-2">AI မှ အသံကိုနားထောင်ပြီး မြန်မာလို ဘာသာပြန်နေပါသည်။ (မိနစ်အနည်းငယ် ကြာနိုင်ပါသည်)</p>
        </div>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        const fileNameDisplay = document.getElementById('fileNameDisplay');
        const uploadForm = document.getElementById('uploadForm');
        const submitBtn = document.getElementById('submitBtn');
        const loadingUI = document.getElementById('loadingUI');

        fileInput.addEventListener('change', function(e) {
            if(e.target.files.length > 0) {
                fileNameDisplay.textContent = "ရွေးချယ်ထားသောဖိုင်: " + e.target.files[0].name;
                fileNameDisplay.classList.remove('hidden');
            }
        });

        uploadForm.addEventListener('submit', function() {
            submitBtn.classList.add('hidden');
            fileNameDisplay.classList.add('hidden');
            loadingUI.classList.remove('hidden');
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload_file():
    if not api_key:
        return "System Error: GEMINI_API_KEY မထည့်သွင်းရသေးပါ။", 500

    if 'video_file' not in request.files:
        return "File မတွေ့ပါ။", 400
    
    file = request.files['video_file']
    if file.filename == '':
        return "File ရွေးချယ်ထားခြင်းမရှိပါ။", 400

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = os.path.join(temp_dir, "input_video.mp4")
            audio_path = os.path.join(temp_dir, "extracted_audio.mp3")
            
            file.save(video_path)
            
            # 1. FFmpeg ဖြင့် Audio ခွဲထုတ်ခြင်း 
            subprocess.run(['ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', audio_path, '-y'], check=True)
            
            # 2. Gemini သို့ Audio file ပို့ခြင်း (mime_type ထည့်သွင်းထားသည်)
            audio_file = genai.upload_file(path=audio_path, mime_type="audio/mp3")
            
            # 3. ဖိုင်ကို AI ဖတ်လို့အသင့်ဖြစ်သည်အထိ စောင့်ရန်
            while audio_file.state.name == 'PROCESSING':
                time.sleep(2)
                audio_file = genai.get_file(audio_file.name)
                
            if audio_file.state.name == 'FAILED':
                return "Error: Gemini ဘက်မှ ဖိုင်လက်ခံရရှိမှု မအောင်မြင်ပါ။", 500

            # 4. AI Model သတ်မှတ်ခြင်း (ပိုမိုမြန်ဆန်သော 1.5-flash သို့ ပြောင်းလဲထားသည်)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = """
            You are an expert Subtitle Translator. Process the attached audio and generate a full Myanmar subtitle file.
            
            STRICT INSTRUCTIONS:
            1. LANGUAGE: Translate into Myanmar Unicode. Use ONLY natural, everyday colloquial language (နေ့စဉ်သုံး မြန်မာစကားပြောဟန်). DO NOT use formal/literary (စာအုပ်ဆန်ဆန်) style.
            2. FORMAT: You MUST return ONLY the raw .srt format text. Ensure precise timestamps (e.g., 00:01:20,000 --> 00:01:24,000).
            3. OUTPUT LIMITATION: Do not output any markdown code blocks (like ```srt). Start directly with subtitle index "1". No introductory or concluding remarks.
            """
            
            response = model.generate_content([prompt, audio_file])
            
            # 5. SRT ဖိုင်ကို သန့်စင်ပြီး သိမ်းဆည်းခြင်း
            srt_content = response.text.replace("```srt", "").replace("```", "").strip()
            
            final_srt_path = "/tmp/Final_Myanmar_Subtitle.srt" 
            with open(final_srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
                
            return send_file(final_srt_path, as_attachment=True, download_name="Final_Myanmar_Subtitle.srt")
            
    except Exception as e:
        # Error အတိအကျကို ဖမ်းယူပြီး Website တွင် ပြသပေးမည့်အပိုင်း
        error_details = traceback.format_exc()
        error_message = str(e)
        
        # Google API HttpError ဖြစ်လျှင် အသေးစိတ်ထုတ်ပြရန်
        if "HttpError" in error_details:
            try:
                error_content = e.content.decode('utf-8')
                parsed_error = json.loads(error_content)
                error_message = f"Google API Error: {parsed_error['error']['code']} - {parsed_error['error']['message']}"
            except:
                pass

        print(error_details)
        return f"""
        <div style="font-family: sans-serif; padding: 20px;">
            <h3>စနစ်ချို့ယွင်းမှု ဖြစ်ပွားနေပါသည်</h3>
            <p style="color:red; font-size:18px;"><b>{error_message}</b></p>
            <hr>
            <p><b>အသေးစိတ် Error (Traceback):</b></p>
            <pre style="background-color:#f8d7da; padding:15px; border-radius:5px; overflow-x:auto;">{error_details}</pre>
        </div>
        """, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
