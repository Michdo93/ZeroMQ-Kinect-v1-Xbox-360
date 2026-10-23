# ZeroMQ Kinect v1 for Ubuntu (Python)

Ubuntu/Python bridge for Xbox 360 Kinect v1. It streams color and depth through OpenKinect libfreenect, captures the Kinect microphone as a Linux ALSA input with sounddevice, and sends each stream over ZeroMQ. It offers a software brightness adjustment for RGB and libfreenect motor tilt/LED controls. This is Kinect v1, not Kinect v2.

## Install sensor support

Connect the Kinect's external power supply and USB 2.0. Install dependencies:

    sudo apt update
    sudo apt install -y git cmake build-essential libusb-1.0-0-dev libudev-dev python3-dev python3-venv python3-numpy python3-sounddevice alsa-utils
    git clone https://github.com/OpenKinect/libfreenect.git
    cd libfreenect
    mkdir build && cd build
    cmake .. -DBUILD_PYTHON3=ON
    make -j
    sudo make install
    sudo ldconfig
    cd ../..

Install and test Python ZeroMQ:

    python3 -m venv --system-site-packages .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

The system-site-packages option lets this environment use Ubuntu's freenect wrapper and sounddevice package. If your distribution packages libfreenect's wrapper separately, install its matching python3-freenect package instead. Add the project's udev rules or group access so your user can open Kinect USB devices without sudo; then log out/in. Do not use sudo pip.

## Audio device setup

List ALSA recording devices with arecord -l and sounddevice devices with:

    .venv/bin/python -m sounddevice

The Kinect microphone array may appear as a USB audio capture device. Note its device index and channel support; choose a supported input. You can test recording in ALSA before running the bridge. The Linux libfreenect Python wrapper does not expose libfreenect's audio API, so this project captures audio through ALSA/sounddevice. Audio firmware and device model can affect availability.

## Run / test

Terminal A:

    .venv/bin/python src/kinect_bridge.py

Terminal B:

    .venv/bin/python examples/monitor.py

The monitor prints metadata and payload sizes for kinect.color.rgb, kinect.depth.u16 and kinect.audio.pcm. If ALSA chooses the wrong microphone or reports unsupported channels, stop and pass the device index from the device list:

    .venv/bin/python src/kinect_bridge.py --audio-device 2

The bridge binds PUB tcp://*:5557 and control PULL tcp://127.0.0.1:5558. Ctrl+C stops it. Start subscriber first.

## Settings and controls

RGB brightness is software adjustment after capture, integer offset -100..100; it is not the Kinect camera's hardware brightness control. For example, while bridge runs:

    .venv/bin/python examples/control.py brightness 25

Set it back to neutral with brightness 0. Controls also include motor tilt in degrees (-30..30) and LED mode; exact LED values depend on libfreenect enums, so use standard values 0-6. Examples:

    .venv/bin/python examples/control.py tilt 10
    .venv/bin/python examples/control.py led 3

Control PUB/PULL is unauthenticated and loopback-only. Do not expose it on a public interface.

## Message format and customization

Every PUB message has three frames: UTF-8 topic, UTF-8 JSON metadata, then binary payload. RGB is packed RGB24; depth is little-endian uint16 depth data. Audio is int16 PCM at 16 kHz with channel count metadata. Color/depth callbacks copy data before queuing. Queue is bounded; overloaded capture drops new packets rather than blocking device callbacks. Edit image callback for brightness/gamma, choose alternative libfreenect modes there, or change bind addresses in CLI. RGB uses ~27 MB/s at 640x480x30; use topic filtering or lower resolution/fps for constrained links.

## Limits and troubleshooting

The Kinect v1 skeleton tracker is part of Microsoft's Windows SDK, not libfreenect; this Ubuntu project forwards RGB/depth/audio and does not claim skeleton frames. The Python libfreenect wrapper documents that audio is not implemented, hence separate ALSA capture. Brightness changes RGB pixels in software; hardware camera settings available in the Windows SDK are not exposed by this Linux backend. No device: check power, USB, udev permissions and libfreenect build. No audio: inspect arecord -l, select device, ensure audio firmware/driver works. References: https://github.com/OpenKinect/libfreenect ; Python wrapper notes: https://github.com/OpenKinect/libfreenect/blob/master/wrappers/python/freenect.pyx .
