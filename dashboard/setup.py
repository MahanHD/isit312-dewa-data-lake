import json
import sys
import time
import urllib.request
from pathlib import Path

REPORTS = Path("/workspace/hive/02_reports.hql")
NOTEBOOK = Path("/opt/zeppelin/notebook/DEWA dashboard_2MDEWA001.zpln")
API = "http://localhost:8080/api/interpreter/setting"

CHARTS = {
    1: ("multiBarChart", 0, [2]),
    3: ("lineChart", 0, [1]),
    7: ("multiBarChart", 0, [3, 4]),
    8: ("lineChart", 0, [1]),
    9: ("multiBarChart", 0, [1]),
    13: ("multiBarChart", 1, [4]),
}


def reports():
    title, sql = None, []
    for line in REPORTS.read_text().splitlines():
        if line.startswith("-- ") and line[3:4].isdigit():
            title = line[3:]
        elif line.strip() and not line.lstrip().startswith("--"):
            sql.append(line)
            if line.rstrip().endswith(";"):
                yield int(title.split(".")[0]), title, "\n".join(sql).rstrip().rstrip(";")
                sql = []


def graph(number):
    if number not in CHARTS:
        return {"mode": "table", "height": 300.0}
    mode, key, values = CHARTS[number]
    return {
        "mode": mode, "height": 300.0, "optionOpen": False,
        "keys": [{"name": "", "index": key, "aggr": "sum"}],
        "values": [{"name": "", "index": v, "aggr": "sum"} for v in values],
        "groups": [],
    }


def paragraph(number, title, text, interpreter="jdbc"):
    return {
        "id": f"paragraph_dewa_{number:02d}",
        "title": title,
        "text": f"%{interpreter}\n{text}",
        "config": {"title": True, "colWidth": 12.0, "editorHide": interpreter == "md",
                   "editorSetting": {"language": "sql" if interpreter == "jdbc" else "markdown"},
                   "results": {"0": {"graph": graph(number)}} if interpreter == "jdbc" else {}},
        "settings": {"params": {}, "forms": {}},
        "status": "READY",
    }


def make_notebook():
    intro = ("## DEWA smart meter reports\n"
             "Reports from `hive/02_reports.hql`, run on Hive. Pick a month at the top, then Run all.")
    paragraphs = [paragraph(0, "About", intro, "md")]
    for number, title, sql in reports():
        paragraphs.append(paragraph(number, title, sql.replace("${hivevar:report_month}", "$${month=2013-01}")))
    note = {"id": "2MDEWA001", "name": "DEWA dashboard", "defaultInterpreterGroup": "jdbc",
            "paragraphs": paragraphs, "config": {}, "info": {}, "noteParams": {}, "noteForms": {},
            "angularObjects": {}}
    NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    NOTEBOOK.write_text(json.dumps(note, indent=2))
    print(f"Wrote {NOTEBOOK} with {len(paragraphs) - 1} reports")


def call(url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, method="PUT" if data is not None else "GET",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def setup_interpreter(jar):
    for _ in range(90):
        try:
            settings = call(API)["body"]
            break
        except OSError:
            time.sleep(2)
    else:
        sys.exit("Zeppelin did not start, so the jdbc interpreter was not set up")
    jdbc = next(s for s in settings if s["name"] == "jdbc")
    values = {"default.url": "jdbc:hive2://hive:10000/dewa?hive.server2.in.place.progress=false", "default.driver": "org.apache.hive.jdbc.HiveDriver",
              "default.user": "hive", "default.password": "",
              # one query at a time, or Hive log lines from parallel reports get mixed into the result tables
              "zeppelin.jdbc.concurrent.use": "false"}
    for name, value in values.items():
        jdbc["properties"].setdefault(name, {"name": name, "type": "string"})["value"] = value
    jdbc["dependencies"] = [{"groupArtifactVersion": jar, "local": False}]
    call(f"{API}/{jdbc['id']}", {"properties": jdbc["properties"], "dependencies": jdbc["dependencies"],
                                 "option": jdbc["option"]})
    print("jdbc interpreter now points at Hive")


if __name__ == "__main__":
    if sys.argv[1] == "notebook":
        make_notebook()
    else:
        setup_interpreter(sys.argv[2])
