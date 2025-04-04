from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException
import time
import re
import pandas as pd
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC

def extract_job_details(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    details = {}

    def safe_text(selector):
        tag = soup.select_one(selector)
        return tag.get_text(strip=True) if tag else None

    details["Company"] = safe_text(".job-details-jobs-unified-top-card__company-name a")
    details["Job Title"] = safe_text(".job-details-jobs-unified-top-card__job-title h1")
    details["Location"] = safe_text(".job-details-jobs-unified-top-card__tertiary-description-container span.tvm__text")

    spans = soup.select(".job-details-jobs-unified-top-card__tertiary-description-container span")
    if len(spans) >= 3:
        details["Posted"] = spans[2].get_text(strip=True)
    if len(spans) >= 5:
        details["Applicants"] = spans[4].get_text(strip=True)

    pills = soup.select(".job-details-preferences-and-skills__pill span[aria-hidden='true']")
    for pill in pills:
        text = pill.get_text(strip=True)
        if any(x in text for x in ["On-site", "Remote", "Hybrid"]):
            details["Workplace Type"] = text
        elif any(x in text for x in ["Full-time", "Part-time", "Contract", "Internship"]):
            details["Job Type"] = text

    about = soup.select_one("#job-details")
    if about:
        raw_text = about.get_text(separator="\n", strip=True)
        clean_text = re.sub(r"\s+", " ", raw_text)
        details["Full Description"] = clean_text

        exp = re.search(r"(?i)(Experience)\s*[:\-–]?\s*(-?\s*\d+\+?\s*(?:Years|Yrs)?)", clean_text)
        ctc = re.search(r"(?i)(CTC|Compensation)\s*[:\-–]?\s*([\w\s.,+/-]+)", clean_text)
        notice = re.search(r"(?i)(NP|Notice\s*Period)\s*[:\-–]?\s*([\w\s]+)", clean_text)
        job_loc = re.search(r"(?i)(Location)\s*[:\-–]?\s*([\w\s,&()/-]+)", clean_text)
        role = re.search(r"(?i)(Role|Position|Job\s*Title|Job\s*Description)\s*[:\-–]?\s*(.*?)(?=\n|Responsibilities|Experience|Location|$)", clean_text)

        details["Experience"] = exp.group(0).strip() if exp else None
        details["CTC"] = ctc.group(0).strip() if ctc else None
        details["Notice Period"] = notice.group(0).strip() if notice else None
        details["Job Location"] = job_loc.group(0).strip() if job_loc else None
        details["Role Overview"] = role.group(0).strip() if role else None
    else:
        details["Full Description"] = None

    return details

def process_jobs(driver):
    SCROLL_PAUSE_TIME = 3
    MAX_SCROLL_ATTEMPTS = 50

    job_card_xpath = (
        "//li[contains(@class, 'ember-view') and contains(@class, 'occludable-update') and "
        "(contains(@class, 'scaffold-layout__list-item') or "
        "contains(@class, 'jobs-search-results__list-item') or "
        "contains(@class, 'job-card-container--clickable') or "
        "contains(@class, 'jobs-search-two-pane__job-card-container'))]"
    )

    def load_all_job_cards():
        scroll_attempt = 0
        last_count = 0
        new_count = len(driver.find_elements(By.XPATH, job_card_xpath))

        while scroll_attempt < MAX_SCROLL_ATTEMPTS:
            print(f"🔄 Scroll #{scroll_attempt+1}: Loaded {new_count} job cards so far...")
            try:
                job_list_container = driver.find_element(By.XPATH, "//div[contains(@class, 'jobs-search-results-list')]")
                driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", job_list_container)
            except Exception as e:
                print(f"⚠️ Failed to scroll job list container: {e}")

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)

            last_count = new_count
            new_count = len(driver.find_elements(By.XPATH, job_card_xpath))
            scroll_attempt += 1

            if new_count == last_count:
                print("✅ No new job cards loaded. Ending scroll.")
                break

        print(f"🟢 All job cards loaded. Total: {new_count}")

    load_all_job_cards()

    job_cards = driver.find_elements(By.XPATH, job_card_xpath)
    print(f"📦 Total job cards to process: {len(job_cards)}")

    job_data_list = []
    processed_ids = set()

    for idx, card in enumerate(job_cards):
        try:
            try:
                link_elem = card.find_element(By.XPATH, ".//a[contains(@href, '/jobs/view/')]")
                job_id = link_elem.get_attribute("href")
            except:
                job_id = f"job-{idx}"

            if job_id in processed_ids:
                print(f"⏩ Skipping duplicate card #{idx + 1}")
                continue

            print(f"\n➡️ Clicking job card #{idx + 1}")
            driver.execute_script("arguments[0].scrollIntoView(true);", card)
            card.click()

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CLASS_NAME, "job-details-jobs-unified-top-card__company-name")
                )
            )
            time.sleep(2)

            data = extract_job_details(driver)
            job_data_list.append(data)
            print(f"✅ Extracted: {data.get('Job Title')} at {data.get('Company')}")

            processed_ids.add(job_id)

        except Exception as e:
            print(f"❌ Failed to process job card #{idx + 1}: {e}")
            continue

    return job_data_list

