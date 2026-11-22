import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const workDir = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(await fs.readFile(path.join(workDir, 'efa_provenance_data.json'), 'utf8'));
const workbook = Workbook.create();
const navy = '#20374E';
const pale = '#EAF0F5';
const amber = '#FFF2CC';
const font = 'Arial';

function columnLabel(n) {
  let x = n + 1, s = '';
  while (x > 0) { x--; s = String.fromCharCode(65 + x % 26) + s; x = Math.floor(x / 26); }
  return s;
}

function makeTable(name, headers, rows, widths, freezeColumns = 0) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const end = columnLabel(headers.length - 1);
  sheet.getRange(`A1:${end}1`).values = [headers];
  if (rows.length) sheet.getRangeByIndexes(1, 0, rows.length, headers.length).values = rows;
  const body = sheet.getRange(`A1:${end}${rows.length + 1}`);
  body.format.font = { name: font, size: 10, color: '#1E2933' };
  body.format.rowHeight = 19;
  body.format.verticalAlignment = 'center';
  const header = sheet.getRange(`A1:${end}1`);
  header.format.fill = navy;
  header.format.font = { name: font, size: 10, bold: true, color: '#FFFFFF' };
  header.format.rowHeight = 31;
  header.format.wrapText = true;
  header.format.horizontalAlignment = 'center';
  for (let i = 0; i < widths.length; i++) sheet.getRange(`${columnLabel(i)}:${columnLabel(i)}`).format.columnWidth = widths[i];
  sheet.freezePanes.freezeRows(1);
  if (freezeColumns) sheet.freezePanes.freezeColumns(freezeColumns);
  return sheet;
}

const overview = workbook.worksheets.add('Overview');
overview.showGridLines = false;
overview.tabColor = navy;
overview.getRange('A2').values = [['CHAOS EFA workbook provenance']];
overview.getRange('A2').format.font = { name: font, size: 15, bold: true, color: navy };
overview.getRange('A4:B4').values = [['Finding', 'Evidence from historical files']];
overview.getRange('A5:B15').values = [
  ['Prepared rocksalt records', data.summary.prepared_rocksalt_rows],
  ['Four-cation cohort', data.summary.quaternary_rows],
  ['Five-cation rows misjoined to parents', data.summary.quinary_rows_misjoined],
  ['Four-cation EFA source records', data.summary.efa_source_rows],
  ['Unused four-cation EFA source records', data.summary.unused_efa_source_rows],
  ['Join key', 'Sorted, unordered Metal1–Metal4 only; composition/name not used'],
  ['493-row selection rule', 'Four cations in the full POCC name among the prepared 503 joined rows'],
  ['Verified database snapshot/export date', 'Not recorded in the eight historical files'],
  ['AUID mapping', 'Not present; full POCC name and chem_id supplied as local identifiers'],
  ['Ensemble completion/publication status', 'Not recorded for any of the 493 rows'],
  ['Below-modal configuration-count review', `${data.summary.quaternary_rows_with_configuration_count_below_18} rows with dg_len < 18; this does not prove incomplete status`],
];
overview.getRange('A17').values = [['Read the Creation procedure and Join diagnosis notes for the historical scripts, checks, and limitations.']];
overview.getRange('A18').values = [['No five-cation EFA replacement values have been inferred or inserted.']];
overview.getRange('A4:B4').format = { fill: navy, font: { name: font, size: 10, bold: true, color: '#FFFFFF' } };
overview.getRange('A4:B15').format.rowHeight = 25;
overview.getRange('A5:B15').format.font = { name: font, size: 10, color: '#1E2933' };
overview.getRange('A5:A15').format.fill = pale;
overview.getRange('A13:B14').format.fill = amber;
overview.getRange('A17:B18').format.font = { name: font, size: 10, italic: true, color: '#516273' };
overview.getRange('A:A').format.columnWidth = 38;
overview.getRange('B:B').format.columnWidth = 85;

