from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["GET", "HEAD"])
def home():
    # HEAD request → no body, just status
    if request.method == "HEAD":
        return "", 200

    # GET request
    return "OK", 200
