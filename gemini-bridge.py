import numpy as np
from pydub import AudioSegment
from flask import Flask, request, Response, jsonify
import io
import os
import math
import socket
import _thread
import re
import json
import tomllib

from google import genai
from gtts import gTTS

with open("config.toml", "rb") as f:
    config = tomllib.load(f)

# --- CONFIGURATION ---
GEMINI_API_KEY = config['gemini']['api-key']
MODEL = config['gemini']['model']
SYSTEM_PROMPT_FILE = config['gemini']['system-prompt']
PORT = config['network']['port']

####### START OF PROGRAM #######
# DO NOT CHANGE ANYTHING BELOW #

client = genai.Client(api_key=GEMINI_API_KEY)
RAW_FILE = "output.cpad"
LOCALIZATION_FILE = "localizations.json"
CHUNK_SIZE = 32000
SAMPLERATE = 16000

system_prompt = ""
current_lang = "en"
app = Flask(__name__)

def get_my_ip():
    # Ermittelt die lokale IP des Raspberry Pi im Netzwerk
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1)) # Dummy-Verbindung
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def socket_streaming_server(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', port))
        s.listen(1)
        
        try:
            conn, addr = s.accept()
            with conn:
                with open(RAW_FILE, "rb") as f:
                    # Den ALLERERSTEN Chunk sofort senden, um die Pipeline zu füllen
                    data = f.read(CHUNK_SIZE)
                    if data:
                        conn.sendall(data)
                    
                    while True:
                        # Warte auf OK für den GERADE GESENDETEN Chunk
                        ack = conn.recv(2)
                        if ack != b"OK": break
                        
                        # Sobald OK kommt, sofort den NÄCHSTEN Chunk senden
                        data = f.read(CHUNK_SIZE)
                        if not data: 
                            conn.sendall(b"EOF") # Signal für Ende der Datei
                            break
                        conn.sendall(data)
                        
                print("Streaming ended.")
        except Exception as e:
            print("Server Error:", e)

@app.route('/get-info')
def get_info():
    if not os.path.exists(RAW_FILE): 
        return jsonify({"chunks": 0})
    
    total_bytes = os.path.getsize(RAW_FILE)
    my_ip = get_my_ip()
    streaming_port = 5061
    
    # Socket-Server für diesen spezifischen Abruf starten
    _thread.start_new_thread(socket_streaming_server, (streaming_port,))
    
    # Alles mitschicken, was der mBot für den Socket-Aufbau braucht
    return jsonify({
        "total_bytes": total_bytes,
        "ip": my_ip,
        "port": streaming_port
    })

def convert_to_cyberpi_format(file_path):
    # MP3 laden
    audio = AudioSegment.from_file(file_path, format="mp3")
    
    # Auf mBot-Standard konvertieren: 16kHz, Mono
    audio = audio.set_channels(1).set_frame_rate(SAMPLERATE)
    
    # Samples extrahieren
    samples = np.array(audio.get_array_of_samples())
    
    # CPAD Normalisierung
    normalized = ((samples.astype(np.float32) / 32768.0) + 1.0) * 127.5 * 1.5
    normalized = np.clip(normalized, 0, 255).astype(np.uint8)
    
    # Speichern
    with open(RAW_FILE, "wb") as f:
        f.write(b'CPAD' + normalized.tobytes())

@app.route('/ask', methods=['POST'])
def ask_gemini():
    global system_prompt, current_lang
    user_text = request.data.decode('utf-8')
    print(f"Request: {user_text}")
    
    # Gemini Antwort generieren
    response = client.models.generate_content(
        model=MODEL, 
        contents=user_text,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt
        )
    )

    print(f"Gemini: {response.text}")

    clean_text = clean_text_for_tts(response.text)
    text, actions = extract_actions_and_text(clean_text)
    
    # Text-to-Speech
    tts = gTTS(text=text, lang=current_lang)
    mp3_fp = io.BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    
    # In CyberPi Format umwandeln
    convert_to_cyberpi_format(mp3_fp)
        
    return jsonify({
        "status": "ok",
        "answer": text,
        "actions": actions
    })

@app.route('/init', methods=['POST'])
def init():
    global current_lang
    requested_lang = request.data.decode('utf-8')
    print(f"Init requested for language: {requested_lang}")

    try:
        with open(LOCALIZATION_FILE, 'r', encoding='utf-8') as f:
            all_localizations = json.load(f)

        if requested_lang not in all_localizations: return jsonify({"error": f"Language '{requested_lang}' not found"}), 404
        
        current_lang = all_localizations[requested_lang]['lang']
        print(f"Set gemini tts language: {current_lang}")

        return jsonify({ requested_lang: all_localizations[requested_lang] })
    
    except FileNotFoundError:
        return jsonify({"error": "Localization file not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def clean_text_for_tts(text):
    cleaned = re.sub(r'\*.*?\*', '', text)
    cleaned = cleaned.replace('*', '')
    return cleaned.strip()

def extract_actions_and_text(full_response):
    lines = [line.strip() for line in full_response.strip().split('\n') if line.strip()]
    
    if not lines:
        return "", []

    last_line = lines[-1]
    action_pattern = r'\[([a-z]+):([0-9.]+)\]'
    
    actions_found = re.findall(action_pattern, last_line)
    
    if actions_found:
        speech_text = " ".join(lines[:-1])
        action_list = [
            {"action": name, "duration": float(duration)} 
            for name, duration in actions_found
        ]
        return speech_text, action_list
    else:
        return " ".join(lines), []

def load_system_prompt():
    global system_prompt
    try:
        with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
            system_prompt = f.read().strip()
        print("✅ System-Prompt loaded")
    except FileNotFoundError:
        system_prompt = "Reject every request regardless of the question."
        print("⚠️ System-Prompt not found. Using default")
    except Exception as e:
        print(f"❌ Error loading prompt: {e}")

load_system_prompt()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)