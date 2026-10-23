# ZeroMQ Kinect v1 (Xbox 360)

A Windows example capturing Kinect v1 color, depth, skeleton/joints and microphone audio to ZeroMQ PUB/SUB, plus a brightness control endpoint. This is Kinect v1, not Kinect v2.

## Prerequisites and install

You need the original Kinect sensor with external power, USB 2.0, Windows, Kinect for Windows SDK/runtime 1.8, and .NET Framework 4.8 build tools. Microsoft SDK 1.8 documents Windows 7/8/8.1 support; later versions may run legacy drivers but are outside that support matrix. Download SDK separately from https://www.microsoft.com/en-us/download/details.aspx?id=40278 . Disconnect sensor during SDK setup; connect external power and USB after installation. The proprietary SDK/driver is not included in this repo.

Build in PowerShell at repository root:

    dotnet restore KinectZmqBridge\KinectZmqBridge.csproj
    dotnet build KinectZmqBridge\KinectZmqBridge.csproj -c Release

The project references Microsoft.Kinect.dll via KINECTSDK10_DIR. If missing, set $env:KINECTSDK10_DIR to the SDK folder, commonly C:\Program Files\Microsoft SDKs\Kinect\v1.8\ . Keep x64 consistent. NetMQ and Newtonsoft restore from NuGet.

## Run and test

    dotnet run --project KinectZmqBridge\KinectZmqBridge.csproj

The bridge binds ZeroMQ PUB on tcp://*:5557 and brightness PULL control on tcp://127.0.0.1:5558. Ctrl+C stops it. Confirm the sensor is visible to the SDK before starting.

## Brightness adjustment

While bridge runs, camera brightness example:

    dotnet run --project examples\SetBrightness\SetBrightness.csproj -- 0.35

Valid range is 0.0–1.0 (SDK default about 0.2156). It sets the color camera property; auto exposure can affect perceived brightness. The SDK also exposes contrast, exposure, gain, gamma, hue, sharpness, white balance and saturation. The command socket is unauthenticated and loopback-only.

## Message contract

Each ZeroMQ event has three frames: topic UTF-8, metadata JSON UTF-8, binary payload. Topics: kinect.color.bgra (640x480 BGRA32), kinect.depth.u16 (320x240 little endian depth/player-index samples), kinect.skeleton.json (joint coordinates in meters), kinect.audio.pcm16 (mono 16 kHz PCM16LE), kinect.status. Color is uncompressed (~36 MB/s). Use a subscriber to decode data; this starter intentionally focuses on forwarding.

## Configuration, adaptation and troubleshooting

Set KINECT_ZMQ_PUB to change publisher bind, then update your subscriber. Change command port in bridge and command client together. Disable a modality by removing its stream Enable/event hook or audio startup. Choose another SDK stream format and update metadata/decoder. Depth is packed measurement data, not grayscale. No device: check power, USB, SDK driver and exclusivity. No audio: check audio driver/access. Build cannot find Microsoft.Kinect: install SDK and set KINECTSDK10_DIR. High throughput: filter topics or compress downstream.

References: official Kinect SDK 1.8 installer https://www.microsoft.com/en-us/download/details.aspx?id=40278 ; color settings and brightness ranges https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/jj663774%28v%3Dieb.10%29 ; audio beam interface https://learn.microsoft.com/en-us/previous-versions/windows/kinect-1.8/hh855320%28v%3Dieb.10%29 .