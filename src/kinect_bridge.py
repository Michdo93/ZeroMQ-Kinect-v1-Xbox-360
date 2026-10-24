"""ZeroMQ bridge for the Xbox 360 Kinect v1 (libfreenect) on Linux.

Sockets
  PUB  tcp://*:5557          (--bind)     sensor streams, multipart [topic, json-meta, binary]
       kinect.rgb      640x480 RGB24 (921 600 bytes) or JPEG (--jpeg, needs OpenCV), 30 fps
       kinect.depth    640x480 uint16 little endian, 11-bit raw disparity, 30 fps
       kinect.audio    PCM int16, 16 kHz (via ALSA/sounddevice, optional)
       kinect.status   changes of brightness / tilt / LED
  REP  tcp://127.0.0.1:5558  (--control)  JSON control channel
       {"command": "get_status"}
       {"command": "brightness", "value": -100..100}   software offset on RGB
       {"command": "tilt", "value": -30..30}           motor, degrees
       {"command": "led", "value": "off|green|red|yellow|blink_green|blink_red_yellow"}

Why ZeroMQ: ~46 MB/s of raw image data, binary frames without base64/JSON
overhead, and several independent consumers (viewer, presence detector,
recorder, ...) that each subscribe only to the streams they need.

libfreenect's runloop() owns the main thread; the `body` callback is called
between USB events and is the only place where ZeroMQ sockets are touched.
Stopping is done by raising freenect.Kill inside `body`.

--simulate generates synthetic RGB/depth/audio with the same message format.
"""

import argparse
import json
import math
import queue
import signal
import threading
import time

import numpy as np
import zmq

OUT: "queue.Queue[tuple]" = queue.Queue(maxsize=60)
CFG = {"brightness": 0, "tilt": 0.0, "led": "green", "jpeg": False}
LED_NAMES = ["off", "green", "red", "yellow", "blink_green", "blink_red_yellow"]
RUNNING = threading.Event()
STATS = {"rgb": 0, "depth": 0, "audio": 0, "dropped": 0}


def emit(topic: str, meta: dict, data: bytes = b"") -> None:
    meta["t_pub_us"] = time.time_ns() // 1000
    try:
        OUT.put_nowait((topic.encode(), json.dumps(meta, separators=(",", ":")).encode(), data))
    except queue.Full:
        STATS["dropped"] += 1  # never block the USB callbacks


# --------------------------------------------------------------------------
# Frame callbacks (called by libfreenect or by the simulator)
# --------------------------------------------------------------------------
def on_video(_dev, frame: np.ndarray, timestamp: int) -> None:
    rgb = frame
    if CFG["brightness"]:
        rgb = np.clip(rgb.astype(np.int16) + CFG["brightness"], 0, 255).astype(np.uint8)
    meta = {"width": rgb.shape[1], "height": rgb.shape[0], "timestamp": int(timestamp),
            "brightness": CFG["brightness"]}
    if CFG["jpeg"]:
        import cv2
        ok, buf = cv2.imencode(".jpg", rgb[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 80])  # RGB -> BGR
        meta["format"], data = "jpeg", buf.tobytes()
    else:
        meta["format"], data = "rgb24", np.ascontiguousarray(rgb).tobytes()
    STATS["rgb"] += 1
    emit("kinect.rgb", meta, data)


def on_depth(_dev, frame: np.ndarray, timestamp: int) -> None:
    depth = np.ascontiguousarray(frame, dtype="<u2")
    STATS["depth"] += 1
    emit("kinect.depth", {"width": depth.shape[1], "height": depth.shape[0], "format": "depth11_u16le",
                          "timestamp": int(timestamp)}, depth.tobytes())


def on_audio(indata: np.ndarray, frames: int, _time, status) -> None:
    STATS["audio"] += 1
    emit("kinect.audio", {"rate": 16000, "channels": indata.shape[1], "format": "pcm_s16le",
                          "frames": frames, "status": str(status) if status else ""}, indata.tobytes())