const qHeaders = [
  'Merged Excel row', 'Full POCC name', 'Metal1', 'Metal2', 'Metal3', 'Metal4',
  'Sorted four-metal join key', 'DFT source row', 'Descriptor source row', 'chaos_data row',
  'EFA cleaned-sheet row', 'JSON record index (1-based)', 'chem_id', 'AUID', 'AUID status',
  'Source configuration count (dg_len)', 'Configuration review flag',
  'Ensemble completion/publication status', 'Database snapshot/export date'
];
const qRows = data.quaternary.map(r => [
  r.combined_row, r.pocc_parent_name, r.Metal1, r.Metal2, r.Metal3, r.Metal4,
  r.sorted_four_metal_key, r.dft_source_row, r.element_descriptor_row, r.chaos_data_row,
  r.efa_cleaned_row, r.json_record_index_1_based, r.chem_id, r.AUID,
  r.AUID_status, r.source_configuration_count, r.configuration_review || '',
  r.ensemble_publication_status, r.database_snapshot_or_export_date
]);
const qSheet = makeTable('Quaternary map', qHeaders, qRows,
  [17, 77, 10, 10, 10, 10, 28, 16, 19, 16, 19, 23, 33, 15, 28, 22, 30, 34, 32], 2);
qSheet.tabColor = '#466B8C';
qSheet.getRange(`Q2:Q${qRows.length + 1}`).conditionalFormats.add('containsText', {
  text: 'review', format: { fill: amber, font: { color: '#7A4E00', bold: true } }
});

const fiveHeaders = [
  'Merged Excel row', 'Full five-cation POCC name', 'All five cations', 'Fifth cation dropped',
  'Four-metal join key', 'EFA cleaned-sheet row', 'Incorrectly assigned EFA',
  'Correct five-cation EFA',
  'Four-cation parent merged row', 'Four-cation parent full POCC name'
];
const fiveRows = data.quinary.map(r => [
  r.combined_row, r.pocc_name, r.five_cations, r.fifth_cation_lost_by_parser,
  r.four_metal_join_key, r.efa_cleaned_row, r.assigned_EFA,
  r.correct_five_cation_EFA,
  r.four_cation_parent_combined_row, r.four_cation_parent_name
]);
const five = makeTable('Five-cation issue', fiveHeaders, fiveRows,
  [17, 77, 24, 22, 25, 20, 23, 24, 24, 77], 2);
five.tabColor = '#C26340';
five.getRange('H2:H11').format.fill = amber;
five.getRange('G2:G11').setNumberFormat('0.0000000000');

const sourceHeaders = ['Historical file', 'Role in creation chain', 'SHA-256', 'Verified database snapshot/export date'];
const sourceRows = data.sources.map(r => [r.file, r.role, r.sha256, r.database_snapshot_or_export_date]);
const sources = makeTable('Source files', sourceHeaders, sourceRows, [43, 73, 70, 40]);
sources.tabColor = '#728598';

workbook.recalculate();
for (const [name, range] of [
  ['Overview', 'A4:B15'], ['Quaternary map', 'A1:S4'],
  ['Five-cation issue', 'A1:L11'], ['Source files', 'A1:D9']
]) {
  const report = await workbook.inspect({ kind: 'region', sheetId: name, range, maxChars: 1500, tableMaxRows: 4, tableMaxCols: 6 });
  console.log(name, JSON.stringify(report).slice(0, 1700));
}
const errorReport = await workbook.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#N/A|#NAME\\?|#NUM!', options: { useRegex: true, maxResults: 20 }, maxChars: 2000 });
console.log('ERROR_CHECK', JSON.stringify(errorReport).slice(0, 2500));

const output = path.join(workDir, 'chaos_efa_provenance_493_rows.xlsx');
const blob = await SpreadsheetFile.exportXlsx(workbook);
await blob.save(output);
console.log('WROTE', output);

for (const name of ['Overview', 'Quaternary map', 'Five-cation issue', 'Source files']) {
  try {
    const preview = await workbook.render({ sheetName: name, range: name === 'Quaternary map' ? 'A1:G8' : undefined, autoCrop: 'all', scale: 0.75, format: 'png' });
    const previewPath = path.join(workDir, `preview_${name.toLowerCase().replaceAll(' ', '_')}.png`);
    await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
    console.log('PREVIEW', previewPath);
  } catch (err) {
    console.log('PREVIEW_FAILED', name, String(err));
  }
}
