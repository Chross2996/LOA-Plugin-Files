#!/usr/bin/env node
// Validates LOA.json / sector_ownership.json / volumes.json in one or more
// region folders (e.g. EDWW, EDMM). Mirrors the rules in the configurator's
// "Validate" tab, plus a JSON-parse check that the browser tool never sees
// because broken JSON never loads into the app in the first place.
//
// Usage:
//   node scripts/validate.js EDWW EDMM
//   node scripts/validate.js          (auto-detects region folders containing all 3 files)

const fs = require('fs');
const path = require('path');

const FILE_NAMES = { loa: 'LOA.json', ownership: 'sector_ownership.json', volumes: 'volumes.json' };
const repoRoot = process.cwd();

function findRegions() {
  return fs.readdirSync(repoRoot, { withFileTypes: true })
    .filter(d => d.isDirectory() && !d.name.startsWith('.'))
    .map(d => d.name)
    .filter(name => Object.values(FILE_NAMES).every(f => fs.existsSync(path.join(repoRoot, name, f))));
}

function loadJson(region, key) {
  const filePath = path.join(repoRoot, region, FILE_NAMES[key]);
  const raw = fs.readFileSync(filePath, 'utf8');
  try {
    return { value: JSON.parse(raw), error: null, filePath };
  } catch (err) {
    return { value: null, error: err.message, filePath };
  }
}

function validateRegion(region) {
  const issues = [];
  const loaRes = loadJson(region, 'loa');
  const ownRes = loadJson(region, 'ownership');
  const volRes = loadJson(region, 'volumes');

  // Hard stop per-file if JSON itself doesn't parse — nothing else is checkable.
  [['LOA.json', loaRes], ['sector_ownership.json', ownRes], ['volumes.json', volRes]].forEach(([name, res]) => {
    if (res.error) issues.push(`${region}/${name}: invalid JSON — ${res.error}`);
  });
  if (loaRes.error || ownRes.error || volRes.error) {
    return issues; // can't safely cross-check broken files
  }

  const loa = loaRes.value, ownership = ownRes.value, volumes = volRes.value;
  const volIds = new Set((volumes?.volumes || []).map(v => v.id));
  const sectors = new Set(loa ? Object.keys(loa) : []);

  if (loa) {
    Object.entries(loa).forEach(([sector, groups]) => {
      ['destinationLoas', 'departureLoas'].forEach(g => {
        (groups[g] || []).forEach((r, i) => {
          const where = `${region}/${sector}/${g} #${i + 1}`;
          if (!r.copText) issues.push(`${where}: missing copText`);
          if (r.xfl !== undefined && (!Number.isFinite(Number(r.xfl)) || Number(r.xfl) < 0)) {
            issues.push(`${where}: invalid xfl`);
          }
          ['predictedEnterVolumes', 'predictedFromVolumes', 'predictedToVolumes', 'predictedEndVolumes', 'startVolumes'].forEach(k => {
            (r[k] || []).forEach(v => {
              if (!volIds.has(v)) issues.push(`${where}: ${k} references unknown volume ${v}`);
            });
          });
          (r.nextSectors || []).forEach(ns => {
            if (!sectors.has(ns) && !ownership?.priority?.[ns] && !ownership?.ownership?.[ns]) {
              issues.push(`${where}: nextSector ${ns} not found as sector/ownership key`);
            }
          });
        });
      });
    });
  }

  (volumes?.volumes || []).forEach((v, i) => {
    const where = `${region}/volumes #${i + 1}`;
    if (!v.id) issues.push(`${where}: missing id`);
    if (+v.lowerFL > +v.upperFL) issues.push(`${region}/${v.id || '#' + (i + 1)}: lowerFL is above upperFL`);
    if (!Array.isArray(v.polygon) || v.polygon.length < 3) {
      issues.push(`${region}/${v.id || '#' + (i + 1)}: polygon has fewer than 3 points`);
    }
  });

  return issues;
}

function main() {
  const argRegions = process.argv.slice(2);
  const regions = argRegions.length ? argRegions : findRegions();

  if (!regions.length) {
    console.log('No region folders found (expected subfolders containing LOA.json, sector_ownership.json, volumes.json).');
    process.exit(0);
  }

  let totalIssues = 0;
  regions.forEach(region => {
    const regionPath = path.join(repoRoot, region);
    if (!fs.existsSync(regionPath)) {
      console.log(`\n=== ${region} ===`);
      console.log(`  Region folder not found, skipping.`);
      return;
    }
    const issues = validateRegion(region);
    console.log(`\n=== ${region} ===`);
    if (!issues.length) {
      console.log('  No issues found.');
    } else {
      issues.forEach(i => console.log(`  - ${i}`));
      totalIssues += issues.length;
    }
  });

  console.log(`\n${totalIssues} total issue(s) across ${regions.length} region(s).`);
  if (totalIssues > 0) process.exit(1);
}

main();
