from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaStreamTrack
from ultralytics import YOLO
import numpy as np
import cv2
import requests
import time

# --------------------------
# CONFIG (state)
# --------------------------
state = {
    "detect": "both",     # person / phone / both
    "mode": "active",     # active / stop
    "alerts": True,       # send alert or not
    "confidence": 0.5,    # YOLO confidence
}

WORKFLOW_URL = "https://intern.aimicromind.com/api/v1/prediction/311643f1-0583-4523-89d1-4a16e0ef0e1a"

# --------------------------
# FASTAPI APP
# --------------------------
app = FastAPI()
model = YOLO("yolov8n.pt")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# --------------------------
# WORKFLOW EVENT
# --------------------------
def send_event(persons, phones):
    if not state["alerts"]:
        return

    payload = {
        "question": f"persons={persons}, phones={phones}"
    }

    try:
        requests.post(WORKFLOW_URL, json=payload)
        print("📤 SENT WORKFLOW PAYLOAD:", payload)
    except Exception as e:
        print("❌ Workflow error:", e)


# --------------------------
# VIDEO PROCESSING TRACK
# --------------------------
class YOLOStream(MediaStreamTrack):
    kind = "video"
    event_triggered = False

    def __init__(self, track):
        super().__init__()
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        img = frame.to_ndarray(format="bgr24")

        if state["mode"] != "active":
            new_frame = frame.from_ndarray(img, format="bgr24")
            return new_frame

        results = model(img, conf=state["confidence"])[0]

        persons = 0
        phones = 0

        for box in results.boxes:
            cls = int(box.cls[0])
            if cls == 0:
                persons += 1
            elif cls == 67:
                phones += 1

        # --- detect filter ---
        detect_mode = state["detect"]
        if detect_mode == "person":
            phones = 0
        elif detect_mode == "phone":
            persons = 0

        print(f"Detected → P={persons}, Ph={phones} | mode={state['mode']} detect={detect_mode}")

        # --- event logic ---
        if persons > 0 and phones > 0 and not self.event_triggered:
            send_event(persons, phones)
            self.event_triggered = True

        if persons == 0 or phones == 0:
            self.event_triggered = False

        annotated = results.plot()
        new_frame = frame.from_ndarray(annotated, format="bgr24")
        return new_frame


# --------------------------
# WebRTC OFFER
# --------------------------
@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    pc = RTCPeerConnection()

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            pc.addTrack(YOLOStream(track))

    offer = RTCSessionDescription(
        sdp=params["sdp"]["sdp"],
        type=params["sdp"]["type"]
    )

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }


# --------------------------
# CONFIG API (Custom Tool)
# --------------------------
@app.get("/config")
def get_config():
    return state

@app.post("/set-detect")
def set_detect(data: dict):
    state["detect"] = data.get("detect", "both")
    return {"ok": True, "detect": state["detect"]}

@app.post("/set-mode")
def set_mode(data: dict):
    state["mode"] = data.get("mode", "active")
    return {"ok": True, "mode": state["mode"]}

@app.post("/set-sensitivity")
def set_sensitivity(data: dict):
    state["confidence"] = float(data.get("confidence", 0.5))
    return {"ok": True, "confidence": state["confidence"]}

@app.post("/set-alerts")
def set_alerts(data: dict):
    state["alerts"] = bool(data.get("alerts", True))
    return {"ok": True, "alerts": state["alerts"]}
