import cyberpi, event, mbot2
import urequests as requests
import usocket as socket
import gc
import time
import _thread
from global_objects import mp3_music_o

# --- CONFIGURATION ---
# Apply your changes here.

PROXY_HOST_NAME = "servberry"
LANGUAGE = "german"
IS_SMART_WORLD_GRIPPER = True

# --- END OF CONFIGURATION ---

#### START OF THE PROGRAMM ####
cyberpi.speech.set_recognition_address(url = "{NAVIGATEURL}")
cyberpi.speech.set_access_token(token = "{ACCESSTOKEN}")

localizations = {
    "german": {
        "pending_network": "Warte auf WiFi-Verbindung...",
        "error": "Fehler im Hybrid-Streaming: {}"
    },
    "english": {
        "pending_network": "Waiting for WiFi connection...",
        "error": "Hybrid streaming error: {}"
    },
    "french": {
        "pending_network": "En attente de connexion WiFi...",
        "error": "Erreur de streaming hybride : {}"
    }
}

BASE_URL = "http://{}:5000".format(PROXY_HOST_NAME)
SAMPLERATE = 16000
CHUNK_SIZE = 32000

localization = localizations[LANGUAGE]

is_playing_active = False
abort_streaming = False

def audio_player_worker(payload, samplerate):
    global is_playing_active
    is_playing_active = True
    try:
        mp3_music_o.play_raw_data(payload, samplerate)
    finally:
        is_playing_active = False

def show_error(e):
    global current_localization
    cyberpi.console.println(localization["error"].format(str(e)))

def stream_audio_via_socket(pi_ip, port, total_bytes):
    global is_playing_active, CHUNK_SIZE, SAMPLERATE, abort_streaming
    s = None
    bytes_received = 0
    is_first_chunk = True
    
    try:
        addr = socket.getaddrinfo(pi_ip, port)[0][-1]
        s = socket.socket()
        s.connect(addr)
        
        while bytes_received < total_bytes and not abort_streaming:
            
            remaining = total_bytes - bytes_received
            current_target = min(CHUNK_SIZE, remaining)
            
            chunk_data = b""
            while len(chunk_data) < current_target:
                if abort_streaming: break
                part = s.recv(current_target - len(chunk_data))
                if not part: break
                chunk_data += part
            
            if not chunk_data: break
            bytes_received += len(chunk_data)
            
            if bytes_received < total_bytes:
                try: s.send(b"OK")
                except: pass
            
            while is_playing_active:
                if abort_streaming: break
                time.sleep(0.01)
            
            if abort_streaming: break
            
            payload = chunk_data[4:] if is_first_chunk and chunk_data.startswith(b'CPAD') else chunk_data
            _thread.start_new_thread(audio_player_worker, (payload, SAMPLERATE))
            
            is_first_chunk = False
            gc.collect()
            
        while is_playing_active:
            time.sleep(0.1)
            
    except Exception as e:
        show_error(e)
    finally:
        if s: s.close()

def play_ai_response():
    global BASE_URL, SAMPLERATE, CHUNK_SIZE
    try:
        res = requests.get(BASE_URL + "/get-info")
        info = res.json()
        res.close()
        
        total_bytes = info.get("total_bytes", 0)
        pi_ip = info.get("ip")
        pi_port = info.get("port")
        
        if total_bytes > 0 and pi_ip and pi_port:
            stream_audio_via_socket(pi_ip, pi_port, total_bytes)
            
    except Exception as e:
        show_error(e)

def action_worker(action_list):
    global localization
    for item in action_list:
        if abort_streaming: break
        
        cmd = item['action']
        dur = item['duration']
        
        if cmd == localization["forward"]:
            mbot2.forward(50, dur)
        elif cmd == localization["backward"]:
            mbot2.backward(50, dur)
        elif cmd == localization["left"]:
            mbot2.turn(-15)
        elif cmd == localization["right"]:
            mbot2.turn(15)
        elif IS_SMART_WORLD_GRIPPER:
            if cmd == localization["up"]:
                mbot2.servo_set(60,"S4")
            elif cmd == localization["down"]:
                mbot2.servo_set(0,"S4")
            elif cmd == localization["open"]:
                mbot2.servo_set(0,"S3")
            elif cmd == localization["close"]:
                mbot2.servo_set(50,"S3")
        elif cmd == localization["pause"]:
            time.sleep(dur)
        
        mbot2.EM_stop("ALL")

def start_interaction():
    global BASE_URL, abort_streaming, LANGUAGE, localization
    abort_streaming = False
    cyberpi.led.show_all("red")
    cyberpi.display.show_label(localization["listening"], 12, 0, 0)
    
    cyberpi.cloud.listen(LANGUAGE, 3)
    frage = cyberpi.cloud.listen_result()
    
    if frage:
        cyberpi.display.show_label(frage, 12, 0, 0)
        cyberpi.led.show_all("blue")

        res = requests.post(BASE_URL + "/ask", data=frage)
        data = res.json()
        res.close()

        actions = data["actions"]
        answer = data["answer"]

        cyberpi.display.show_label(answer, 12, 0, 0)
        
        try:
            _thread.start_new_thread(action_worker, (actions,))
            play_ai_response()
        except:
            cyberpi.display.show_label(localization["error_network_unavailable"], 12, 0, 0)
    else:
        cyberpi.display.show_label(localization["nothing_recorded"], 12, 0, 0)
    
    cyberpi.led.show_all("green")

def init():
    global BASE_URL, LANGUAGE, localizations, localization
    res = requests.post(BASE_URL + "/init", data=LANGUAGE)
    localizations = res.json()
    localization = localizations[LANGUAGE]
    res.close()

def stop_interaction():
    global abort_streaming
    abort_streaming = True

@event.is_press('a')
def is_btn_press():
    stop_interaction()

@event.is_press('b')
def is_btn_press():
    start_interaction()

@event.start
def main():
    global localization
    cyberpi.display.show_label(localization["pending_network"], 12, 0, 0)
    while not cyberpi.wifi.is_connect():
        pass
    try:
        init()
        mp3_music_o.set_volume(40)
        cyberpi.led.show_all("green")
        cyberpi.display.show_label(localization["instructions"], 12, 0, 0)
    except:
        show_error()