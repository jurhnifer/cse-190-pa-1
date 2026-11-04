from flask import Flask, send_file, jsonify, make_response, request, redirect, url_for
import uuid, os, psycopg, json
import requests
from psycopg.rows import dict_row
from starter_3_4.part3.user_prediction import get_attribute_table

app = Flask(__name__)
DSP_urls = requests.get("https://webtracking.sysnet.ucsd.edu/pa1/rtb/").json()["bid"]
app.json.sort_keys = False

# check cookie every single app.before_request. app.after_request; 
def get_db_connection():
    return psycopg.connect(os.environ["DATABASE_URL"])

def valid_response(response):
    # Check if response is 200
    if response.status_code != 200:
        return False
    # Check if not valid JSON
    # Use try/catch
    try:
        data = response.json()
    except ValueError:
        return False
    # Check if in a currency other than USD
    if data.get("cur") != "USD":
        return False

    seatbids = data.get("seatbid", [])
    bids = seatbids[0].get("bid", [])
    for bid in bids:
    # Check if names impid didn't send
        if bid.get("impid") != "1":
            return False
    # Check if not a 300 x 250 slot
        # Width
        if bid.get("w") != 300:
            return False
        # Height
        if bid.get("h") != 250:
            return False
    # Check if below bid floor
        if bid.get("price") < 1.00:
            return False

    return True;

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
    response = make_response(send_file('new_boogle.html'))
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
    # If whitespace, go redirect; use strip to remove spaces/tabs
    if not search.strip():
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

# Add get /ad
@app.route('/ad')
def ad():
    # Make a request, an HTTP POST to all four DSPS
    
    # Create our own bid request id
    request_id = str(uuid.uuid4())
    print(request_id)

    # Get the device type from the request header
    device_type = request.headers.get('User-Agent')
    print(device_type)
    # Get the IP
    ip = request.remote_addr

    # Get the cookie ID
    boogle_id = request.cookies.get('boogle_id')
    # Create cookie ?
    # Get the searches from the client
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT query
                FROM userinfo.searches
                WHERE client_id = %s
            """,
                (boogle_id,))

            search = cur.fetchall();

    # Get the attribute table from running model
    searches = [query['query'] for query in search]
    attribute_df = get_attribute_table(boogle_id, searches)

    # Get the attribute & extract from segment.json to populate
    print(attribute_df)

    # Load the json file
    with open("starter_3_4/part4/segments.json", "r", encoding="utf-8") as file:
        segments_json = json.load(file)

    # Extract the segments only
    segments_list = segments_json.get("segments")

    # Create a segment list for openrtb request
    segments = []

    for col in attribute_df.columns:
        curr_attribute = attribute_df[col][0]
        #TO DO: confidence threshold: if fs don't know < 0.75, just remove it --> where to get the confidence threshold??
        for seg in segments_list:
            if seg['value'] == curr_attribute:
                segments.append(seg)

    print(segments)   

    # Gather badv requests
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT domain
                FROM userinfo.badv
            """)

            badv = [row[0] for row in cur.fetchall()]
    
    # Generate the OpenRTB request
    openrtb_request = {
        "id": request_id,
        "imp": [{"id": "1",
                 "banner": {"format": [{"w": 300, "h": 250}]},
                 "bidfloor": 1.00}],
        "device": {"ua": device_type,
                  "ip": ip},
        "user": {"id": boogle_id,
                 "data": [{"id": "boogle",
                           "segment": segments,
                           "ext": {"segtax": 500}}]},
        "tmax": 500,
        "badv": badv
    }

    bidfloor = 1.00
    valid_bids = []
    # Send request to DSP URLS
    for url in DSP_urls:
        # Get the DSP responses (send to DSP with openrtb_request along with my timeout (tmax = 500 ms))
        try:
            dsp_response = requests.post(url, json=openrtb_request, timeout=0.5)
        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.RequestException:
            continue
        

        # Loop through all to see if valid bid
        if valid_response(dsp_response):
            data = dsp_response.json()
            # Get the bid & price
            # Could there be multiple seatbids??
            for seatbid in data.get("seatbid", []):
                for bid in seatbid.get("bid", []):
                    valid_bids.append({"id": data.get("id"), "ad": bid.get("adm"), "price": bid.get("price"), "bill_to": bid.get("burl"), "adomain": (bid.get("adomain") or [None])[0]})

    print(valid_bids)
    if len(valid_bids) == 0:
        return "No valid bid", 202
    # Pick & price the winner
    # First sort:
    sorted_bids = sorted(valid_bids, key=lambda x: x["price"], reverse=True)

    print(sorted_bids)
    # Select the first winner & calculate
    winner = sorted_bids[0]

    print(winner)
    # Calculate the auction_price using the second-highest bid
    if len(sorted_bids) >= 2:
        second_price = max(sorted_bids[1].get("price"), bidfloor)
    else:
        second_price = bidfloor

    auction_price = min(winner.get("price"), second_price + 0.01)
    # Fix bill URL with auction price
    bill_url = winner.get("bill_to").replace("${AUCTION_PRICE}", str(auction_price))

    # Store winner information in a database, auction id & the adm (domain)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO userinfo.winners(auction_id, dsp_domain)
                VALUES (%s, %s)
                """, (winner.get("id"), winner.get("adomain")))

    # Bill to the DSP using a GET request
    try: 
        requests.get(url=bill_url, timeout=0.5)
    except requests.exceptions.RequestException as e:
        print("Billing request failed:", e)

    # Display the ad
    

    return winner.get("ad")

@app.route('/ad/feedback', methods=['POST'])
def feedback():
    # Get the post request
    complaint = request.get_json()
    # Given this complaint; how can i figure out the advertisement/advertisor that came from it
    # If we've recieved an auction id, does this mean like, all advertisers who recieved that auction_id
    auction_id = complaint.get("auction_id")
    if not auction_id:
        return "Missing auction_id", 400

    # Insert complaint into badv
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check if the auction_id exists in the winner
            cur.execute("""
                SELECT dsp_domain
                FROM winners
                WHERE auction_id = %s 
            """, (auction_id,))

            row = cur.fetchone()

            if row is None:
                return "No auction id exists", 404

            domain = row[0]
            cur.execute("""
                INSERT INTO userinfo.badv(domain)
                VALUES (%s)
            """, (domain,))

    return "Recorded the complaint", 200
                
    





if __name__ == "__main__":
    app.run(host="0.0.0.0", port="8000")
