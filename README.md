# pyInkDisplay

My need was to display a Home Assistant dashboard on an e-ink display

![image](https://github.com/user-attachments/assets/8d20875c-5dad-4961-9875-134c08eebf63)

## Details
This project takes an image, either locally, or remotaly, and displays it on an e-ink display.

This was writter on a Raspberry Pi Zero W 2, using Waveshare's 7.3 inch 7 color e-ink display.

## Libraries
This project pulls in Rob Weber's [Omni-EPD](https://github.com/robweber/omni-epd/), so it "should" work with most e-ink displays.

I found this to be quite a dependancy nightmare, so included in the repo is a requirements.in. To use, follow this, preferably in a virtual environment:

1.  **Install `pip-tools`:** `pip install pip-tools`
2.  **Compile:** `pip-compile requirements.in`
3.  **Install:** `pip install -r requirements.txt`

## Systemd

I've added a basic systemd service template that can be used to run this on startup.

Here are the commands to manage your systemd service:

1.  **Reload:** `sudo systemctl daemon-reload` -  Reload the systemd daemon configuration.  This is necessary after creating or modifying a service file.

2.  **Enable:** `sudo systemctl enable pyInkDisplay.service` - Enable the service to start automatically at boot.

3.  **Start:** `sudo systemctl start pyInkDisplay.service` - Start the service immediately.

4.  **Status:** `sudo systemctl status pyInkDisplay.service` -  Show the current status of the service (running, stopped, errors, etc.).

5.  **Stop:** `sudo systemctl stop pyInkDisplay.service` - Stop the service.

6.  **Disable:** `sudo systemctl disable pyInkDisplay.service` - Prevent the service from starting automatically at boot.

## Similar work
This project was inspired by several e-ink display project including:

* [pycasso](https://github.com/jezs00/pycasso) - System to send AI generated art to an E-Paper display through a Raspberry PI unit.
* [PiArtFrame](https://github.com/runezor/PiArtFrame) - EPD project that displays randomly generated fractal art.
