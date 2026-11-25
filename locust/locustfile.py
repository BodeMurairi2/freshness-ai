import csv
import random
import time
from datetime import datetime
from pathlib import Path

from locust import HttpUser, between, events, task
from locust.runners import WorkerRunner

ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = ROOT / "data" / "test"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PHOTOS_PER_CLASS = 5
RESULTS_DIR = ROOT / "locust" / "results"
REPORT_COLUMNS = [
    "tested_at", "host", "users", "spawn_rate", "duration_s", "method", "endpoint",
    "requests", "failures", "failure_rate_%", "requests_per_s",
    "average_ms", "median_ms", "p95_ms", "p99_ms", "min_ms", "max_ms",
]
peak_users = 0


def load_test_photos() -> list[tuple[str, str, bytes]]:
    """(class name, file name, bytes) for a few test photos of every class, read once into memory"""
    photos = []
    for class_dir in sorted(path for path in TEST_DIR.iterdir() if path.is_dir()):
        image_paths = [path for path in sorted(class_dir.iterdir()) if path.suffix.lower() in IMAGE_EXTENSIONS]
        for image_path in image_paths[:PHOTOS_PER_CLASS]:
            photos.append((class_dir.name, image_path.name, image_path.read_bytes()))
    if not photos:
        raise SystemExit(f"No test photos found in {TEST_DIR}")
    return photos


TEST_PHOTOS = load_test_photos()


class FreshnessUser(HttpUser):
    wait_time = between(1, 3)  # seconds a user waits between two requests

    def send_photo(self, path: str, name: str):
        class_name, file_name, content = random.choice(TEST_PHOTOS)
        with self.client.post(path, files={"image": (file_name, content, "image/jpeg")},
                              name=name, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}: {response.text[:120]}")
                return
            answer = response.json()
            answer = answer.get("prediction", answer)  # the Grad-CAM answer wraps the prediction
            if not answer.get("fruit_name"):
                response.failure(f"no class in the answer for {class_name}/{file_name}")
            else:
                response.success()

    @task(10)
    def predict(self):
        self.send_photo("/predict/", "/predict")

    @task(1)
    def predict_with_gradcam(self):
        self.send_photo("/predict/gradcam", "/predict/gradcam")

    @task(2)
    def view_models(self):
        self.client.get("/retrain/models/performance", name="/retrain/models/performance")

    @task(2)
    def view_insights(self):
        self.client.get("/insights/", name="/insights")


@events.spawning_complete.add_listener
def remember_users(user_count, **kwargs):
    """Keeps the number of users reached, also when it is chosen on the web page"""
    global peak_users
    peak_users = max(peak_users, user_count)


def report_row(entry, run_details: dict, duration: float) -> dict:
    return {
        **run_details,
        "method": entry.method or "",
        "endpoint": entry.name,
        "requests": entry.num_requests,
        "failures": entry.num_failures,
        "failure_rate_%": round(100 * entry.fail_ratio, 2),
        "requests_per_s": round(entry.num_requests / duration, 2) if duration else 0,
        "average_ms": round(entry.avg_response_time),
        "median_ms": round(entry.median_response_time),
        "p95_ms": round(entry.get_response_time_percentile(0.95)),
        "p99_ms": round(entry.get_response_time_percentile(0.99)),
        "min_ms": round(entry.min_response_time or 0),
        "max_ms": round(entry.max_response_time),
    }


@events.test_stop.add_listener
def save_report(environment, **kwargs):
    """
    This function writes locust/results/locust_rapport_<timestamp>.csv when a test ends:
    one row per endpoint and a final "All requests" row, each with the number of users tested
    """
    global peak_users
    if isinstance(environment.runner, WorkerRunner) or environment.stats.total.num_requests == 0:
        return
    finished_at = datetime.now()
    duration = time.time() - environment.stats.total.start_time
    options = environment.parsed_options
    run_details = {
        "tested_at": finished_at.isoformat(timespec="seconds"),
        "host": environment.host,
        "users": peak_users or getattr(options, "num_users", 0),
        "spawn_rate": f"{getattr(options, 'spawn_rate', 0):g}",
        "duration_s": round(duration),
    }

    rows = [report_row(entry, run_details, duration)
            for entry in sorted(environment.stats.entries.values(), key=lambda entry: entry.name)]
    total_row = report_row(environment.stats.total, run_details, duration)
    total_row.update({"method": "ALL", "endpoint": "All requests"})
    rows.append(total_row)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / f"locust_rapport_{finished_at:%Y-%m-%d_%H-%M-%S}.csv"
    with open(report_path, "w", newline="") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Report for {run_details['users']} users saved to {report_path.relative_to(ROOT)}")
    peak_users = 0
