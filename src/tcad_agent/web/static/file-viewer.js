"use strict";

(() => {
  function parseDelimited(source, delimiter) {
    const rows = [];
    let row = [];
    let cell = "";
    let quoted = false;
    for (let index = 0; index < source.length; index += 1) {
      const character = source[index];
      if (character === '"') {
        if (quoted && source[index + 1] === '"') {
          cell += '"';
          index += 1;
        } else {
          quoted = !quoted;
        }
      } else if (character === delimiter && !quoted) {
        row.push(cell);
        cell = "";
      } else if ((character === "\n" || character === "\r") && !quoted) {
        if (character === "\r" && source[index + 1] === "\n") index += 1;
        row.push(cell);
        rows.push(row);
        row = [];
        cell = "";
      } else {
        cell += character;
      }
    }
    if (cell || row.length) {
      row.push(cell);
      rows.push(row);
    }
    return rows;
  }

  function limitTable(rows, rowLimit = 500, columnLimit = 100) {
    const limitedRows = rows.slice(0, rowLimit).map((row) => row.slice(0, columnLimit));
    return {
      rows: limitedRows,
      truncated: rows.length > rowLimit || rows.some((row) => row.length > columnLimit),
    };
  }

  function markdownBlocks(source) {
    const blocks = [];
    const lines = source.split(/\r?\n/);
    let index = 0;
    while (index < lines.length) {
      const line = lines[index];
      if (!line.trim()) {
        index += 1;
        continue;
      }
      const heading = line.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        blocks.push({type: "heading", level: heading[1].length, text: heading[2]});
        index += 1;
        continue;
      }
      if (line.startsWith("```")) {
        const language = line.slice(3).trim();
        const content = [];
        index += 1;
        while (index < lines.length && !lines[index].startsWith("```")) {
          content.push(lines[index]);
          index += 1;
        }
        if (index < lines.length) index += 1;
        blocks.push({type: "code", language, text: content.join("\n")});
        continue;
      }
      if (/^\s*[-*+]\s+/.test(line)) {
        const items = [];
        while (index < lines.length && /^\s*[-*+]\s+/.test(lines[index])) {
          items.push(lines[index].replace(/^\s*[-*+]\s+/, ""));
          index += 1;
        }
        blocks.push({type: "list", items});
        continue;
      }
      if (/^>\s?/.test(line)) {
        const parts = [];
        while (index < lines.length && /^>\s?/.test(lines[index])) {
          parts.push(lines[index].replace(/^>\s?/, ""));
          index += 1;
        }
        blocks.push({type: "quote", text: parts.join("\n")});
        continue;
      }
      const paragraph = [line];
      index += 1;
      while (
        index < lines.length
        && lines[index].trim()
        && !/^(#{1,6})\s+/.test(lines[index])
        && !/^\s*[-*+]\s+/.test(lines[index])
        && !/^>\s?/.test(lines[index])
        && !lines[index].startsWith("```")
      ) {
        paragraph.push(lines[index]);
        index += 1;
      }
      blocks.push({type: "paragraph", text: paragraph.join(" ")});
    }
    return blocks;
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Number((bytes / 1024).toFixed(1))} KB`;
    return `${Number((bytes / (1024 * 1024)).toFixed(1))} MB`;
  }

  function sourceLines(source) {
    return source.split("\n");
  }

  function viewModes(kind) {
    if (["markdown", "json", "csv", "tsv"].includes(kind)) {
      return ["preview", "source"];
    }
    if (kind === "text") return ["source"];
    return ["preview"];
  }

  function fileUrl(workspaceId, path, download = false) {
    const base = `/api/workspaces/${encodeURIComponent(workspaceId)}/files/raw`;
    return `${base}?path=${encodeURIComponent(path)}${download ? "&download=true" : ""}`;
  }

  globalThis.AgentKronigFileViewer = {
    fileUrl,
    formatBytes,
    limitTable,
    markdownBlocks,
    parseDelimited,
    sourceLines,
    viewModes,
  };
})();
