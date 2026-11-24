import { useCallback, useEffect, useRef, useState } from "react";
import { api, RETRAIN_MAX_EPOCHS, RETRAIN_MIN_IMAGES } from "../api/client";
import { CLASS_NAMES, checkImageFile, percent, readableClass } from "../data/classes";
import { BarList } from "../components/Charts";
import Icon from "../components/Icon";
import "./RetrainPage.css";

const STEPS = ["Add images", "Retrain", "Compare"];
const STAGES = [
  { key: "preparing data", label: "Preparing data" },
  { key: "evaluating current model", label: "Evaluating the current model" },
  { key: "training", label: "Training" },
  { key: "validating", label: "Validating" },
  { key: "evaluating new model", label: "Evaluating the new model" },
  { key: "saving model", label: "Saving the model" },
];
const POLL_EVERY_MILLISECONDS = 1500;

export default function RetrainPage() {
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState(null);
  const [queue, setQueue] = useState(null);

  const refreshQueue = useCallback(async () => {
    try {
      const insights = await api.insights();
      setQueue({ total: insights.dataset.total_uploads, perClass: insights.dataset.uploads_per_class, servingModel: insights.model.selected_model });
    } catch {
      setQueue({ total: 0, perClass: {}, servingModel: null });
    }
  }, []);

  // the page follows the server: a running retraining opens step 2
  useEffect(() => {
    refreshQueue();
    api.retrainingStatus().then((currentStatus) => {
      setStatus(currentStatus);
      if (currentStatus.state === "running") setStep(1);
    }).catch(() => {});
  }, [refreshQueue]);

  const canCompare = status?.state === "done" && status?.result;

  return (
    <main className="page">
      <section className="hero page-header">
        <div>
          <span className="eyebrow">Fine-tuning the model</span>
          <h1 style={{ marginTop: 6 }}>Retrain the model</h1>
          <p>Add labelled fruit photos, retrain the model on them together with the original dataset, then compare the new model with the current one.</p>
        </div>
        <ol className="stepper" aria-label="Retraining steps">
          {STEPS.map((label, index) => {
            const available = index === 0 || (index === 1 && status && status.state !== "idle") || (index === 2 && canCompare);
            return (
              <li key={label}>
                <button className={`step ${step === index ? "current" : ""} ${index < step ? "done" : ""}`}
                  disabled={!available} onClick={() => setStep(index)} aria-current={step === index ? "step" : undefined}>
                  <span className="step-number">{index < step ? <Icon name="check" size={14} /> : index + 1}</span>
                  {label}
                </button>
              </li>
            );
          })}
        </ol>
      </section>

      {step === 0 && (
        <AddImagesStep queue={queue} onUploaded={refreshQueue}
          onStarted={(startedStatus) => { setStatus(startedStatus); setStep(1); }} />
      )}
      {step === 1 && (
        <ProgressStep status={status} onStatus={setStatus} onFinished={() => { setStep(2); refreshQueue(); }} onBack={() => setStep(0)} />
      )}
      {step === 2 && canCompare && <CompareStep status={status} onNewRun={() => setStep(0)} />}
    </main>
  );
}

// ------------------------------------------------------------ step 1: add images
let nextIdentifier = 1;
const newGroup = (label = "") => ({ id: nextIdentifier++, label, images: [] });