# --------------------------------------------------------------------------
class Bridge:
    def __init__(self, args, hardware):
        self.hw = hardware  # module freenect or None (simulation)
        self.context = zmq.Context()
        self.pub = self.context.socket(zmq.PUB)
        self.pub.setsockopt(zmq.SNDHWM, 30)  # ~1 s of frames per slow subscriber
        self.pub.bind(args.bind)
        self.ctl = self.context.socket(zmq.REP)
        self.ctl.bind(args.control)
        self.dev = None

    def control(self, req: dict) -> dict:
        cmd, value = req.get("command"), req.get("value")
        if cmd == "get_status":
            return {"ok": True, **CFG, **STATS, "simulated": self.hw is None}
        if cmd == "brightness":
            CFG["brightness"] = max(-100, min(100, int(value)))
        elif cmd == "tilt":
            CFG["tilt"] = max(-30.0, min(30.0, float(value)))
            if self.hw and self.dev is not None:
                self.hw.set_tilt_degs(self.dev, CFG["tilt"])
        elif cmd == "led":
            if value not in LED_NAMES:
                return {"ok": False, "error": f"led must be one of {LED_NAMES}"}
            CFG["led"] = value
            if self.hw and self.dev is not None:
                self.hw.set_led(self.dev, getattr(self.hw, "LED_" + value.upper()))
        else:
            return {"ok": False, "error": f"unknown command {cmd!r}"}
        emit("kinect.status", {"changed": cmd, **CFG})
        return {"ok": True, **CFG}

    def body(self, dev, _ctx=None) -> None:
        """Called repeatedly from the capture loop - ZeroMQ work happens here."""
        self.dev = dev
        if self.ctl.poll(0):
            try:
                reply = self.control(json.loads(self.ctl.recv()))
            except (ValueError, TypeError, KeyError) as exc:
                reply = {"ok": False, "error": str(exc)}
            self.ctl.send_json(reply)
        while True:
            try:
                self.pub.send_multipart(OUT.get_nowait(), copy=False)
            except queue.Empty:
                break
        if not RUNNING.is_set():
            if self.hw:
                raise self.hw.Kill  # ends freenect.runloop()
            raise StopIteration

    def close(self) -> None:
        self.pub.close(linger=0)
        self.ctl.close(linger=0)
        self.context.term()


# --------------------------------------------------------------------------
def simulate(bridge: Bridge, fps: float = 30.0) -> None:
    """Synthetic scene: colour gradient + a 'person' walking towards the sensor."""
    yy, xx = np.mgrid[0:480, 0:640]
    t0 = time.time()
    next_frame = t0
    while True:
        now = time.time()
        if now >= next_frame:
            t = now - t0
            rgb = np.stack([(xx + int(t * 60)) % 256, yy * 255 // 479,
                            np.full_like(xx, 128)], axis=-1).astype(np.uint8)
            raw = np.full((480, 640), 1000, np.uint16)  # wall ~ 3 m
            dist_raw = int(700 + 250 * (1 + math.sin(t * 0.8)) / 2)  # person ~0.9 ... 2.4 m
            cx = int(320 + 150 * math.sin(t * 0.5))
            raw[120:440, max(cx - 60, 0):cx + 60] = dist_raw
            ts = int(t * 1e6)
            on_video(None, rgb, ts)
            on_depth(None, raw, ts)
            next_frame += 1 / fps
        bridge.body(None)
        time.sleep(0.002)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kinect v1 -> ZeroMQ bridge")
    parser.add_argument("--bind", default="tcp://*:5557")
    parser.add_argument("--control", default="tcp://127.0.0.1:5558")
    parser.add_argument("--jpeg", action="store_true", help="send RGB as JPEG (needs opencv-python)")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--audio-device", default=None, help="sounddevice index or name")
    parser.add_argument("--audio-channels", type=int, default=1)
    parser.add_argument("--simulate", action="store_true", help="no Kinect needed")
    args = parser.parse_args()
    CFG["jpeg"] = args.jpeg

    RUNNING.set()
    signal.signal(signal.SIGINT, lambda *_: RUNNING.clear())
    signal.signal(signal.SIGTERM, lambda *_: RUNNING.clear())

    freenect = None
    if not args.simulate:
        import freenect  # python3-freenect / libfreenect wrapper
    bridge = Bridge(args, freenect)

    stream = None
    if not args.no_audio and not args.simulate:
        try:
            import sounddevice as sd
            device = int(args.audio_device) if str(args.audio_device).isdigit() else args.audio_device
            stream = sd.InputStream(device=device, samplerate=16000, channels=args.audio_channels,
                                    dtype="int16", blocksize=1600, callback=on_audio)
            stream.start()
        except Exception as exc:  # audio is optional
            print(f"Audio disabled: {exc}")
            stream = None

    print(f"Kinect bridge ({'simulated' if args.simulate else 'libfreenect'}): "
          f"PUB {args.bind}, control {args.control} (Ctrl+C to stop)")
    try:
        if args.simulate:
            simulate(bridge)
        else:
            freenect.runloop(video=on_video, depth=on_depth, body=bridge.body)
    except StopIteration:
        pass
    finally:
        if stream is not None:
            stream.stop()
            stream.close()
        bridge.close()
        print("Kinect bridge stopped", STATS)


if __name__ == "__main__":
    main()
