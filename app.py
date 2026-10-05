from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from pypdf import PdfReader
from datetime import datetime
import os
import json
import re


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = "rentwise-ai-secret-key"


# =========================================================
# FOLDERS
# =========================================================

UPLOAD_FOLDER = "documents"
DATA_FOLDER = "data"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


DATABASE_FILE = os.path.join(
    DATA_FOLDER,
    "rentwise_data.json"
)


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def load_database():

    if not os.path.exists(DATABASE_FILE):

        return {
            "users": {},
            "agreements": []
        }

    try:

        with open(
            DATABASE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception:

        return {
            "users": {},
            "agreements": []
        }


def save_database(database):

    with open(
        DATABASE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            database,
            file,
            indent=4
        )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()


        if not email or not password:

            return render_template(
                "login.html",
                error="Please enter email and password."
            )


        database = load_database()


        # Create demo account if it doesn't exist
        if email not in database["users"]:

            database["users"][email] = {

                "name": email.split("@")[0],

                "email": email,

                "password": password

            }

            save_database(database)


        session["user"] = email


        return redirect(
            url_for("dashboard")
        )


    return render_template(
        "login.html"
    )


# =========================================================
# SIGN UP
# =========================================================

@app.route(
    "/signup",
    methods=["GET", "POST"]
)
def signup():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()


        if not name or not email or not password:

            return render_template(
                "signup.html",
                error="Please fill all the fields."
            )


        database = load_database()


        if email in database["users"]:

            return render_template(
                "signup.html",
                error="An account with this email already exists."
            )


        database["users"][email] = {

            "name": name,

            "email": email,

            "password": password

        }


        save_database(database)


        session["user"] = email


        return redirect(
            url_for("dashboard")
        )


    return render_template(
        "signup.html"
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    return render_template(
        "dashboard.html",
        user=session["user"]
    )


# =========================================================
# PROFILE
# =========================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
def profile():

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    database = load_database()

    email = session["user"]


    # Make sure user exists
    if email not in database["users"]:

        database["users"][email] = {

            "name": email.split("@")[0],

            "email": email,

            "password": ""

        }

        save_database(database)


    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()


        if name:

            database["users"][email]["name"] = name

            save_database(database)


        return redirect(
            url_for("profile")
        )


    user = database["users"][email]


    return render_template(
        "profile.html",
        user=user
    )


# =========================================================
# HISTORY
# =========================================================

@app.route("/history")
def history():

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    database = load_database()

    email = session["user"]


    user_agreements = [

        agreement

        for agreement in database["agreements"]

        if agreement.get("user") == email

    ]


    # Newest first
    user_agreements.reverse()


    return render_template(
        "history.html",
        agreements=user_agreements,
        user=email
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# RISK DETECTION
# =========================================================

def detect_risks(text):

    text_lower = text.lower()


    risks = []


    risk_rules = [

        {
            "category": "Security Deposit",

            "severity": "Medium",

            "keywords": [
                "security deposit",
                "deposit",
                "forfeit deposit",
                "non-refundable deposit"
            ],

            "explanation":
                "The agreement contains conditions related to the security deposit. Check when it is refundable and what deductions are permitted."
        },


        {
            "category": "Termination",

            "severity": "High",

            "keywords": [
                "termination",
                "terminate the agreement",
                "eviction",
                "vacate immediately",
                "early termination"
            ],

            "explanation":
                "The agreement contains termination-related conditions. Review who can terminate the agreement and under what circumstances."
        },


        {
            "category": "Notice Period",

            "severity": "Medium",

            "keywords": [
                "notice period",
                "notice of",
                "days notice",
                "month notice"
            ],

            "explanation":
                "A notice requirement is present. Check the exact notice duration and whether it applies equally to both parties."
        },


        {
            "category": "Late Payment",

            "severity": "Medium",

            "keywords": [
                "late fee",
                "late payment",
                "penalty",
                "interest on delayed",
                "delay in payment"
            ],

            "explanation":
                "The agreement contains consequences for delayed payments. Review the applicable amount or penalty."
        },


        {
            "category": "Maintenance",

            "severity": "Medium",

            "keywords": [
                "maintenance",
                "repair",
                "repairs",
                "maintenance charges"
            ],

            "explanation":
                "Maintenance or repair responsibilities are mentioned. Check whether responsibilities are clearly divided between tenant and landlord."
        },


        {
            "category": "Additional Charges",

            "severity": "Medium",

            "keywords": [
                "additional charges",
                "additional fee",
                "utility charges",
                "service charges",
                "other charges"
            ],

            "explanation":
                "Additional charges may apply under the agreement. Check what these charges cover and how they are calculated."
        },


        {
            "category": "Subletting",

            "severity": "High",

            "keywords": [
                "sublet",
                "subletting",
                "assign the premises",
                "assignment of lease"
            ],

            "explanation":
                "The agreement contains restrictions or conditions concerning subletting or transferring the property."
        },


        {
            "category": "Renewal",

            "severity": "Low",

            "keywords": [
                "renewal",
                "renew the agreement",
                "extension of lease"
            ],

            "explanation":
                "The agreement contains renewal or extension conditions. Check whether renewal is automatic and whether rent can change."
        }

    ]


    for rule in risk_rules:

        found_keyword = None


        for keyword in rule["keywords"]:

            if keyword in text_lower:

                found_keyword = keyword

                break


        if found_keyword:

            sentences = re.split(
                r'(?<=[.!?])\s+',
                text
            )


            clause = ""


            for sentence in sentences:

                if found_keyword.lower() in sentence.lower():

                    clause = sentence.strip()

                    break


            if not clause:

                clause = (
                    f"Detected reference to: "
                    f"{found_keyword}"
                )


            risks.append({

                "category":
                    rule["category"],

                "severity":
                    rule["severity"],

                "keyword":
                    found_keyword,

                "clause":
                    clause[:500],

                "explanation":
                    rule["explanation"]

            })


    return risks


# =========================================================
# UPLOAD AND ANALYZE AGREEMENT
# =========================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload_file():

    if "user" not in session:

        return jsonify({

            "success": False,

            "message":
                "Please login first."

        }), 401


    if "file" not in request.files:

        return jsonify({

            "success": False,

            "message":
                "No file uploaded."

        })


    file = request.files["file"]


    if file.filename == "":

        return jsonify({

            "success": False,

            "message":
                "Please select a PDF file."

        })


    if not file.filename.lower().endswith(".pdf"):

        return jsonify({

            "success": False,

            "message":
                "Only PDF files are supported."

        })


    # -----------------------------------------------------
    # CREATE UNIQUE FILE NAME
    # -----------------------------------------------------

    original_filename = file.filename


    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


    safe_filename = re.sub(
        r"[^a-zA-Z0-9_.-]",
        "_",
        original_filename
    )


    saved_filename = (
        timestamp +
        "_" +
        safe_filename
    )


    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        saved_filename
    )


    file.save(file_path)


    # -----------------------------------------------------
    # EXTRACT TEXT
    # -----------------------------------------------------

    try:

        reader = PdfReader(
            file_path
        )


        text = ""


        for page in reader.pages:

            page_text = page.extract_text()


            if page_text:

                text += (
                    page_text +
                    "\n"
                )


    except Exception as error:

        return jsonify({

            "success": False,

            "message":
                f"Could not read PDF: {str(error)}"

        }), 500


    # -----------------------------------------------------
    # RISK DETECTION
    # -----------------------------------------------------

    risks = detect_risks(
        text
    )


    # -----------------------------------------------------
    # AGREEMENT RECORD
    # -----------------------------------------------------

    agreement = {

        "id": timestamp,

        "user": session["user"],

        "filename": original_filename,

        "saved_filename": saved_filename,

        "pages": len(reader.pages),

        "uploaded_at":
            datetime.now().strftime(
                "%d %b %Y, %I:%M %p"
            ),

        "text": text,

        "text_preview":
            text[:5000],

        "risks": risks,

        "risk_count":
            len(risks)

    }


    # -----------------------------------------------------
    # SAVE DATABASE
    # -----------------------------------------------------

    database = load_database()


    database["agreements"].append(
        agreement
    )


    save_database(
        database
    )


    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return jsonify({

        "success": True,

        "message":
            "Agreement analyzed successfully.",

        "agreement_id":
            agreement["id"],

        "filename":
            original_filename,

        "pages":
            len(reader.pages),

        "risk_count":
            len(risks),

        "risks":
            risks,

        "text_preview":
            text[:5000]

    })


# =========================================================
# DASHBOARD STATISTICS
# =========================================================

@app.route("/api/stats")
def api_stats():

    if "user" not in session:

        return jsonify({

            "success": False,

            "message":
                "Please login first."

        }), 401


    database = load_database()

    email = session["user"]


    agreements = [

        agreement

        for agreement in database["agreements"]

        if agreement.get("user") == email

    ]


    total_agreements = len(
        agreements
    )


    total_documents = len(
        agreements
    )


    total_risks = sum(

        agreement.get(
            "risk_count",
            0
        )

        for agreement in agreements

    )


    return jsonify({

        "success": True,

        "agreements":
            total_agreements,

        "risks":
            total_risks,

        "documents":
            total_documents

    })


# =========================================================
# GET AGREEMENT
# =========================================================

@app.route(
    "/api/agreement/<agreement_id>"
)
def get_agreement(agreement_id):

    if "user" not in session:

        return jsonify({

            "success": False,

            "message":
                "Please login first."

        }), 401


    database = load_database()

    email = session["user"]


    for agreement in database["agreements"]:

        if (

            agreement.get("id") ==
            agreement_id

            and

            agreement.get("user") ==
            email

        ):

            return jsonify({

                "success": True,

                "agreement":
                    agreement

            })


    return jsonify({

        "success": False,

        "message":
            "Agreement not found."

    }), 404


# =========================================================
# DELETE AGREEMENT
# =========================================================

@app.route(
    "/api/agreement/<agreement_id>",
    methods=["DELETE"]
)
def delete_agreement(agreement_id):

    if "user" not in session:

        return jsonify({

            "success": False,

            "message":
                "Please login first."

        }), 401


    database = load_database()

    email = session["user"]


    agreement_to_delete = None


    for agreement in database["agreements"]:

        if (

            agreement.get("id") ==
            agreement_id

            and

            agreement.get("user") ==
            email

        ):

            agreement_to_delete = agreement

            break


    if not agreement_to_delete:

        return jsonify({

            "success": False,

            "message":
                "Agreement not found."

        }), 404


    database["agreements"].remove(
        agreement_to_delete
    )


    # Delete PDF
    file_path = os.path.join(

        UPLOAD_FOLDER,

        agreement_to_delete.get(
            "saved_filename",
            ""
        )

    )


    if os.path.exists(file_path):

        try:

            os.remove(
                file_path
            )

        except Exception:

            pass


    save_database(
        database
    )


    return jsonify({

        "success": True,

        "message":
            "Agreement deleted successfully."

    })


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )