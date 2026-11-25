import { useRef, useState } from "react";
import { Link } from "react-router";
import { api, DECISION_THRESHOLD } from "../api/client";
import { capitalize, checkImageFile, FRUITS, percent, readableClass, SAMPLE_PHOTOS } from "../data/classes";
import Icon from "../components/Icon";
import "./PredictPage.css";

const GUIDELINES = [
  { icon: "eye", title: "Whole fruit with the skin visible", text: "The model learned from whole, uncut fruit. Cut or peeled fruit is outside what it knows." },
  { icon: "scan", title: "One kind of fruit per photo", text: "A single subject keeps the model focused on one fruit instead of splitting its attention." },
  { icon: "sun", title: "Good, even light", text: "Avoid strong shadows, glare and blur: they hide the skin texture the model relies on." },
];

const REFUSAL_REASONS = [
  { title: "Blurred, dark or overexposed photo", text: "Poor light hides the skin texture the model needs." },
  { title: "The fruit is cut, peeled or opened", text: "The model was trained on whole fruit only." },
  { title: "Not one of the 8 supported fruits", text: "Other fruits or objects are outside what it learned." },
  { title: "Several fruits or a busy background", text: "Clutter splits the model's attention." },
];

export default function PredictPage() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function analyse(file) {
    const problem = checkImageFile(file);
    if (problem) {
      setError(`${file.name}: ${problem}. Use JPG, PNG, WEBP or HEIC up to 10 MB.`);
      return;
    }
    setError(null);
    setLoading(true);
    try {
      setResult(await api.predictWithGradcam(file));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function analyseSample(sample) {
    const response = await fetch(sample.path);
    const blob = await response.blob();
    analyse(new File([blob], `${sample.name.toLowerCase()}.jpg`, { type: "image/jpeg" }));
  }

  if (result) {
    return <ResultView result={result} onReset={() => setResult(null)} />;
  }

  return (
    <main className="page">
      <section className="hero">
        <div className="row-wrap" style={{ marginBottom: 14 }}>
          <span className="pill mono"><span className="live-dot" />8 fruits · 16 classes</span>
          <span className="pill mono">98.59% test accuracy</span>
          <span className="pill mono">Explained with Grad-CAM</span>
        </div>
        <h1>Is your fruit fresh or rotten?</h1>
        <p className="muted" style={{ marginTop: 10, maxWidth: 640 }}>
          Upload a photo of one fruit. Freshness-ai tells you the fruit, its condition and how sure it is, and shows
          what it looked at to decide.
        </p>
      </section>

      <section className="split">
        <UploadCard loading={loading} error={error} onFile={analyse} onSample={analyseSample} />
        <HowItWorks />
      </section>

      <section className="stack">
        <span className="eyebrow">What the model knows</span>
        <div className="row between" style={{ flexWrap: "wrap" }}>
          <h2>Works with 8 fruits (16 fresh &amp; rotten classes)</h2>
          <span className="small muted">Trained on 3,200 photos, 200 per class</span>
        </div>
        <div className="fruit-grid">
          {FRUITS.map((fruit) => (
            <div key={fruit.key} className="fruit-tile">
              <img src={`/fruits/${fruit.key}.jpg`} alt="" loading="lazy" />
              <strong>{fruit.name}</strong>
              <span className="tiny muted">Fresh · Rotten</span>
            </div>
          ))}
        </div>
      </section>

      <section className="stack">
        <span className="eyebrow">For the best result</span>
        <h2>How to take the photo</h2>
        <div className="grid grid-3">
          {GUIDELINES.map((guideline, index) => (
            <div key={guideline.title} className="card stack">
              <span className="guideline-icon"><Icon name={guideline.icon} size={20} /></span>
              <h3><span className="muted number">0{index + 1}</span> {guideline.title}</h3>
              <p className="small muted">{guideline.text}</p>
            </div>
          ))}
        </div>
      </section>

      <p className="tiny muted" style={{ textAlign: "center" }}>
        <Icon name="lock" size={12} /> Photos may be kept, without any personal information, to improve the model.
      </p>
    </main>
  );
}

function UploadCard({ loading, error, onFile, onSample }) {
  const fileInput = useRef(null);
  const cameraInput = useRef(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) onFile(file);
  }

  function handleChosen(event) {
    const file = event.target.files?.[0];
    if (file) onFile(file);
    event.target.value = "";
  }

  return (
    <div className="card stack-large">
      <div className="row between">
        <span className="eyebrow"><span className="live-dot" />Check a fruit</span>
        <span className="pill mono">{loading ? "Analysing…" : "Ready"}</span>
      </div>

      <div className={`dropzone ${dragging ? "dragging" : ""}`}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)} onDrop={handleDrop}>
        {loading ? (
          <div className="stack" style={{ alignItems: "center" }}>
            <span className="spinner dark" style={{ width: 34, height: 34 }} />
            <strong>Analysing your photo…</strong>
            <span className="small muted">Predicting and computing the Grad-CAM heatmap</span>
          </div>
        ) : (
          <>
            <span className="dropzone-icon"><Icon name="upload" size={24} /></span>
            <div>
              <h3>Drag &amp; drop your fruit photo here</h3>
              <p className="small muted">or choose a file from your device</p>
            </div>
            <div className="row-wrap" style={{ justifyContent: "center" }}>
              <button className="button primary" onClick={() => fileInput.current.click()}><Icon name="image" /> Choose a file</button>
              <button className="button secondary" onClick={() => cameraInput.current.click()}><Icon name="camera" /> Take a photo</button>
            </div>
            <p className="tiny muted">JPG, PNG, WEBP or HEIC · up to 10 MB</p>
          </>
        )}
        <input ref={fileInput} type="file" accept="image/*,.heic,.heif" hidden onChange={handleChosen} />
        <input ref={cameraInput} type="file" accept="image/*" capture="environment" hidden onChange={handleChosen} />
      </div>

      {error && <div className="alert error"><Icon name="alert" />{error}</div>}

      <div className="row-wrap">
        <span className="eyebrow">Try a sample:</span>
        {SAMPLE_PHOTOS.map((sample) => (
          <button key={sample.name} className="pill sample-button" disabled={loading} onClick={() => onSample(sample)}>
            <img src={sample.path} alt="" /> {sample.name}
          </button>
        ))}
      </div>
    </div>
  );
}

