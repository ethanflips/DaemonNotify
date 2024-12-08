#!/usr/bin/python
# -*- coding:utf-8 -*-

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
import sys
import os

# Path setup for e-paper display
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

# E-paper display imports
import logging
from waveshare_epd import epd2in13b_V4
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.DEBUG)

# Cache to store the last error state for each sim
last_error_cache = defaultdict(str)

try:
    # Initialize e-paper display
    logging.info("epd2in13b_V4 Demo")
    epd = epd2in13b_V4.EPD()
    logging.info("init and Clear")
    epd.init()
    epd.Clear()
    time.sleep(1)
    
    # Initialize fonts and images
    logging.info("Drawing")    
    font20 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 20)
    font18 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 18)
    
    # Create image for black layer only
    HBlackimage = Image.new('1', (epd.height, epd.width), 255)  # 250*122
    drawblack = ImageDraw.Draw(HBlackimage)

except IOError as e:
    logging.info(e)
    
except KeyboardInterrupt:    
    logging.info("ctrl + c:")
    epd2in13b_V4.epdconfig.module_exit(cleanup=True)
    exit()

def setup_driver():
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Performance optimizations
    chrome_options.add_argument('--disable-gpu')  # Disable GPU hardware acceleration
    chrome_options.add_argument('--disable-extensions')  # Disable extensions
    chrome_options.add_argument('--disable-software-rasterizer')  # Disable software rasterizer
    chrome_options.add_argument('--disable-javascript')  # Disable JavaScript if the page doesn't require it
    chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # Disable images
    chrome_options.add_argument('--disable-infobars')  # Disable infobars
    chrome_options.add_argument('--disable-notifications')  # Disable notifications
    chrome_options.add_argument('--ignore-certificate-errors')  # Ignore certificate errors
    chrome_options.add_argument('--disable-popup-blocking')  # Disable popup blocking
    chrome_options.add_argument('--log-level=3')  # Minimal logging
    chrome_options.page_load_strategy = 'eager'  # Don't wait for all resources to load
    
    # Initialize the Chrome WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(10)  # Set page load timeout
    return driver

def send_alert(message):
    # Clear the display
    drawblack.rectangle((0, 0, epd.height, epd.width), fill=255)  # Clear black layer
    
    # Calculate text wrapping and positioning
    max_chars_per_line = 20  # Adjust based on font size and display width
    y_position = 10
    current_time = time.strftime('%H:%M:%S')
    
    # Display time at the top
    drawblack.text((10, y_position), current_time, font=font18, fill=0)
    y_position += 25  # Move down past the time
    
    # Split message into lines and display each alert
    for alert in message.split('\n\n'):
        # Split long lines into multiple lines
        words = alert.split()
        current_line = ''
        
        for word in words:
            if len(current_line) + len(word) + 1 <= max_chars_per_line:
                current_line += (word + ' ')
            else:
                # Draw the current line and start a new one
                drawblack.text((10, y_position), current_line.strip(), font=font18, fill=0)
                y_position += 20
                current_line = word + ' '
        
        # Draw any remaining text
        if current_line:
            drawblack.text((10, y_position), current_line.strip(), font=font18, fill=0)
            y_position += 30  # Extra space between alerts
    
    # Send notification to ntfy
    requests.post("https://ntfy.sh/ethandaemonalerts444",
        data=message,
        headers={
            "Title": "SIM ALERT",
            "Tags": "skull"
        })

def fetch_html_table():
    url = 'http://10.101.20.10:3000/game-servers/daemon-states'
    max_retries = 3
    retry_delay = 5
    
    driver = setup_driver()
    
    for attempt in range(max_retries):
        try:
            driver.get(url)
            
            # Wait for table to be present and have content
            wait = WebDriverWait(driver, 10)  # Shorter initial timeout
            table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            
            # Wait for rows and verify table has content
            rows = wait.until(lambda d: len(d.find_elements(By.TAG_NAME, "tr")) > 1)
            
            # Get the initial row count
            initial_row_count = len(driver.find_elements(By.TAG_NAME, "tr"))
            
            # Quick check if more rows are loading
            time.sleep(1)
            current_row_count = len(driver.find_elements(By.TAG_NAME, "tr"))
            
            # If row count is still increasing, wait a bit longer
            if current_row_count > initial_row_count:
                time.sleep(2)
            
            html_content = driver.page_source
            soup = BeautifulSoup(html_content, 'html.parser')
            table = soup.find('table')
            
            if table is None:
                return []
            
            rows = table.find_all('tr', recursive=True)
            
            data = []
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    row_data = [cell.text.strip() for cell in cells if cell.text.strip()]
                    
                    if len(row_data) > 1:
                        if 'SI' in row_data[1]:
                            row_data[1] = 'SI'
                        elif 'SP' in row_data[1]:
                            row_data[1] = 'SP'
                    
                    if len(row_data) > 2:
                        if 'online' in row_data[2].lower():
                            row_data[2] = 'ON'
                        elif 'offline' in row_data[2].lower():
                            row_data[2] = 'OFF'
                    
                    if len(row_data) > 3 and row_data[3].strip() and len(row_data) >= 7:
                        data.append(row_data)
            
            # Verify we have a reasonable amount of data
            if len(data) > 1:  # At least header + one row
                return data[1:]
            else:
                # If data seems incomplete, retry
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return []
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return []
        finally:
            if attempt == max_retries - 1:
                driver.quit()

