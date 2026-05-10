import requests
from requests.exceptions import RequestException


class ShadowDriveClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def check_health(self):
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=3
            )

            return response.status_code == 200

        except RequestException as e:
            print(f"[NETWORK ERROR] Health check failed: {e}")
            return False

    def announce_metadata(self, metadata):
        try:
            response = self.session.post(
                f"{self.base_url}/sync/announce",
                json=metadata,
                timeout=5
            )

            return response

        except RequestException as e:
            print(f"[NETWORK ERROR] Metadata announce failed: {e}")
            return None

    def upload_file(self, file_path, remote_path):
        try:
            with open(file_path, "rb") as f:

                files = {
                    "file": (remote_path, f)
                }

                response = self.session.post(
                    f"{self.base_url}/sync/upload",
                    files=files,
                    timeout=60
                )

                return response.status_code == 200

        except FileNotFoundError:
            print(f"[UPLOAD ERROR] File missing: {file_path}")
            return False

        except RequestException as e:
            print(f"[NETWORK ERROR] Upload failed: {e}")
            return False