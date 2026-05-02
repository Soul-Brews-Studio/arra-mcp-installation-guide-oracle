#!/usr/bin/env bun
/**
 * Vault Analyser — scan the Oracle vault and report what's indexable
 *
 * Usage: bun scripts/analyse-vault.ts [vault-path]
 * Default: ~/Code/github.com/Soul-Brews-Studio/oracle-vault
 */

import { readdir, stat, readFile } from 'fs/promises';
import { join, relative, extname } from 'path';

const VAULT_PATH = process.argv[2]
  || process.env.ORACLE_VAULT_PATH
  || join(process.env.HOME!, '.arra-oracle-v2/ψ');

interface FileInfo {
  path: string;
  size: number;
  type: string;
  project?: string;
  date?: string;
  hasFrontmatter: boolean;
  charCount: number;
}

interface VaultStats {
  totalFiles: number;
  totalSize: number;
  byType: Record<string, number>;
  byProject: Record<string, number>;
  byMonth: Record<string, number>;
  avgCharCount: number;
  over2000Chars: number;
  under100Chars: number;
  withFrontmatter: number;
  topDirs: Record<string, number>;
}

async function walkDir(dir: string): Promise<string[]> {
  const files: string[] = [];
  try {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const full = join(dir, entry.name);
      if (entry.name === '.git' || entry.name === 'node_modules') continue;
      if (entry.isDirectory()) {
        files.push(...await walkDir(full));
      } else if (entry.isFile() && extname(entry.name) === '.md') {
        files.push(full);
      }
    }
  } catch {}
  return files;
}

function detectType(path: string, content: string): string {
  if (path.includes('/learnings/')) return 'learning';
  if (path.includes('/retrospectives/') || path.includes('/retro')) return 'retro';
  if (path.includes('/resonance/')) return 'resonance';
  if (path.includes('/handoff/')) return 'handoff';
  if (path.includes('/principles/')) return 'principle';
  if (path.includes('/traces/')) return 'trace';

  // Check frontmatter
  const typeMatch = content.match(/^---[\s\S]*?type:\s*(\w+)/m);
  if (typeMatch) return typeMatch[1];

  return 'unknown';
}

function extractDate(path: string, content: string): string | undefined {
  // From filename: 2026-05-02_...
  const fileDate = path.match(/(\d{4}-\d{2}-\d{2})/);
  if (fileDate) return fileDate[1];

  // From frontmatter
  const fmDate = content.match(/^---[\s\S]*?(?:created|date):\s*(\d{4}-\d{2}-\d{2})/m);
  if (fmDate) return fmDate[1];

  return undefined;
}

function extractProject(path: string): string | undefined {
  // github.com/org/repo pattern in path
  const match = path.match(/github\.com\/([^/]+\/[^/]+)/);
  if (match) return match[1];

  // agent-N pattern
  const agentMatch = path.match(/(agent-\d+)/);
  if (agentMatch) return agentMatch[1];

  return undefined;
}

async function analyseFile(filePath: string): Promise<FileInfo> {
  const content = await readFile(filePath, 'utf-8');
  const stats = await stat(filePath);

  return {
    path: relative(VAULT_PATH, filePath),
    size: stats.size,
    type: detectType(filePath, content),
    project: extractProject(filePath),
    date: extractDate(filePath, content),
    hasFrontmatter: content.startsWith('---'),
    charCount: content.length,
  };
}

async function main() {
  console.log(`\n🔮 Oracle Vault Analyser`);
  console.log(`   Path: ${VAULT_PATH}\n`);

  const files = await walkDir(VAULT_PATH);
  console.log(`   Scanning ${files.length} .md files...\n`);

  const results: FileInfo[] = [];
  for (const f of files) {
    results.push(await analyseFile(f));
  }

  const stats: VaultStats = {
    totalFiles: results.length,
    totalSize: results.reduce((s, f) => s + f.size, 0),
    byType: {},
    byProject: {},
    byMonth: {},
    avgCharCount: Math.round(results.reduce((s, f) => s + f.charCount, 0) / results.length),
    over2000Chars: results.filter(f => f.charCount > 2000).length,
    under100Chars: results.filter(f => f.charCount < 100).length,
    withFrontmatter: results.filter(f => f.hasFrontmatter).length,
    topDirs: {},
  };

  for (const f of results) {
    stats.byType[f.type] = (stats.byType[f.type] || 0) + 1;
    if (f.project) stats.byProject[f.project] = (stats.byProject[f.project] || 0) + 1;
    if (f.date) {
      const month = f.date.slice(0, 7);
      stats.byMonth[month] = (stats.byMonth[month] || 0) + 1;
    }
    const topDir = f.path.split('/')[0];
    stats.topDirs[topDir] = (stats.topDirs[topDir] || 0) + 1;
  }

  // Print report
  console.log(`═══ VAULT SUMMARY ═══`);
  console.log(`  Total files:      ${stats.totalFiles}`);
  console.log(`  Total size:       ${(stats.totalSize / 1024 / 1024).toFixed(1)} MB`);
  console.log(`  Avg chars/file:   ${stats.avgCharCount}`);
  console.log(`  With frontmatter: ${stats.withFrontmatter} (${Math.round(stats.withFrontmatter / stats.totalFiles * 100)}%)`);
  console.log(`  Over 2000 chars:  ${stats.over2000Chars} (would be truncated by embedder)`);
  console.log(`  Under 100 chars:  ${stats.under100Chars} (too short for useful embedding)`);

  console.log(`\n═══ BY TYPE ═══`);
  const sortedTypes = Object.entries(stats.byType).sort((a, b) => b[1] - a[1]);
  for (const [type, count] of sortedTypes) {
    console.log(`  ${type.padEnd(15)} ${count}`);
  }

  console.log(`\n═══ TOP DIRECTORIES ═══`);
  const sortedDirs = Object.entries(stats.topDirs).sort((a, b) => b[1] - a[1]).slice(0, 15);
  for (const [dir, count] of sortedDirs) {
    console.log(`  ${dir.padEnd(30)} ${count}`);
  }

  console.log(`\n═══ BY PROJECT (top 15) ═══`);
  const sortedProjects = Object.entries(stats.byProject).sort((a, b) => b[1] - a[1]).slice(0, 15);
  for (const [project, count] of sortedProjects) {
    console.log(`  ${project.padEnd(40)} ${count}`);
  }

  console.log(`\n═══ BY MONTH ═══`);
  const sortedMonths = Object.entries(stats.byMonth).sort((a, b) => a[0].localeCompare(b[0]));
  for (const [month, count] of sortedMonths) {
    console.log(`  ${month}  ${count}`);
  }

  // Indexing recommendation
  console.log(`\n═══ INDEXING RECOMMENDATION ═══`);
  const indexable = results.filter(f => f.charCount >= 100 && f.charCount <= 50000);
  const needsChunking = results.filter(f => f.charCount > 2000);
  console.log(`  Indexable (100-50k chars):  ${indexable.length}`);
  console.log(`  Needs chunking (>2000):     ${needsChunking.length}`);
  console.log(`  Current embedder truncates at 2000 chars → ${needsChunking.length} docs lose content`);
  console.log(`  Recommended: chunk at ~1500 chars with 200 char overlap`);

  // Write JSON report
  const reportPath = join(process.cwd(), 'vault-analysis.json');
  await Bun.write(reportPath, JSON.stringify({ stats, sampleFiles: results.slice(0, 20) }, null, 2));
  console.log(`\n  Report saved: ${reportPath}`);
}

main().catch(console.error);
