from flask_bootstrap import Bootstrap5
from flask import Flask, session
from flask_session import Session

import tempfile

app = Flask(__name__)
bootstrap = Bootstrap5(app)
sess = Session()

app.secret_key = 'super secret key'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

sess.init_app(app)

from app import routes