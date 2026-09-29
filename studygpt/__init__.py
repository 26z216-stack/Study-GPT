import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///' + os.path.join(app.instance_path, 'studygpt.db'))
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    csrf.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .auth import auth
    from .planner import planner
    from .learn import learn
    from .coach import coach
    app.register_blueprint(auth)
    app.register_blueprint(planner)
    app.register_blueprint(learn)
    app.register_blueprint(coach)

    from .quotes import quote_of_the_day

    @app.context_processor
    def inject_globals():
        return {'daily_quote': quote_of_the_day()}

    with app.app_context():
        db.create_all()
        _add_missing_columns()

    return app


def _add_missing_columns():
    from sqlalchemy import inspect, text
    for table, column in [('availability', 'windows'), ('user', 'routine')]:
        cols = {c['name'] for c in inspect(db.engine).get_columns(table)}
        if column not in cols:
            with db.engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {column} TEXT'))
