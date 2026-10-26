# SERVER VIDEO:
# -aprO l’endoscopio come videocamera
# -leggo continuamente i frame (30 frame al secondo)
# -li comprimo in JPEG
# -li rendo disponibili via rete
# -espone:
# -/video_feed → stream MJPEG continuo
# -/snapshot.jpg → immagine singola di debug
import cv2
import time
import threading
from flask import Flask, Response, abort

app = Flask(__name__)   #Creo il server Flask

# =========================
# CONFIG
# =========================
camera_index = 1
server_host = "0.0.0.0"   # importante per HoloLens!!!!
server_port = 5000

frame_width = 640
frame_height = 480
target_fps = 30
jpeg_quality = 70   

# =========================
# CAMERA SETUP
# =========================
cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)  #Apro la camera

#Controllo apertura della camera
if not cap.isOpened():
    raise RuntimeError(f"Impossibile aprire camera index {camera_index}")

cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
cap.set(cv2.CAP_PROP_FPS, target_fps)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  #Uso MJPG come formato interno

# =========================
# SHARED STATE
# =========================
frame_lock = threading.Lock()
latest_jpg = None
frame_id = 0
running = True

# =========================
# CAMERA LOOP
# =========================
def grab_loop():
    global latest_jpg, frame_id, running

    while running:
        ret, frame = cap.read()   #leggo continuamente un frame dalla camera

        if not ret:
            print("Frame non letto. Tento reconnect camera...")
            time.sleep(0.02)
            cap.open(camera_index, cv2.CAP_DSHOW)
            continue

        success, buffer = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]  #Converto il frame in JPEG
        )

        if not success:
            continue

        jpg_bytes = buffer.tobytes()

#OBS: Non sto creando una "coda "di frame ma mantengo solo l'ultimo frame disponibile
        with frame_lock:
            latest_jpg = jpg_bytes
            frame_id += 1

# =========================
# MJPEG GENERATOR
# =========================
def generate_mjpeg():   #Genero lo stream MJPEG da mandare ai client
    last_sent_id = -1

    while True:
        with frame_lock:
            current_frame = latest_jpg
            current_id = frame_id

        if current_frame is None:
            time.sleep(0.001)
            continue

        if current_id == last_sent_id:
            time.sleep(0.001)
            continue

        last_sent_id = current_id

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            current_frame +
            b"\r\n"
        )

# =========================
# ROUTES
# =========================
@app.route("/")
def index():
    return """
    <html>
        <head><title>Endoscope Stream Test</title></head>
        <body>
            <h1>Endoscope Stream Test</h1>
            <h2>Live MJPEG</h2>
            <img src="/video_feed" width="640">
            <h2>Snapshot debug</h2>
            <img src="/snapshot.jpg" width="640">
        </body>
    </html>
    """

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/snapshot.jpg")  #Questo lo uso solo per debug!!
def snapshot():
    with frame_lock:
        frame_bytes = latest_jpg

    if frame_bytes is None:
        return abort(503)

    return Response(frame_bytes, mimetype="image/jpeg")

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    t = threading.Thread(target=grab_loop, daemon=True)  #Avvio il server
    t.start()

    print("=== SERVER AVVIATO ===")
    print(f"Test locale:   http://127.0.0.1:{server_port}")
    print(f"Video feed:    http://127.0.0.1:{server_port}/video_feed")
    print(f"Snapshot:      http://127.0.0.1:{server_port}/snapshot.jpg")
    print("Per Unity/HoloLens usa l'IP del PC sulla rete locale.")

    try:
        app.run(host=server_host, port=server_port, threaded=True)
    finally:
        running = False
        cap.release()
    
    #http://127.0.0.1:5000/video_feed