"""
OVH VPS Availability Monitor and Telegram Bot

This script monitors OVH VPS availability and sends alerts via Telegram.
It supports running as a continuous background process, a one-off cron job,
or an HTTP server for external ping services.
"""

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import telebot
from flask import Flask, jsonify
from curl_cffi import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Load environment variables
load_dotenv()


ovhSubsidiary = ["ASIA", "US"]
planCode = ["vps-2025-model2", "vps-2025-model2-eu", "vps-2025-model2-ca"]
osName = ["Ubuntu 25.04", "Ubuntu 24.10"]

BASE_URL = {
    "us": "https://us.ovhcloud.com/engine/api/v1/vps/order/rule/datacenter/", # ovhSubsidiary US
    "ca": "https://www.ovhcloud.com/ca/engine/api/v1/vps/order/rule/datacenter/", # ovhSubsidiary ASIA 
}

# Global emoji storage (Telegram Premium Custom Emoji IDs)
CUSTOM_EMOJIS: Dict[str, str] = {
    "vps": "5318885171494139260",
    "server": "4985708576770097801",
    "verified": "5859296708504063489",
    "loading": "5854732502593180838",
    "out": "5314504236132747481"
}

PLAN_LINK = {
    "US" : "https://us.ovhcloud.com/vps/configurator/?planCode=vps-2025-model2", # Model 2 VPS
    "ASIA" : "https://www.ovhcloud.com/asia/vps/configurator/?planCode=vps-2025-model2", # Model 2 VPS Asia 
}

