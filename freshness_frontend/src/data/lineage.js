// a retrained model's parents, oldest first, from the models' performance documents
export function lineageOf(modelPerformance, performanceByName) {
  const lineage = [];
  let parentName = modelPerformance?.parent_model;
  while (parentName && performanceByName[parentName] && lineage.length < 50) {
    if (performanceByName[parentName].training) lineage.unshift(performanceByName[parentName].training);
    parentName = performanceByName[parentName].parent_model;
  }
  return lineage;
}
