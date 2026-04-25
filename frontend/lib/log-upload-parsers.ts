/**
 * Parsers for the upload screen.
 *
 * **Option A — JSON file:** a single top-level JSON array of log row objects
 * (see backend `upload_logs` / `api_logs.json`).
 *
 * Also accepts `{ "format": "live_monitor_logs_v1", "logs": [...] }` from live monitoring export.
 *
 * **Option B — Rdv / mixed text logs:** line-oriented scan. Rows are created from
 * `Rest Response Message:` blocks that contain XML with `RdvStatusCode`.
 * Endpoint: last `RequestUri: '...'`, or `Request URI : https://...` (Dewa), then
 * `Message Label [url]`, then `LABEL: [url]`. **Response time (ms):** end timestamp
 * minus first `RdvMessageId is <id>` (business id) on an earlier line; if missing,
 * `Message Id is [correlation-uuid]` matched to an optional first-line GUID in the
 * bracket before `<Response>`, when that GUID is present. Otherwise 0.
 * **raw_json:** JSON string `{ "source": "rdv_response_xml", "filename", "xml" }`.
 */

export type LogRow = Record<string, unknown>;

const RDV_PIPE_PREFIX = /^(\d{2}\/\d{2}\/\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\|/;

/**
 * Map DD/MM/YY from Rdv logs to ISO-8601. Two-digit years: 00–99 → 2000–2099
 * (common for 2020s integration logs).
 */
export function rdvLineTimestampToIso(raw: string): string {
  const m = raw.match(
    /^(\d{1,2})\/(\d{1,2})\/(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})/
  );
  if (!m) return new Date().toISOString();
  const [, day, mon, y2, hh, mm, ss, ms] = m;
  const year = 2000 + (parseInt(y2, 10) % 100);
  const pad = (n: string, w: number) => n.padStart(w, "0");
  return `${year}-${pad(mon, 2)}-${pad(day, 2)}T${pad(hh, 2)}:${pad(mm, 2)}:${pad(ss, 2)}.${ms}Z`;
}

function lineTimestampMsFromRdvLine(line: string): number | null {
  const p = line.match(RDV_PIPE_PREFIX);
  if (!p) return null;
  return new Date(rdvLineTimestampToIso(p[1])).getTime();
}

function extractRequestUriFromLine(line: string): string | null {
  const m1 = line.match(/RequestUri:\s*'([^']+)'/i);
  if (m1) return m1[1];
  const m2 = line.match(/RequestUri:\s*"([^"]+)"/i);
  if (m2) return m2[1];
  // Dewa / HTTP client style
  const m3 = line.match(/Request URI\s*:\s*(\S+)/i);
  if (m3) return m3[1].replace(/,+$/, "").trim();
  return null;
}

function extractMessageLabelFromLine(line: string): string | null {
  const m1 = line.match(/Message Label \[([^\]]+)\]/i);
  if (m1) return m1[1].trim();
  const m2 = line.match(/LABEL:\s*\[([^\]]*)\]/i);
  return m2 ? m2[1].trim() : null;
}

/**
 * `Rest Response Message: [ ... ]` may span several lines. Dewa: first line has
 * `[<guid>` with no `]`; XML is on the next line(s) ending with `]`.
 */
function collectRestResponseBlock(lines: string[], startIndex: number): { block: string; nextIndex: number } {
  const first = lines[startIndex] ?? "";
  const idx = first.indexOf("Rest Response Message:");
  if (idx < 0) return { block: "", nextIndex: startIndex + 1 };

  let acc = first.slice(idx);
  let i = startIndex;
  const o = acc.indexOf("[");
  const c = acc.lastIndexOf("]");
  const hasOpenBracket = acc.includes("[");
  const hasCloseAfterOpen = c > o;

  if (hasOpenBracket && hasCloseAfterOpen) {
    return { block: acc, nextIndex: startIndex + 1 };
  }
  if (!hasOpenBracket) {
    return { block: acc, nextIndex: startIndex + 1 };
  }

  while (i + 1 < lines.length && !acc.includes("]")) {
    i += 1;
    acc += "\n" + lines[i];
  }
  return { block: acc, nextIndex: i + 1 };
}

/** Inner bracket content: may start with a correlation GUID, then XML. */
function extractXmlFromBracketInner(inner: string): string | null {
  const t = inner.trim();
  if (t.startsWith("<")) return t;
  const i = t.indexOf("<");
  if (i < 0) return null;
  return t.slice(i).trim();
}

function leadingGuidFromBracketInner(inner: string): string | null {
  const firstLine = (inner.trim().split(/\r?\n/)[0] ?? "").trim();
  const m = firstLine.match(
    /^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$/i
  );
  return m ? m[0] : null;
}

function parseResponseXmlBody(xml: string): {
  status_code: number;
  method: string;
  trace_id: string;
  error_text: string | null;
} | null {
  const rStatus = xml.match(/<RdvStatusCode>(\d+)<\/RdvStatusCode>/i);
  const rMethod = xml.match(/<RdvMethod>([^<]*)<\/RdvMethod>/i);
  // Business ids (e.g. 00006220260113101015) or UUIDs
  const rId = xml.match(/<RdvMessageId>([^<]+)<\/RdvMessageId>/i);
  if (!rStatus) return null;
  return {
    status_code: parseInt(rStatus[1], 10),
    method: (rMethod?.[1] ?? "GET").trim() || "GET",
    trace_id: (rId?.[1] ?? "").trim(),
    error_text: (() => {
      const et = xml.match(/<error_text>([^<]*)<\/error_text>/i);
      const t1 = et?.[1]?.trim() ?? "";
      if (t1.length > 0) return t1;
      const um = xml.match(/<userMessage>([^<]*)<\/userMessage>/i);
      const t2 = um?.[1]?.trim() ?? "";
      return t2.length > 0 ? t2 : null;
    })(),
  };
}