class OvhVpsChecker:
    """Monitors OVH VPS inventory and sends professional Telegram notifications."""

    def __init__(self) -> None:
        # Load configuration from environment
        self.bot_token: Optional[str] = os.environ.get("BOT_TOKEN")
        self.chat_id: Optional[str] = os.environ.get("CHAT_ID")
        self.debug_print: bool = os.environ.get("DEBUG_PRINT", "True").lower() == "true"
        self.sleep_interval: int = int(os.environ.get("SLEEP", 120))
        self.port: int = int(os.environ.get("PORT", 8080))
        self.check_sg_only: bool = os.environ.get("CHECK_SG_VPS_ONLY", "False").lower() == "true"
        self.send_only_available: bool = os.environ.get("SEND_ONLY_AVAILABLE_VPS", "False").lower() == "true"

        # Regional groupings for tree structure
        self.regions = {
            "Asia": {
                "YNM": "India",
                "SGP": "Singapore",
                "SYD": "Australia"
            },
            "Europe": {
                "WAW": "Poland",
                "DE": "Germany",
                "GRA": "France (Gravelines)",
                "SBG": "France (Strasbourg)",
                "UK": "United Kingdom",
                "EU-SOUTH-MIL": "Italy",
                "EU-WEST-RBX": "France (Roubaix)"
            },
            "North America": {
                "BHS": "Canada",
                "US-EAST-VA": "USA (East)",
                "US-WEST-OR": "USA (West)"
            }
        }

        # Use global emojis
        self.custom_emojis = CUSTOM_EMOJIS


    def _get_emoji_tag(self, key: str, fallback: str) -> str:
        """Returns a Telegram HTML emoji tag or fallback character."""
        emoji_id = self.custom_emojis.get(key)
        if emoji_id:
            return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
        return fallback

    def fetch_availability(self) -> None:
        """Fetches and aggregates availability data from all configured OVH API combinations."""
        aggregated_datacenters: Dict[str, Dict[str, Any]] = {}

        for sub in ovhSubsidiary:
            url = BASE_URL["us"] if sub == "US" else BASE_URL["ca"]
            for plan in planCode:
                for os_v in osName:
                    params = {
                        "ovhSubsidiary": sub,
                        "os": os_v,
                        "planCode": plan,
                    }

                    try:
                        response = requests.get(url, params=params, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            for dc in data.get("datacenters", []):
                                name = dc.get("datacenter")
                                status = dc.get("status")
                                
                                # Merge logic: 'available' > 'out-of-stock-preorder-allowed' > 'out-of-stock'
                                if name not in aggregated_datacenters:
                                    dc["subsidiary"] = sub
                                    aggregated_datacenters[name] = dc
                                else:
                                    current_status = aggregated_datacenters[name].get("status")
                                    if status == "available":
                                        aggregated_datacenters[name]["status"] = "available"
                                        aggregated_datacenters[name]["subsidiary"] = sub
                                    elif status == "out-of-stock-preorder-allowed" and current_status != "available":
                                        aggregated_datacenters[name]["status"] = "out-of-stock-preorder-allowed"
                                        aggregated_datacenters[name]["subsidiary"] = sub

                    except Exception as e:
                        if self.debug_print:
                            logging.error(f"Error fetching {sub}/{plan}/{os_v}: {e}")

        if aggregated_datacenters:
            self._process_data(list(aggregated_datacenters.values()))
        else:
            if self.debug_print:
                logging.warning("No data collected from any API endpoint.")

    def _process_data(self, datacenters: List[Dict[str, Any]]) -> None:
        """Categorizes results and triggers notifications."""
        results: Dict[str, List[Dict[str, Any]]] = {}
        any_available = False
        
        for dc in datacenters:
            short_name = dc.get("datacenter", "Unknown")
            
            # Filter for Singapore only if enabled
            if self.check_sg_only and short_name != "SGP":
                continue

            status = dc.get("status", "unknown")
            is_available = (status == "available")
            is_preorder = (status == "out-of-stock-preorder-allowed")
            
            # Filter: if SEND_ONLY_AVAILABLE is True, skip out-of-stock items
            if self.send_only_available and not (is_available or is_preorder):
                continue

            if is_available or is_preorder:
                any_available = True
            
            # Map to region
            found_region = "Other"
            loc_name = short_name
            for region, locations in self.regions.items():
                if short_name in locations:
                    found_region = region
                    loc_name = f"{region} {locations[short_name]}"
                    break
            
            if found_region not in results:
                results[found_region] = []
            
            results[found_region].append({
                "name": loc_name,
                "available": is_available,
                "preorder": is_preorder,
                "subsidiary": dc.get("subsidiary")
            })

        # Terminal Output
        if self.debug_print:
            tree_text = self._generate_tree_text(results, is_telegram=False)
            logging.info(f"VPS Status Tree:\n\n{tree_text}")
        
        # Telegram Output
        if any_available:
            self._send_telegram(results)

    def _generate_tree_text(self, results: Dict[str, List[Dict[str, Any]]], is_telegram: bool) -> str:
        """Constructs the message format (Tree for Terminal, List for Telegram)."""
        vps = self._get_emoji_tag("vps", "💻") if is_telegram else "💻"
        srv = self._get_emoji_tag("server", "🖥️") if is_telegram else "🖥️"
        ver = self._get_emoji_tag("verified", "✅") if is_telegram else "✅"
        ld = self._get_emoji_tag("loading", "⏳") if is_telegram else "⏳"
        out = self._get_emoji_tag("out", "❌") if is_telegram else "❌"
        
        header = f"{vps} <b>OVHCloud -- VPS Availability Checker</b> {srv}\n" if is_telegram else "💻 OVHCloud -- VPS Availability Checker 🖥️\n"
        
        # Flatten results
        flat_list = [item for sublist in results.values() for item in sublist]
        
        if is_telegram:
            # Professional List for Telegram (No Tree, No <pre>)
            body = ""
            for item in flat_list:
                if item["available"]:
                    emoji = f"{ver}"
                    status = "Available now"
                    # Add Plan Link if available
                    sub = item.get("subsidiary")
                    if sub in PLAN_LINK:
                        status = f'<a href="{PLAN_LINK[sub]}">{status}</a>'
                elif item["preorder"]:
                    emoji = f"{ld}"
                    status = "Pre-order"
                else:
                    emoji = f"{out}"
                    status = "Out Of Stock"
                
                body += f"{emoji} {item['name']} | {status}\n"
            return f"{header}\n{body}"
        else:
            # Tree structure for Terminal
            body = ".\n└── OVHCloud/\n"
            for i, item in enumerate(flat_list):
                connector = "├── " if i < len(flat_list) - 1 else "└── "
                if item["available"]:
                    emoji, status = "✅", "Available now"
                elif item["preorder"]:
                    emoji, status = "⏳", "Pre-order"
                else:
                    emoji, status = "❌", "Out Of Stock"
                
                body += f"{connector}{emoji} {item['name']} | {status}\n"
            return body

    def _send_telegram(self, results: Dict[str, List[Dict[str, Any]]]) -> None:
        """Sends the formatted HTML message to Telegram."""
        if not self.bot_token or not self.chat_id:
            return

        text = self._generate_tree_text(results, is_telegram=True)
        try:
            bot = telebot.TeleBot(self.bot_token)
            bot.send_message(self.chat_id, text, parse_mode="HTML", disable_web_page_preview=True)
            if self.debug_print:
                logging.info("Telegram notification sent successfully.")
        except Exception as e:
            if self.debug_print:
                logging.error(f"Telegram Error: {e}")

    def run_server(self) -> None:
        """Starts a Flask HTTP server for health checks."""
        app = Flask(__name__)

        @app.route('/')
        def home():
            return "Bot Active."

        @app.route('/check')
        def trigger_check():
            threading.Thread(target=self.fetch_availability).start()
            return "Check triggered."

        if self.debug_print:
            logging.info(f"Health server started on port {self.port}")
        else:
            print(f"[+] Flask App Running on port {self.port}")
        
        # Run Flask silently
        import logging as flask_logging
        from flask import cli
        
        # Suppress Flask banner and logs
        cli.show_server_banner = lambda debug, app_import_path: None
        log = flask_logging.getLogger('werkzeug')
        log.setLevel(flask_logging.ERROR)
        
        app.run(host='0.0.0.0', port=self.port)

    def start(self) -> None:
        """Main entry point to start the monitor."""
        try:
            if not self.debug_print:
                print("[+] Bot Running")
            else:
                logging.info(f"Starting OVH Monitor (Mode: loop, Sleep: {self.sleep_interval}s)")

            # Start health server in background
            threading.Thread(target=self.run_server, daemon=True).start()

            # Main monitoring loop
            while True:
                self.fetch_availability()
                time.sleep(self.sleep_interval)
        except KeyboardInterrupt:
            if self.debug_print:
                logging.info("Monitor stopped by user.")
            os._exit(0)


if __name__ == "__main__":
    # Initialize and start the bot
    checker = OvhVpsChecker()
    checker.start()