function HowItWorks() {
  return (
    <div className="card stack-large">
      <span className="eyebrow">How it works</span>
      <ol className="steps-list">
        <li><strong>Prediction.</strong> A MobileNetV2 model, fine-tuned on 3,200 fruit photos, scores the 16 classes.</li>
        <li><strong>Safety threshold.</strong> If it is less than {percent(DECISION_THRESHOLD, 0)} sure, the answer is marked as uncertain.</li>
        <li><strong>Explanation.</strong> A Grad-CAM heatmap shows which parts of the photo mattered most.</li>
        <li><strong>Improvement.</strong> Registered users can add labelled photos and retrain the model.</li>
      </ol>
      <div className="alert info"><Icon name="info" />Predictions need no account. <Link to="/insights">See how the model performs →</Link></div>
    </div>
  );
}

function ResultView({ result, onReset }) {
  const prediction = result.prediction;
  const answered = prediction.status;
  const [showHeatmap, setShowHeatmap] = useState(answered);
  const [heatmapOpacity, setHeatmapOpacity] = useState(0.55);
  const [showOtherClasses, setShowOtherClasses] = useState(!answered);
  const [topClass, ...otherClasses] = prediction.top_classes || [];
  const confidence = topClass?.probability ?? 0;

  return (
    <main className="page">
      <div className="row between" style={{ flexWrap: "wrap" }}>
        <button className="button ghost" onClick={onReset}>← Check another fruit</button>
        <span className={`badge ${answered ? "success" : "unsure"}`}>
          {answered ? "Prediction complete" : "Uncertain prediction"} · {prediction.latency_ms} ms
        </span>
      </div>

      <section className="split">
        <div className="card stack">
          <div className="row between" style={{ flexWrap: "wrap" }}>
            <div className="segmented" role="tablist">
              <button role="tab" aria-selected={!showHeatmap} className={!showHeatmap ? "on" : ""} onClick={() => setShowHeatmap(false)}>
                <Icon name="image" size={15} /> Photo
              </button>
              <button role="tab" aria-selected={showHeatmap} className={showHeatmap ? "on" : ""} onClick={() => setShowHeatmap(true)}>
                <Icon name="eye" size={15} /> What the model saw
              </button>
            </div>
            {showHeatmap && (
              <label className="row small" style={{ gap: 8 }}>
                <span className="eyebrow">Heatmap</span>
                <input type="range" min="0" max="1" step="0.05" value={heatmapOpacity}
                  onChange={(event) => setHeatmapOpacity(Number(event.target.value))} aria-label="Heatmap opacity" />
                <span className="number strong" style={{ width: 38 }}>{Math.round(heatmapOpacity * 100)}%</span>
              </label>
            )}
          </div>

          <div className="photo-frame">
            <img src={result.photo_image} alt="Your photo" />
            {showHeatmap && <img className="heatmap-layer" src={result.heatmap_image} alt="" style={{ opacity: heatmapOpacity }} />}
            {showHeatmap && <span className="photo-tag">Grad-CAM · {readableClass(result.explained_class)}</span>}
          </div>

          {showHeatmap && (
            <div className="stack" style={{ gap: 6 }}>
              <div className="heat-scale" />
              <div className="row between tiny muted"><span>Less important</span><span>Most important</span></div>
              {!answered && (
                <p className="small muted">
                  The heatmap explains the top guess ({readableClass(result.explained_class).toLowerCase()}). Scattered attention
                  usually means the model could not find clear fruit features.
                </p>
              )}
            </div>
          )}
        </div>

        <div className="stack-large">
          {answered ? (
            <div className="card stack">
              <div className="row between">
                <span className="eyebrow">Model classification</span>
                <span className={`badge ${prediction.fruit_condition}`}>{capitalize(prediction.fruit_condition)}</span>
              </div>
              <h1 className="verdict">{capitalize(prediction.fruit_condition)} {prediction.fruit_name}</h1>
              <ConfidenceMeter confidence={confidence} />
            </div>
          ) : (
            <div className="card stack">
              <div className="row between">
                <span className="eyebrow">Low confidence</span>
                <div className="row-wrap">
                  <span className={`badge ${prediction.fruit_condition}`}>{capitalize(prediction.fruit_condition)}</span>
                  <span className="badge unsure">Uncertain</span>
                </div>
              </div>
              <span className="small muted">Most likely</span>
              <h1 className="verdict" style={{ marginTop: -8 }}>{capitalize(prediction.fruit_condition)} {prediction.fruit_name}</h1>
              <p className="small muted">AI models can be inaccurate.</p>
              <ConfidenceMeter confidence={confidence} />
            </div>
          )}

          <div className="card stack">
            <button className="row between disclosure" onClick={() => setShowOtherClasses((open) => !open)} aria-expanded={showOtherClasses}>
              <span className="eyebrow">{answered ? "Other possibilities" : "All possibilities"}</span>
              <Icon name={showOtherClasses ? "chevronUp" : "chevronDown"} />
            </button>
            {showOtherClasses ? (
              <div className="stack">
                {[topClass, ...otherClasses].map((item, index) => (
                  <ProbabilityRow key={item.class_name} rank={index + 1} item={item} />
                ))}
                <div className="row between small muted">
                  <span>All fresh classes <strong className="number">{percent(prediction.fresh_probability, 1)}</strong></span>
                  <span>All rotten classes <strong className="number">{percent(prediction.rotten_probability, 1)}</strong></span>
                </div>
              </div>
            ) : (
              <p className="small muted">See the next two most likely classes.</p>
            )}
          </div>

          {!answered && (
            <div className="card stack">
              <span className="eyebrow">Why this might have happened</span>
              {REFUSAL_REASONS.map((reason) => (
                <div key={reason.title} className="reason">
                  <Icon name="info" size={16} />
                  <div><strong className="small">{reason.title}</strong><p className="tiny muted">{reason.text}</p></div>
                </div>
              ))}
            </div>
          )}

          <div className="card-soft row between small" style={{ flexWrap: "wrap" }}>
            <span className="muted">Model <strong className="mono-text">{prediction.model}</strong></span>
            <span className="muted">Time <strong className="number">{prediction.latency_ms} ms</strong></span>
          </div>

          <button className="button primary full" onClick={onReset}><Icon name="camera" /> {answered ? "Check another fruit" : "Try another photo"}</button>
        </div>
      </section>
    </main>
  );
}

function ConfidenceMeter({ confidence }) {
  const passed = confidence >= DECISION_THRESHOLD;
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row between">
        <span className="eyebrow">Confidence</span>
        <span className={`confidence-value ${passed ? "" : "low"}`}>{percent(confidence)}</span>
      </div>
      <div className="meter">
        <div className={`meter-fill ${passed ? "" : "warning"}`} style={{ width: `${confidence * 100}%` }} />
        <div className="meter-marker" style={{ left: `${DECISION_THRESHOLD * 100}%` }} title="Decision threshold" />
      </div>
      <div className="row between tiny muted">
        <span>0%</span><span>{percent(DECISION_THRESHOLD, 0)} threshold</span><span>100%</span>
      </div>
    </div>
  );
}

function ProbabilityRow({ rank, item }) {
  return (
    <div className="stack" style={{ gap: 5 }}>
      <div className="row between small">
        <span><span className="muted number">{rank}.</span> <strong>{readableClass(item.class_name)}</strong></span>
        <span className="number strong">{percent(item.probability)}</span>
      </div>
      <div className="bar-track"><div className={item.fruit_condition === "rotten" ? "weak" : ""} style={{ width: `${Math.max(1, item.probability * 100)}%` }} /></div>
    </div>
  );
}
