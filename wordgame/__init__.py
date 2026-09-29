"""Guess the Word: a five-letter word guessing game with player and admin roles."""
import os

from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.path.join(app.instance_path, "wordgame.sqlite"),
        ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME", "Admin"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "Admin$123"),
        CSRF_ENABLED=True,
        MAX_GUESSES=5,
        DAILY_WORD_LIMIT=3,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    from . import admin, auth, db, game, security

    db.init_app(app)
    security.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(game.bp)
    app.register_blueprint(admin.bp)

    with app.app_context():
        db.init_db()

    return app
