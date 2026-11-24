import { useState } from "react";
import { percent } from "../data/classes";
import { LineChart } from "./Charts";

const CURVES = [
  { key: "loss", label: "Loss" },
  { key: "accuracy", label: "Accuracy" },
  { key: "Precision", label: "Precision" },
  { key: "Recall", label: "Recall" },
  { key: "F1Score", label: "F1 score" },
  { key: "AUC", label: "ROC-AUC" },
];

const formatValue = (key, value) => (value === null || value === undefined ? "—" : key === "loss" ? value.toFixed(3) : percent(value, 1));

// a retrained model continues from its parents: join each parent's kept epochs (oldest first), then this model's epochs
function fullPath(training, lineage) {
  const segments = [...lineage, training].map((segmentTraining, index, all) => {
    const history = segmentTraining.history || {};
    const isLast = index === all.length - 1;
    const recorded = history.val_loss?.length || segmentTraining.epochs || 0;
    return { history, epochs: isLast ? recorded : (segmentTraining.best_epoch || recorded) };
  });
  const starts = [];
  let total = 0;
  segments.forEach((segment) => { starts.push(total); total += segment.epochs; });
  return {
    retrainingStarts: starts.slice(1).map((start) => start + 1),
    keptEpoch: total - segments[segments.length - 1].epochs + (training.best_epoch || segments[segments.length - 1].epochs),
    values: (key) => segments.flatMap((segment) =>
      segment.history[key] ? segment.history[key].slice(0, segment.epochs) : Array(segment.epochs).fill(null)),
    hasEverywhere: (key) => segments.every((segment) => segment.history[key]),
  };
}

export default function TrainingCurves({ training, lineage = [], title = "Training vs validation" }) {
  const history = training?.history;
  const available = history
    ? CURVES.filter((curve) => [training, ...lineage].some((item) => item.history?.[curve.key] && item.history[`val_${curve.key}`]))
    : [];
  const [selected, setSelected] = useState(available[0]?.key);
  if (!history || !available.length) return null;

  const curve = available.find((item) => item.key === selected) || available[0];
  const path = fullPath(training, lineage);
  const ownKeptIndex = (training.best_epoch || history.val_loss?.length || training.epochs) - 1;
  const markers = [
    ...path.retrainingStarts.map((epoch, index) => ({ epoch, label: path.retrainingStarts.length > 1 ? `retraining ${index + 1}` : "retraining starts" })),
    { epoch: path.keptEpoch, label: `kept: epoch ${path.keptEpoch}` },
  ];
  const missingAuc = !path.hasEverywhere("AUC");
  const retrainings = path.retrainingStarts.length;

  return (
    <div className="stack-large">
      <div className="row between" style={{ flexWrap: "wrap" }}>
        <div>
          <span className="eyebrow">
            {retrainings
              ? `${path.retrainingStarts[0] - 1} epochs from the notebook · ${retrainings} retraining${retrainings === 1 ? "" : "s"} · this one: ${training.epochs} epoch${training.epochs === 1 ? "" : "s"} · learning rate ${training.learning_rate}`
              : `${training.epochs} epochs · learning rate ${training.learning_rate}`}
          </span>
          <h2 style={{ marginTop: 4 }}>{title}</h2>
          <p className="small muted" style={{ marginTop: 6 }}>
            Training curves use the photos the model learns from; validation curves use photos it never trains on.
            Curves that stay close mean the model is not just memorising.
            {retrainings > 0 && " A retrained model continues from the models before it, so its curves start with their training."}
          </p>
        </div>
        <div className="stepper" role="tablist" aria-label="Metric">
          {available.map((item) => (
            <button key={item.key} role="tab" aria-selected={item.key === curve.key} className={`step ${item.key === curve.key ? "current" : ""}`}
              onClick={() => setSelected(item.key)}>{item.label}</button>
          ))}
        </div>
      </div>

      <div className="training-layout">
        <div className="stack" style={{ gap: 8 }}>
          <div className="row-wrap small">
            <span className="row" style={{ gap: 6 }}><span className="legend-dot" style={{ background: "var(--green-600)" }} />Training</span>
            <span className="row" style={{ gap: 6 }}><span className="legend-dot" style={{ background: "var(--orange-500)" }} />Validation</span>
            <span className="muted tiny">x: epoch</span>
          </div>
          <LineChart isPercent={curve.key !== "loss"} markers={markers} series={[
            { label: "Training", values: path.values(curve.key), color: "var(--green-600)" },
            { label: "Validation", values: path.values(`val_${curve.key}`), color: "var(--orange-500)" },
          ]} />
        </div>
        <div className="stack">
          <span className="eyebrow">At the kept epoch ({path.keptEpoch})</span>
          <table>
            <thead><tr><th>Metric</th><th className="number">Train</th><th className="number">Validation</th></tr></thead>
            <tbody>
              {available.map((item) => (
                <tr key={item.key}>
                  <td>{item.label}</td>
                  <td className="number">{formatValue(item.key, history[item.key]?.[ownKeptIndex])}</td>
                  <td className="number strong">{formatValue(item.key, history[`val_${item.key}`]?.[ownKeptIndex])}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {missingAuc && (
            <p className="tiny muted">
              ROC-AUC was not recorded per epoch during the notebook training, so its curve only covers retraining epochs.
              The test ROC-AUC is always shown with the test metrics.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
