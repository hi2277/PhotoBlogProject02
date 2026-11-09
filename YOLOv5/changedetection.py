import os
from datetime import datetime
from getpass import getpass
from pathlib import Path

import cv2
import requests


class ChangeDetection:
    def __init__(self, names):
        self.result_prev = [0] * len(names)
        self.host = os.environ.get(
            "PHOTOBLOG_HOST", "http://127.0.0.1:8000"
        ).rstrip("/")

        username = input("Django username [admin]: ").strip() or "admin"
        password = getpass("Django password: ")

        response = requests.post(
            self.host + "/api-token-auth/",
            data={"username": username, "password": password},
            timeout=15,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Login failed: HTTP {response.status_code}. "
                "Check your Django username and password."
            )

        self.token = response.json()["token"]
        print("Django login OK. Ready to upload detections.")

    def add(self, names, detected_current, save_dir, image):
        appeared = [
            names[i]
            for i in range(len(self.result_prev))
            if self.result_prev[i] == 0 and detected_current[i] == 1
        ]
        self.result_prev = detected_current[:]

        if appeared:
            self.send(save_dir, image, appeared)

    def send(self, save_dir, image, appeared):
        now = datetime.now().astimezone()
        folder = (
            Path(save_dir)
            / "detected"
            / now.strftime("%Y/%m/%d")
        )
        folder.mkdir(parents=True, exist_ok=True)
        image_path = folder / (now.strftime("%H%M%S_%f") + ".jpg")

        resized = cv2.resize(image, (320, 240))
        if not cv2.imwrite(str(image_path), resized):
            print("Could not save detection image.")
            return

        labels = ", ".join(appeared)
        data = {
            "title": "YOLO: " + labels,
            "text": "New objects detected: " + labels,
            "published_date": now.isoformat(),
        }
        headers = {
            "Authorization": "Token " + self.token,
            "Accept": "application/json",
        }

        try:
            with image_path.open("rb") as photo:
                response = requests.post(
                    self.host + "/api_root/Post/",
                    data=data,
                    files={"image": (image_path.name, photo, "image/jpeg")},
                    headers=headers,
                    timeout=15,
                )

            if response.status_code == 201:
                post_id = response.json().get("id")
                print(f"UPLOAD OK: HTTP 201, Post ID={post_id}, {labels}")
            else:
                print(f"UPLOAD FAILED: HTTP {response.status_code}")
                print(response.text[:300])
        except requests.RequestException as error:
            print(f"UPLOAD ERROR: {error}")
