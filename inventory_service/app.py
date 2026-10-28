from flask import Flask, request, jsonify
from models import db
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
import requests

import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")

db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

def check_token_with_auth():
    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/validate-token",
            headers={
                "Authorization": request.headers.get("Authorization", ""),
            },
            timeout=5,
            allow_redirects=False
                        
        )

    except requests.RequestException:
        return jsonify({"error": "Authentication service is unavailable."}), 503

    if response.status_code in (401,403,422):
        return jsonify({"error": "Access token is not accepted."}), response.status_code

    if response.status_code != 200:
        return jsonify({"error": "Could not verify access token."}), 503

    return None






if __name__ == "__main__":
    app.run(debug=True, port=5007)