# pyInkDisplay

My need was to display a Home Assistant dashboard

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

## Similar work
This project was inspired by several e-ink display project including:

* [pycasso](https://github.com/jezs00/pycasso) - System to send AI generated art to an E-Paper display through a Raspberry PI unit.
* [PiArtFrame](https://github.com/runezor/PiArtFrame) - EPD project that displays randomly generated fractal art.
