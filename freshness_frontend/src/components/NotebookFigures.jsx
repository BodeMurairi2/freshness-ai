import { useEffect, useState } from "react";
import { readableClass } from "../data/classes";
import Icon from "./Icon";

const GRADCAM_TAB = "gradcam";

// figures drawn in the original model's notebook (exported by scripts/export_notebook_figures.py)
export default function NotebookFigures({ title = "From the notebook" }) {
  const [figures, setFigures] = useState(null);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState("training-history");

  useEffect(() => {
    fetch("/notebook/figures.json")
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then(setFigures)
      .catch(() => setFailed(true));
  }, []);

  if (failed) return null;
  if (!figures) return <div className="skeleton" style={{ height: 320 }} />;

  const tabs = [
    ...figures.figures.map((figure) => ({ key: figure.name, label: figure.title })),
    ...(figures.gradcam.length ? [{ key: GRADCAM_TAB, label: "Grad-CAM examples" }] : []),
  ];
  const figure = figures.figures.find((item) => item.name === selected);

  return (
    <div className="stack-large">
      <div className="row between" style={{ flexWrap: "wrap" }}>
        <div>
          <span className="eyebrow">Original model · {figures.model}</span>
          <h2 style={{ marginTop: 4 }}>{title}</h2>
          <p className="small muted" style={{ marginTop: 6 }}>The figures drawn in the notebook when the original model was trained and tested.</p>
        </div>
      </div>
      <div className="stepper" role="tablist" aria-label="Notebook figure">
        {tabs.map((tab) => (
          <button key={tab.key} role="tab" aria-selected={tab.key === selected} className={`step ${tab.key === selected ? "current" : ""}`}
            onClick={() => setSelected(tab.key)}>{tab.label}</button>
        ))}
      </div>

      {selected === GRADCAM_TAB ? (
        <div className="stack">
          <p className="small muted">One test photo per class: the photo, then what the model looked at (red = most important).</p>
          <div className="gradcam-grid">
            {figures.gradcam.map((item) => (
              <a key={item.class_name} href={item.file} target="_blank" rel="noreferrer" className="gradcam-item" title="Open full size">
                <img src={item.file} alt={`Grad-CAM for ${readableClass(item.class_name)}`} loading="lazy" width={item.width} height={item.height} />
                <span className="small strong">{readableClass(item.class_name)}</span>
              </a>
            ))}
          </div>
        </div>
      ) : figure ? (
        <div className="stack">
          <p className="small muted">{figure.caption}</p>
          <a href={figure.file} target="_blank" rel="noreferrer" className="notebook-figure" title="Open full size">
            <img src={figure.file} alt={figure.title} loading="lazy" width={figure.width} height={figure.height} />
          </a>
          <a className="small" href={figure.file} target="_blank" rel="noreferrer"><Icon name="external" size={13} /> Open full size</a>
        </div>
      ) : null}
    </div>
  );
}
