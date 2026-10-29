from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/api/v1/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
