from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
CORS(app)

DATABASE = 'smartresolve.db'

# ==========================================
# ADVANCED DOMAIN, ESCALATION & EMAIL MAPPING
# ==========================================
DOMAIN_MAP = {
    'Banking': {
        'level1': 'Branch Manager / Grievance Officer',
        'level1_email': 'nodal.officer@bank.com',
        'level2': 'Banking Ombudsman, Reserve Bank of India (RBI)',
        'level2_email': 'ombudsman@rbi.org.in'
    },
    'Education': {
        'level1': 'Dean of Student Welfare / University Registrar',
        'level1_email': 'registrar@university.edu',
        'level2': 'Vice Chancellor / State Higher Education Board',
        'level2_email': 'vcoffice@stateboard.edu'
    },
    'Healthcare': {
        'level1': 'Chief Medical Officer (CMO) / Hospital Admin',
        'level1_email': 'cmo.admin@hospital.org',
        'level2': 'State Health Ministry / Medical Council of India',
        'level2_email': 'grievance@healthministry.gov.in'
    },
    'Technical': {
        'level1': 'Regional Nodal Officer / Support Head',
        'level1_email': 'support.head@techservice.com',
        'level2': 'Telecom Regulatory Authority (TRAI) / Consumer Court',
        'level2_email': 'apellate@trai.gov.in'
    }
}

# ==========================================
# EMAIL DISPATCHER
# ==========================================
def send_escalation_email(ticket_id, to_email, authority_name, entity_name):
    subject = f"URGENT ESCALATION: Unresolved Grievance {ticket_id} at {entity_name}"
    body = f"""
    Respected {authority_name},

    This is an automated escalation alert from the Smart Complaint Management System.
    Grievance Ticket {ticket_id} concerning {entity_name} has exceeded the 24-hour resolution SLA.

    Please take immediate action. 
    
    Regards,
    SCMS Enterprise Redressal Node
    """
    print("\n" + "="*50)
    print(f"📧 EMAIL SENT TO: {to_email}")
    print(f"SUBJECT: {subject}")
    print(body)
    print("="*50 + "\n")

