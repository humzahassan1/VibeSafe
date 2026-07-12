import os
import pickle
from flask import Flask, request, jsonify

app = Flask(__name__)

# SEC-017: Hardcoded secret key
app.config['SECRET_KEY'] = 'super-secret-flask-key-12345'

# SEC-036: Debug mode on
app.debug = True


@app.route('/search')
def search():
    query = request.args.get('q', '')
    # SEC-022: eval
    result = eval(query)
    return jsonify(result=str(result))


@app.route('/user/<user_id>')
def get_user(user_id):
    # SEC-020: SQL injection
    import sqlite3
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return jsonify(user=cursor.fetchone())


@app.route('/upload', methods=['POST'])
def upload():
    data = request.get_data()
    # SEC-022: Pickle deserialization
    obj = pickle.loads(data)
    return jsonify(result=str(obj))


@app.route('/run', methods=['POST'])
def run_cmd():
    cmd = request.json.get('cmd')
    # SEC-022: os.system
    os.system(cmd)
    return jsonify(status='done')


@app.route('/admin', methods=['POST'])
def admin_login():
    # SEC-018: Default credentials
    admin_user = "admin"
    admin_pass = "password123"
    if request.form.get('user') == admin_user:
        return jsonify(status='ok')
    return jsonify(status='denied'), 401


if __name__ == '__main__':
    app.run(debug=True)
