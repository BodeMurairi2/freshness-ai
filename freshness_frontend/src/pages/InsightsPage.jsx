import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, DECISION_THRESHOLD } from "../api/client";
import { BarList, F1PerClass } from "../components/Charts";
import TrainingCurves from "../components/TrainingCurves";
import NotebookFigures from "../components/NotebookFigures";
import { lineageOf } from "../data/lineage";
import { CLASS_NAMES, FRUITS, percent, readableClass } from "../data/classes";
import Icon from "../components/Icon";

const SECTIONS = ["All", "Dataset", "Model"];

export default function InsightsPage() {
  const [insights, setInsights] = useState(null);
  const [error, setError] = useState(null);
  const [section, setSection] = useState("All");

  useEffect(() => {
    api.insights().then(setInsights).catch((requestError) => setError(requestError.message));
  }, []);


  return (
    <main className="page">
      <section className="hero page-header">
        <div>
          <span className="eyebrow">Model &amp; dataset insights</span>
          <h1 style={{ marginTop: 6 }}>Insights</h1>
        </div>
        <div className="stepper" role="tablist" aria-label="Insight sections">
          {SECTIONS.map((name) => (
            <button key={name} role="tab" aria-selected={section === name} className={`step ${section === name ? "current" : ""}`} onClick={() => setSection(name)}>
              {name}
            </button>
          ))}
        </div>
      </section>

      {error && <div className="alert error"><Icon name="alert" />{error}</div>}
      {!insights && !error && <div className="skeleton" style={{ height: 480 }} />}
      {insights && (
        <>
          <ArchitectureCard model={insights.model} />
          <TestMetrics model={insights.model} />
          <KeyNumbers insights={insights} />
          {section === "All" && (
            <>
              {insights.model.training?.history && (
                <section className="card"><TrainingCurves training={insights.model.training} lineage={insights.model.lineage_training || []} /></section>
              )}
              <section className="card"><NotebookFigures /></section>
              <section className="grid grid-2" style={{ alignItems: "start" }}>
                <DatasetCard dataset={insights.dataset} />
                <ModelCard model={insights.model} />
              </section>
              <ImagesPerClass dataset={insights.dataset} />
              {insights.dataset.features && <DatasetFeatures features={insights.dataset.features} />}
            </>
          )}
          {section === "Dataset" && (
            <>
              <section className="insights-pair">
                <DatasetCard dataset={insights.dataset} />
                <ImagesPerClass dataset={insights.dataset} />
              </section>
              {insights.dataset.features && <DatasetFeatures features={insights.dataset.features} />}
            </>
          )}
          {section === "Model" && (
            <>
              {insights.model.training?.history && (
                <section className="card"><TrainingCurves training={insights.model.training} lineage={insights.model.lineage_training || []} /></section>
              )}
              <section className="card"><NotebookFigures /></section>
              <ModelCard model={insights.model} />
            </>
          )}
        </>
      )}
    </main>
  );
}

