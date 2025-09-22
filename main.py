import json
import os
import time
import traceback
from dotenv import load_dotenv
import requests
import bz2
import logging
from datetime import date
import csv

for name, value in os.environ.items():
    print("{0}: {1}".format(name, value))

today = date.today()
formatted_date = today.strftime("%Y-%m-%d")

logging.basicConfig(
    filename=f"{formatted_date}.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

REGION_MAP = {
    1: "US WEST",
    2: "US EAST",
    3: "EUROPE",
    5: "SINGAPORE",
    6: "DUBAI",
    7: "AUSTRALIA",
    8: "STOCKHOLM",
    9: "AUSTRIA",
    10: "BRAZIL",
    11: "SOUTHAFRICA",
    12: "PW SHANGHAI",
    13: "PW UNICOM",
    14: "CHILE",
    15: "PERU",
    16: "INDIA",
    17: "PW GUANGDONG",
    18: "PW ZHEJIANG",
    19: "JAPAN",
    20: "PW WUHAN",
    25: "PW TIANJIN",
    37: "TAIWAN",
    38: "ARGENTINA",
}

ALLOWED_REGION_IDS = {1, 2, 3, 8, 9}  # US WEST, US EAST, EUROPE, STOCKHOLM, AUSTRIA

load_dotenv()

REPLAY_PATH = os.getenv("REPLAY_PATH")
REPLAY_CSV = os.getenv("REPLAY_CSV")

if not REPLAY_PATH or not REPLAY_CSV:
    raise Exception(
        "You need to set local variables REPLAY_CSV and REPLAY_PATH in settings"
    )


def main():
    try:
        create_csv()
        latest_match_id = None
        while True:
            with open(REPLAY_CSV, mode="r") as file:
                csv_reader = csv.reader(file)
                my_list = [row[0] for row in csv_reader if row]

            if len(my_list) > 4:
                logger.debug(
                    f"Number of items in the list: {len(my_list)}. Not adding more."
                )
                time.sleep(600)
                continue

            publicMatches, new_latest_match_id = get_matches(latest_match_id)

            latest_match_id = new_latest_match_id
            if not publicMatches:
                continue

            download_replay(publicMatches)

    except Exception as ex:
        logger.error(f"An error occurred: {ex}\n{traceback.format_exc()}")


def create_csv():
    if not os.path.exists(REPLAY_CSV):
        with open(REPLAY_CSV, mode="w", newline="") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow([])

            logger.debug(f"Empty CSV file '{REPLAY_CSV}' has been created.")
    else:
        logger.debug(
            f"CSV file '{REPLAY_CSV}' already exists. No new file was created."
        )


def parse_replay(matchId):
    parseUrl = f"https://api.opendota.com/api/request/{matchId}"
    requests.post(parseUrl)


def download_replay(matches):
    matchGetUrl = "https://api.opendota.com/api/matches/"
    matchResponses = []

    for match in matches:
        matchId = match.get("match_id")

        currentMatchGetUrl = matchGetUrl + str(matchId)

        parseRequestSent = False

        while True:
            matchResponse = requests.get(currentMatchGetUrl)

            if matchResponse.status_code != 200:
                logger.error(
                    f"Error making get replay call {currentMatchGetUrl}. Status code: {matchResponse.status_code}"
                )
                return None

            matchResponseJson = matchResponse.json()

            if matchResponseJson and matchResponseJson.get("replay_url") is not None:
                matchResponses.append(matchResponseJson)
                break
            elif not parseRequestSent:
                logger.debug(
                    f"Request for match {matchId} failed due to not being parsed. Sending parse reqeust"
                )
                parse_replay(matchId)
                parseRequestSent = True
                time.sleep(10)
            else:
                logger.debug(
                    f"Match with id {matchId} is still not parsed. Waiting 60 seconds and trying again"
                )
                time.sleep(60)

    for match in matchResponses:
        replay_url = match.get("replay_url")
        match_id = match.get("match_id")

        if not replay_url:
            continue

        response = requests.get(replay_url, stream=True)

        if response.status_code != 200:
            logger.error(
                f"Error fetching replay from url {replay_url}. Status code: {response.status_code}"
            )
            continue

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

        with open(REPLAY_CSV, mode="r") as file:
            csv_reader = csv.reader(file)
            my_list = [row[0] for row in csv_reader if row]

        if match_id in my_list:
            logger.debug(f"The match '{match_id}' already exists in the list.")
        else:
            my_list.append(match_id)
            logger.debug(f"The match '{match_id}' was appended to the list.")

        with open(REPLAY_CSV, mode="w", newline="") as file:
            csv_writer = csv.writer(file)
            for item in my_list:
                csv_writer.writerow([item])

        logger.debug(f"Successfully downloaded and added {match_id} to replay list")


def delete_file(replay_file_name):
    os.remove(f"{REPLAY_PATH}\\{replay_file_name}")


def get_matches(last_match_id=None):
    url = "https://api.opendota.com/api/publicMatches"
    publicMatches = []

    while not publicMatches:
        params = {}
        if last_match_id:
            params["less_than_match_id"] = last_match_id

        exception_triggered = False
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.ConnectionError:
            logger.error("Failed to connect to the URL.")
            exception_triggered = True
        except requests.Timeout:
            logger.error("The request timed out.")
            exception_triggered = True
        except requests.RequestException as e:
            logger.error(f"An error occurred while making the request: {e}")
            exception_triggered = True
        except json.JSONDecodeError:
            logger.error("Failed to parse the response as JSON.")
            exception_triggered = True
        else:
            # First pass: your existing filters
            for publicMatch in data:
                last_match_id = publicMatch["match_id"]

                if (
                    publicMatch.get("lobby_type") == 7
                    and publicMatch.get("avg_rank_tier") is not None
                    and publicMatch["avg_rank_tier"] < 20
                ):
                    publicMatches.append(publicMatch)

            # Sort like before
            publicMatches = sorted(publicMatches, key=lambda x: x["avg_rank_tier"])

            # Second pass: fetch match details and keep only allowed regions
            filtered = []
            for m in publicMatches:
                match_id = m["match_id"]
                try:
                    detail_resp = requests.get(
                        f"https://api.opendota.com/api/matches/{match_id}"
                    )
                    # Handle rate limits gently
                    if detail_resp.status_code == 429:
                        time.sleep(1)
                        detail_resp = requests.get(
                            f"https://api.opendota.com/api/matches/{match_id}"
                        )
                    detail_resp.raise_for_status()
                    detail = detail_resp.json()
                except requests.ConnectionError:
                    logger.warning(
                        f"Failed to connect for match {match_id} – skipping."
                    )
                    continue
                except requests.Timeout:
                    logger.warning(
                        f"Timeout on details for match {match_id} – skipping."
                    )
                    continue
                except requests.RequestException as e:
                    logger.warning(f"Detail request failed for {match_id}: {e}")
                    continue
                except json.JSONDecodeError:
                    logger.warning(
                        f"Failed to parse details for {match_id} – skipping."
                    )
                    continue

                region_id = detail.get("region")
                if region_id in ALLOWED_REGION_IDS:
                    m = dict(m)
                    m["region_id"] = region_id
                    filtered.append(m)

                # small pause to be gentle to the API
                time.sleep(0.2)

            publicMatches = filtered

            time.sleep(1)

        if exception_triggered:
            time.sleep(60)

    if not publicMatches:
        return None

    return publicMatches, last_match_id


if __name__ == "__main__":
    main()

# pyinstaller --add-data "heroData.json;." --add-data "local_settings.py;." --add-data "background_white.jpg;."  main.py


# Available Input Kinds:
# image_source
# color_source
# slideshow
# browser_source
# ffmpeg_source
# text_gdiplus
# text_ft2_source
# vlc_source
# monitor_capture
# window_capture
# game_capture
# dshow_input
# wasapi_input_capture
# wasapi_output_capture
# wasapi_process_output_capture
