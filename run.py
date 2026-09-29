"""Start the app locally: python run.py  ->  http://127.0.0.1:5000"""
import os

from wordgame import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