function KeyNumbers({ insights }) {
  const { dataset, model, usage } = insights;
  const weekTotal = usage.last_7_days.reduce((sum, day) => sum + day.predictions, 0);
  const selectedVersion = model.versions.find((version) => version.model === model.selected_model);
  return (
    <section className="grid grid-4">
      <div className="kpi">
        <span className="eyebrow">Test set</span>
        <div className="kpi-title">Test accuracy</div>
        <div className="kpi-value">{model.accuracy !== undefined && model.accuracy !== null ? percent(model.accuracy) : "—"}</div>
        <div className="kpi-sub">{selectedVersion ? `${selectedVersion.errors} errors out of ${dataset.split_totals.test} test images` : "Not evaluated yet"}</div>
      </div>
      <div className="kpi">
        <span className="eyebrow">Dataset</span>
        <div className="kpi-title">Training images</div>
        <div className="kpi-value">{dataset.total_images.toLocaleString()}</div>
        <div className="kpi-sub">16 classes, {dataset.images_per_class.fresh_apple ? Object.values(dataset.images_per_class.fresh_apple).reduce((sum, count) => sum + count, 0) : 200} images each</div>
      </div>
      <div className="kpi">
        <span className="eyebrow">Usage</span>
        <div className="kpi-title">Predictions (last 7 days)</div>
        <div className="kpi-value">{weekTotal.toLocaleString()}</div>
        <div className="kpi-sub">{usage.total_predictions.toLocaleString()} in total</div>
      </div>
      <div className="kpi">
        <span className="eyebrow">Safety threshold</span>
        <div className="kpi-title">Uncertain predictions</div>
        <div className="kpi-value" style={{ color: usage.refusal_rate > 0.15 ? "var(--orange-700)" : undefined }}>
          {usage.total_predictions ? percent(usage.refusal_rate, 1) : "—"}
        </div>
        <div className="kpi-sub">Below {percent(DECISION_THRESHOLD, 0)} confidence: {usage.refused} photo{usage.refused === 1 ? "" : "s"}</div>
      </div>
    </section>
  );
}

function DatasetCard({ dataset }) {
  const splits = [
    { name: "Train", count: dataset.split_totals.train, color: "var(--green-700)" },
    { name: "Validation", count: dataset.split_totals.validation, color: "var(--green-500)" },
    { name: "Test", count: dataset.split_totals.test, color: "var(--green-200)" },
  ];
  const uploads = Object.entries(dataset.uploads_per_class).sort((first, second) => second[1] - first[1]);
  return (
    <div className="card stack-large">
      <div>
        <span className="eyebrow">Dataset · {dataset.total_images.toLocaleString()} images</span>
        <h2 style={{ marginTop: 4 }}>Split &amp; class balance</h2>
        <p className="small muted" style={{ marginTop: 6 }}>Every class has the same number of photos, so the model is not biased towards any fruit or condition.</p>
      </div>
      <div className="stack" style={{ gap: 8 }}>
        <div className="row between small"><strong>Split</strong>
          <span className="muted number">{splits.map((split) => Math.round((split.count / dataset.total_images) * 100)).join(" / ")}%</span>
        </div>
        <div className="split-bar">{splits.map((split) => <div key={split.name} style={{ flex: split.count, background: split.color }} />)}</div>
        <div className="row-wrap small">{splits.map((split) => (
          <span key={split.name} className="row" style={{ gap: 6 }}><span className="legend-dot" style={{ background: split.color }} />{split.name} <strong>{split.count.toLocaleString()}</strong></span>
        ))}</div>
      </div>
      <div className="grid grid-2" style={{ gap: 10 }}>
        <div className="card-soft"><span className="eyebrow">Fresh</span><div className="kpi-value" style={{ fontSize: 24 }}>{dataset.condition_totals.fresh.toLocaleString()}</div><span className="tiny muted">8 fruits</span></div>
        <div className="card-soft"><span className="eyebrow">Rotten</span><div className="kpi-value" style={{ fontSize: 24, color: "var(--orange-700)" }}>{dataset.condition_totals.rotten.toLocaleString()}</div><span className="tiny muted">8 fruits</span></div>
      </div>
      <div className="stack">
        <div className="row between"><strong className="small">Uploaded for retraining</strong><span className="badge neutral">+{dataset.total_uploads}</span></div>
        {uploads.length ? (
          <BarList items={uploads.map(([className, count]) => ({ label: readableClass(className), value: count }))} scaleEnd={uploads[0][1]} />
        ) : (
          <p className="small muted">No uploads yet. Registered users can add labelled photos on the <Link to="/retrain">Retrain</Link> page.</p>
        )}
      </div>
    </div>
  );
}

