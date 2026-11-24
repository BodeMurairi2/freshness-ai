import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { CLASS_NAMES, percent } from "../data/classes";
import { ConfusionMatrix, F1PerClass } from "../components/Charts";
import Icon from "../components/Icon";
import TrainingCurves from "../components/TrainingCurves";
import NotebookFigures from "../components/NotebookFigures";
import { lineageOf } from "../data/lineage";

// metrics recorded during training (Keras names), shown for training and validation
const EPOCH_METRICS = [
  { key: "loss", label: "Loss", isLoss: true },
  { key: "accuracy", label: "Accuracy" },
  { key: "Precision", label: "Precision" },
  { key: "Recall", label: "Recall" },
  { key: "F1Score", label: "F1 score" },
  { key: "AUC", label: "ROC-AUC" },
];

const TEST_METRICS = [
  { key: "accuracy", label: "Accuracy" },
  { key: "precision", label: "Precision" },
  { key: "recall", label: "Recall" },
  { key: "f1", label: "F1 score" },
  { key: "auc_score", label: "ROC-AUC" },
];

function formatDate(value) {
  return value ? new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—";
}

function MetricTiles({ items }) {
  return (
    <div className="metric-grid">
      {items.map((item) => (
        <div key={item.label} className="card-soft">
          <span className="eyebrow">{item.label}</span>
          <div className="kpi-value" style={{ fontSize: 26 }}>{item.value}</div>
          {item.note && <span className="tiny muted">{item.note}</span>}
        </div>
      ))}
    </div>
  );
}

function epochTiles(history, epochIndex, prefix) {
  return EPOCH_METRICS
    .filter((metric) => history[`${prefix}${metric.key}`])
    .map((metric) => {
      const value = history[`${prefix}${metric.key}`][epochIndex];
      return { label: metric.label, value: metric.isLoss ? value.toFixed(3) : percent(value) };
    });
}

function testTiles(evaluation) {
  return TEST_METRICS.map((metric) => ({ label: metric.label, value: percent(evaluation[metric.key]) }));
}

function StepHeader({ number, eyebrow, title, text }) {
  return (
    <div className="row" style={{ alignItems: "flex-start", gap: 14 }}>
      <span className="step-badge">{number}</span>
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h2 style={{ marginTop: 2 }}>{title}</h2>
        {text && <p className="small muted" style={{ marginTop: 4 }}>{text}</p>}
      </div>
    </div>
  );
}

