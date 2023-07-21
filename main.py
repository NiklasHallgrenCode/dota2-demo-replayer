import importlib
import json
import os
import subprocess
import time
import traceback
import requests
import bz2
import logging
from datetime import date
from PIL import Image, ImageDraw, ImageFont
from DeferredProcess import DeferredProcess


today = date.today()
formatted_date = today.strftime("%Y-%m-%d")
print(formatted_date)
logging.basicConfig(
    filename=f"{formatted_date}.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

try:
    from local_settings import DOTA2_CLIENT_PATH, REPLAY_PATH, ISDEBUG
except ImportError:
    logger.error("Could not import original settings")

if os.path.exists("local_settings.py"):
    spec = importlib.util.spec_from_file_location(
        "local_settings", "./local_settings.py"
    )
    local_settings = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(local_settings)
    DOTA2_CLIENT_PATH = getattr(local_settings, "DOTA2_CLIENT_PATH", DOTA2_CLIENT_PATH)
    REPLAY_PATH = getattr(local_settings, "REPLAY_PATH", REPLAY_PATH)
    ISDEBUG = getattr(local_settings, "ISDEBUG", ISDEBUG)
else:
    logger.warning("Could not import local settings. Using original settings")


def download_replay(replay_url, match_id):
    response = requests.get(replay_url, stream=True)

    if response.status_code != 200:
        logger.error(
            f"Error fetching replay from url {replay_url}. Status code: {response.status_code}"
        )
        return None

    replay_download_path = f"{REPLAY_PATH}\\{match_id}.dem.bz2"
    with open(replay_download_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    extracted_replay_path = f"{REPLAY_PATH}\\{match_id}.dem"
    with bz2.open(replay_download_path, "rb") as source_file, open(
        extracted_replay_path, "wb"
    ) as dest_file:
        for data in iter(lambda: source_file.read(8192), b""):
            dest_file.write(data)

    delete_file(f"{match_id}.dem.bz2")

    return f"{match_id}.dem"


def delete_file(replay_file_name):
    os.remove(f"{REPLAY_PATH}\\{replay_file_name}")


def main():
    try:
        latest_match_id = None
        processesReplayFileNamesMatches = []
        with open("heroData.json", "r") as file:
            heroes = json.load(file)

        while True:
            match, replay_url, new_latest_match_id = get_random_match_and_replay_url(
                latest_match_id
            )

            latest_match_id = new_latest_match_id
            if not match or not replay_url:
                continue

            match_id = match["match_id"]

            replay_file_name = download_replay(replay_url, match_id)

            if not replay_file_name:
                continue

            process = DeferredProcess(), replay_file_name, match

            logger.debug(
                f"Successfully downloaded replay. Adding {replay_file_name} to queue"
            )

            process[0].set_command(
                f"{DOTA2_CLIENT_PATH} -console -novid +playdemo /replays/{replay_file_name} +demo_quitafterplayback 1 +dota_spectator_mode 3"
            )
            processesReplayFileNamesMatches.append(process)
            processToExecute = processesReplayFileNamesMatches[0][0]
            fileToDelete = None

            if len(processesReplayFileNamesMatches) > 1:
                if processToExecute.is_running():
                    processToExecute.wait()
                    fileToDelete = processesReplayFileNamesMatches[0][1]
                    del processesReplayFileNamesMatches[0]
                    processToExecute = processesReplayFileNamesMatches[0][0]

            if not processToExecute.is_running():
                match = processesReplayFileNamesMatches[0][2]
                generate_loadscreen_image(match, heroes)
                processToExecute.execute()
                if fileToDelete:
                    delete_file(fileToDelete)
    except Exception as ex:
        logger.error(f"An error occurred: {ex}\n{traceback.format_exc()}")


def get_lowest_average_rank_match(last_match_id=None):
    url = "https://api.opendota.com/api/publicMatches"
    publicMatches = []

    while not publicMatches:
        params = {}
        if last_match_id:
            params["less_than_match_id"] = last_match_id

        response = requests.get(url, params=params).json()

        if not response:
            break

        for publicMatch in response:
            last_match_id = publicMatch["match_id"]

            if (
                publicMatch.get("lobby_type") == 7
                and publicMatch.get("avg_mmr") is not None
                and publicMatch["avg_mmr"] < 500
            ):
                publicMatches.append(publicMatch)

        publicMatches = sorted(publicMatches, key=lambda x: x["avg_mmr"])

        # Avoid making too many requests in a short period
        time.sleep(1)

    if not publicMatches:
        return None

    return publicMatches[0], last_match_id


def get_random_match_and_replay_url(latest_match_id):
    matchResponse = None
    while not matchResponse:
        publicMatch, new_latest_match_id = get_lowest_average_rank_match(
            latest_match_id
        )
        latest_match_id = new_latest_match_id
        match_id = publicMatch["match_id"]
        cluster = publicMatch.get("cluster")

        matchUrl = f"https://api.opendota.com/api/matches/{match_id}"
        matchResponse = requests.get(matchUrl).json()

    replay_salt = matchResponse.get("replay_salt")

    if not cluster or not replay_salt:
        return None, None

    replay_url = (
        f"http://replay{cluster}.valve.net/570/{match_id}_{replay_salt}.dem.bz2"
    )
    return matchResponse, replay_url, new_latest_match_id


def generate_loadscreen_image(match, heroes):
    players = match.get("players")
    player_hero_ids = [player["hero_id"] for player in players]
    filtered_heroes = [hero for hero in heroes if hero["id"] in player_hero_ids]

    image = Image.open("background_white.jpg")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", 40)

    top = 50
    left = 50
    for x in range(10):
        position = (left, top)

        draw.text(position, filtered_heroes[x]["localized_name"], (0, 0, 0), font=font)

        if x == 4:
            top = 800
            left = 50
        else:
            left += 300

    current_dir = os.getcwd()
    imageName = f'tmpImg_{match["match_id"]}.png'
    image_path = os.path.join(current_dir, imageName)

    image.save(image_path)

    sleepTime = 3 if ISDEBUG else 45
    subprocess.Popen(["start", image_path], shell=True)
    time.sleep(sleepTime)
    os.system("taskkill /F /IM Microsoft.Photos.exe")


if __name__ == "__main__":
    main()

# pyinstaller --add-data "heroData.json;." --add-data "local_settings.py;." --add-data "background_white.jpg;."  main.py
