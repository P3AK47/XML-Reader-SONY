
import re
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

PAGE = """
<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sony XML Reader</title>
<style>
* { box-sizing:border-box }
body { background:#101416; color:#edf2f0; font:16px/1.5 system-ui,sans-serif;
       max-width:1000px; margin:0 auto; padding:32px 18px }
header { margin-bottom:24px }
h1 { margin:0 0 6px; font-size:clamp(1.7rem,5vw,2.4rem) }
.muted, .hint { color:#aabbb5 }
#drop { padding:32px 20px; text-align:center; border:2px dashed #647c76;
        border-radius:16px; background:#192120; transition:background .15s,border-color .15s }
#drop.dragover { background:#263630; border-color:#e3b45c }
#files { display:block; width:min(100%,420px); margin:16px auto }
.actions { display:flex; justify-content:center; flex-wrap:wrap; gap:10px }
button { min-height:44px; padding:10px 18px; border:0; border-radius:8px;
         cursor:pointer; font:inherit; font-weight:700 }
button:focus-visible, input:focus-visible, summary:focus-visible {
  outline:3px solid #e3b45c; outline-offset:3px
}
button:disabled { opacity:.55; cursor:not-allowed }
.primary { background:#e3b45c; color:#171612 }
.secondary { background:#35403d; color:#edf2f0 }
#fileList { margin:18px auto 0; padding:0; max-width:600px; list-style:none;
            text-align:left; overflow-wrap:anywhere }
#fileList li { padding:5px 0; border-bottom:1px solid #35403d }
#status { min-height:1.5em; margin:14px 0 0 }
#status.error { color:#ff9e91 }
#resultsTools { display:none; margin:24px 0 12px }
#search { width:100%; min-height:44px; padding:10px 12px; border:1px solid #647c76;
          border-radius:8px; background:#192120; color:#edf2f0; font:inherit }
.card { background:#192120; padding:clamp(16px,4vw,24px); margin-top:16px;
        border-radius:12px; overflow-wrap:anywhere }
.card h2 { margin:0 0 14px; font-size:1.1rem }
.card.error { border-left:4px solid #ff9e91 }
.table-wrap { overflow-x:auto }
table { width:100%; border-collapse:collapse; text-align:left }
th, td { padding:10px 8px; border-bottom:1px solid #35403d; vertical-align:top }
th:first-child, td:first-child { color:#aabbb5; width:40% }
.highlights { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
              gap:12px; margin-bottom:16px }
.highlight { padding:14px; background:#101416; border-radius:10px; min-width:0 }
.highlight-label { margin-bottom:4px; color:#aabbb5 }
.iso { font-size:clamp(1.4rem,4vw,1.8rem); color:#e3b45c; font-weight:bold;
       overflow-wrap:anywhere }
.card-actions { display:flex; gap:10px; flex-wrap:wrap; margin-top:16px }
details { margin-top:14px }
pre { white-space:pre-wrap; overflow-wrap:anywhere }
@media (max-width:560px) {
  body { padding:20px 12px }
  #drop { padding:24px 14px }
  th, td { padding:8px 5px }
}
</style>
</head>
<body>
<main>
  <header>
    <h1>Sony XML Reader</h1>
    <p class="muted">อ่าน Metadata จากไฟล์ XML ของกล้อง Sony โดยไฟล์จะถูกประมวลผลในเครื่องนี้</p>
  </header>
  <section id="drop" aria-label="เลือกไฟล์ XML">
    <p><strong>ลากไฟล์ XML มาวางที่นี่</strong> หรือเลือกจากอุปกรณ์</p>
    <input id="files" type="file" accept=".xml,application/xml,text/xml" multiple
           aria-label="เลือกไฟล์ XML">
    <p class="hint">เลือกได้หลายไฟล์ ขนาดรวมไม่เกิน 20 MB</p>
    <ul id="fileList" aria-live="polite"></ul>
    <div class="actions">
      <button id="read" class="primary" type="button" disabled>อ่านข้อมูล</button>
      <button id="clear" class="secondary" type="button" disabled>ล้างรายการ</button>
    </div>
    <p id="status" role="status" aria-live="polite"></p>
  </section>
  <section id="resultsTools" aria-label="ค้นหาในผลลัพธ์">
    <label for="search">ค้นหาชื่อหรือค่า Metadata</label>
    <input id="search" type="search" placeholder="เช่น ISO, FPS, Duration">
    <p id="resultCount" class="muted" aria-live="polite"></p>
  </section>
  <div id="result" aria-live="polite"></div>
</main>
<script>
const drop = document.querySelector("#drop");
const picker = document.querySelector("#files");
const result = document.querySelector("#result");
const fileList = document.querySelector("#fileList");
const readButton = document.querySelector("#read");
const clearButton = document.querySelector("#clear");
const status = document.querySelector("#status");
const resultsTools = document.querySelector("#resultsTools");
const search = document.querySelector("#search");
const resultCount = document.querySelector("#resultCount");
const maxUploadBytes = {{ max_upload_bytes }};
let files = [];

picker.onchange = () => {
  files = [...picker.files].filter(file => file.name.toLowerCase().endsWith(".xml"));
  picker.value = "";
  updateFileList();
};
drop.ondragover = e => {
  e.preventDefault();
  drop.classList.add("dragover");
};
drop.ondragleave = e => {
  if (!drop.contains(e.relatedTarget)) drop.classList.remove("dragover");
};
drop.ondrop = e => {
  e.preventDefault();
  drop.classList.remove("dragover");
  files = [...e.dataTransfer.files].filter(file =>
    file.name.toLowerCase().endsWith(".xml"));
  updateFileList();
};
clearButton.onclick = () => {
  files = [];
  fileList.replaceChildren();
  clearResults();
  readButton.disabled = true;
  clearButton.disabled = true;
  status.textContent = "";
  status.classList.remove("error");
  picker.value = "";
};
readButton.onclick = async () => {
  if (!files.length) {
    setStatus("กรุณาเลือกไฟล์ XML ก่อน", true);
    return;
  }
  readButton.disabled = true;
  clearButton.disabled = true;
  setStatus("กำลังอ่านข้อมูล...");
  result.replaceChildren();
  resultsTools.style.display = "none";
  const form = new FormData();
  files.forEach(f => form.append("files", f));
  try {
    const response = await fetch("/analyze", {method:"POST", body:form});
    let data;
    try {
      data = await response.json();
    } catch {
      throw Error(response.status === 413
        ? "ไฟล์มีขนาดใหญ่เกินไป (จำกัดรวม 20 MB)"
        : "เซิร์ฟเวอร์ตอบกลับผิดรูปแบบ กรุณาลองใหม่");
    }
    if (!response.ok) throw Error(data.error || "อ่านไม่สำเร็จ");
    result.replaceChildren();
    data.forEach(item => result.append(makeCard(item)));
    resultsTools.style.display = data.length ? "block" : "none";
    search.value = "";
    updateResultCount();
    setStatus(data.length ? "อ่านไฟล์เสร็จแล้ว" : "ไม่พบไฟล์ที่อ่านได้", !data.length);
  } catch (err) {
    setStatus(err.message || "เกิดข้อผิดพลาด กรุณาลองใหม่", true);
  } finally {
    readButton.disabled = files.length === 0
      || files.reduce((total, file) => total + file.size, 0) > maxUploadBytes;
    clearButton.disabled = files.length === 0;
  }
};
search.oninput = filterResults;
function updateFileList() {
  clearResults();
  fileList.replaceChildren();
  files.forEach(file => {
    const entry = document.createElement("li");
    entry.textContent = file.name + " (" + formatFileSize(file.size) + ")";
    fileList.append(entry);
  });
  const totalBytes = files.reduce((total, file) => total + file.size, 0);
  const tooLarge = totalBytes > maxUploadBytes;
  readButton.disabled = files.length === 0 || tooLarge;
  clearButton.disabled = files.length === 0;
  if (files.length === 0) {
    setStatus("ไม่พบไฟล์ .XML ที่รองรับ", true);
  } else if (tooLarge) {
    setStatus("ขนาดไฟล์รวมเกิน 20 MB กรุณาเลือกไฟล์ให้น้อยลง", true);
  } else {
    setStatus("เลือกแล้ว " + files.length + " ไฟล์ รวม " + formatFileSize(totalBytes));
  }
}
function clearResults() {
  result.replaceChildren();
  resultsTools.style.display = "none";
  search.value = "";
  resultCount.textContent = "";
}
function setStatus(message, isError = false) {
  status.textContent = message;
  status.classList.toggle("error", isError);
}
function formatFileSize(bytes) {
  if (bytes === 0) return "0 KB";
  return bytes < 1024 * 1024
    ? Math.max(1, Math.round(bytes / 1024)) + " KB"
    : (bytes / (1024 * 1024)).toFixed(1) + " MB";
}
function makeCard(item) {
  const card = document.createElement("section");
  card.className = item.error ? "card error" : "card";
  const title = document.createElement("h2");
  title.textContent = item.filename;
  card.append(title);
  if (item.error) {
    const p = document.createElement("p");
    p.textContent = item.error;
    card.append(p);
    return card;
  }
  const highlights = document.createElement("div");
  highlights.className = "highlights";
  highlights.append(
    makeHighlight("รุ่นกล้อง (Model Name)", item.models?.length
      ? [...new Set(item.models)].join(" / ")
      : "ไม่พบชื่อรุ่นกล้องใน XML")
  );
  highlights.append(
    makeHighlight("ค่า ISO ที่ระบุชัดเจนใน XML", item.iso.length
      ? [...new Set(item.iso.map(x => x.value))].join(" / ")
      : "ไม่พบแท็ก ISO")
  );
  card.append(highlights);

  const tableWrap = document.createElement("div");
  tableWrap.className = "table-wrap";
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headerRow = document.createElement("tr");
  ["รายการ", "ค่า"].forEach(label => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    headerRow.append(th);
  });
  head.append(headerRow);
  table.append(head);
  const body = document.createElement("tbody");
  item.fields.forEach(field => {
    const tr = document.createElement("tr");
    const a = document.createElement("td");
    const b = document.createElement("td");
    a.textContent = formatFieldName(field.displayTag || field.tag);
    b.textContent = field.displayValue || field.value;
    tr.append(a,b);
    body.append(tr);
  });
  table.append(body);
  tableWrap.append(table);
  card.append(tableWrap);

  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = "ดู XML ที่อ่านได้ทั้งหมด";
  const pre = document.createElement("pre");
  pre.style.whiteSpace = "pre-wrap";
  pre.textContent = JSON.stringify(item.fields, null, 2);
  details.append(summary, pre);
  card.append(details);

  const actions = document.createElement("div");
  actions.className = "card-actions";
  const download = document.createElement("button");
  download.className = "secondary";
  download.type = "button";
  download.textContent = "ดาวน์โหลด JSON";
  download.onclick = () => {
    const blob = new Blob([JSON.stringify(item, null, 2)],
      {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = item.filename.replace(/\.xml$/i, "") + ".json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  actions.append(download);
  card.append(actions);
  return card;
}
function makeHighlight(label, text) {
  const panel = document.createElement("div");
  panel.className = "highlight";
  const heading = document.createElement("div");
  heading.className = "highlight-label";
  heading.textContent = label;
  const value = document.createElement("div");
  value.className = "iso";
  value.textContent = text;
  panel.append(heading, value);
  return panel;
}
function filterResults() {
  const query = search.value.trim().toLocaleLowerCase();
  document.querySelectorAll("#result .card").forEach(card => {
    let matchingRows = 0;
    card.querySelectorAll("tbody tr").forEach(row => {
      const matches = !query || row.textContent.toLocaleLowerCase().includes(query);
      row.hidden = !matches;
      if (matches) matchingRows++;
    });
    const matchesTitle = card.querySelector("h2").textContent
      .toLocaleLowerCase().includes(query);
    card.hidden = Boolean(query) && !matchesTitle && matchingRows === 0
      && !card.classList.contains("error");
  });
  updateResultCount();
}
function updateResultCount() {
  const visibleCards = [...document.querySelectorAll("#result .card")]
    .filter(card => !card.hidden).length;
  resultCount.textContent = "แสดง " + visibleCards + " จาก "
    + document.querySelectorAll("#result .card").length + " ไฟล์";
}
function formatFieldName(tag) {
  const labels = {"LtcChangeTable@tcFps": "FPS"};
  if (labels[tag]) return labels[tag];

  const acronyms = {
    exif: "EXIF", fps: "FPS", gps: "GPS", iso: "ISO",
    lut: "LUT", ltc: "LTC", tc: "TC", timecode: "Timecode", utc: "UTC", wb: "WB",
    xml: "XML"
  };
  return tag
    .replace(/@value$/i, "")
    .replace(/@/g, " ")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .trim()
    .split(/\s+/)
    .map(word => acronyms[word.toLowerCase()]
      || word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}
</script>
</body>
</html>
"""

