import { describe, expect, it } from "vitest";
import {
  parseRdvOrTextLogFile,
  parseUploadJsonFile,
  rdvLineTimestampToIso,
} from "./log-upload-parsers";

/** Redacted: structure only, no PII. Single-line Rest Response + .NET RequestUri. */
const REDACTED_RDV_SNIP = `26/03/30 13:37:38.717|2|009|RequestThreadProc   |Got Message, Message Label [http://127.0.0.1:8555/rim_x/api/rim]
26/03/30 13:37:38.913|4|009|PostRequest         |Post Request Method: POST, RequestUri: 'http://127.0.0.1:8555/rim_x/api/rim', Version: 1.1, Content: System.Net.Http.StringContent, Headers:
26/03/30 13:37:39.031|7|009|Invoke              |Rest Response Message: [<ExampleResponse><RdvStatusCode>200</RdvStatusCode><RdvMethod>POST</RdvMethod><RdvMessageId>aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee</RdvMessageId></ExampleResponse>]
`;

/**
 * Redacted: Dewa-style — correlation GUID on line after `Rest Response Message: [`,
 * one line, then `</XResponse>]`; Request URI with spaces; Rdv business id; timing for RTT.
 */
const REDACTED_DEWA_SNIP = `26/01/13 11:27:15.213|1|X|X   |X
26/01/13 11:27:15.239|4|X|Invoke              |RdvMessageId is 00006220260113101015
26/01/13 11:27:15.254|4|X|PostTokenRequest    |Request URI : https://api.test.example.com/v55/pay/consumer/001?ch=WEB
26/01/13 11:27:15.254|1|X|X   |RdvMessageId is 00006220260113101015
26/01/13 11:27:15.495|4|X|Invoke              |Rest Response Message: [aaaaaaaa-bbbb-cccc-ffff-00000000dddd
<EnquiryResponse><RdvMessageId>00006220260113101015</RdvMessageId><RdvStatusCode>401</RdvStatusCode><RdvMethod>Post</RdvMethod><userMessage>Access Token</userMessage></EnquiryResponse>]
`;

describe("rdvLineTimestampToIso", () => {
  it("maps Rdv date prefix to ISO", () => {
    expect(rdvLineTimestampToIso("26/03/30 13:37:39.031")).toBe("2030-03-26T13:37:39.031Z");
  });
});

describe("parseUploadJsonFile", () => {
  it("parses a JSON array of objects", () => {
    const logs = parseUploadJsonFile(
      JSON.stringify([{ timestamp: "t", endpoint: "/a", method: "GET", status_code: 200 }])
    );
    expect(logs).toHaveLength(1);
    expect(logs[0].endpoint).toBe("/a");
  });

  it("rejects non-array", () => {
    expect(() => parseUploadJsonFile("{}")).toThrow(/array/);
  });

  it("rejects null elements", () => {
    expect(() => parseUploadJsonFile("[null]")).toThrow();
  });

  it("accepts live_monitor_logs_v1 wrapper", () => {
    const logs = parseUploadJsonFile(
      JSON.stringify({
        format: "live_monitor_logs_v1",
        logs: [{ timestamp: "t", endpoint: "/x", method: "GET", status_code: 201 }],
      }),
    );
    expect(logs).toHaveLength(1);
    expect(logs[0].status_code).toBe(201);
  });
});

describe("parseRdvOrTextLogFile", () => {
  it("builds one row from Rest Response with RequestUri and Message Label", () => {
    const { logs, warnings } = parseRdvOrTextLogFile(REDACTED_RDV_SNIP, "sample.log");
    expect(logs).toHaveLength(1);
    const row = logs[0];
    expect(row.status_code).toBe(200);
    expect(row.method).toBe("POST");
    expect(row.trace_id).toBe("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
    expect(row.endpoint).toBe("http://127.0.0.1:8555/rim_x/api/rim");
    expect(row.service).toBe("RdvRestService");
    expect(String(row.raw_json)).toContain("rdv_response_xml");
    expect(warnings).toEqual([]);
  });

  it("parses Dewa-style multiline Rest Response, Request URI line, and response_time_ms", () => {
    const { logs, warnings } = parseRdvOrTextLogFile(REDACTED_DEWA_SNIP, "dewa.log");
    expect(warnings).toEqual([]);
    expect(logs).toHaveLength(1);
    const row = logs[0];
    expect(row.status_code).toBe(401);
    expect(row.method).toBe("Post");
    expect(row.trace_id).toBe("00006220260113101015");
    expect(String(row.endpoint)).toContain("api.test.example.com");
    expect(row.response_time_ms).toBe(256);
    expect(String(row.error_message)).toContain("Access Token");
  });

  it("uses LABEL: [url] when Request URI is absent", () => {
    const s = `26/01/13 10:00:00.000|2|X|X|LABEL: [https://h.example/ops/]
26/01/13 10:00:00.200|4|X|X|RdvMessageId is id-label-1
26/01/13 10:00:00.500|4|X|X|Rest Response Message: [<X><RdvMessageId>id-label-1</RdvMessageId><RdvStatusCode>200</RdvStatusCode><RdvMethod>GET</RdvMethod></X>]`;
    const { logs } = parseRdvOrTextLogFile(s, "x.log");
    expect(logs[0].endpoint).toBe("https://h.example/ops/");
  });

  it("returns empty for empty file without scary warnings", () => {
    const { logs, warnings } = parseRdvOrTextLogFile("   \n  ", "empty.log");
    expect(logs).toHaveLength(0);
    expect(warnings).toEqual([]);
  });
});
