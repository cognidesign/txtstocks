from flask import Flask
app = Flask(__name__)


@app.route('/')
def get_stocks():
    return "Coming Soon!"

if __name__ == '__main__':
    app.run()