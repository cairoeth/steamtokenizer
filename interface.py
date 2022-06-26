import os
import sys
import flask
from flask import Flask, request, render_template


sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__))))
app = Flask(__name__)


@app.route('/')
def main():
    name = request.args.get('name')
    hash = request.args.get('hash')
    cooldown = request.args.get('cooldown')
    signature = request.args.get('signature')

    return render_template('base.html', name=name, hash=hash, cooldown=cooldown, signature=signature)


if __name__ == '__main__':
    os.environ['FLASK_ENV'] = 'development'
    app.run(host='localhost', port=8080, debug=False)