function AddImagesStep({ queue, onUploaded, onStarted }) {
  const [groups, setGroups] = useState(() => [newGroup()]);
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [chosenEpochs, setChosenEpochs] = useState("");
  const [message, setMessage] = useState(null);

  // free the preview URLs when images leave the page
  const previewUrls = useRef(new Set());
  useEffect(() => () => previewUrls.current.forEach((url) => URL.revokeObjectURL(url)), []);

  const usedLabels = groups.map((group) => group.label).filter(Boolean);
  const readyImages = groups.flatMap((group) => group.label
    ? group.images.filter((image) => !image.problem).map((image) => ({ file: image.file, label: group.label })) : []);
  const readyClasses = new Set(readyImages.map((image) => image.label)).size;
  const excluded = groups.reduce((count, group) => count + group.images.filter((image) => image.problem).length, 0);

  function updateGroup(groupId, change) {
    setGroups((current) => current.map((group) => (group.id === groupId ? { ...group, ...change(group) } : group)));
  }

  function addFiles(groupId, files) {
    const added = Array.from(files).map((file) => {
      const previewUrl = URL.createObjectURL(file);
      previewUrls.current.add(previewUrl);
      return { id: nextIdentifier++, file, previewUrl, problem: checkImageFile(file) };
    });
    updateGroup(groupId, (group) => ({ images: [...group.images, ...added] }));
  }

  function removeImage(groupId, imageId) {
    updateGroup(groupId, (group) => ({ images: group.images.filter((image) => image.id !== imageId) }));
  }

  function clearAll() {
    setGroups([newGroup()]);
    setMessage(null);
  }

  // returns true when the staged images were saved on the server
  async function uploadAll() {
    setUploading(true);
    setMessage(null);
    try {
      const response = await api.uploadTrainingImages(readyImages);
      setMessage({ type: "success", text: response.message });
      setGroups([newGroup()]);
      await onUploaded();
      return true;
    } catch (error) {
      setMessage({ type: "error", text: error.message });
      return false;
    } finally {
      setUploading(false);
    }
  }

  // staged images are uploaded first, so one click is enough
  async function startRetraining() {
    if (readyImages.length > 0 && !(await uploadAll())) return;
    setStarting(true);
    setMessage(null);
    try {
      await api.startRetraining(chosenEpochs ? Number(chosenEpochs) : null);
      onStarted(await api.retrainingStatus());
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setStarting(false);
    }
  }

  const waiting = queue?.total ?? 0;
  const epochsInvalid = chosenEpochs !== "" && (Number(chosenEpochs) < 1 || Number(chosenEpochs) > RETRAIN_MAX_EPOCHS);
  const availableForRetraining = waiting + readyImages.length; // uploaded + staged (uploaded on start)
  const eligible = availableForRetraining >= RETRAIN_MIN_IMAGES;
  const missingImages = Math.max(0, RETRAIN_MIN_IMAGES - availableForRetraining);

  return (
    <section className="split-wide">
      <div className="stack-large">
        <div className="row between" style={{ flexWrap: "wrap" }}>
          <div>
            <h2>Labelled image groups</h2>
            <p className="small muted">One group per class. Upload several classes at once.</p>
          </div>
          <span className="pill mono">Resized to 512 px on upload</span>
        </div>

        {groups.map((group) => (
          <ClassGroup key={group.id} group={group} usedLabels={usedLabels}
            onLabel={(label) => updateGroup(group.id, () => ({ label }))}
            onFiles={(files) => addFiles(group.id, files)}
            onRemoveImage={(imageId) => removeImage(group.id, imageId)}
            onRemoveGroup={groups.length > 1 ? () => setGroups((current) => current.filter((item) => item.id !== group.id)) : null} />
        ))}

        <button className="button secondary" onClick={() => setGroups((current) => [...current, newGroup()])}
          disabled={usedLabels.length >= CLASS_NAMES.length}>
          <Icon name="plus" /> Add another class ({CLASS_NAMES.length - usedLabels.length} left)
        </button>

        {message && <div className={`alert ${message.type}`}><Icon name={message.type === "error" ? "alert" : "checkCircle"} />{message.text}</div>}

        <div className="card row between upload-bar">
          <div>
            <h3>Ready to upload</h3>
            <p className="small muted">
              {readyImages.length} image{readyImages.length === 1 ? "" : "s"} in {readyClasses} class{readyClasses === 1 ? "" : "es"}
              {excluded > 0 && ` · ${excluded} excluded (invalid)`}
            </p>
          </div>
          <div className="row-wrap">
            <button className="button secondary" onClick={clearAll} disabled={uploading}>Clear all</button>
            <button className="button primary" onClick={uploadAll} disabled={uploading || readyImages.length === 0}>
              {uploading ? <span className="spinner" /> : <Icon name="upload" />} Upload {readyImages.length || ""} image{readyImages.length === 1 ? "" : "s"}
            </button>
          </div>
        </div>
      </div>

      <aside className="stack-large">
        <div className="card stack">
          <div className="row between">
            <span className="eyebrow">Waiting for retraining</span>
            <span className={`badge ${eligible ? "success" : "neutral"}`}>{eligible ? "Ready" : "Not enough"}</span>
          </div>
          <div className="row" style={{ alignItems: "baseline", gap: 8 }}>
            <span className="big-number">{queue ? waiting : "…"}</span>
            <span className="muted small">uploaded image{waiting === 1 ? "" : "s"}</span>
            {readyImages.length > 0 && <span className="badge neutral">+{readyImages.length} ready to upload</span>}
          </div>
          <div className="meter">
            <div className="meter-fill" style={{ width: `${Math.min(100, (availableForRetraining / (RETRAIN_MIN_IMAGES * 3)) * 100)}%` }} />
            <div className="meter-marker" style={{ left: `${100 / 3}%` }} />
          </div>
          <span className="tiny muted">At least {RETRAIN_MIN_IMAGES} images are needed to retrain.</span>
          {queue && Object.keys(queue.perClass).length > 0 && (
            <BarList items={Object.entries(queue.perClass).sort((first, second) => second[1] - first[1])
              .map(([className, count]) => ({ label: readableClass(className), value: count }))}
              scaleEnd={Math.max(...Object.values(queue.perClass))} />
          )}
          <div className="card-soft small">
            <span className="eyebrow">Starting point</span>
            <p style={{ marginTop: 4 }}><strong className="mono-text">{queue?.servingModel || "…"}</strong></p>
            <p className="tiny muted">The model currently answering predictions is fine-tuned on the original training set plus all uploads.</p>
          </div>
          <label className="field">
            <span className="field-row">Epochs <span className="hint">Optional</span></span>
            <input className="input" type="number" inputMode="numeric" min="1" max={RETRAIN_MAX_EPOCHS} placeholder="Default (server setting)"
              value={chosenEpochs} onChange={(event) => setChosenEpochs(event.target.value.replace(/\D/g, ""))} />
            <span className={`hint ${epochsInvalid ? "bad" : ""}`}>
              {epochsInvalid ? `Choose between 1 and ${RETRAIN_MAX_EPOCHS}.` : `Leave empty to use the default. More epochs take longer (1 to ${RETRAIN_MAX_EPOCHS}).`}
            </span>
          </label>
          <button className="button primary full" onClick={startRetraining} disabled={!eligible || starting || uploading || epochsInvalid}>
            {starting || uploading ? <span className="spinner" /> : <Icon name="refresh" />}
            {uploading ? " Uploading…" : readyImages.length > 0 ? ` Upload ${readyImages.length} & start retraining` : " Start retraining"}
          </button>
          {!eligible && (
            <span className="tiny hint bad" style={{ textAlign: "center" }}>
              Add {missingImages} more image{missingImages === 1 ? "" : "s"} (with a class) to retrain.
            </span>
          )}
        </div>

        <div className="card stack">
          <h3>Good training images</h3>
          <div className="reason good"><Icon name="check" size={16} /><p className="small">Keep fresh and rotten classes balanced.</p></div>
          <div className="reason good"><Icon name="check" size={16} /><p className="small">Whole fruit, one kind per photo, even light.</p></div>
          <div className="reason good"><Icon name="check" size={16} /><p className="small">Label carefully: a wrong label teaches the model a mistake.</p></div>
        </div>
      </aside>
    </section>
  );
}

