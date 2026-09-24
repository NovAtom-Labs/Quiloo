"use strict";

function assertEqual(actual, expected, message) {
  if (actual !== expected) throw new Error(`${message}: ${actual}`);
}

const viewer = globalThis.QuilooFileViewer;

const rows = viewer.parseDelimited(
  'bias,current,note\n0,0,"equilibrium, reference"\n1,2e-6,forward\n',
  ",",
);
assertEqual(rows.length, 3, "CSV headers and both data rows should be retained");
assertEqual(rows[1][2], "equilibrium, reference", "quoted delimiters must stay in one cell");

const limited = viewer.limitTable(rows, 2, 2);
assertEqual(limited.rows.length, 2, "table row limit should be enforced");
assertEqual(limited.rows[0].length, 2, "table column limit should be enforced");
assertEqual(limited.truncated, true, "limited data should be marked truncated");

const blocks = viewer.markdownBlocks(
  '# Junction\n\n<script>alert(1)</script>\n\n- Fermi statistics\n- SRH recombination\n',
);
assertEqual(blocks[0].type, "heading", "heading should be recognized");
assertEqual(blocks[1].type, "paragraph", "raw HTML should remain inert text");
assertEqual(blocks[1].text, "<script>alert(1)</script>", "raw HTML must not be interpreted");
assertEqual(blocks[2].type, "list", "list should be recognized");
assertEqual(blocks[2].items.length, 2, "both list items should be retained");

assertEqual(viewer.formatBytes(1536), "1.5 KB", "binary file sizes should be readable");
assertEqual(viewer.sourceLines("a\nb\n").length, 3, "line structure should be preserved");
assertEqual(
  viewer.viewModes("markdown").join(","),
  "preview,source",
  "Markdown should expose safe preview and source modes",
);
assertEqual(
  viewer.viewModes("text").join(","),
  "source",
  "plain text should open directly as source",
);
assertEqual(
  viewer.fileUrl("workspace-1", "results/field x.png", false),
  "/api/workspaces/workspace-1/files/raw?path=results%2Ffield%20x.png",
  "raw file URLs must preserve repository-relative paths",
);
assertEqual(
  viewer.fileUrl("workspace-1", "mesh.bin", true),
  "/api/workspaces/workspace-1/files/raw?path=mesh.bin&download=true",
  "download URLs should request attachment delivery",
);
