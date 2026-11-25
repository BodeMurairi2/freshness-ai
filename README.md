# Freshness-ai

Freshness-ai tells you whether a fruit is **fresh or rotten** from a single photo.

## Video demo

YouTube: **<add the YouTube link here>**

## URLs

| | |
|---|---|
| Web app | https://freshness.bodemurairi.me |
| API | https://api.freshness.bodemurairi.me |

## Project description

Freshness-ai is a 16-class image classifier: 8 fruits (apple, banana, grape, guava, jujube, orange, pomegranate, strawberry), each either fresh or rotten. The model is a MobileNetV2 fine-tuned on 224×224 photos (see [notebook/freshness_ai.ipynb](notebook/freshness_ai.ipynb)).

The application has four pages:

- **Predict:** upload or take a photo and get the fruit, its condition, the confidence and the three most likely classes. Answers below 75% confidence are marked as uncertain. A Grad-CAM heatmap shows which parts of the photo the model relied on.
- **Models:** every model version with its training, validation and test metrics, training curves and confusion matrix, and a button to choose the model used for predictions.
- **Insights:** dataset class distribution, visual features of fresh and rotten fruit (colour, dark spots, brown areas), and the model's performance.
- **Retrain:** signed-in users upload labelled photos (saved in MongoDB and Cloudflare R2), then retrain the current model on them and follow the progress live. Each new model keeps a link to the model it was trained from.

Stack: FastAPI and TensorFlow (backend), React and Vite (frontend), MongoDB Atlas (database), Cloudflare R2 (image storage), Docker Compose with Caddy for HTTPS, hosted on AWS EC2.

## Model performance

Overall performance of the deployed model, `freshness-ai.keras`.

| Metric | Training (2,080 images) | Validation (480 images) | Test (640 images) |
|---|---|---|---|
| Accuracy | 99.33% | 96.25% | 98.59% |
| Precision | 99.42% | 97.45% | 98.61% |
| Recall | 98.99% | 95.63% | 98.59% |
| F1 score | 99.32% | 96.23% | 98.58% |
| Loss | 0.0448 | 0.1123 | – |
| ROC-AUC | – | – | 99.97% |

Training and validation values come from epoch 25, the epoch kept by early stopping (out of 30). Training values were measured with data augmentation on. On the test set, 9 of 640 photos were misclassified.

## Setup

### Requirements

- Python 3.13 and Node.js 20
- A MongoDB Atlas cluster (with your IP address in its network access list)
- A Cloudflare R2 bucket with a public development URL
- A Gmail address with an app password (sends the password reset codes)
- Docker and Docker Compose, only for deployment

### 1. Get the code

```bash
git clone https://github.com/BodeMurairi2/freshness-ai.git
cd freshness-ai
```

The trained model (`models/model/freshness-ai.keras`) and the train/validation/test images (`data/`) are included.

### 2. Configure the environment

```bash
cp .env.example .env
cp freshness_frontend/.env.example freshness_frontend/.env
```

Fill in every value marked `<...>` in `.env`: MongoDB, Cloudflare R2, JWT secret and Gmail. Each value is explained in the file.

### 3. Run the API

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

The API runs at http://localhost:8000. Set `DOCS_ENABLED=true` in `.env` to open the API documentation at http://localhost:8000/docs.

### 4. Run the frontend

In a second terminal:

```bash
cd freshness_frontend
npm install
npm run dev
```

Open http://localhost:5173.

### 5. Deploy with Docker (optional)

On a server with Docker, after steps 1 and 2:

1. Point two DNS A records at the server's IP address, one for the app and one for the API.
2. In `.env`, set `CORS_ALLOWED_ORIGINS` to the app's address, for example `["https://freshness.bodemurairi.me"]`.
3. Start the stack:

   ```bash
   APP_DOMAIN=freshness.example.com API_DOMAIN=api.freshness.example.com docker compose up -d --build
   ```

Without `APP_DOMAIN` and `API_DOMAIN`, the defaults are `freshness.bodemurairi.me` and `api.freshness.bodemurairi.me`. Caddy gets the HTTPS certificates automatically. Check the containers with `docker compose ps`.

## Results from the flood request simulation

The flood test uses [Locust](https://locust.io) ([locust/locustfile.py](locust/locustfile.py)). Each simulated user waits 1–3 seconds between requests. Out of every 15 requests, 10 are predictions, 1 is a Grad-CAM prediction, 2 open the models page and 2 open the insights page. The photos come from the test set.

Run it with any number of users:

```bash
bash locust/run_load_test.sh 50              # 50 users for 3 minutes
bash locust/run_load_test.sh 100 5m 10       # 100 users for 5 minutes, 10 new users per second
```

Each run saves a report in `locust/results/locust_rapport_<date>_<time>.csv`, with the number of users tested.

### 50 users for 3 minutes

The test ran against the deployed API on one AWS EC2 `c7i-flex.large` instance (2 vCPUs, 4 GB RAM), with 5 new users per second.

| Endpoint | Requests | Failures | Requests/s | Median | Average | 95th percentile | Max |
|---|---|---|---|---|---|---|---|
| `POST /predict` | 813 | 0 | 4.54 | 16.0 s | 14.7 s | 18.0 s | 19.9 s |
| `POST /predict/gradcam` | 89 | 0 | 0.50 | 19.0 s | 18.1 s | 22.0 s | 22.4 s |
| `GET /retrain/models/performance` | 181 | 0 | 1.01 | 0.47 s | 0.55 s | 1.0 s | 2.4 s |
| `GET /insights` | 165 | 0 | 0.92 | 0.48 s | 0.56 s | 0.99 s | 2.3 s |
| **All requests** | **1,248** | **0** | **6.97** | **15.0 s** | **11.0 s** | **19.0 s** | **22.4 s** |

All 1,248 requests succeeded. The server answered about 4.5 predictions per second, the most its 2 CPUs allow. With 50 users sending more than that, prediction requests waited in line, so the median prediction took 16 s. Page requests stayed under half a second at the median. Faster predictions under this load would need more CPUs, or more backend containers behind Caddy.

Full Locust output: [locust/results/](locust/results/).

## Contributing

Contributions are welcome.

1. Fork the repository and create a branch: `git checkout -b ft/your-feature`.
2. Make your changes and test them locally (steps 3 and 4 above).
3. Commit with a clear message, for example `feat: add a new fruit class`.
4. Push the branch and open a pull request describing what you changed and why.

To report a bug or suggest an idea, open an issue on GitHub.

## Author

**Bode Murairi**, GitHub: [BodeMurairi2](https://github.com/BodeMurairi2)