function ClassGroup({ group, usedLabels, onLabel, onFiles, onRemoveImage, onRemoveGroup }) {
  const fileInput = useRef(null);
  const valid = group.images.filter((image) => !image.problem).length;
  const invalid = group.images.length - valid;

  return (
    <div className="card stack">
      <div className="row between" style={{ flexWrap: "wrap" }}>
        <label className="row" style={{ gap: 10 }}>
          <span className="eyebrow">Class</span>
          <select className="select" style={{ width: 220 }} value={group.label} onChange={(event) => onLabel(event.target.value)}>
            <option value="">Choose a class…</option>
            {CLASS_NAMES.map((className) => (
              <option key={className} value={className} disabled={className !== group.label && usedLabels.includes(className)}>
                {readableClass(className)}
              </option>
            ))}
          </select>
        </label>
        <div className="row-wrap">
          {valid > 0 && <span className="badge success">{valid} valid</span>}
          {invalid > 0 && <span className="badge danger">{invalid} invalid</span>}
          {onRemoveGroup && <button className="button ghost small" onClick={onRemoveGroup} aria-label="Remove this class"><Icon name="trash" /></button>}
        </div>
      </div>

      {!group.label && group.images.length > 0 && (
        <div className="alert warning"><Icon name="alert" />Choose a class: these images are not uploaded without one.</div>
      )}

      <div className="thumb-grid"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => { event.preventDefault(); onFiles(event.dataTransfer.files); }}>
        {group.images.map((image) => (
          <figure key={image.id} className={`thumb ${image.problem ? "invalid" : ""}`}>
            <img src={image.previewUrl} alt={image.file.name} />
            <figcaption>
              <span className="thumb-name" title={image.file.name}>{image.file.name}</span>
              <span className={image.problem ? "hint bad" : "hint good"}>{image.problem || `${Math.round(image.file.size / 1024)} KB`}</span>
            </figcaption>
            <button className="thumb-remove" onClick={() => onRemoveImage(image.id)} aria-label={`Remove ${image.file.name}`}><Icon name="close" size={14} /></button>
          </figure>
        ))}
        <button className="thumb add" onClick={() => fileInput.current.click()}>
          <Icon name="plus" size={22} />
          <span className="small strong">Add images</span>
          <span className="tiny muted">Drop or click</span>
        </button>
        <input ref={fileInput} type="file" accept="image/*,.heic,.heif" multiple hidden
          onChange={(event) => { onFiles(event.target.files); event.target.value = ""; }} />
      </div>
    </div>
  );
}

