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
        """Upload a file to the server.

        Week 4 Hardening (Scenario A & B):
            - 0-byte files: `open(file_path, "rb")` on a 0-byte file is
              valid and produces an empty bytes object. The `requests`
              library sends a valid multipart form with a Content-Length
              of 0 inside the file part. The server accepts this and
              writes a 0-byte file to disk. No special-casing needed here
              because the announce step already told the server not to
              expect an upload for 0-byte files (upload_required=False).
              This method will simply never be called for 0-byte files.
            - Network drops mid-upload: `requests` raises a
              `RequestException` (subclass: `ConnectionError`). We catch
              it, return False, and the event stays `is_synced=0` in
              SQLite. The next sync cycle re-announces (which detects the
              stale pending version) and re-tries the upload.
        """
        try:
            with open(file_path, "rb") as f:

                files = {
                    "file": (remote_path, f)
                }

                response = self.session.post(
                    f"{self.base_url}/sync/upload",
                    files=files,
                    timeout=120  # Week 4: Increased from 60s for large files
                )

                return response.status_code == 200

        except FileNotFoundError:
            print(f"[UPLOAD ERROR] File missing: {file_path}")
            return False

        except RequestException as e:
            print(f"[NETWORK ERROR] Upload failed: {e}")
            return False