"""Flask web app: upload an Excel file, get back the same file annotated with
F5 hardware End-of-Life / End-of-Support dates."""

from __future__ import annotations

import io
import os
from pathlib import Path

from flask import Flask, render_template, request, send_file, abort

from annotator import annotate_workbook
from matcher import data_revision


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", data_revision=data_revision())


@app.route("/annotate", methods=["POST"])
def annotate():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        abort(400, "No file uploaded")

    name = upload.filename
    if not name.lower().endswith((".xlsx", ".xlsm")):
        abort(400, "Only .xlsx / .xlsm files are supported.")

    raw = upload.read()
    if not raw:
        abort(400, "Uploaded file is empty.")

    try:
        annotated, _stats = annotate_workbook(raw)
    except Exception as e:
        # surface the error message to the user; the trace is in stderr
        app.logger.exception("annotation failed")
        abort(500, f"Failed to process workbook: {e}")

    base, ext = os.path.splitext(name)
    download_name = f"{base}__F5-EoL{ext}"

    return send_file(
        io.BytesIO(annotated),
        as_attachment=True,
        download_name=download_name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
