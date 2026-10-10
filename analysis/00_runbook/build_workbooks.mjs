import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const here = path.dirname(fileURLToPath(import.meta.url));
const pkg = path.resolve(here, "..");
const mode = process.argv[2];

function writeRows(sheet, rows, width, chunkSize = 100) {
  for (let start = 0; start < rows.length; start += chunkSize) {
    const block = rows.slice(start, start + chunkSize);
    sheet.getRangeByIndexes(start, 0, block.length, width).values = block;
  }
}

async function exportLocked() {
  const inputPath = path.join(pkg, "00_cohort_lock/output/locked_493_typed.json");
  const outputPath = path.join(pkg, "00_cohort_lock/output/locked_493.xlsx");
  const source = JSON.parse(await fs.readFile(inputPath, "utf8"));
  if (source.data.length !== 493 || source.columns.length !== 44) {
    throw new Error("Locked input must contain exactly 493 rows and 44 columns");
  }
  const wb = Workbook.create();
  const combined = wb.worksheets.add("combined");
  writeRows(combined, [source.columns, ...source.data], 44);
  combined.freezePanes.freezeRows(1);
  const note = wb.worksheets.add("Cohort");
  const rows = [
    ["Property", "Value"],
    ["Cohort", "493 composition-verified four-cation systems"],
    ["Selection", "Exact match on all metal cations; one EFA source row per system"],
    ["Source", "See 00_cohort_lock/input and cohort_validation.json"],
    ["Excluded", "10 five-cation rows without composition-specific EFA values"],
    ["Paper use", "Use this combined sheet for all EFA figures and models"],
  ];
  writeRows(note, rows, 2);
  note.getRange("A1:B1").format.font = { name: "Arial", bold: true };
  note.getRange("A1:A6").format.columnWidth = 24;
  note.getRange("B1:B6").format.columnWidth = 80;
  wb.recalculate();
  const result = await wb.inspect({
    kind: "region",
    sheetId: "combined",
    range: "A1:D4",
    maxChars: 1800,
  });
  console.log(result.ndjson);
  const blob = await SpreadsheetFile.exportXlsx(wb);
  await blob.save(outputPath);
  console.log(outputPath);
}

async function exportSummary() {
  const inputPath = path.join(pkg, "13_summary/output/summary_workbook.json");
  const outputPath = path.join(pkg, "13_summary/output/CHAOS_EFA493_production_summary.xlsx");
  const source = JSON.parse(await fs.readFile(inputPath, "utf8"));
  const wb = Workbook.create();
  for (const item of source.sheets) {
    const sheet = wb.worksheets.add(item.name);
    const rows = [item.columns, ...item.data];
    writeRows(sheet, rows, item.columns.length);
    sheet.freezePanes.freezeRows(1);
    sheet.showGridLines = false;
    sheet.getRangeByIndexes(0, 0, 1, item.columns.length).format = {
      fill: "#263D56",
      font: { name: "Arial", bold: true, color: "#FFFFFF" },
    };
    sheet.getRangeByIndexes(0, 0, rows.length, item.columns.length).format.font.name =
      "Arial";
    const header = sheet.getRangeByIndexes(0, 0, 1, item.columns.length);
    header.format.rowHeight = 28;
    for (let col = 0; col < item.columns.length; col++) {
      const label = String(item.columns[col]);
      const width = label === "metric" ? 78
        : label === "analysis_folder" ? 58
        : label === "note" ? 100
        : label === "suggested_display" ? 70
        : Math.min(Math.max(label.length + 6, 20), 55);
      sheet.getRangeByIndexes(0, col, rows.length, 1).format.columnWidth = width;
    }
  }
  wb.recalculate();
  const check = await wb.inspect({
    kind: "region",
    sheetId: "Final_Metrics",
    range: "A1:F12",
    maxChars: 3500,
  });
  console.log(check.ndjson);
  const preview = await wb.render({
    sheetName: "Final_Metrics",
    range: "A1:F18",
    scale: 1.5,
    format: "png",
  });
  await fs.writeFile(
    path.join(pkg, "13_summary/output/summary_preview.png"),
    new Uint8Array(await preview.arrayBuffer()),
  );
  const blob = await SpreadsheetFile.exportXlsx(wb);
  await blob.save(outputPath);
  console.log(outputPath);
}

if (mode === "locked") {
  await exportLocked();
} else if (mode === "summary") {
  await exportSummary();
} else {
  throw new Error("Usage: node build_workbooks.mjs locked|summary");
}