export default function ModelsPage() {
  const { isLoggedIn } = useAuth();
  const location = useLocation();
  const [models, setModels] = useState(null);
  const [performance, setPerformance] = useState([]);
  const [inspected, setInspected] = useState(null);
  const [switching, setSwitching] = useState(false);
  const [message, setMessage] = useState(null);

  const load = useCallback(async () => {
    try {
      const [modelList, modelPerformance] = await Promise.all([api.models(), api.modelPerformance()]);
      setModels(modelList);
      setPerformance(modelPerformance);
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function chooseModel(modelName) {
    setSwitching(true);
    setMessage(null);
    try {
      await api.selectModel(modelName);
      setMessage({ type: "success", text: `Predictions now use ${modelName}.` });
      await load();
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setSwitching(false);
    }
  }

  if (!models) {
    return (
      <main className="page">
        {message ? <div className="alert error">{message.text}</div> : <div className="skeleton" style={{ height: 420 }} />}
      </main>
    );
  }

  const performanceByName = Object.fromEntries(performance.map((item) => [item.model, item]));
  const modelNames = [models.latest, ...models.archived.filter((name) => name !== models.latest)];
  const serving = performanceByName[models.selected];
  const inspectedPerformance = performanceByName[inspected];

  return (
    <main className="page">
      <section className="hero page-header">
        <div>
          <span className="eyebrow">Model versions</span>
          <h1 style={{ marginTop: 6 }}>Models</h1>
          <p>Every trained model and how it scores on the same test images. Pick a version to see how it was trained, validated and tested.</p>
        </div>
      </section>

      {message && <div className={`alert ${message.type}`}><Icon name={message.type === "error" ? "alert" : "checkCircle"} />{message.text}</div>}

      <section className="card stack-large">
        <div className="row between" style={{ flexWrap: "wrap" }}>
          <div>
            <span className="eyebrow"><span className="live-dot" />Answering predictions</span>
            <h2 className="mono-text" style={{ fontSize: 20, marginTop: 4 }}>{models.selected}</h2>
            <p className="small muted" style={{ marginTop: 4 }}>
              {serving?.source === "notebook" ? "Trained in the notebook" : serving ? "Retrained in the app" : "No evaluation saved"}
              {" · "}{modelNames.length} version{modelNames.length === 1 ? "" : "s"}
              {serving && " · Test set results"}
            </p>
          </div>
          {serving && <span className="pill mono">{serving.test_evaluation.errors} errors of {serving.test_evaluation.test_images}</span>}
        </div>
        {serving && <MetricTiles items={testTiles(serving.test_evaluation)} />}
      </section>

      <section className="card stack">
        <div className="row between" style={{ flexWrap: "wrap" }}>
          <h2>All versions</h2>
          <span className="small muted">Use “Get insights” to see how a version was trained, validated and tested.</span>
        </div>
        <div className="table-scroll">
          <table className="versions-table">
            <thead>
              <tr>
                <th>Model</th><th>Origin</th><th>Date</th><th className="number">Epochs</th>
                <th className="number">Accuracy</th><th className="number">Precision</th><th className="number">Recall</th>
                <th className="number">F1</th><th className="number">ROC-AUC</th><th className="number">Errors</th><th>Status</th><th />
              </tr>
            </thead>
            <tbody>
              {modelNames.map((name) => {
                const modelPerformance = performanceByName[name];
                const scores = modelPerformance?.test_evaluation;
                return (
                  <tr key={name} className={inspected === name ? "active" : ""}>
                    <td><strong className="mono-text">{name}</strong></td>
                    <td>{modelPerformance ? (modelPerformance.source === "notebook" ? "Notebook" : "Retrained") : "—"}</td>
                    <td>{formatDate(modelPerformance?.created_at || modelPerformance?.evaluated_at)}</td>
                    <td className="number">{modelPerformance?.training?.epochs ?? "—"}</td>
                    {["accuracy", "precision", "recall", "f1", "auc_score"].map((key) => (
                      <td key={key} className={`number ${key === "accuracy" ? "strong" : ""}`}>{scores ? percent(scores[key]) : "—"}</td>
                    ))}
                    <td className="number">{scores ? `${scores.errors} / ${scores.test_images}` : "—"}</td>
                    <td>
                      <div className="row-wrap">
                        {name === models.selected && <span className="badge success">In use</span>}
                        {name === models.latest && <span className="badge neutral">Latest</span>}
                        {name !== models.selected && name !== models.latest && <span className="badge neutral">Archived</span>}
                      </div>
                    </td>
                    <td>
                      <button className={`button small ${inspected === name ? "primary" : "secondary"}`} disabled={!modelPerformance}
                        onClick={() => setInspected((current) => (current === name ? null : name))}>
                        <Icon name="chart" size={15} /> {inspected === name ? "Hide insights" : "Get insights"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {inspectedPerformance && (
        <ModelDetails key={inspected} name={inspected} modelPerformance={inspectedPerformance} inUse={inspected === models.selected}
          lineage={lineageOf(inspectedPerformance, performanceByName)}
          isLoggedIn={isLoggedIn} switching={switching} onChoose={() => chooseModel(inspected)}
          onClose={() => setInspected(null)} from={location.pathname} />
      )}
    </main>
  );
}

function UseModelButton({ inUse, isLoggedIn, switching, onChoose, from }) {
  if (inUse) return <span className="badge success">In use: answers predictions</span>;
  if (!isLoggedIn) {
    return <Link className="button secondary" to="/login" state={{ from }}><Icon name="lock" /> Log in to use this model</Link>;
  }
  return (
    <button className="button primary" disabled={switching} onClick={onChoose}>
      {switching ? <span className="spinner" /> : <Icon name="check" />} Use this model
    </button>
  );
}

const STEP_COUNT = 5;

function ModelDetails({ name, modelPerformance, lineage, inUse, isLoggedIn, switching, onChoose, onClose, from }) {
  const [revealedSteps, setRevealedSteps] = useState(1);
  const panel = useRef(null);
  const latestStep = useRef(null);

  // bring the panel into view when it opens, and each new step when it is revealed
  useEffect(() => { panel.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, []);
  useEffect(() => {
    if (revealedSteps > 1) latestStep.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [revealedSteps]);

  const training = modelPerformance.training;
  const history = training?.history;
  const keptEpoch = training?.best_epoch || history?.val_loss?.length || training?.epochs;
  const epochIndex = keptEpoch ? keptEpoch - 1 : 0;
  const evaluation = modelPerformance.test_evaluation;
  const f1PerClass = Object.fromEntries(Object.entries(evaluation.per_class).map(([className, scores]) => [className, scores.f1]));
  const useButton = <UseModelButton inUse={inUse} isLoggedIn={isLoggedIn} switching={switching} onChoose={onChoose} from={from} />;
  const stepRef = (step) => (step === revealedSteps ? latestStep : undefined);

  const steps = [
    <div key="training" className="card stack-large" ref={stepRef(1)}>
      <StepHeader number="1" eyebrow={history ? `Training set · epoch ${keptEpoch} of ${training.epochs}` : "Training set"}
        title="Training metrics"
        text={history ? "Scores on the photos the model learned from, at the epoch whose weights were kept." : "The epoch-by-epoch training history was not saved for this model."} />
      {history && <MetricTiles items={epochTiles(history, epochIndex, "")} />}
    </div>,
    <div key="validation" className="card stack-large" ref={stepRef(2)}>
      <StepHeader number="2" eyebrow={history ? `Validation set · epoch ${keptEpoch}` : "Validation set"} title="Validation metrics"
        text="Scores on photos held out from training, used to choose the epoch to keep." />
      {history ? (
        <MetricTiles items={epochTiles(history, epochIndex, "val_")} />
      ) : training?.final_validation ? (
        <MetricTiles items={[
          { label: "Loss", value: training.final_validation.loss.toFixed(3) },
          { label: "Accuracy", value: percent(training.final_validation.accuracy) },
        ]} />
      ) : <p className="small muted">No validation scores saved.</p>}
    </div>,
    <div key="curves" className="card stack-large" ref={stepRef(3)}>
      <StepHeader number="3" eyebrow="Epoch by epoch" title="Training curves"
        text="How training and validation scores evolved while the model was trained." />
      {history
        ? <TrainingCurves training={training} lineage={lineage} title="Training vs validation" />
        : <p className="small muted">The epoch-by-epoch history was not saved for this model.</p>}
      {modelPerformance.source === "notebook" && <div className="card-soft"><NotebookFigures title="Notebook figures" /></div>}
    </div>,
    <div key="test" className="card stack-large" ref={stepRef(4)}>
      <StepHeader number="4" eyebrow={`Test set results · ${evaluation.test_images} images · ${evaluation.errors} errors`} title="Test metrics"
        text="The final, unbiased check: how the model does on photos it has never seen." />
      <MetricTiles items={testTiles(evaluation)} />
    </div>,
    <div key="per-class" className="card stack-large" ref={stepRef(5)}>
      <StepHeader number="5" eyebrow="Test set · per class" title="Confusion matrix & F1 by class"
        text={`Rows are the true classes, columns what the model predicted. Green is correct, orange is a mistake (${evaluation.errors} in total).`} />
      <div className="split">
        <ConfusionMatrix matrix={evaluation.confusion_matrix} classNames={CLASS_NAMES} />
        <div className="stack">
          <span className="eyebrow">F1 by class · weakest first</span>
          <F1PerClass f1PerClass={f1PerClass} />
        </div>
      </div>
    </div>,
  ];

  return (
    <section className="stack-large insights-panel" ref={panel}>
      <div className="card row between" style={{ flexWrap: "wrap", gap: 14 }}>
        <div>
          <span className="eyebrow">Model insights</span>
          <h2 className="mono-text" style={{ fontSize: 20, marginTop: 4 }}>{name}</h2>
        </div>
        <div className="row-wrap">
          {useButton}
          <button className="button ghost" onClick={onClose}><Icon name="close" /> Close</button>
        </div>
      </div>

      {steps.slice(0, revealedSteps)}

      {revealedSteps < STEP_COUNT ? (
        <div className="show-more">
          <button className="button secondary" onClick={() => setRevealedSteps((count) => count + 1)}>
            <Icon name="chevronDown" /> Show more
          </button>
          <span className="tiny muted">Next: {["", "validation metrics", "training curves", "test metrics", "confusion matrix & F1 by class"][revealedSteps]}</span>
        </div>
      ) : (
        <div className="card row between" style={{ flexWrap: "wrap", gap: 14 }}>
          <div>
            <h3>{inUse ? "This model answers predictions" : "Use this model?"}</h3>
            <p className="small muted" style={{ marginTop: 4 }}>
              {inUse ? "Open another version above to compare it." : "Switching only changes which model answers predictions. Nothing is deleted, and you can switch back at any time."}
            </p>
          </div>
          {useButton}
        </div>
      )}
    </section>
  );
}
