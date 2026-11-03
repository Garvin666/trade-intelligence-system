export async function parseUserDataFile(file: File): Promise<Record<string, unknown>> {
  const text = await file.text();
  if (file.name.toLowerCase().endsWith(".csv")) {
    const rows = parseCsv(text);
    return {
      file_name: file.name,
      history: rows,
      source: "user_csv",
    };
  }
  const data = JSON.parse(text) as unknown;
  if (Array.isArray(data)) {
    return {
      file_name: file.name,
      history: data,
      source: "user_json",
    };
  }
  return {
    file_name: file.name,
    ...(data as Record<string, unknown>),
    source: "user_json",
  };
}

function parseCsv(text: string): Record<string, unknown>[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2) return [];
  const headers = splitCsvLine(lines[0]).map((header) => header.trim());
  return lines.slice(1).map((line) => {
    const values = splitCsvLine(line);
    const row: Record<string, unknown> = {};
    headers.forEach((header, index) => {
      const value = values[index];
      row[header] = value === undefined ? "" : tryNumber(value.trim());
    });
    return row;
  });
}

function splitCsvLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"') {
      if (quoted && line[index + 1] === '"') {
        current += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (char === "," && !quoted) {
      result.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  result.push(current);
  return result;
}

function tryNumber(value: string): string | number {
  if (value === "") return "";
  const number = Number(value);
  return Number.isFinite(number) && value.trim() !== "" ? number : value;
}