# ==========================================
# DATABASE SETUP
# ==========================================
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, pass TEXT NOT NULL,
            name TEXT, phone TEXT, role TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grievances (
            id TEXT PRIMARY KEY, fName TEXT, lName TEXT, phone TEXT, email TEXT,
            domain TEXT, subdomain TEXT, entity TEXT, destination_address TEXT, 
            assigned_officer TEXT, desc TEXT, state TEXT, city TEXT, pin TEXT, idType TEXT,
            priority TEXT, status TEXT DEFAULT 'Pending Review', timestamp TEXT,
            date TEXT, userRef TEXT, escalationLevel INTEGER DEFAULT 1, emailSent BOOLEAN DEFAULT 0
        )
    ''')
    
    # NEW FEATURE: Feedback / Conversations Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            senderRole TEXT,
            message TEXT,
            timestamp TEXT,
            FOREIGN KEY (ticket_id) REFERENCES grievances (id)
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE grievances ADD COLUMN idType TEXT')
    except sqlite3.OperationalError:
        pass 
        
    conn.commit()
    conn.close()

init_db()

# ==========================================
# API ROUTES
# ==========================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (id, email, pass, name, phone, role) VALUES (?, ?, ?, ?, ?, ?)', 
                       (data.get('id'), data.get('email'), data.get('pass'), data.get('name'), data.get('phone'), data.get('role', 'resident')))
        conn.commit()
        return jsonify({"success": True, "user": data}), 201
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Email already exists"}), 400
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ? AND pass = ?', (data.get('email'), data.get('pass'))).fetchone()
    conn.close()
    return jsonify({"success": True, "user": dict(user)}) if user else jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route('/api/grievances', methods=['POST'])
def create_grievance():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    domain_key = data.get('domain')
    entity_name = data.get('entity')
    auto_destination = "Central Routing Node"
    
    if domain_key in DOMAIN_MAP:
        auto_destination = f"{DOMAIN_MAP[domain_key]['level1']}, {entity_name} ({DOMAIN_MAP[domain_key]['level1_email']})"
    
    final_destination = data.get('destination') or data.get('destinationAddress') or auto_destination
    
    try:
        cursor.execute('''
            INSERT INTO grievances (
                id, fName, lName, phone, email, domain, subdomain, entity, destination_address, 
                assigned_officer, desc, state, city, pin, idType, priority, status, timestamp, date, userRef, escalationLevel, emailSent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('id'), data.get('fName'), data.get('lName'), data.get('phone'),
            data.get('email'), data.get('domain'), data.get('subdomain'), data.get('entity'),
            final_destination, data.get('assignedOfficer', 'Unassigned Node'),
            data.get('desc'), data.get('state'), data.get('city'), data.get('pin'),
            data.get('idType'), data.get('priority'), data.get('status', 'Pending Review'), data.get('timestamp'),
            data.get('date'), data.get('userRef'), data.get('escalationLevel', 1), data.get('emailSent', False)
        ))
        
        # NEW FEATURE: Automatically add the first message (the description) to the communication thread
        time_str = data.get('timestamp')  # or format it specifically if needed
        cursor.execute('''
            INSERT INTO feedback (ticket_id, senderRole, message, timestamp) 
            VALUES (?, ?, ?, ?)
        ''', (data.get('id'), 'sender', data.get('desc'), time_str))
        
        conn.commit()
        data['destination'] = final_destination
        # Initialize an empty feedback array for the immediate frontend response
        data['feedback'] = [{
            "senderRole": "sender",
            "message": data.get('desc'),
            "timestamp": time_str
        }]
        return jsonify({"success": True, "grievance": data}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ==========================================
# NEW FEATURE: FETCH & POST FEEDBACK MESSAGES
# ==========================================
@app.route('/api/grievances/<string:g_id>/messages', methods=['GET'])
def get_messages(g_id):
    conn = get_db_connection()
    messages = conn.execute('SELECT * FROM feedback WHERE ticket_id = ? ORDER BY id ASC', (g_id,)).fetchall()
    conn.close()
    return jsonify([dict(m) for m in messages])

@app.route('/api/grievances/<string:g_id>/messages', methods=['POST'])
def add_message(g_id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO feedback (ticket_id, senderRole, message, timestamp) 
            VALUES (?, ?, ?, ?)
        ''', (g_id, data.get('senderRole'), data.get('message'), data.get('timestamp')))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ==========================================
# GRIEVANCE MANAGEMENT ROUTES
# ==========================================
@app.route('/api/grievances', methods=['GET'])
def get_grievances():
    try:
        conn = get_db_connection()
        rows = conn.execute('SELECT * FROM grievances ORDER BY rowid DESC').fetchall()
        
        result = []
        for row in rows:
            d = dict(row)
            d['destination'] = d.pop('destination_address', None)
            d['emailSent'] = bool(d.get('emailSent'))
            
            # NEW FEATURE: Attach the communication thread to the grievance object
            msgs = conn.execute('SELECT * FROM feedback WHERE ticket_id = ? ORDER BY id ASC', (d['id'],)).fetchall()
            d['feedback'] = [dict(m) for m in msgs]
            
            result.append(d)
            
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/grievances/<string:g_id>/status', methods=['PATCH'])
def update_status(g_id):
    data = request.json
    new_status = data.get('status')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE grievances SET status = ? WHERE id = ?', (new_status, g_id))
        conn.commit()
        updated_row = cursor.execute('SELECT * FROM grievances WHERE id = ?', (g_id,)).fetchone()
        
        if updated_row:
            d = dict(updated_row)
            d['destination'] = d.pop('destination_address', None)
            d['emailSent'] = bool(d.get('emailSent'))
            return jsonify({"success": True, "grievance": d})
        return jsonify({"success": False, "message": "Not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/escalate', methods=['POST'])
def simulate_escalation():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.json or {}
        specific_id = data.get('ticket_id')
        
        if specific_id:
            query = "SELECT * FROM grievances WHERE id = ?"
            rows = cursor.execute(query, (specific_id,)).fetchall()
        else:
            query = "SELECT * FROM grievances WHERE status != 'Resolved' AND escalationLevel = 1"
            rows = cursor.execute(query).fetchall()
            
        escalated_count = 0
        for row in rows:
            g_id = row['id']
            domain = row['domain']
            entity = row['entity']
            current_level = row['escalationLevel']
            
            level_auth = "Higher Regional Authority"
            target_email = "admin@system.com"
            
            if domain in DOMAIN_MAP:
                if current_level == 1 and not specific_id:
                    level_auth = DOMAIN_MAP[domain]['level2']
                    target_email = DOMAIN_MAP[domain]['level2_email']
                    new_dest = f"{level_auth} ({target_email}) - Auto-Escalated from {entity}"
                    cursor.execute("UPDATE grievances SET escalationLevel = 2, emailSent = 1, destination_address = ? WHERE id = ?", (new_dest, g_id))
                else:
                    level_auth = DOMAIN_MAP[domain]['level2'] if current_level == 2 else DOMAIN_MAP[domain]['level1']
                    target_email = DOMAIN_MAP[domain]['level2_email'] if current_level == 2 else DOMAIN_MAP[domain]['level1_email']
            
            send_escalation_email(g_id, target_email, level_auth, entity)
            escalated_count += 1
            
        conn.commit()
        msg = f"Email sent successfully for {escalated_count} ticket(s)." if specific_id else f"{escalated_count} grievances auto-escalated and emails dispatched."
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    print("🚀 Smart Complaint Management Server running on http://localhost:5000")
    app.run(port=5000, debug=True)