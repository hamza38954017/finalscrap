import requests
import random
import threading
import time
import warnings
import os
from flask import Flask
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ------------------------------------------------------------------
# ⚙️ HARDCODED CONFIGURATION (EDIT THIS)
# ------------------------------------------------------------------
# ⚠️ REPLACE THIS WITH YOUR EXACT PHP FILE URL FROM INFINITYFREE
YOUR_PHP_ENDPOINT = "https://drdev.gt.tc/insert_data.php" 

# NUMBER OF THREADS (Don't go too high on Free Tier)
CONCURRENT_THREADS = 3

PREFIXES = [94718, 78359, 77668, 93135, 97161, 62092, 90157, 78277, 88513, 99104,98916, 74799,70114,92679,99104,87894,87578]
API_URL = "https://api.x10.network/numapi.php"
API_KEY = "num_devil"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
]

# ------------------------------------------------------------------
# 🌐 DUMMY WEB SERVER (REQUIRED FOR RENDER)
# ------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    with stats_lock:
        return f"Bot is Running...<br>Total: {stats['total']}<br>Success: {stats['success']}<br>Errors: {stats['errors']}"

def run_web_server():
    # Render assigns a port automatically via the 'PORT' env var
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# ------------------------------------------------------------------
# 🔌 NETWORK SETUP
# ------------------------------------------------------------------
warnings.filterwarnings("ignore", category=DeprecationWarning)

session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
session.mount("https://", adapter)
session.mount("http://", adapter)

stats = {"total": 0, "success": 0, "duplicates": 0, "errors": 0}
stats_lock = threading.Lock()

# ------------------------------------------------------------------
# 🛠 LOGIC
# ------------------------------------------------------------------

def generate_unique_id():
    # BCL + 15 random digits
    random_digits = ''.join([str(random.randint(0, 9)) for _ in range(15)])
    return f"BCL{random_digits}"

def save_to_php_bridge(data_dict):
    try:
        # Send data as JSON to your PHP file
        response = session.post(
            YOUR_PHP_ENDPOINT, 
            json=data_dict,
            headers={"Content-Type": "application/json", "User-Agent": "PythonApp"},
            timeout=10
        )
        
        if response.status_code == 200:
            try:
                resp_json = response.json()
                return resp_json.get("status", "error")
            except:
                # If HTML is returned, it means InfinityFree blocked us
                print(f"⚠️ BLOCKAGE DETECTED: InfinityFree sent HTML instead of JSON.")
                return "blocked"
        else:
            print(f"⚠️ Server Error: {response.status_code}")
            return "error"

    except Exception as e:
        print(f"⚠️ Connection Error: {str(e)[:50]}")
        return "error"

def generate_random_number():
    prefix = random.choice(PREFIXES)
    suffix = random.randint(10000, 99999)
    return f"{prefix}{suffix}"

def process_pipeline(thread_id):
    print(f"🚀 Pipeline {thread_id} active...")

    while True:
        mobile_number = generate_random_number()
        headers = {"User-Agent": random.choice(USER_AGENTS)}

        try:
            # 1. Fetch Data
            params = {"action": "api", "key": API_KEY, "number": mobile_number}
            response = session.get(API_URL, params=params, headers=headers, timeout=20)

            try:
                data = response.json()
            except:
                time.sleep(1)
                continue

            results = []
            if isinstance(data, list):
                results = data
            elif isinstance(data, dict):
                if not (data.get('error') or data.get('response') == 'error'):
                    results = [data]

            with stats_lock:
                stats["total"] += 1
                curr_total = stats["total"]

            if results:
                found_valid_data = False
                for p in results:
                    raw_name = p.get("name")
                    if not raw_name or str(raw_name).strip() in ["", "N/A"]:
                        continue

                    found_valid_data = True
                    
                    # 2. Prepare Data
                    raw_address = str(p.get("address", "N/A"))
                    clean_address = raw_address.replace("!", ", ").replace(" ,", ",").strip()[:250]

                    record = {
                        'unique_id': generate_unique_id(),
                        'name': str(raw_name),
                        'father_name': str(p.get("father_name", "N/A")),
                        'mobile': str(p.get("mobile", mobile_number)),
                        'address': clean_address,
                        'amount_won': 1000000, 
                        'gst_fee': 1000
                    }

                    # 3. Send to PHP Bridge
                    status = save_to_php_bridge(record)

                    if status == "success":
                        with stats_lock: stats["success"] += 1
                        print(f"✅ [{curr_total}] SAVED | {record['mobile']}")
                    elif status == "duplicate":
                        with stats_lock: stats["duplicates"] += 1
                        print(f"🔁 [{curr_total}] EXISTS | {record['mobile']}")
                    elif status == "blocked":
                         print(f"⛔ [{curr_total}] BLOCKED BY HOST")
                         time.sleep(5) # Slow down if blocked

                if not found_valid_data:
                    print(f"⚠️ [{curr_total}] Skipped (Empty/N/A)")
            else:
                print(f"❌ [{curr_total}] Not Found")

        except Exception as e:
            with stats_lock: stats["errors"] += 1
            print(f"⚠️ Error: {str(e)[:50]}")

        # Throttle to prevent crashing
        time.sleep(1.5)

# ------------------------------------------------------------------
# ▶️ RUNNER
# ------------------------------------------------------------------
if __name__ == "__main__":
    print(f"🔥 Starting Bot on Render...")
    
    # 1. Start the Data Pipelines in Background Threads
    executor = ThreadPoolExecutor(max_workers=CONCURRENT_THREADS)
    for i in range(CONCURRENT_THREADS):
        executor.submit(process_pipeline, i+1)

    # 2. Run the Web Server (Main Thread) - This keeps Render alive
    run_web_server()