function ModelCard({ model }) {
  if (!model.f1_per_class) {
    return <div className="card empty">No evaluation saved yet for {model.selected_model}.</div>;
  }
  const scores = Object.entries(model.f1_per_class).sort((first, second) => first[1] - second[1]);
  return (
    <div className="card stack-large">
      <div>
        <span className="eyebrow">Test set · per class</span>
        <h2 style={{ marginTop: 4 }}>F1 score by class</h2>
      </div>
      <F1PerClass f1PerClass={model.f1_per_class} />
      <div className="row between small muted">
        <span>Min {percent(scores[0][1], 1)}</span>
        <span>Macro F1 {percent(model.f1, 1)}</span>
        <span>{scores.filter(([, value]) => value >= 0.9999).length} classes perfect</span>
      </div>
    </div>
  );
}

function ArchitectureCard({ model }) {
  const facts = [
    { label: "Backbone", value: "MobileNetV2", note: "Pre-trained on ImageNet, fine-tuned head" },
    { label: "Input", value: "224 × 224 × 3", note: "Photos resized to 512 px, then 224 px" },
    { label: "Explanation", value: "Grad-CAM", note: "Last convolution layer (out_relu)" },
    { label: "Safety threshold", value: percent(DECISION_THRESHOLD, 0), note: "Below it, the answer is marked as uncertain" },
  ];
  return (
    <section className="card stack-large">
      <div className="row between" style={{ flexWrap: "wrap" }}>
        <div>
          <span className="eyebrow">Model</span>
          <h2 style={{ marginTop: 4 }}>Architecture &amp; reproducibility</h2>
        </div>
        <span className="pill mono">{model.selected_model}</span>
      </div>
      <div className="grid grid-4">
        {facts.map((fact) => (
          <div key={fact.label} className="card-soft">
            <span className="eyebrow">{fact.label}</span>
            <div className="strong" style={{ fontSize: 18, marginTop: 4 }}>{fact.value}</div>
            <span className="tiny muted">{fact.note}</span>
          </div>
        ))}
      </div>
      <ModelHistory model={model} />
    </section>
  );
}

