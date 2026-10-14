from flask import Flask, send_file, jsonify, make_response, request, redirect, url_for
import uuid, os, psycopg
from psycopg.rows import dict_row
app = Flask(__name__)
app.json.sort_keys = False

# check cookie every single app.before_request. app.after_request; 
def get_db_connection():
    return psycopg.connect(os.environ["DATABASE_URL"])

#Assign a client
def get_client(cur):
    client_id = request.cookies.get('boogle_id')
    ip = request.remote_addr
    is_new = client_id is None
    if is_new:
        client_id = uuid.uuid4()
    cur.execute("""
        INSERT INTO userinfo.clients(client_id, first_seen, last_seen, latest_ip)
        VALUES (%s, now(), now(), %s)
        ON CONFLICT (client_id)
        DO UPDATE SET last_seen = now(), latest_ip = EXCLUDED.latest_ip
        """,
        (client_id, ip))
    return client_id, is_new
    
        
@app.route('/')
def index():
    # Serve boogle.html
    response = make_response(send_file('boogle.html'))
    boogle_id = request.cookies.get('boogle_id')
    # Create cookie
    if(boogle_id == None):
        cookie_uuid = uuid.uuid4()
        cookie_value = str(cookie_uuid)
        response.set_cookie('boogle_id', cookie_value, 6048000, None, '/', None, 
                            False, False, "Lax", False)
    # Return
    return response

@app.route('/jsontest')
def jsontest():
    jsontest_response = {"data": "I am in CSE190/CSE291!"}
    return jsonify(jsontest_response)

@app.route('/search')
def search():
    # Get the query
    search = request.args.get('q')
    # If whitespace, go redirect
    if not search:
        return redirect(url_for('index'), code=303)
    # Get ip
    ip = request.remote_addr
    # Handles if there's a client 
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            #Run client function
            client_id, is_new = get_client(cur)
            # Populate the searches for row
            cur.execute("""
                INSERT INTO userinfo.searches(client_id, query, ts, ip)
                VALUES (%s, %s, now(), %s)
                """, (client_id, search, ip))
            # Create response
            # If there is no cookie, set response
            response = redirect(url_for('index'), code=303)
            if(is_new):
                response.set_cookie('boogle_id', str(client_id), 6048000, None, '/', None, 
                            False, False, "Lax", False)

    return response

# Creating api/history; should display all previous searches to the specific client made
@app.route('/api/history')
def history():
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            client_id, is_new = get_client(cur)
            # Grab searches info strictly for that client
            cur.execute("""
                SELECT client_id, query, to_char(ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS ts
                FROM userinfo.searches
                WHERE client_id = %s
                ORDER BY searches.ts DESC
                """,
                (client_id,))

            searches_info = cur.fetchall()

    # Create history list
    history = {
        "client_id": str(client_id),
        "searches": [{"query": s['query'], "ts": s['ts']} for s in searches_info],
    }

    response = jsonify(history)

    #Add cookie if needed
    if is_new:
        response.set_cookie('boogle_id', str(client_id), 6048000, None, '/', None, 
                        False, False, "Lax", False)

    return response







# Creating dump
@app.route('/dump')
def dump():
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Grab clients table
            cur.execute("""
                SELECT client_id, to_char(first_seen AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS first_seen,
                       to_char(last_seen  AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS last_seen, latest_ip
                FROM userinfo.clients
            """) 

            clients_info = cur.fetchall()

            # Select searches table
            
            cur.execute("""
                SELECT client_id, query, to_char(ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS ts, ip
                FROM userinfo.searches
            """)

            searches_info = cur.fetchall()
    
    # Set up the JSON table 

    all_clients = {}
    # Set up for clients
    for c in clients_info:
        cid = str(c['client_id'])
        all_clients[cid] = {
            "client_id": cid,
            "first_seen": c['first_seen'],
            "last_seen": c['last_seen'],
            "latest_ip": str(c['latest_ip']),
            "ips": [],
            "searches": [],
        }
        # Populate searches for clients
    for s in searches_info:
        client = all_clients.get(str(s['client_id']))
        if client == None:
            continue
        client["searches"].append({
            "query": s['query'],
            "ts": s['ts']
        })

        # Add the ip
        if s['ip'] != None and str(s['ip']) not in client["ips"]:
            client["ips"].append(str(s['ip']))

    # Return in json format
    return jsonify({"clients": list(all_clients.values())})




if __name__ == "__main__":
    app.run(host="0.0.0.0", port="8000")
