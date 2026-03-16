# Arma Reforger Queue Joiner

Simple tool that automatically retries joining full servers in Arma Reforger until you get into the queue.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## How to use

1. Run the program
2. In-game, go to the server browser and hover your mouse over the **Join** button of the server you want
3. Press **F6** (or whatever hotkey you chose)
4. The tool remembers the position and starts clicking for you
5. When the server is full → it auto-presses ESC and tries again
6. As soon as you get into the queue → it stops and plays a loud beep
7. Press **F4** to stop anytime

### Experimental Mode (new feature)
There is a checkbox called **"Experimental Mode: FAST ESC"**.  
When enabled, instead of pressing the ESC key, the program automatically finds the yellow "ESC" button on screen and clicks it with the mouse so it can be **faster**.


## Download

Please use the Releases section of this repository to download the latest build

## Run from source

```bash
git clone https://github.com/micorytican981/arma-queue-joiner.git
cd arma-queue-joiner
pip install -r requirements.txt
python app.py
