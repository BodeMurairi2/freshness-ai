// The 8 fruits and 16 classes the model knows (same order as src/target_class.py)
export const FRUITS = [
  { key: "apple", name: "Apple" },
  { key: "banana", name: "Banana" },
  { key: "grape", name: "Grape" },
  { key: "guava", name: "Guava" },
  { key: "jujube", name: "Jujube" },
  { key: "orange", name: "Orange" },
  { key: "pomegranate", name: "Pomegranate" },
  { key: "strawberry", name: "Strawberry" },
];

export const CLASS_NAMES = ["fresh", "rotten"].flatMap((condition) =>
  FRUITS.map((fruit) => `${condition}_${fruit.key}`),
).sort();

export function readableClass(className) {
  const [condition, fruit] = className.split("_");
  return `${capitalize(condition)} ${fruit}`;
}

export function capitalize(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

export function conditionOf(className) {
  return className.split("_")[0];
}

// one-click samples on the Predict page (public/samples): photos from the test set
// (never used for training), with their true label shown on the button
export const SAMPLE_PHOTOS = [
  { name: "Fresh banana", path: "/samples/fresh-banana.jpg" },
  { name: "Rotten apple", path: "/samples/rotten-apple.jpg" },
  { name: "Fresh guava", path: "/samples/fresh-guava.jpg" },
  { name: "Rotten strawberry", path: "/samples/rotten-strawberry.jpg" },
];

export const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"];
export const MAX_IMAGE_MEGABYTES = 10;

// quick check before sending: the server checks again (including corrupted files)
export function checkImageFile(file) {
  const extension = `.${file.name.split(".").pop()}`.toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(extension)) return "Unsupported file type";
  if (file.size === 0) return "Empty file";
  if (file.size > MAX_IMAGE_MEGABYTES * 1024 * 1024) return `Larger than ${MAX_IMAGE_MEGABYTES} MB`;
  return null;
}

export function percent(value, digits = 2) {
  return `${(value * 100).toFixed(digits)}%`;
}
