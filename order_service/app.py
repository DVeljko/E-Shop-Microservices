from flask import Flask, render_template
from flask_migrate import Migrate
from models import db, Order

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///order.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate = Migrate(app, db)








if __name__ == "__main__":
    app.run(debug=True, port=5003, host="0.0.0.0")