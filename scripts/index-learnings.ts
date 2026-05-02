#!/usr/bin/env bun
/**
 * Index only learnings into nomic LanceDB — filtered version of index-model.ts
 */

import { Database } from 'bun:sqlite';
import { createVectorStore } from '/Users/nat/Code/github.com/Soul-Brews-Studio/arra-oracle-v3/src/vector/factory.ts';

const DB_PATH = `${process.env.HOME}/.arra-oracle-v2/oracle.db`;
const LANCEDB_DIR = `${process.env.HOME}/.arra-oracle-v2/lancedb`;
const BATCH_SIZE = 100;

const sqlite = new Database(DB_PATH, { readonly: true });

const store = createVectorStore({
  type: 'lancedb',
  collectionName: 'oracle_knowledge',
  embeddingProvider: 'ollama',
  embeddingModel: 'nomic-embed-text',
  dataPath: LANCEDB_DIR,
});

await store.connect();
await store.ensureCollection();

const rows = sqlite.prepare(`
  SELECT d.id, d.type, GROUP_CONCAT(f.content, '\n') as content, d.source_file, d.concepts, d.project
  FROM oracle_documents d
  JOIN oracle_fts f ON d.id = f.id
  WHERE d.type = 'learning'
  GROUP BY d.id
  ORDER BY d.created_at DESC
`).all() as any[];

console.log(`=== Learnings-only Indexer ===`);
console.log(`Docs: ${rows.length} learnings`);

const totalBatches = Math.ceil(rows.length / BATCH_SIZE);
let indexed = 0;
const start = Date.now();

for (let i = 0; i < rows.length; i += BATCH_SIZE) {
  const batch = rows.slice(i, i + BATCH_SIZE);
  try {
    await store.addDocuments(batch.map(r => ({
      id: r.id,
      document: r.content || '',
      metadata: {
        type: r.type,
        source_file: r.source_file || '',
        project: r.project || '',
        concepts: r.concepts || '',
      },
    })));
    indexed += batch.length;
    const rate = (indexed / ((Date.now() - start) / 1000)).toFixed(1);
    const eta = Math.round((rows.length - indexed) / Number(rate));
    console.log(`  Batch ${Math.floor(i / BATCH_SIZE) + 1}/${totalBatches} — ${indexed}/${rows.length} — ${rate}/s — ETA ${eta}s`);
  } catch (e) {
    console.error(`  Batch FAILED:`, e instanceof Error ? e.message : e);
  }
}

console.log(`\n=== Done ===`);
console.log(`Indexed: ${indexed}/${rows.length} learnings`);
console.log(`Time: ${((Date.now() - start) / 1000).toFixed(1)}s`);
await store.close();
