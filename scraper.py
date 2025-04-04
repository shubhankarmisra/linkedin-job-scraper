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
