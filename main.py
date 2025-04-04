import os
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import scraper
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow requests from any origin (for Streamlit to access this backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    url: str
    pages: int

@app.post("/scrape")
def run_scraper(req: ScrapeRequest):
    df = scraper.scrape_and_save(req.url, req.pages)
    df = df.fillna("")
    df.to_csv("linkedin_jobs.csv", index=False)  # Save CSV for Streamlit to read
    return {"message": "Scraping done", "results": df.to_dict(orient="records")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