# จับเฉพาะชื่อแท็กที่ระบุ ISO โดยตรง
ISO_NAMES = {"iso", "isosensitivity", "isospeed", "isonumber"}
MODEL_NAMES = {"model", "modelname", "cameramodel", "cameramodelname"}

def format_aspect_ratio(value):
    value = value.strip()
    if not value or len(value) > 100:
        return value

    ratio_match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)", value
    )
    dimensions_match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)", value, re.IGNORECASE
    )
    try:
        if ratio_match or dimensions_match:
            match = ratio_match or dimensions_match
            ratio = Fraction(match.group(1)) / Fraction(match.group(2))
        elif re.fullmatch(r"\d+(?:\.\d+)?", value):
            ratio = Fraction(value)
            if ratio < 1:
                ratio = 1 / ratio
        else:
            return value
    except (ValueError, ZeroDivisionError):
        return value

    if ratio <= 0:
        return value

    simplified = ratio.limit_denominator(100)
    if abs(float(simplified - ratio)) <= max(float(ratio) * 0.002, 0.0001):
        if simplified.denominator <= 10:
            return f"{simplified.numerator}:{simplified.denominator}"
        ratio_value = float(ratio)
    else:
        ratio_value = float(ratio)

    formatted = f"{ratio_value:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}:1"