// every model version, each with a button to see how that model was trained
function ModelHistory({ model }) {
  const [openModel, setOpenModel] = useState(null);
  const [performance, setPerformance] = useState(null);
  const [error, setError] = useState(null);

  async function toggleHistory(modelName) {
    if (openModel === modelName) {
      setOpenModel(null);
      return;
    }
    setOpenModel(modelName);
    if (!performance) {
      try {
        setPerformance(await api.modelPerformance());
      } catch (requestError) {
        setError(requestError.message);
      }
    }
  }

  const performanceByName = Object.fromEntries((performance || []).map((item) => [item.model, item]));
  const opened = performanceByName[openModel];

  return (
    <div className="stack">
      <strong className="small">Model history · test accuracy</strong>
      <div className="history-list">
        {model.versions.map((version) => (
          <div key={version.model} className={`history-row ${openModel === version.model ? "open" : ""}`}>
            <span className="mono-text">{version.model.replace(".keras", "")}</span>
            <div className="bar-track"><div style={{ width: `${Math.max(2, ((version.accuracy - 0.9) / 0.1) * 100)}%` }} /></div>
            <span className="number strong">{percent(version.accuracy)}</span>
            <button className={`button small ${openModel === version.model ? "primary" : "secondary"}`} onClick={() => toggleHistory(version.model)}>
              <Icon name="chart" size={15} /> {openModel === version.model ? "Hide training history" : "See training history"}
            </button>
          </div>
        ))}
      </div>
      {openModel && (
        <div className="card-soft">
          {error ? <div className="alert error">{error}</div>
            : !performance ? <div className="skeleton" style={{ height: 260 }} />
            : opened?.training?.history ? (
              <TrainingCurves key={openModel} training={opened.training}
                lineage={lineageOf(opened, performanceByName)}
                title={`Training history · ${openModel.replace(".keras", "")}`} />
            ) : <p className="small muted">No epoch-by-epoch training history was saved for {openModel}.</p>}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------ images per class and split
const SPLIT_COLORS = { train: "var(--green-700)", validation: "var(--green-500)", test: "var(--green-200)" };

function ImagesPerClass({ dataset }) {
  const perClass = CLASS_NAMES.map((className) => ({ className, counts: dataset.images_per_class[className] || {} }));
  const totals = perClass.map(({ counts }) => (counts.train || 0) + (counts.validation || 0) + (counts.test || 0));
  const balanced = totals.every((total) => total === totals[0]);
  return (
    <section className="card stack-large">
      <div className="row between" style={{ flexWrap: "wrap" }}>
        <div>
          <span className="eyebrow">Dataset · per class</span>
          <h2 style={{ marginTop: 4 }}>Images per class and split</h2>
          <p className="small muted" style={{ marginTop: 6 }}>
            {balanced
              ? `All 16 classes have exactly ${totals[0]} images, split the same way, so no fruit or condition dominates training or testing.`
              : "Image counts per class: an unbalanced class can bias the model towards it."}
          </p>
        </div>
        <div className="row-wrap small">
          {Object.entries(SPLIT_COLORS).map(([split, color]) => (
            <span key={split} className="row" style={{ gap: 6 }}><span className="legend-dot" style={{ background: color }} />{split.charAt(0).toUpperCase() + split.slice(1)}</span>
          ))}
        </div>
      </div>
      <div className="class-split-grid">
        {perClass.map(({ className, counts }, index) => (
          <div key={className} className="class-split">
            <div className="row between small"><strong>{readableClass(className)}</strong><span className="muted number">{totals[index]}</span></div>
            <div className="split-bar thin">
              {["train", "validation", "test"].map((split) => (
                <div key={split} title={`${split}: ${counts[split] || 0}`} style={{ flex: counts[split] || 0, background: SPLIT_COLORS[split] }} />
              ))}
            </div>
            <span className="tiny muted number">{counts.train || 0} / {counts.validation || 0} / {counts.test || 0}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

// ------------------------------------------------------------ visual features of the photos
// expected direction when fruit rots: duller colours, more dark spots, more brown
const EXPECTED_DIRECTION = { saturation: -1, dark_share: 1, brown_share: 1 };

function featureStory(name, perFruit) {
  const direction = EXPECTED_DIRECTION[name];
  const following = perFruit.filter((item) => Math.sign(item.rotten - item.fresh) === direction);
  const averageFresh = perFruit.reduce((sum, item) => sum + item.fresh, 0) / perFruit.length;
  const averageRotten = perFruit.reduce((sum, item) => sum + item.rotten, 0) / perFruit.length;
  const strongest = [...following].sort((first, second) =>
    direction < 0 ? first.rotten / first.fresh - second.rotten / second.fresh : second.rotten / second.fresh - first.rotten / first.fresh)[0];
  const exceptions = perFruit.filter((item) => !following.includes(item)).map((item) => item.fruit.toLowerCase());

  if (name === "saturation") {
    const drop = Math.round((1 - averageRotten / averageFresh) * 100);
    return `Rotten fruit is duller for ${following.length} of ${perFruit.length} fruits: ${drop}% less colourful on average`
      + (strongest ? `, most for ${strongest.fruit.toLowerCase()} (${Math.round((1 - strongest.rotten / strongest.fresh) * 100)}% less).` : ".")
      + (exceptions.length ? ` Not for ${exceptions.join(" and ")}.` : "");
  }
  const what = name === "dark_share" ? "dark spots" : "brown areas";
  return `Rotten photos show more ${what} for ${following.length} of ${perFruit.length} fruits`
    + (strongest ? `, most for ${strongest.fruit.toLowerCase()} (×${(strongest.rotten / Math.max(strongest.fresh, 0.0001)).toFixed(1)}).` : ".")
    + (exceptions.length ? ` The opposite for ${exceptions.join(", ")}.` : "");
}

function DatasetFeatures({ features }) {
  return (
    <section className="stack-large">
      <div>
        <span className="eyebrow">Dataset · what the photos look like</span>
        <h2 style={{ marginTop: 4 }}>Three visual features: fresh vs rotten</h2>
        <p className="small muted" style={{ marginTop: 6, maxWidth: 820 }}>
          Measured on the {features.images.toLocaleString()} training photos. No single feature separates fresh from rotten for
          every fruit, which is why the model learns its own features instead of a simple colour rule (see what it looks at
          with Grad-CAM on the Predict page).
        </p>
      </div>
      <div className="grid grid-3" style={{ alignItems: "start" }}>
        {Object.entries(features.features).map(([name, description]) => {
          const perFruit = FRUITS.map((fruit) => ({
            fruit: fruit.name,
            fresh: features.per_class[`fresh_${fruit.key}`]?.[name] ?? 0,
            rotten: features.per_class[`rotten_${fruit.key}`]?.[name] ?? 0,
          }));
          const peak = Math.max(...perFruit.flatMap((item) => [item.fresh, item.rotten]), 0.0001);
          const asPercent = name !== "saturation";
          const format = (value) => (asPercent ? `${(value * 100).toFixed(1)}%` : value.toFixed(2));
          return (
            <div key={name} className="card stack">
              <span className="eyebrow">{description.unit}</span>
              <h3 style={{ fontSize: 17 }}>{description.label}</h3>
              <p className="small muted">{description.description}</p>
              <div className="row-wrap tiny">
                <span className="row" style={{ gap: 5 }}><span className="legend-dot" style={{ background: "var(--green-500)" }} />Fresh</span>
                <span className="row" style={{ gap: 5 }}><span className="legend-dot" style={{ background: "var(--orange-500)" }} />Rotten</span>
              </div>
              <div className="pair-list">
                {perFruit.map((item) => (
                  <div key={item.fruit} className="pair-row">
                    <span className="small">{item.fruit}</span>
                    <div className="pair-bars">
                      <div className="bar-track"><div style={{ width: `${(item.fresh / peak) * 100}%` }} /></div>
                      <div className="bar-track"><div className="weak" style={{ width: `${(item.rotten / peak) * 100}%` }} /></div>
                    </div>
                    <span className="tiny number muted pair-values">{format(item.fresh)}<br />{format(item.rotten)}</span>
                  </div>
                ))}
              </div>
              <div className="insight-note">{featureStory(name, perFruit)}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ------------------------------------------------------------ test metrics of the current model
const TEST_METRICS = [
  { key: "accuracy", label: "Accuracy", note: "Share of test photos classified correctly" },
  { key: "precision", label: "Precision", note: "When it names a class, how often it is right" },
  { key: "recall", label: "Recall", note: "How many photos of each class it finds" },
  { key: "f1", label: "F1 score", note: "Balance of precision and recall" },
  { key: "auc_score", label: "ROC-AUC", note: "How well it ranks the right class first" },
];

function TestMetrics({ model }) {
  if (model.accuracy === undefined || model.accuracy === null) return null;
  const selectedVersion = model.versions.find((version) => version.model === model.selected_model);
  return (
    <section className="card stack-large">
      <div className="row between" style={{ flexWrap: "wrap" }}>
        <div>
          <span className="eyebrow">Test set · never seen in training</span>
          <h2 style={{ marginTop: 4 }}>How the current model performs</h2>
        </div>
        <span className="pill mono">{model.selected_model}{selectedVersion ? ` · ${selectedVersion.errors} errors` : ""}</span>
      </div>
      <div className="metric-grid">
        {TEST_METRICS.map((metric) => (
          <div key={metric.key} className="card-soft">
            <span className="eyebrow">{metric.label}</span>
            <div className="kpi-value" style={{ fontSize: 26 }}>{percent(model[metric.key])}</div>
            <span className="tiny muted">{metric.note}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
