from flask import Flask, request, jsonify
from flask_mail import Mail, Message
import os
from dotenv import load_dotenv

app = Flask(__name__)


load_dotenv()

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_USERNAME")

mail = Mail(app)


@app.route("/send-verification-email", methods=["POST"])
def verify_email_registration():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    email = data.get("email")
    verification_url = data.get("verification_url")

    if not email and not verification_url:
        return jsonify({"error": "Email and verification URL are required."}), 400

    message = Message(
        subject="Verify your email address",
        recipients=[email],
        body=f"Click this link to verify your account:\n{verification_url}"
    )

    try:
        mail.send(message)
    except Exception:
        return jsonify({"error": "Email could not be sent."}), 500

    return jsonify({"success": "Verification email has been sent."}), 200

@app.route("/send-password-reset-email", methods=['POST'])
def send_password_reset():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    email = data.get('email')
    reset_url = data.get('reset_url')

    if not isinstance(email, str) or not email.strip():
        return jsonify({
            "error": "Email is required and must be a string."
        }), 400

    if not isinstance(reset_url, str) or not reset_url.strip():
        return jsonify({
            "error": "Reset URL is required and must be a string."
        }), 400

    email = email.strip()
    reset_url = reset_url.strip()

    message = Message(
        subject="Reset your password",
        recipients=[email],
        body=f"Click this link to reset your password:\n{reset_url}"
    )

    try:
        mail.send(message)
    except Exception:
        return jsonify({"error": "Email could not be sent"}), 500

    return jsonify({"success": "Password reset email has been sent successfully."}), 200





if __name__ == "__main__":
    app.run(debug=True, port=5006)