def check_daemons():
    global last_error_cache
    
    # Record start time of check
    start_time = time.time()
    
    table_data = fetch_html_table()
    
    # Collect all alerts before sending
    all_alerts = []
    current_errors = defaultdict(str)
    
    # Define keywords to search for
    error_keywords = ['fail', 'idle', 'crash', 'estop', 'motion']
    
    # Check each row for error conditions
    for row in table_data:
        if not row:
            continue
            
        messages = []
        sim_name = row[0]
        sim_type = row[1] if len(row) > 1 else ""
        
        for cell in row:
            cell_text = cell.lower()
            if any(keyword in cell_text for keyword in error_keywords):
                messages.append(cell)
        
        if messages:
            error_message = " | ".join(messages)
            current_errors[sim_name] = error_message
            
            if last_error_cache[sim_name] != error_message:
                alert_message = f"{sim_name} ({sim_type}) | {error_message}"
                all_alerts.append(alert_message)
    
    sims_to_remove = [sim for sim in last_error_cache if sim not in current_errors]
    for sim in sims_to_remove:
        del last_error_cache[sim]
    
    last_error_cache.update(current_errors)
    
    # Clear the display for status update
    drawblack.rectangle((0, 0, epd.height, epd.width), fill=255)
    
    # Calculate actual time taken for this check
    check_duration = time.time() - start_time
    
    # Display current time and status
    current_time = time.strftime('%H:%M:%S')
    next_check = time.strftime('%H:%M:%S', time.localtime(time.time() + check_duration + 5))
    
    drawblack.text((10, 10), f"Last Check: {current_time}", font=font18, fill=0)
    drawblack.text((10, 35), f"Next Check: {next_check}", font=font18, fill=0)
    
    if all_alerts:
        # If there are alerts, display them
        full_message = "\n\n".join(all_alerts)
        y_position = 60
        for alert in all_alerts:
            words = alert.split()
            current_line = ''
            for word in words:
                if len(current_line) + len(word) + 1 <= 20:  # 20 chars per line
                    current_line += (word + ' ')
                else:
                    drawblack.text((10, y_position), current_line.strip(), font=font18, fill=0)
                    y_position += 20
                    current_line = word + ' '
            if current_line:
                drawblack.text((10, y_position), current_line.strip(), font=font18, fill=0)
                y_position += 30
        
        # Draw X in bottom right for issues
        drawblack.text((epd.height - 40, epd.width - 40), "✗", font=font20, fill=0)
        
        # Send notification
        send_alert(full_message)
    else:
        # If no alerts, display "No Issues Found"
        drawblack.text((10, 60), "No Issues Found", font=font18, fill=0)
        # Draw checkmark in bottom right for no issues
        drawblack.text((epd.height - 40, epd.width - 40), "✓", font=font20, fill=0)
    
    # Update the display (send empty buffer for red layer)
    empty_buffer = Image.new('1', (epd.height, epd.width), 255)
    epd.display(epd.getbuffer(HBlackimage), epd.getbuffer(empty_buffer))

def check_sleep_mode():
    current_hour = int(time.strftime('%H'))
    current_time = time.strftime('%H:%M')
    wake_time = '10:45'
    
    if current_hour >= 1 and current_time < wake_time:
        # Clear display and show sleep message
        drawblack.rectangle((0, 0, epd.height, epd.width), fill=255)
        drawblack.text((10, 10), "Sleep Mode", font=font20, fill=0)
        drawblack.text((10, 40), f"Will wake at {wake_time}", font=font18, fill=0)
        current_time = time.strftime('%H:%M:%S')
        drawblack.text((10, 70), f"Current: {current_time}", font=font18, fill=0)
        
        # Update display with sleep message
        empty_buffer = Image.new('1', (epd.height, epd.width), 255)
        epd.display(epd.getbuffer(HBlackimage), epd.getbuffer(empty_buffer))
        
        # Calculate time until wake
        now = time.localtime()
        wake_hour, wake_minute = map(int, wake_time.split(':'))
        
        # If it's past midnight, wait for wake time today
        wake_timestamp = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 
                                    wake_hour, wake_minute, 0, 0, 0, -1))
        
        # If wake time today has passed, wait for tomorrow
        if time.time() > wake_timestamp:
            wake_timestamp += 24 * 60 * 60  # Add 24 hours
            
        # Sleep until wake time
        sleep_duration = wake_timestamp - time.time()
        if sleep_duration > 0:
            time.sleep(sleep_duration)
        return True
    return False

def main():
    while True:
        try:
            # Check if we should enter sleep mode
            if check_sleep_mode():
                continue
            
            check_daemons()
        except Exception as e:
            pass
        finally:
            time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("ctrl + c:")
        epd2in13b_V4.epdconfig.module_exit(cleanup=True)
        exit()