def scrape_and_save(url, max_pages=2):
    

    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")  # Recommended for cloud
    chrome_options.add_argument("--disable-dev-shm-usage")  # Recommended for Docker/CI
    chrome_options.add_argument("--window-size=1920x1080")  # Optional but helpful
    chrome_options.add_argument("--disable-gpu")  # Optional on non-Windows
    chrome_options.add_argument("--disable-extensions")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)


    driver.get('https://www.linkedin.com/login')
    time.sleep(2)

    username = driver.find_element(By.ID, 'username')
    password = driver.find_element(By.ID, 'password')
    username.send_keys('shubhankarmisra00@gmail.com')
    password.send_keys('Shub@1996')
    driver.find_element(By.XPATH, '//button[@type="submit"]').click()
    time.sleep(5)

    driver.get(url)

    final_data = []
    for _ in range(max_pages):
        final_data.extend(process_jobs(driver))

    df = pd.DataFrame(final_data)
    df.to_csv("linkedin_jobs.csv", index=False)
    print("📁 File saved: linkedin_jobs.csv")
    driver.quit()
    return df

{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": None,
   "id": "658af0a3-d68c-427e-9c57-74602c0acd19",
   "metadata": {},
   "outputs": [],
   "source": [
    "from selenium import webdriver\n",
    "from selenium.webdriver.chrome.service import Service\n",
    "from webdriver_manager.chrome import ChromeDriverManager\n",
    "from selenium.webdriver.common.by import By\n",
    "from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException\n",
    "import time\n",
    "from selenium.webdriver.common.keys import Keys\n",
    "import time\n",
    "import re\n",
    "import pandas as pd\n",
    "from bs4 import BeautifulSoup\n",
    "from selenium.webdriver.support.ui import WebDriverWait\n",
    "from selenium.webdriver.support import expected_conditions as EC\n",
    "\n",
    "# === User Inputs ===\n",
    "url = input(\"Enter LinkedIn job search URL: \")\n",
    "max_pages = int(input(\"Enter number of pages to scrape: \"))\n",
    "\n",
    "# Initialize the WebDriver\n",
    "driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))  # Replace with your WebDriver (e.g., Firefox, Edge)\n",
    "driver.maximize_window()\n",
    "\n",
    "# Login to LinkedIn\n",
    "driver.get('https://www.linkedin.com/login')\n",
    "time.sleep(2)\n",
    "\n",
    "# Enter your LinkedIn credentials\n",
    "username = driver.find_element(By.ID, 'username')\n",
    "password = driver.find_element(By.ID, 'password')\n",
    "username.send_keys('shubhankarmisra00@gmail.com')  # Replace with your LinkedIn email\n",
    "password.send_keys('Shub@1996')          # Replace with your LinkedIn password\n",
    "driver.find_element(By.XPATH, '//button[@type=\"submit\"]').click()\n",
    "time.sleep(5)\n",
    "\n",
    "# Open LinkedIn and log in\n",
    "#url='https://www.linkedin.com/jobs/search/?currentJobId=4092177554&distance=25&f_AL=true&f_E=1%2C2%2C3&geoId=102713980&keywords=data%20analytics&origin=JOB_COLLECTION_PAGE_KEYWORD_HISTORY&refresh=true'\n",
    "driver.get(url)\n",
    "#driver.get('https://www.linkedin.com/jobs/search/?currentJobId=4013877987&f_AL=true&f_E=1%2C2%2C3&keywords=Data%20Analyst&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh=true')\n",
    "\n",
    "\n",
    "def extract_job_details(driver):\n",
    "    soup = BeautifulSoup(driver.page_source, \"html.parser\")\n",
    "    details = {}\n",
    "\n",
    "    def safe_text(selector):\n",
    "        tag = soup.select_one(selector)\n",
    "        return tag.get_text(strip=True) if tag else None\n",
    "\n",
    "    details[\"Company\"] = safe_text(\".job-details-jobs-unified-top-card__company-name a\")\n",
    "    details[\"Job Title\"] = safe_text(\".job-details-jobs-unified-top-card__job-title h1\")\n",
    "    details[\"Location\"] = safe_text(\".job-details-jobs-unified-top-card__tertiary-description-container span.tvm__text\")\n",
    "\n",
    "    # Posted time + Applicants\n",
    "    spans = soup.select(\".job-details-jobs-unified-top-card__tertiary-description-container span\")\n",
    "    if len(spans) >= 3:\n",
    "        details[\"Posted\"] = spans[2].get_text(strip=True)\n",
    "    if len(spans) >= 5:\n",
    "        details[\"Applicants\"] = spans[4].get_text(strip=True)\n",
    "\n",
    "    # Workplace type and job type\n",
    "    pills = soup.select(\".job-details-preferences-and-skills__pill span[aria-hidden='true']\")\n",
    "    for pill in pills:\n",
    "        text = pill.get_text(strip=True)\n",
    "        if any(x in text for x in [\"On-site\", \"Remote\", \"Hybrid\"]):\n",
    "            details[\"Workplace Type\"] = text\n",
    "        elif any(x in text for x in [\"Full-time\", \"Part-time\", \"Contract\", \"Internship\"]):\n",
    "            details[\"Job Type\"] = text\n",
    "\n",
    "    # ✅ Extract Full Job Description as clean text\n",
    "    about = soup.select_one(\"#job-details\")\n",
    "    if about:\n",
    "        raw_text = about.get_text(separator=\"\\n\", strip=True)\n",
    "        clean_text = re.sub(r\"\\s+\", \" \", raw_text)\n",
    "        details[\"Full Description\"] = clean_text  # Add full cleaned text\n",
    "\n",
    "        # Extract all fields with full matched line (group 0)\n",
    "        exp = re.search(r\"(?i)(Experience)\\s*[:\\-–]?\\s*(-?\\s*\\d+\\+?\\s*(?:Years|Yrs)?)\", clean_text)\n",
    "        ctc = re.search(r\"(?i)(CTC|Compensation)\\s*[:\\-–]?\\s*([\\w\\s.,+/-]+)\", clean_text)\n",
    "        notice = re.search(r\"(?i)(NP|Notice\\s*Period)\\s*[:\\-–]?\\s*([\\w\\s]+)\", clean_text)\n",
    "        job_loc = re.search(r\"(?i)(Location)\\s*[:\\-–]?\\s*([\\w\\s,&()/-]+)\", clean_text)\n",
    "        role = re.search(r\"(?i)(Role|Position|Job\\s*Title|Job\\s*Description)\\s*[:\\-–]?\\s*(.*?)(?=\\n|Responsibilities|Experience|Location|$)\", clean_text)\n",
    "        \n",
    "        details[\"Experience\"] = exp.group(0).strip() if exp else None\n",
    "        details[\"CTC\"] = ctc.group(0).strip() if ctc else None\n",
    "        details[\"Notice Period\"] = notice.group(0).strip() if notice else None\n",
    "        details[\"Job Location\"] = job_loc.group(0).strip() if job_loc else None\n",
    "        details[\"Role Overview\"] = role.group(0).strip() if role else None\n",
    "\n",
    "\n",
    "    else:\n",
    "        details[\"Full Description\"] = None\n",
    "\n",
    "    return details\n",
    "\n",
    "\n",
    "\n",
    "def process_jobs(driver):\n",
    "    from selenium.webdriver.common.by import By\n",
    "    from selenium.webdriver.support.ui import WebDriverWait\n",
    "    from selenium.webdriver.support import expected_conditions as EC\n",
    "    import time\n",
    "\n",
    "    SCROLL_PAUSE_TIME = 3\n",
    "    MAX_SCROLL_ATTEMPTS = 50\n",
    "\n",
    "    job_card_xpath = (\n",
    "        \"//li[contains(@class, 'ember-view') and contains(@class, 'occludable-update') and \"\n",
    "        \"(contains(@class, 'scaffold-layout__list-item') or \"\n",
    "        \"contains(@class, 'jobs-search-results__list-item') or \"\n",
    "        \"contains(@class, 'job-card-container--clickable') or \"\n",
    "        \"contains(@class, 'jobs-search-two-pane__job-card-container'))]\"\n",
    "    )\n",
    "\n",
    "    def load_all_job_cards():\n",
    "        scroll_attempt = 0\n",
    "        last_count = 0\n",
    "        new_count = len(driver.find_elements(By.XPATH, job_card_xpath))\n",
    "\n",
    "        while scroll_attempt < MAX_SCROLL_ATTEMPTS:\n",
    "            print(f\"🔄 Scroll #{scroll_attempt+1}: Loaded {new_count} job cards so far...\")\n",
    "            try:\n",
    "                job_list_container = driver.find_element(By.XPATH, \"//div[contains(@class, 'jobs-search-results-list')]\")\n",
    "                driver.execute_script(\"arguments[0].scrollTo(0, arguments[0].scrollHeight);\", job_list_container)\n",
    "            except Exception as e:\n",
    "                print(f\"⚠️ Failed to scroll job list container: {e}\")\n",
    "\n",
    "            driver.execute_script(\"window.scrollTo(0, document.body.scrollHeight);\")\n",
    "            time.sleep(SCROLL_PAUSE_TIME)\n",
    "\n",
    "            last_count = new_count\n",
    "            new_count = len(driver.find_elements(By.XPATH, job_card_xpath))\n",
    "            scroll_attempt += 1\n",
    "\n",
    "            if new_count == last_count:\n",
    "                print(\"✅ No new job cards loaded. Ending scroll.\")\n",
    "                break\n",
    "\n",
    "        print(f\"🟢 All job cards loaded. Total: {new_count}\")\n",
    "\n",
    "    # Step 1: Scroll and load all job cards\n",
    "    load_all_job_cards()\n",
    "\n",
    "    # Step 2: Fetch all visible job card elements\n",
    "    job_cards = driver.find_elements(By.XPATH, job_card_xpath)\n",
    "    print(f\"📦 Total job cards to process: {len(job_cards)}\")\n",
    "\n",
    "    job_data_list = []\n",
    "    processed_ids = set()\n",
    "\n",
    "    for idx, card in enumerate(job_cards):\n",
    "        try:\n",
    "            # Get job link (unique ID) for deduplication\n",
    "            try:\n",
    "                link_elem = card.find_element(By.XPATH, \".//a[contains(@href, '/jobs/view/')]\")\n",
    "                job_id = link_elem.get_attribute(\"href\")\n",
    "            except:\n",
    "                job_id = f\"job-{idx}\"\n",
    "\n",
    "            if job_id in processed_ids:\n",
    "                print(f\"⏩ Skipping duplicate card #{idx + 1}\")\n",
    "                continue\n",
    "\n",
    "            print(f\"\\n➡️ Clicking job card #{idx + 1}\")\n",
    "            driver.execute_script(\"arguments[0].scrollIntoView(true);\", card)\n",
    "            card.click()\n",
    "\n",
    "            WebDriverWait(driver, 10).until(\n",
    "                EC.presence_of_element_located(\n",
    "                    (By.CLASS_NAME, \"job-details-jobs-unified-top-card__company-name\"))\n",
    "            )\n",
    "            time.sleep(2)\n",
    "\n",
    "            data = extract_job_details(driver)  # Your extraction function\n",
    "            job_data_list.append(data)\n",
    "            print(f\"✅ Extracted: {data.get('Job Title')} at {data.get('Company')}\")\n",
    "\n",
    "            processed_ids.add(job_id)\n",
    "\n",
    "        except Exception as e:\n",
    "            print(f\"❌ Failed to process job card #{idx + 1}: {e}\")\n",
    "            continue\n",
    "\n",
    "    return job_data_list\n",
    "\n",
    "\n",
    "\n",
    "def scrape_all_pages(driver, max_pages=2):\n",
    "    all_job_data = []\n",
    "\n",
    "    for page_num in range(1, max_pages + 1):\n",
    "        print(f\"\\n📄 Scraping Page {page_num}...\\n\")\n",
    "\n",
    "        try:\n",
    "            WebDriverWait(driver, 15).until(\n",
    "                EC.presence_of_element_located((By.XPATH, \"//li[contains(@class, 'job-card-container')]\"))\n",
    "            )\n",
    "        except Exception as e:\n",
    "            print(f\"⚠️ Job cards not found on page {page_num}: {e}\")\n",
    "            continue\n",
    "\n",
    "        page_data = process_jobs(driver)\n",
    "        all_job_data.extend(page_data)\n",
    "\n",
    "        if page_num < max_pages:\n",
    "            try:\n",
    "                next_btn = driver.find_element(By.XPATH, f\"//li[@data-test-pagination-page-btn='{page_num + 1}']/button\")\n",
    "                driver.execute_script(\"arguments[0].scrollIntoView(true);\", next_btn)\n",
    "                time.sleep(1)\n",
    "                next_btn.click()\n",
    "\n",
    "                WebDriverWait(driver, 15).until(\n",
    "                    EC.text_to_be_present_in_element(\n",
    "                        (By.XPATH, \"//li[contains(@class, 'artdeco-pagination__indicator--number active')]/button/span\"),\n",
    "                        str(page_num + 1)\n",
    "                    )\n",
    "                )\n",
    "                time.sleep(2)\n",
    "            except Exception as e:\n",
    "                print(f\"⚠️ Could not navigate to page {page_num + 1}: {e}\")\n",
    "                break\n",
    "\n",
    "    return all_job_data\n",
    "\n",
    "\n",
    "# Step 1: Scrape all 5 pages\n",
    "final_data = scrape_all_pages(driver, max_pages=max_pages)\n",
    "\n",
    "# Step 2: Convert to DataFrame\n",
    "df = pd.DataFrame(final_data)\n",
    "\n",
    "# Step 3: Save to CSV\n",
    "df.to_csv(\"linkedin_jobs.csv\", index=False)\n",
    "print(\"📁 File saved: linkedin_jobs.csv\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3 (ipykernel)",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.11.7"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}

