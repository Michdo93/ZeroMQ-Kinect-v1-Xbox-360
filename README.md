# ZeroMQ Kinect v1 (Xbox 360) for Linux (Python)

Streams **RGB, depth and microphone audio** of the Xbox 360 Kinect (v1) with **ZeroMQ** – about 46 MB/s of binary frames at 30 fps – to any number of consumers, plus a control channel for brightness, motor tilt and LED.

Companion example of the book *From Zero to Hero – ZeroMQ in Python meistern* (chapter "Two things MQTT cannot do (well)").

```
                         PUB tcp://*:5557  [topic, json-meta, binary]
 Kinect ─ libfreenect ─ kinect_bridge.py ─┬─ kinect.rgb   (27 MiB/s) ──► viewer.py
          ALSA mic  ──┘                    ├─ kinect.depth (18 MiB/s) ──► presence.py ── presence.zone ──► smart home
                                           ├─ kinect.audio             └► monitor.py
                                           └─ kinect.status
                         REP tcp://127.0.0.1:5558 ◄── control.py (brightness, tilt, led, status)
```

`--simulate` produces a synthetic scene (moving colour gradient, a "person" walking towards the sensor) with the same message format – everything can be tried without a Kinect.

## 1. Hardware

Kinect v1 (model 1414 or 1473) with its **external power supply / USB adapter** – USB power alone is not enough. Use a USB 2.0 port or a USB 3 port with good USB 2 compatibility.

## 2. Install libfreenect + Python wrapper

Ubuntu packages (simplest):

```bash
sudo apt update
sudo apt install -y freenect python3-freenect python3-numpy python3-venv
freenect-glview          # test: shows RGB + depth
```

Or build from source (newest version):

```bash
sudo apt install -y git cmake build-essential libusb-1.0-0-dev python3-dev python3-numpy cython3
git clone https://github.com/OpenKinect/libfreenect.git
cd libfreenect && mkdir build && cd build
cmake .. -DBUILD_PYTHON3=ON
make -j"$(nproc)" && sudo make install && sudo ldconfig
```

Access without `sudo`: install the udev rule from `libfreenect/platform/linux/udev/51-kinect.rules` to `/etc/udev/rules.d/`, add yourself to the `plugdev` and `video` groups and log in again.

## 3. This project

```bash
git clone https://github.com/Michdo93/ZeroMQ-Kinect-v1-Xbox-360.git
cd ZeroMQ-Kinect-v1-Xbox-360
python3 -m venv --system-site-packages .venv     # sees the apt package python3-freenect
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Microphone (optional)

The libfreenect Python wrapper has no audio API, so the bridge records through ALSA (`sounddevice`). The Kinect only appears as a USB audio device after its **audio firmware** has been uploaded (`audios.bin`, extracted from Microsoft's Kinect SDK with libfreenect's `fwfetcher.py`, uploaded by `kinect_upload_fw` or a udev rule). Then:

```bash
arecord -l                         # Kinect listed as capture device?
python -m sounddevice              # find its index
python src/kinect_bridge.py --audio-device 3 --audio-channels 4   # 4-mic array
```

Without firmware start the bridge with `--no-audio`.

## 5. Run

```bash
python src/kinect_bridge.py             # real Kinect   (add --jpeg to send RGB as JPEG, ~25x smaller)
python src/kinect_bridge.py --simulate  # no hardware
```

Consumers in other terminals:

```bash
python examples/monitor.py                 # msg/s, MiB/s and latency per stream
python examples/viewer.py                  # RGB + colour-mapped depth (needs opencv-python)
python examples/presence.py                # near / medium / far / empty events on :5559
python examples/control.py status
python examples/control.py brightness 25   # -100 ... 100 (software offset)
python examples/control.py tilt 10         # -30 ... 30 degrees (motor)
python examples/control.py led blink_green # off|green|red|yellow|blink_green|blink_red_yellow
```

## Message format

Three frames: `[topic, UTF-8 JSON metadata, binary payload]`; metadata always contains `t_pub_us`.

| Topic | Payload | Size / rate |
|-------|---------|-------------|
| `kinect.rgb` | RGB24 640×480 (`format: rgb24`) or JPEG (`format: jpeg`) | 900 KiB (≈40 KiB JPEG) @ 30 fps |
| `kinect.depth` | uint16 little endian, 640×480, 11-bit raw disparity (2047 = invalid) | 600 KiB @ 30 fps |
| `kinect.audio` | PCM int16, 16 kHz, `channels` from metadata | 1600 frames per message |
| `kinect.status` | – | on change |

Convert raw depth to metres (common approximation): `d = 0.1236 * tan(raw / 2842.5 + 1.1863)`.

## Design notes

* `freenect.runloop()` owns the main thread. The video/depth callbacks only enqueue copies; the `body` callback is the **only** place that touches ZeroMQ sockets. Ctrl+C sets a flag, `body` raises `freenect.Kill` → clean exit.
* `SNDHWM=30` on the publisher and `RCVHWM=2` in the viewer: a slow consumer drops old frames instead of lagging behind or filling RAM. `ZMQ_CONFLATE` would be even stricter but does not support multipart messages.
* `presence.py` shows the typical *data reduction* stage: 18 MiB/s in, a few bytes per minute out, with hysteresis to avoid flapping at zone borders.
* The skeleton tracking of Kinect v1 is part of Microsoft's Windows SDK, not of libfreenect – this project forwards RGB/depth/audio only.

## Troubleshooting

* `ModuleNotFoundError: freenect` – install `python3-freenect` and create the venv with `--system-site-packages`.
* `Could not open device` / no frames – power supply connected? udev rule / group membership? Another program (e.g. `freenect-glview`) still running?
* Viewer lags – use `--jpeg` or reduce consumers on slow links; check `monitor.py`.
* `Address already in use` – another bridge is running.