function timestampFromRdvLineHead(fullLine: string): string {
  const p = fullLine.match(RDV_PIPE_PREFIX);
  if (p) return rdvLineTimestampToIso(p[1]);
  return new Date().toISOString();
}

/**
 * **Option A** — one JSON file = one array of log objects. Throws with a clear message
 * on invalid top-level shape.
 */
export function parseUploadJsonFile(text: string): LogRow[] {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("Invalid JSON: file must contain a single JSON array of log objects.");
  }
  if (
    data !== null &&
    typeof data === "object" &&
    !Array.isArray(data) &&
    (data as { format?: string }).format === "live_monitor_logs_v1" &&
    Array.isArray((data as { logs?: unknown }).logs)
  ) {
    data = (data as { logs: unknown }).logs;
  }
  if (!Array.isArray(data)) {
    throw new Error("File must be a JSON array of log objects.");
  }
  for (const item of data) {
    if (item === null || typeof item !== "object" || Array.isArray(item)) {
      throw new Error("Log array must contain only objects, not null or arrays.");
    }
  }
  return data as LogRow[];
}

function responseTimeMs(
  endMs: number,
  rdvId: string,
  leadingGuid: string | null,
  startByRdv: Map<string, number>,
  startByGuid: Map<string, number>
): number {
  let t0: number | undefined;
  if (rdvId && startByRdv.has(rdvId)) t0 = startByRdv.get(rdvId);
  if (t0 === undefined && leadingGuid && startByGuid.has(leadingGuid)) t0 = startByGuid.get(leadingGuid);
  if (t0 === undefined) return 0;
  const d = endMs - t0;
  return d >= 0 && d < 86_400_000 ? d : 0;
}

/**
 * **Option B** — Rdv-style mixed text; never `JSON.parse` the whole file.
 */
export function parseRdvOrTextLogFile(text: string, filename: string): {
  logs: LogRow[];
  warnings: string[];
} {
  if (text.trim().length === 0) {
    return { logs: [], warnings: [] };
  }
  const lines = text.split(/\r?\n/);
  const startByRdvMessageId = new Map<string, number>();
  const startByMessageGuid = new Map<string, number>();

  for (const line of lines) {
    const ms = lineTimestampMsFromRdvLine(line);
    if (ms == null) continue;
    const rRdv = line.match(/RdvMessageId is (\S+)/i);
    if (rRdv) {
      const id = rRdv[1].trim();
      if (id && !startByRdvMessageId.has(id)) startByRdvMessageId.set(id, ms);
    }
    const rGuid = line.match(/Message Id is \[([0-9A-Fa-f-]{36})\]/i);
    if (rGuid) {
      const g = rGuid[1].toLowerCase();
      if (!startByMessageGuid.has(g)) startByMessageGuid.set(g, ms);
    }
  }

  let lastRequestUri: string | null = null;
  let lastMessageLabel: string | null = null;
  const logs: LogRow[] = [];
  const warnings: string[] = [];
  let i = 0;
  let skippedXml = 0;

  while (i < lines.length) {
    const line = lines[i] ?? "";
    const uri = extractRequestUriFromLine(line);
    if (uri) lastRequestUri = uri;
    const lab = extractMessageLabelFromLine(line);
    if (lab) lastMessageLabel = lab;

    if (line.includes("Rest Response Message:")) {
      const headForTs = line;
      const endMs = lineTimestampMsFromRdvLine(headForTs) ?? 0;
      const { block, nextIndex } = collectRestResponseBlock(lines, i);
      i = nextIndex;
      const after = block.split("Rest Response Message:").pop() ?? "";
      const a = after.indexOf("[");
      const b = after.lastIndexOf("]");
      if (a < 0 || b <= a) {
        skippedXml += 1;
        continue;
      }
      const inner = after.slice(a + 1, b).trim();
      const leadGuid = leadingGuidFromBracketInner(inner);
      const innerXml = extractXmlFromBracketInner(inner);
      if (!innerXml) {
        skippedXml += 1;
        continue;
      }
      const parsed = parseResponseXmlBody(innerXml);
      if (!parsed) {
        skippedXml += 1;
        continue;
      }
      const leadGuidKey = leadGuid ? leadGuid.toLowerCase() : null;
      const rtm = responseTimeMs(
        endMs,
        parsed.trace_id,
        leadGuidKey,
        startByRdvMessageId,
        startByMessageGuid
      );
      const raw = JSON.stringify({
        source: "rdv_response_xml" as const,
        filename,
        xml: innerXml,
      });
      const endpoint = lastRequestUri ?? lastMessageLabel ?? "/unknown";
      logs.push({
        timestamp: timestampFromRdvLineHead(headForTs),
        endpoint: typeof endpoint === "string" && endpoint ? endpoint : "/unknown",
        method: parsed.method,
        status_code: parsed.status_code,
        response_time_ms: rtm,
        error_message: parsed.error_text,
        service: "RdvRestService",
        trace_id: parsed.trace_id || (leadGuid ?? "unknown"),
        raw_json: raw,
      });
    } else {
      i += 1;
    }
  }

  if (skippedXml > 0) {
    warnings.push(
      `Skipped ${skippedXml} rest response line(s) without a usable RdvStatusCode or XML block.`
    );
  }
  if (lines.length > 0 && logs.length === 0) {
    warnings.push(
      "No entries parsed. Expected lines containing 'Rest Response Message:' with XML including <RdvStatusCode>."
    );
  }
  return { logs, warnings };
}
