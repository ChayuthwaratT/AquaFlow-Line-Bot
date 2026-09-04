import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("AQUAFLOW_BASE_URL")


def check_bill(meter_number):
    url = f"{BASE_URL}/api/v1/public/check"

    response = requests.get(
        url,
        params={"id": meter_number},
        timeout=10
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    return response.json()


def get_history(meter_number):
    url = f"{BASE_URL}/api/v1/public/history"

    response = requests.get(
        url,
        params={"id": meter_number},
        timeout=10
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    return response.json()