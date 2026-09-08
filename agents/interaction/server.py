"""Internal reviewed-template renderer. No public network or model dependency."""
from flask import Flask, jsonify, request
from she_engine.learning_render import render

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32768


@app.get("/healthz")
def health():
    return jsonify(ok=True)


@app.post("/interaction/render")
def learning_render():
    action = request.get_json(silent=True)
    if not isinstance(action, dict) or type(action.get("scaffold_level")) is not int or not 0 <= action["scaffold_level"] <= 6:
        return jsonify(error="invalid_action"), 400
    return jsonify(text=render(action), source="reviewed_template")
