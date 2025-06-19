SurePet Data Pull Script

A concise Python tool to centralize your Sure Petcare data for analysis and reporting.

Why This Matters

- Unified view: Combine structured feeding and drinking events. Includes extra code to capture water-consumption events not tied to a microchip (mis-scan).
- Actionable insights: Export to CSV for dashboards, charts, or automated reports.
- Reliability: Scheduled pulls ensure your data stays up to date without manual intervention.

Prerequisites

- Python 3.8+
- Libraries:
  pip install requests pandas

Configuration

1. Edit `surepet_data_pull.py`  
   Update these values at the top of the script:

   ```python
   EMAIL       = "you@example.com"      # Sure Petcare login email
   PASSWORD    = "your-password"        # Sure Petcare account password
   DEVICE_ID   = "0123456789"           # (Default; change only if required)
   START_DATE  = "2025-01-01"           # Data pull start date
   END_DATE    = datetime.utcnow().date().isoformat()
   OUTPUT_PATH = "surepet_events.csv"   # CSV output file

3. Map alert devices
   In the same script, adjust ALERT_DEVICE_MAP for any additional fountain names and IDs.

Usage

Run the pull script on demand:
python3 surepet_data_pull.py

The script will:
1. Authenticate and retrieve a token.
2. Fetch pet feeding, drinking, and movement data.
3. Collect water-consumption alerts.
4. Merge everything into a single CSV.

Automation (macOS)
You can schedule this script to run automatically using macOS’s built-in launchd system. In this project, I set up a LaunchAgent by installing a property list file (*.plist) into ~/Library/LaunchAgents/.