@app.get("/")
def home():
    return render_template_string(PAGE, max_upload_bytes=MAX_UPLOAD_BYTES)

@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "ขนาดไฟล์รวมเกิน 20 MB"}), 413

@app.post("/analyze")
def analyze():
    results = []
    uploads = request.files.getlist("files")
    if not uploads or all(not upload.filename for upload in uploads):
        return jsonify({"error": "กรุณาเลือกไฟล์ XML"}), 400

    for upload in uploads:
        if not upload.filename:
            results.append({"filename": "", "error": "ไม่พบชื่อไฟล์"})
            continue
        name = Path(upload.filename.replace("\\", "/")).name
        if not name.lower().endswith(".xml"):
            results.append({"filename": name, "error": "รองรับเฉพาะ XML"})
            continue
        try:
            raw = upload.read()
            root = ET.fromstring(raw)
            parents = {
                child: parent
                for parent in root.iter()
                for child in parent
            }
            fields = []
            iso = []
            models = []

            for node in root.iter():
                tag = node.tag.split("}")[-1].split(":")[-1]
                display_tag = tag
                parent = parents.get(node)
                if tag.lower() == "item" and parent is not None:
                    parent_tag = parent.tag.split("}")[-1].split(":")[-1]
                    normalized_parent = re.sub(r"[^a-z]", "", parent_tag.lower())
                    if "lut" in normalized_parent:
                        display_tag = "LUT"
                    elif "gamut" in normalized_parent:
                        display_tag = "Gamut"

                value = (node.text or "").strip()
                if value:
                    field = {"tag": tag, "value": value}
                    if display_tag != tag:
                        field["displayTag"] = display_tag
                    normalized_tag = re.sub(r"[^a-z]", "", display_tag.lower())
                    if "aspectratio" in normalized_tag:
                        field["displayValue"] = format_aspect_ratio(value)
                    fields.append(field)
                    normalized_tag_name = re.sub(r"[^a-z]", "", tag.lower())
                    if normalized_tag_name in ISO_NAMES:
                        iso.append({"tag": tag, "value": value})
                    if normalized_tag_name in MODEL_NAMES:
                        models.append(value)

                for key, val in node.attrib.items():
                    attr = key.split("}")[-1].split(":")[-1]
                    display_attr_tag = display_tag + "@" + attr
                    field = {"tag": tag + "@" + attr, "value": val}
                    if display_attr_tag != field["tag"]:
                        field["displayTag"] = display_attr_tag
                    normalized_field_name = re.sub(
                        r"[^a-z]", "", display_attr_tag.lower()
                    )
                    if "aspectratio" in normalized_field_name:
                        field["displayValue"] = format_aspect_ratio(val)
                    fields.append(field)
                    normalized_attr_name = re.sub(r"[^a-z]", "", attr.lower())
                    if normalized_attr_name in ISO_NAMES:
                        iso.append({"tag": tag + "@" + attr, "value": val})
                    if normalized_attr_name in MODEL_NAMES:
                        models.append(val)

            results.append({
                "filename": name,
                "iso": iso,
                "models": list(dict.fromkeys(models)),
                "fields": fields
            })
        except ET.ParseError:
            results.append({
                "filename": name,
                "error": "ไฟล์ XML มีรูปแบบไม่ถูกต้อง"
            })
        except Exception as exc:
            app.logger.exception("Failed to analyze uploaded XML file: %s", name)
            results.append({
                "filename": name,
                "error": "เกิดข้อผิดพลาดขณะอ่านไฟล์"
            })
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)