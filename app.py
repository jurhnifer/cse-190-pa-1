from flask import Flask, send_file, jsonify, make_response, request, redirect, url_for
import uuid, os, psycopg
app = Flask(__name__)


def get_db_connection():
    return psycopg.connect(os.environ["DATABASE_URL"])

@app.route('/')
def index():
    # Read the cookie
    boogle_id = request.cookies.get('boogle_id')
    response = make_response(send_file('boogle.html'))
    # Make the cookie if no cookie assigned yet
    if (boogle_id == None):
        cookie_value = str(uuid.uuid4())
        response.set_cookie('boogle_id', cookie_value, 6048000, None, '/', None, 
                            False, False, "Lax", False)
    return response

@app.route('/jsontest')
def jsontest():
    jsontest_response = {"data": "I am in CSE190/CSE291!"}
    return jsonify(jsontest_response)

@app.route('/search')
def search():
    # Get the query
    query = request.args.get('q')
    # Store query on database
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
               INSERT INTO userinfo.clients
               VALUES (%s)
            """,
            (query,))

    # Create 303 See Other response
    response = redirect(url_for('index'), code=303)

    return response

@app.route('/api/history')
def history():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT client_id, json_agg(searches ORDER BY ts DESC) as recent_searches
                FROM userinfo.clients
            """)

            search_history = cur.fetchall()

    return jsonify(search_history)


@app.route('/dump')
def dump():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT json_agg(clients) AS all_clients
                FROM clients
            """) 

            clients_info = cur.fetchall()

    return jsonify(clients_info)
    


if __name__ == "__main__":
    app.run(host="0.0.0.0", port="8000")
