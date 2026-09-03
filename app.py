import os
from flask import Flask, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)


@app.route("/")
def login():
    return render_template("index.html")


@app.route("/register")
def register():
    return render_template("register.html")


if __name__ == "__main__":
    print("Project folder:", BASE_DIR)
    print("Static folder:", app.static_folder)
    app.run(debug=True)