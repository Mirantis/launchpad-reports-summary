from flask import Flask


app = Flask(__name__)


@app.route("/iso_build/<version>/<iso_number>/<result>")
def iso_build_result(version, iso_number, result):
    

if __name__ == "__main__":
    app.run()
