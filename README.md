# Dota 2 replay downloader

This project downloads recent Dota 2 replay demos from OpenDota and stores the
decompressed `.dem` files locally.

## Requirements

- Python 3.10+
- OpenDota API access (public endpoints)

## Setup

1. Create a `.env` file or set the following environment variables:
   - `REPLAY_PATH`: directory where `.dem` files should be stored.
   - `REPLAY_CSV`: CSV file that tracks downloaded match IDs.
2. Install dependencies:
   - `pip install -r requirements.txt` (or `pip install requests python-dotenv`).

## Run

```bash
python main.py
```

The script will:

- Fetch recent public matches from OpenDota.
- Filter matches by rank and region.
- Download and decompress replay demos.
- Track downloaded match IDs in the CSV file.
