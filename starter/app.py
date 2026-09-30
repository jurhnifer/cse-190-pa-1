from flask import Flask, send_file, jsonify, make_response
app = Flask(__name__)

@app.route('/')
def index():
    return send_file('boogle.html')

@app.route('/jsontest')
def jsontest():
    jsontest_response = {"data": "I am in CSE190/CSE291!"}
    return jsonify(jsontest_response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port="8000")
