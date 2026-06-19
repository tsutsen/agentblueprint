/**
 * Extracts glossary references from all spec JSON files and the glossary itself,
 * then outputs a combined graph data file for visualization.
 *
 * Usage: node extract-graph-data.js [artifacts-dir]
 *   defaults to: ../ (parent of this script)
 */

const fs = require('fs');
const path = require('path');

const ARTIFACTS_DIR = process.argv[2] || path.resolve(__dirname, '..');
const GLOSSARY_FILE = path.join(ARTIFACTS_DIR, 'Glossary.json');

const SPEC_FILES = [
  'GoalSpec.json',
  'DesignSpec.json',
  'ApiSpec.json',
  'ArchitectureSpec.json',
  'DataSpec.json',
  'TestSpec.json',
];

/**
 * Recursively find all glossaryRefs in a JSON object,
 * returning { specName, path, refs[] }
 */
function findRefs(obj, specName, currentPath = '') {
  const results = [];

  function walk(node, path) {
    if (node && typeof node === 'object') {
      if (Array.isArray(node)) {
        node.forEach((item, i) => walk(item, `${path}[${i}]`));
      } else {
        if (Array.isArray(node.glossaryRefs) && node.glossaryRefs.length > 0) {
          results.push({
            spec: specName,
            path,
            refs: node.glossaryRefs,
          });
        }
        for (const key of Object.keys(node)) {
          walk(node[key], `${path}.${key}`);
        }
      }
    }
  }

  walk(obj, currentPath);
  return results;
}

function main() {
  // Load glossary
  const glossaryData = JSON.parse(fs.readFileSync(GLOSSARY_FILE, 'utf-8'));
  const terms = glossaryData.terms;
  const termMap = new Map();
  for (const t of terms) {
    termMap.set(t.id, t);
  }

  // Collect all spec references
  const specRefs = [];
  const specTermRefs = new Map(); // specName -> Set of GL IDs

  for (const specFile of SPEC_FILES) {
    const specPath = path.join(ARTIFACTS_DIR, specFile);
    if (!fs.existsSync(specPath)) {
      console.warn(`Warning: ${specFile} not found, skipping.`);
      continue;
    }

    const specData = JSON.parse(fs.readFileSync(specPath, 'utf-8'));
    const refs = findRefs(specData, specFile.replace('.json', ''));
    specRefs.push(...refs);

    const termSet = new Set();
    for (const r of refs) {
      for (const glId of r.refs) {
        termSet.add(glId);
      }
    }
    specTermRefs.set(specFile.replace('.json', ''), termSet);
  }

  // Build graph nodes from glossary terms
  const nodes = terms.map((t) => ({
    id: t.id,
    term: t.term,
    definition: t.definition,
    category: t.category,
    relatedCount: (t.relatedTerms || []).length,
    degree: 0, // will be updated below
    specRefCount: 0, // will be updated below
  }));

  // Count how many specs reference each term
  const termSpecRefs = new Map(); // GL-ID -> Set of spec names
  for (const [specName, termSet] of specTermRefs) {
    for (const glId of termSet) {
      if (!termSpecRefs.has(glId)) {
        termSpecRefs.set(glId, new Set());
      }
      termSpecRefs.get(glId).add(specName);
    }
  }

  for (const node of nodes) {
    const refs = termSpecRefs.get(node.id);
    node.specRefCount = refs ? refs.size : 0;
    node.specs = refs ? [...refs] : [];
  }

  // Build edges from glossary relatedTerms
  const edges = [];
  const edgeSet = new Set(); // avoid duplicates

  for (const t of terms) {
    for (const relatedId of (t.relatedTerms || [])) {
      const key = [t.id, relatedId].sort().join('→');
      if (!edgeSet.has(key)) {
        edgeSet.add(key);
        edges.push({
          source: t.id,
          target: relatedId,
          type: 'relatedTerms',
        });
      }
    }
  }

  // Build edges from spec references (spec -> term)
  const specNodes = [];
  for (const [specName, termSet] of specTermRefs) {
    const specNodeId = `SPEC:${specName}`;
    specNodes.push({
      id: specNodeId,
      term: specName,
      definition: `Specification file: ${specName}.json`,
      category: 'spec',
      relatedCount: termSet.size,
      degree: 0,
      specRefCount: 0,
      specs: [],
    });

    for (const glId of termSet) {
      const edgeKey = `${specNodeId}→${glId}`;
      if (!edgeSet.has(edgeKey)) {
        edgeSet.add(edgeKey);
        edges.push({
          source: specNodeId,
          target: glId,
          type: 'specRef',
        });
      }
    }
  }

  // Build cross-spec edges: which specs share glossary references
  const specNames = [...specTermRefs.keys()];
  const crossSpecEdges = [];
  for (let i = 0; i < specNames.length; i++) {
    const setA = specTermRefs.get(specNames[i]) || new Set();
    for (let j = i + 1; j < specNames.length; j++) {
      const setB = specTermRefs.get(specNames[j]) || new Set();
      const shared = [...setA].filter((x) => setB.has(x));
      if (shared.length > 0) {
        crossSpecEdges.push({
          source: `SPEC:${specNames[i]}`,
          target: `SPEC:${specNames[j]}`,
          type: 'crossSpec',
          sharedTerms: shared,
          sharedCount: shared.length,
        });
      }
    }
  }

  // Compute degree from all edges
  const degreeMap = new Map();
  for (const e of [...edges, ...crossSpecEdges]) {
    degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1);
    degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1);
  }

  // Set degree on all nodes
  for (const n of [...nodes, ...specNodes]) {
    n.degree = degreeMap.get(n.id) || 0;
  }

  // Output
  const output = {
    project: glossaryData.project,
    version: glossaryData.version,
    summary: {
      totalTerms: terms.length,
      totalEdges: edges.length,
      totalSpecs: specTermRefs.size,
      categories: terms.reduce((acc, t) => {
        acc[t.category] = (acc[t.category] || 0) + 1;
        return acc;
      }, {}),
    },
    nodes: [...nodes, ...specNodes],
    edges: [...edges, ...crossSpecEdges],
  };

  const outputPath = path.join(__dirname, 'graph-data.json');
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));
  console.log(`Graph data written to ${outputPath}`);
  console.log(`  ${output.nodes.length} nodes, ${output.edges.length} edges`);
}

main();
