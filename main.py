from fastapi import FastAPI
from pydantic import BaseModel
import scraper
import pandas as pd

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str
    pages: int

@app.post("/scrape")
def run_scraper(req: ScrapeRequest):
    df = scraper.scrape_and_save(req.url, req.pages)
    df = df.fillna("")  # ensure no NaNs for JSON
    return {"message": "Scraping done", "results": df.to_dict(orient="records")}
