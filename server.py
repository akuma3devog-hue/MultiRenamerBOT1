from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    """
    Health check endpoint for Render & UptimeRobot
    """
    return jsonify(status="ok"), 200
