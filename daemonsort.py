import requests
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from collections import defaultdict

# Cache to store the last error state for each sim
last_error_cache = defaultdict(str)

def setup_driver():
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode (no GUI)
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Initialize the Chrome WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def send_alert(message):
    print("\nSending notification with content:")
    print("-" * 50)
    print(message)
    print("-" * 50)
    
    requests.post("https://ntfy.sh/ethandaemonalerts444",
        data=message,
        headers={
            "Title": "SIM ALERT",
            "Tags": "skull"
        })
    print(f"Notification sent at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

def fetch_html_table():
    url = 'http://10.101.20.10:3000/game-servers/daemon-states'
    max_retries = 3
    retry_delay = 5
    
    driver = setup_driver()
    print("WebDriver initialized successfully")
    
    for attempt in range(max_retries):
        try:
            print(f"\nAttempt {attempt + 1} to fetch data from {url}")
            driver.get(url)
            print("Page loaded")
            
            # Wait longer and be more specific about what we're waiting for
            wait = WebDriverWait(driver, 20)  # Increased timeout to 20 seconds
            print("Waiting for table content to appear...")
            
            # Wait for both table and at least one row to be present
            table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
            
            # Add a small delay to ensure content is fully loaded
            time.sleep(2)
            
            print("Table element found")
            html_content = driver.page_source
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try different ways to find the table and its contents
            table = soup.find('table')
            if table is None:
                print("Couldn't find table, trying alternative selectors...")
                return []
            
            # Print the table HTML for debugging
            print("Table HTML structure:")
            print(table.prettify()[:500])  # First 500 chars of formatted table HTML
            
            # Try to find rows in different ways
            rows = table.select('tr')  # Using CSS selector
            if not rows:
                rows = table.find_all('tr', recursive=True)  # Try recursive search
            
            print(f"Found {len(rows)} rows in the table")
            
            data = []
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:  # Make sure we have cells
                    # Filter out empty strings
                    row_data = [cell.text.strip() for cell in cells if cell.text.strip()]
                    
                    # Special handling for the second item (index 1) if it exists
                    if len(row_data) > 1:
                        if 'SI' in row_data[1]:
                            row_data[1] = 'SI'
                        elif 'SP' in row_data[1]:
                            row_data[1] = 'SP'
                    
                    # Special handling for the third item (index 2) if it exists
                    if len(row_data) > 2:
                        if 'online' in row_data[2].lower():
                            row_data[2] = 'ON'
                        elif 'offline' in row_data[2].lower():
                            row_data[2] = 'OFF'
                    
                    # Only add and print the row if SessionId is not blank and there are at least 7 items
                    if len(row_data) > 3 and row_data[3].strip() and len(row_data) >= 7:
                        data.append(row_data)
                        print(" | ".join(row_data))  # Print formatted row data
            
            # Skip the header row when returning data
            return data[1:] if len(data) > 1 else []
            
        except Exception as e:
            print(f"Error details: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Fetch attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Error fetching data after {max_retries} attempts: {e}")
                return []
        finally:
            if attempt == max_retries - 1:
                print("Closing WebDriver")
                driver.quit()

def check_daemons():
    global last_error_cache
    table_data = fetch_html_table()
    
    # Collect all alerts before sending
    all_alerts = []
    current_errors = defaultdict(str)  # Track current errors
    
    # Define keywords to search for
    error_keywords = ['fail', 'idle', 'crash', 'estop', 'motion']
    
    # Check each row for error conditions
    for row in table_data:
        if not row:  # Skip empty rows
            continue
            
        messages = []  # Collect all messages for this row
        sim_name = row[0]  # Assuming first column is sim name
        sim_type = row[1] if len(row) > 1 else ""  # Get SI/SP label
        
        # Check each cell in the row for keywords
        for cell in row:
            cell_text = cell.lower()
            if any(keyword in cell_text for keyword in error_keywords):
                messages.append(cell)  # Remove "ERR:" prefix
        
        # If we found any issues, process them
        if messages:
            error_message = " | ".join(messages)
            current_errors[sim_name] = error_message
            
            # Only add to alerts if the error is new or different
            if last_error_cache[sim_name] != error_message:
                alert_message = f"{sim_name} ({sim_type}) | {error_message}"
                all_alerts.append(alert_message)
    
    # Update the cache with current errors
    # Remove sims that no longer have errors
    sims_to_remove = [sim for sim in last_error_cache if sim not in current_errors]
    for sim in sims_to_remove:
        del last_error_cache[sim]
    
    # Update cache with current errors
    last_error_cache.update(current_errors)
    
    # Send all alerts as one message if there are any
    if all_alerts:
        full_message = "\n\n".join(all_alerts)
        send_alert(full_message)
    else:
        print("No new issues found in this check.")

def main():
    print("Starting daemon monitor...")
    while True:
        try:
            check_daemons()
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            print(f"Next check at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 30))}")
            time.sleep(50)

if __name__ == "__main__":
    main()
