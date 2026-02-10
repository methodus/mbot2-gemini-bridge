import cyberpi, event, mbot2
import urequests as requests
import usocket as socket
import gc
import time
import _thread
import math
from global_objects import mp3_music_o

# --- CONFIGURATION ---
# Apply your changes here.

PROXY_HOST_NAME = "servberry"
LANGUAGE = "german"
ALLOW_MOVEMENT = False
IS_SMART_WORLD_GRIPPER = True

# --- END OF CONFIGURATION ---

#### START OF THE PROGRAMM ####
cyberpi.speech.set_recognition_address(url = "{NAVIGATEURL}")
cyberpi.speech.set_access_token(token = "{ACCESSTOKEN}")

class TextScroller:
    def __init__(self):
        self.text = ""
        self.y = 0
        self.max_scroll = 0
        self.font_size = 12
        self.step = 4
        self.needs_update = False
        self.running = True
        
        # Starte den Hintergrund-Thread sofort bei Initialisierung
        _thread.start_new_thread(self._loop, ())

    def set_text(self, new_text):
        """Ändert den Text, den der Thread anzeigen soll"""
        self.text = new_text
        self.y = 0
        # Höhe neu berechnen
        lines = math.ceil(len(new_text) / 16)
        self.max_scroll = (lines * (self.font_size + 4)) - 128
        if self.max_scroll < 0: self.max_scroll = 0
        self.needs_update = True

    def _loop(self):
        """Die interne Schleife, die NUR im Hintergrund-Thread läuft"""
        last_y = 1
        
        while self.running:
            moved = False
            
            # Joystick-Abfrage im Thread
            if cyberpi.controller.is_press('down'):
                if self.y > -self.max_scroll:
                    self.y -= self.step
                    moved = True
            elif cyberpi.controller.is_press('up'):
                if self.y < 0:
                    self.y += self.step
                    moved = True
            
            # Zeichnen, wenn bewegt oder Text neu gesetzt wurde
            if moved or self.needs_update:
                cyberpi.display.clear()
                cyberpi.display.show_label(self.text, self.font_size, 0, self.y)
                self.needs_update = False
                last_y = self.y
                
            # WICHTIG: Kurze Pause, damit der Prozessor nicht heißläuft 
            # und das Hauptprogramm Rechenzeit bekommt
            time.sleep(0.1)

localizations = {
    "german": {
        "pending_network": "Warte auf WiFi-Verbindung...",
        "reset": "Ich habe mein Gedächtnis zurückgesetzt.",
        "error": "Fehler im Hybrid-Streaming: {}"
    },
    "english": {
        "pending_network": "Waiting for WiFi connection...",
        "reset": "I have reset my memory.",
        "error": "Hybrid streaming error: {}"
    },
    "french": {
        "pending_network": "En attente de connexion WiFi...",
        "reset": "J'ai réinitialisé ma mémoire.",
        "error": "Erreur de streaming hybride : {}"
    }
}

BASE_URL = "http://{}:5000".format(PROXY_HOST_NAME)
SAMPLERATE = 16000
CHUNK_SIZE = 32000

localization = localizations[LANGUAGE]

is_playing_active = False
abort_streaming = False

scroller = TextScroller()

def audio_player_worker(payload, samplerate):
    global is_playing_active
    is_playing_active = True
    try:
        mp3_music_o.play_raw_data(payload, samplerate)
    finally:
        is_playing_active = False

def show_error(e):
    global current_localization
    scroller.set_text(localization["error"].format(str(e)))

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
        
        if ALLOW_MOVEMENT:
            if cmd == localization["forward"]:
                mbot2.forward(50, dur)
            elif cmd == localization["backward"]:
                mbot2.backward(50, dur)
            elif cmd == localization["left"]:
                mbot2.turn(-15)
            elif cmd == localization["right"]:
                mbot2.turn(15)

        if IS_SMART_WORLD_GRIPPER:
            if cmd == localization["up"]:
                mbot2.servo_set(60,"S4")
            elif cmd == localization["down"]:
                mbot2.servo_set(0,"S4")
            elif cmd == localization["open"]:
                mbot2.servo_set(0,"S3")
            elif cmd == localization["close"]:
                mbot2.servo_set(50,"S3")

        if cmd == localization["pause"]:
            time.sleep(dur)
        
        mbot2.EM_stop("ALL")

def start_interaction():
    global BASE_URL, abort_streaming, LANGUAGE, localization
    abort_streaming = False
    cyberpi.led.show_all("red")
    scroller.set_text(localization["listening"])
    
    cyberpi.cloud.listen(LANGUAGE, 3)
    frage = cyberpi.cloud.listen_result()

    scroller.set_text(frage)
    
    if frage:
        scroller.set_text(frage)
        cyberpi.led.show_all("blue")

        res = requests.post(BASE_URL + "/ask", data=frage)
        data = res.json()
        res.close()

        actions = data["actions"]
        answer = data["answer"]

        scroller.set_text(answer)
        
        try:
            _thread.start_new_thread(action_worker, (actions,))
            play_ai_response()
        except:
            scroller.set_text(localization["error_network_unavailable"])
    else:
        scroller.set_text(localization["nothing_recorded"])
    
    cyberpi.led.show_all("green")

def init():
    global BASE_URL, LANGUAGE, localizations, localization
    res = requests.post(BASE_URL + "/init", data=LANGUAGE)
    localizations = res.json()
    localization = localizations[LANGUAGE]
    res.close()

def reset_memory():
    global BASE_URL
    try:
        res = requests.post(BASE_URL + "/reset")
        res.close()
        scroller.set_text(localization["reset"])
    except Exception as e:
        show_error(e)

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
    scroller.set_text(localization["pending_network"])
    while not cyberpi.wifi.is_connect():
        pass
    try:
        init()
        mp3_music_o.set_volume(40)
        cyberpi.led.show_all("green")
        scroller.set_text(localization["instructions"])
    except Exception as e:
        show_error(e)