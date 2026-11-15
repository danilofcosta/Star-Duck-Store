"""
MiniDLNA Web UI - Simple Flask app for status, config, folder management, and service control
"""
import os
import signal
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder="templates")

# Config from environment
MINIDLNA_HOST = os.getenv("MINIDLNA_HOST", "localhost")
MINIDLNA_PORT = int(os.getenv("MINIDLNA_PORT", "8200"))
MINIDLNA_STATUS_URL = f"http://{MINIDLNA_HOST}:{MINIDLNA_PORT}/status"
MINIDLNA_CONFIG_PATH = Path("/config/minidlna.conf")
MINIDLNA_PID_PATH = Path("/run/minidlna/minidlna.pid")

# Media type prefixes for minidlna.conf
MEDIA_TYPES = {
    "A": "Áudio",
    "V": "Vídeo",
    "P": "Imagens",
    "": "Mista (todos os tipos)",
}


def parse_minidlna_status():
    """Fetch and parse MiniDLNA status XML"""
    try:
        resp = requests.get(MINIDLNA_STATUS_URL, timeout=5)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        status = {}
        for child in root:
            status[child.tag] = child.text

        return {
            "success": True,
            "friendly_name": status.get("friendlyname", "MiniDLNA"),
            "version": status.get("version", "Unknown"),
            "clients": int(status.get("clients", 0)),
            "files": int(status.get("files", 0)),
            "audio_files": int(status.get("audio_files", 0)),
            "video_files": int(status.get("video_files", 0)),
            "image_files": int(status.get("image_files", 0)),
            "db_status": status.get("database", "Unknown"),
            "raw": status,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def parse_minidlna_config():
    """Parse minidlna.conf file"""
    config = {}
    media_dirs = []
    if MINIDLNA_CONFIG_PATH.exists():
        content = MINIDLNA_CONFIG_PATH.read_text()
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                config[key] = value
                if key == "media_dir":
                    media_dirs.append(value)
    return config, media_dirs


def write_minidlna_config(config_dict):
    """Write minidlna.conf file preserving comments and structure"""
    # Read original to preserve comments
    original_lines = []
    if MINIDLNA_CONFIG_PATH.exists():
        original_lines = MINIDLNA_CONFIG_PATH.read_text().splitlines()

    # Build new config
    new_lines = []
    media_dir_written = False

    for line in original_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=")[0].strip()
            if key in config_dict:
                if key == "media_dir":
                    if not media_dir_written:
                        for v in config_dict[key]:
                            new_lines.append(f"media_dir={v}")
                        media_dir_written = True
                else:
                    new_lines.append(f"{key}={config_dict[key]}")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Add any missing keys
    for key, value in config_dict.items():
        if key == "media_dir":
            continue
        if not any(l.strip().startswith(f"{key}=") for l in new_lines if "=" in l):
            new_lines.append(f"{key}={value}")

    MINIDLNA_CONFIG_PATH.write_text("\n".join(new_lines) + "\n")


def get_media_folders():
    """Get configured media folders from config"""
    _, media_dirs = parse_minidlna_config()
    folders = []
    for m in media_dirs:
        m = m.strip()
        if not m:
            continue
        # Parse type prefix (A,V,P)
        ftype = ""
        path = m
        if m.startswith(("A,", "V,", "P,")):
            ftype = m[0]
            path = m[2:]
        folders.append({"type": ftype, "path": path, "raw": m})
    return folders


def add_media_folder(folder_type, path):
    """Add a media folder to config"""
    config, media_dirs = parse_minidlna_config()
    prefix = f"{folder_type}," if folder_type else ""
    new_entry = f"{prefix}{path}"
    media_dirs.append(new_entry)
    config["media_dir"] = media_dirs
    write_minidlna_config(config)
    return True


def remove_media_folder(index):
    """Remove a media folder by index"""
    config, media_dirs = parse_minidlna_config()
    if 0 <= index < len(media_dirs):
        media_dirs.pop(index)
        config["media_dir"] = media_dirs
        write_minidlna_config(config)
        return True
    return False


def send_minidlna_signal(sig):
    """Send signal to MiniDLNA process via PID file"""
    try:
        if MINIDLNA_PID_PATH.exists():
            pid = int(MINIDLNA_PID_PATH.read_text().strip())
            os.kill(pid, sig)
            return {"success": True, "message": f"Signal {sig} sent to PID {pid}"}
        return {"success": False, "error": "PID file not found"}
    except ProcessLookupError:
        return {"success": False, "error": "Process not found (already stopped?)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def trigger_rescan():
    """Trigger MiniDLNA rescan"""
    # Try HTTP rescan first
    try:
        resp = requests.post(f"http://{MINIDLNA_HOST}:{MINIDLNA_PORT}/rescan", timeout=10)
        if resp.status_code == 200:
            return {"success": True, "message": "Rescan triggered via HTTP"}
    except Exception:
        pass

    # Fallback: SIGHUP triggers rescan
    return send_minidlna_signal(signal.SIGHUP)


def restart_minidlna():
    """Restart MiniDLNA by sending SIGTERM (supervisord will restart it)"""
    result = send_minidlna_signal(signal.SIGTERM)
    if result["success"]:
        result["message"] = "MiniDLNA reiniciando... (supervisord vai reiniciar automaticamente)"
    return result


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify(parse_minidlna_status())


@app.route("/api/folders")
def api_folders():
    folders = get_media_folders()
    return jsonify([{"type": f["type"], "path": f["path"]} for f in folders])


@app.route("/api/folders", methods=["POST"])
def api_add_folder():
    data = request.get_json() or {}
    folder_type = data.get("type", "")
    path = data.get("path", "").strip()

    if not path:
        return jsonify({"success": False, "error": "Caminho da pasta é obrigatório"}), 400

    if not path.startswith("/media"):
        return jsonify({"success": False, "error": "Caminho deve estar dentro de /media"}), 400

    try:
        add_media_folder(folder_type, path)
        return jsonify({"success": True, "message": "Pasta adicionada"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/folders/<int:index>", methods=["DELETE"])
def api_remove_folder(index):
    try:
        if remove_media_folder(index):
            return jsonify({"success": True, "message": "Pasta removida"})
        return jsonify({"success": False, "error": "Índice inválido"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/config")
def api_config():
    config, _ = parse_minidlna_config()
    # Hide sensitive info
    safe_config = {k: v for k, v in config.items() if "password" not in k.lower() and "secret" not in k.lower()}
    return jsonify({"config": "\n".join(f"{k}={v}" for k, v in sorted(safe_config.items()))})


@app.route("/api/rescan", methods=["POST"])
def api_rescan():
    return jsonify(trigger_rescan())


@app.route("/api/restart", methods=["POST"])
def api_restart():
    return jsonify(restart_minidlna())


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8250, debug=False)