// ------------------------------------------------------------ step 2: progress
function elapsedSeconds(status) {
  if (!status?.started_at) return 0;
  const end = status.finished_at ? new Date(status.finished_at) : new Date();
  return Math.max(0, (end - new Date(status.started_at)) / 1000);
}

function duration(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

function ProgressStep({ status, onStatus, onFinished, onBack }) {
  const [, setTick] = useState(0);

  useEffect(() => {
    if (status?.state !== "running") return undefined;
    const poll = setInterval(async () => {
      try {
        const latest = await api.retrainingStatus();
        onStatus(latest);
        if (latest.state === "done") onFinished();
      } catch {
        // a missed poll is retried on the next tick
      }
      setTick((tick) => tick + 1);
    }, POLL_EVERY_MILLISECONDS);
    return () => clearInterval(poll);
  }, [status?.state, onStatus, onFinished]);

  if (!status || status.state === "idle") {
    return <div className="card empty">No retraining has run yet. <button className="button ghost" onClick={onBack}>Add images first</button></div>;
  }

  const running = status.state === "running";
  const progress = status.progress_percent ?? 0;
  const elapsed = elapsedSeconds(status);
  const remaining = running && progress > 3 ? (elapsed / progress) * (100 - progress) : null;
  const currentStageIndex = STAGES.findIndex((stage) => stage.key === status.stage);
  const metrics = status.current_metrics || {};
  const history = status.epoch_history || [];

  return (
    <section className="stack-large">
      <div className="card stack">
        <div className="row between" style={{ flexWrap: "wrap" }}>
          <span className={`badge ${status.state === "failed" ? "danger" : running ? "success" : "neutral"}`}>
            {status.state === "failed" ? "Failed" : running ? "Running" : "Finished"}
          </span>
          <span className="small muted row" style={{ gap: 6 }}>
            <Icon name="clock" size={14} /> {duration(elapsed)}{remaining !== null && ` · about ${duration(remaining)} left`}
          </span>
        </div>
        <div className="row between" style={{ flexWrap: "wrap" }}>
          <h2>
            {status.stage === "training" || status.stage === "validating"
              ? `${status.stage === "training" ? "Training" : "Validating"} · epoch ${status.epoch ?? 1} of ${status.total_epochs}`
              : STAGES.find((stage) => stage.key === status.stage)?.label || status.stage}
          </h2>
          <span className="big-number">{progress.toFixed(0)}%</span>
        </div>
        <div className="meter"><div className="meter-fill" style={{ width: `${progress}%` }} /></div>
        <div className="row between small muted" style={{ flexWrap: "wrap" }}>
          <span>{status.batch ? `Batch ${status.batch} of ${status.batches_per_epoch}` : status.evaluated_batches ? `Evaluated ${status.evaluated_batches} of ${status.evaluation_batches} test batches` : " "}</span>
          <span>{status.uploaded_images} new image{status.uploaded_images === 1 ? "" : "s"} · starting from {status.base_model || "the current model"}</span>
        </div>
        {running && <div className="alert info"><Icon name="info" />You can leave this page: training continues on the server.</div>}
        {status.state === "failed" && <div className="alert error"><Icon name="alert" />{status.error}</div>}
      </div>

      <div className="grid grid-3">
        {[["Loss", metrics.loss], ["Accuracy", metrics.accuracy], ["Precision", metrics.Precision],
          ["Recall", metrics.Recall], ["F1 score", metrics.F1Score], ["ROC-AUC", metrics.AUC]].map(([label, value]) => (
          <div key={label} className="kpi">
            <span className="eyebrow">Training · live</span>
            <div className="kpi-title">{label}</div>
            <div className="kpi-value number">{value === undefined ? "—" : label === "Loss" ? value.toFixed(3) : percent(value)}</div>
          </div>
        ))}
      </div>

      <div className="split">
        <div className="card stack">
          <h3>Epoch results</h3>
          {history.length === 0 ? (
            <p className="small muted">Validation scores appear here at the end of each epoch.</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead><tr><th>Epoch</th><th className="number">Train loss</th><th className="number">Train acc.</th><th className="number">Val loss</th><th className="number">Val acc.</th><th className="number">Val F1</th></tr></thead>
                <tbody>
                  {history.map((epoch) => (
                    <tr key={epoch.epoch}>
                      <td>Epoch {epoch.epoch}</td>
                      <td className="number">{epoch.loss?.toFixed(3)}</td>
                      <td className="number">{epoch.accuracy !== undefined ? percent(epoch.accuracy, 1) : "—"}</td>
                      <td className="number">{epoch.val_loss?.toFixed(3)}</td>
                      <td className="number">{epoch.val_accuracy !== undefined ? percent(epoch.val_accuracy, 1) : "—"}</td>
                      <td className="number">{epoch.val_F1Score?.toFixed(3) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card stack">
          <h3>Steps</h3>
          <ol className="timeline">
            {STAGES.map((stage, index) => {
              const finished = !running ? status.state === "done" || index < currentStageIndex : index < currentStageIndex;
              const current = running && index === currentStageIndex;
              return (
                <li key={stage.key} className={finished ? "done" : current ? "current" : "todo"}>
                  <span className="timeline-dot">{finished ? <Icon name="check" size={12} /> : current ? <span className="spinner dark" style={{ width: 12, height: 12, borderWidth: 2 }} /> : null}</span>
                  {stage.label}
                </li>
              );
            })}
          </ol>
        </div>
      </div>

      {!running && <button className="button secondary" onClick={onBack} style={{ alignSelf: "flex-start" }}>← Back to images</button>}
    </section>
  );
}

// ------------------------------------------------------------ step 3: compare
function errorCount(evaluation) {
  const total = evaluation.confusion.flat().reduce((sum, count) => sum + count, 0);
  const correct = evaluation.confusion.reduce((sum, row, index) => sum + row[index], 0);
  return { errors: total - correct, total };
}

function CompareStep({ status, onNewRun }) {
  const { before, after, model: newModel } = status.result;
  const previousModel = status.base_model;
  const [servingModel, setServingModel] = useState(null);
  const [switching, setSwitching] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    api.models().then((models) => setServingModel(models.selected)).catch(() => {});
  }, []);

  const beforeErrors = errorCount(before);
  const afterErrors = errorCount(after);
  const metrics = [
    { label: "Accuracy", before: before.accuracy, after: after.accuracy },
    { label: "Precision (macro)", before: before.precision, after: after.precision },
    { label: "Recall (macro)", before: before.recall, after: after.recall },
    { label: "F1 score (macro)", before: before.f1, after: after.f1 },
    { label: "AUC", before: before.auc_score, after: after.auc_score },
  ];
  const f1Change = (after.f1 - before.f1) * 100;
  const verdict = f1Change > 0.05 ? "better" : f1Change < -0.05 ? "worse" : "same";

  async function chooseModel(modelName) {
    setSwitching(true);
    setMessage(null);
    try {
      const selection = await api.selectModel(modelName);
      setServingModel(selection.selected);
      setMessage({ type: "success", text: `Predictions now use ${selection.selected}.` });
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setSwitching(false);
    }
  }

  return (
    <section className="split-wide">
      <div className="stack-large">
        <div className={`alert ${verdict === "worse" ? "warning" : "success"}`}>
          <Icon name={verdict === "worse" ? "alert" : "checkCircle"} />
          <div>
            <strong>
              {verdict === "better" ? "The new model is better." : verdict === "worse" ? "The new model is slightly worse." : "The new model performs about the same."}
            </strong>{" "}
            {verdict === "worse"
              ? `With only ${status.uploaded_images} new image${status.uploaded_images === 1 ? "" : "s"}, retraining mostly adds noise. You can switch back to the previous model.`
              : "Both models were tested on the same test images."}
          </div>
        </div>

        <div className="card stack">
          <div className="row between" style={{ flexWrap: "wrap" }}>
            <h2>Side-by-side evaluation</h2>
            <span className="pill mono">Same {beforeErrors.total} test images</span>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr><th>Metric</th><th className="number">Previous</th><th className="number">New</th><th className="number">Change</th></tr>
              </thead>
              <tbody>
                {metrics.map((metric) => {
                  const rawChange = (metric.after - metric.before) * 100;
                  const change = Math.abs(rawChange) < 0.005 ? 0 : rawChange; // no "-0.00"
                  return (
                    <tr key={metric.label}>
                      <td>{metric.label}</td>
                      <td className="number">{percent(metric.before)}</td>
                      <td className="number strong">{percent(metric.after)}</td>
                      <td className={`number delta ${change > 0.005 ? "up" : change < -0.005 ? "down" : ""}`}>{change >= 0 ? "+" : ""}{change.toFixed(2)} pts</td>
                    </tr>
                  );
                })}
                <tr>
                  <td>Errors (of {beforeErrors.total})</td>
                  <td className="number">{beforeErrors.errors}</td>
                  <td className="number strong">{afterErrors.errors}</td>
                  <td className={`number delta ${afterErrors.errors < beforeErrors.errors ? "up" : afterErrors.errors > beforeErrors.errors ? "down" : ""}`}>
                    {afterErrors.errors - beforeErrors.errors >= 0 ? "+" : ""}{afterErrors.errors - beforeErrors.errors}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="tiny muted">Change in percentage points. Green is better, orange is worse.</p>
        </div>
      </div>

      <aside className="card stack">
        <span className="eyebrow">Answering predictions now</span>
        <strong className="mono-text">{servingModel || "…"}</strong>
        <p className="small muted">A retrained model is selected automatically. You decide which one stays.</p>
        {message && <div className={`alert ${message.type}`}>{message.text}</div>}
        <button className="button primary full" disabled={switching || servingModel === previousModel} onClick={() => chooseModel(previousModel)}>
          Switch back to {previousModel}
        </button>
        <button className="button secondary full" disabled={switching || servingModel === newModel} onClick={() => chooseModel(newModel)}>
          Use the new model
        </button>
        <div className="card-soft tiny muted stack" style={{ gap: 4 }}>
          <span>New model: <strong className="mono-text">{newModel}</strong></span>
          <span>Epochs: {status.result.epochs} · New images: {status.result.n_uploads}</span>
          <span>Nothing is deleted: every model stays available on the Models page.</span>
        </div>
        <button className="button ghost" onClick={onNewRun}>Add more images →</button>
      </aside>
    </section>
  );
}
