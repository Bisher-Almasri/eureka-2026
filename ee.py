from flask import Flask, Response
import cv2
import mediapipe as mp
import numpy as np

app = Flask(__name__)

W, H = 320, 180
PROCESS_EVERY = 5
JPEG_QUALITY = 35

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cap.set(cv2.CAP_PROP_FPS, 60)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

face_mesh = mp.solutions.face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    static_image_mode=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

LEFT_EYE_L, LEFT_EYE_R, LEFT_EYE_TOP, LEFT_EYE_BOTTOM = 33, 133, 159, 145
RIGHT_EYE_L, RIGHT_EYE_R, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM = 362, 263, 386, 374
LEFT_IRIS = [468, 469, 470, 471]
RIGHT_IRIS = [473, 474, 475, 476]

frame_count = 0
status = "NO FACE"
color = (0, 0, 255)
debug = ""

def pt(lm, i):
    return np.array([lm[i].x * W, lm[i].y * H])

def iris(lm, ids):
    return np.mean([pt(lm, i) for i in ids], axis=0)

def eye(lm, L, R, T, B, iris_ids):
    left, right, top, bottom = pt(lm, L), pt(lm, R), pt(lm, T), pt(lm, B)
    ic = iris(lm, iris_ids)

    ew = max(np.linalg.norm(right - left), 1)
    eh = max(np.linalg.norm(bottom - top), 1)

    x = np.linalg.norm(ic - left) / ew
    y = np.linalg.norm(ic - top) / eh
    return x, y

def gen():
    global frame_count, status, color, debug

    while True:
        for _ in range(4):
            cap.grab()

        ret, frame = cap.read()
        if not ret:
            continue

        frame_count += 1

        if frame_count % PROCESS_EVERY == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = face_mesh.process(rgb)

            status = "NO FACE"
            color = (0, 0, 255)
            debug = ""

            if res.multi_face_landmarks:
                lm = res.multi_face_landmarks[0].landmark

                lx, ly = eye(lm, LEFT_EYE_L, LEFT_EYE_R, LEFT_EYE_TOP, LEFT_EYE_BOTTOM, LEFT_IRIS)
                rx, ry = eye(lm, RIGHT_EYE_L, RIGHT_EYE_R, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM, RIGHT_IRIS)

                gx = (lx + rx) / 2
                gy = (ly + ry) / 2

                debug = f"x:{gx:.2f} y:{gy:.2f}"

                if gx < 0.35 or gx > 0.65:
                    status = "NOT FOCUSED - SIDE"
                    color = (0, 0, 255)
                elif gy > 0.66:
                    status = "NOT FOCUSED - DOWN"
                    color = (0, 0, 255)
                else:
                    status = "FOCUSED"
                    color = (0, 255, 0)

        cv2.putText(frame, status, (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        cv2.putText(frame, debug, (8, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            continue

        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"

@app.route("/")
def home():
    return '<img src="/video" style="width:100%;">'

@app.route("/video")
def video():
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

app.run(host="0.0.0.0", port=5001, threaded=True)

