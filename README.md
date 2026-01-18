# mbot2-gemini-bridge
A Python bridge for MBot2 to communicate with Google Gemini

This is a demonstration of a working Gemini integration on the CyberPi. There were several caveats to solve due to the limitations of the CyberPi. The primary issue of the CyberPi is its limited CPU power and low memory capacity.

## Limitations of the CyberPi

### MicroPyhton

The CyberPi runs a minimalistic version of Python, a.k.a. MicroPython, which is on one hand highly optimized to run on this small piece of hardware, but also comes with a huge lack of support in terms of libraries and capabilites.

### HTTPS

On of the first limitations during the project was the missing HTTPS support on the CyberPi. Whenever you try to contact a HTTPS endpoint, the CyberPi dies. This means, we need to proxy the requests via HTTP to HTTPS.

### Limited TTS engine

The TTS engine of the CyberPi may be capable of English and maybe Chinese, but thats it. The English output of a German or Frensh text for instance sounds horrible. This means, we need an external TTS engine

### Limited memory

The memory of the CyberPi is limited and if you want to download larger files, the CyberPi - you'll guess it - dies. This means, we have to use some streaming technology to play the TTS output.

### Threading

The CyberPi supports threads, but it has its limitations. Some calls, block, some not. Others run smoothly, while certain task just simply kill the CyberPi instantly. So, we need to make sure, that the program is structured to separate heavy working tasks into separate threads to keep the main thread alive.

### And many many more...

There are even more limitations, but we'll will not go into those any deeper...

# Preparation

To run the program on your CyberPi, MBot2 or MBotNeo you have to prepare some things. Follow the steps below and it should work for you.

# Gemini Proxy Setup

The project contains the Gemini Proxy, which proxies the HTTP requests from the Cyberpi via HTTPS to the Google Gemini API, so the CyberPi is not required to perform HTTPS.

## 📋 Prerequisites

* **Raspberry Pi** (3, 4, or 5) with Python 3.11+
* **Google Gemini API Key** (Get it at [aistudio.google.com](https://aistudio.google.com/))
* CyberPi and Raspberry Pi must be on the **same Wi-Fi network**.

## 🛠️ Installation
1. **Clone the repository:**

   ```bash
   git clone [https://github.com/methodus/mbot2-gemini-bridge](https://github.com/methodus/mbot2-gemini-bridge)
   cd mbot2-gemini-bridge
   ```

2. **Install dependencies:**

    ```bash
    pip install flask google-genai
    ```

## ⚙️ Configuration

The proxy requires three main configuration files in the root directory:

1. **config.toml (Technical Settings)**

    Create or rename the `config.example.toml` to this file to store your API keys and model parameters:

    ```toml
    [gemini]
    api_key = "YOUR_API_KEY_HERE"
    model_name = "gemini-2.5-flash"
    prompt_file = "system_prompt.txt"

    [parameters]
    temperature = 0.7

    [server]
    port = 5000
    ```

2. **localizations.json (UI Strings)**
    
    This file handles the translations for the mBot's display. Ensure it has the reset key and all movement actions:

    ```json
    {
        "german": {
            "listening": "Ich höre...",
            "reset": "Ich habe mein Gedächtnis zurückgesetzt.",
            "forward": "vor",
            ...
        },
        "english": {
            "listening": "I'm listening...",
            "reset": "I have reset my memory.",
            "forward": "forward",
            ...
        }
        ...
    }
    ```

3. **system_prompt.txt (AI Personality)**
    
    Define the mBot's behavior here. Use the system prompt exampl to act as a cool roboter which is targeted to a 10-year old child.

## 🏃 Starting the Proxy
Run the server with:

  ```bash
  python3 gemini-bridge.py
  ```

The server will be reachable at http://<your-pi-ip>:5000. Update the BASE_URL in your mBot's MicroPython script to this address.

# 🤖 mBot2 (CyberPi) Configuration Guide

This guide explains how to configure the MicroPython script on your CyberPi to communicate with the Raspberry Pi Proxy and control the robot's hardware.

## Copy cyberpi_gemini_client.py

Copy the `cyberpi_gemini_client.py` into the mBlock software into the Python tab.

## ⚙️ Configuration Section

In the main Python script on your mBot2, locate the `CONFIGURATION` block at the top. Adjust these variables to match your setup:

```python
# --- CONFIGURATION ---
# Apply your changes here.

PROXY_HOST_NAME = "hostname"  # The hostname or IP of your Raspberry Pi
LANGUAGE = "german"            # Options: "german", "english", "french"
ALLOW_MOVEMENT = False         # Set to True to enable wheels (forward, backward, etc.)
IS_SMART_WORLD_GRIPPER = True  # Set to True if the "Smart World" gripper is installed
```

### 🔍 Variable Breakdown

|Variable|Description|
|--------|-----------|
|PROXY_HOST_NAME|The network address of your Raspberry Pi. If your Pi is named servberry.local, enter that here.|
|LANGUAGE|Determines which dictionary the mBot fetches from the proxy via /init.|
|ALLOW_MOVEMENT|Safety switch. If False, the mBot will ignore movement commands (left, right, etc.) to prevent falling off tables during testing.|
|IS_SMART_WORLD_GRIPPER|Enables/Disables commands for the CyberPi Smart World add-on. If True, the robot will execute up, down, open, and close.|

## 🏃 Starting the CyberPi

Connect your CyberPi via USB or Bluetooth Dongle to your PC, select the "Upload" mode and copy the program to your CyberPi

# ⌨️ Controls

Button B: Press to talk. You have 3 seconds to record your question to the AI.
Button A: Press to immediately stop the current speech or movement (Emergency Stop).

# ⚠️ Troubleshooting

WiFi Error: Ensure the CyberPi is connected to the same network as the Raspberry Pi.

Response Lag: This is usually due to network latency or the time Gemini takes to process the request.

No Movement: Check if ALLOW_MOVEMENT is set to True and the battery is sufficiently charged.
