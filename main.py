import os
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import scraper
import pandas as pd

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for Streamlit frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to your Streamlit domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define request body schema
class ScrapeRequest(BaseModel):
    url: str
    pages: int

# Scrape endpoint
@app.post("/scrape")
def run_scraper(req: ScrapeRequest):
    df = scraper.scrape_and_save(req.url, req.pages)
    df = df.fillna("")  # Clean NaNs for JSON safety
    df.to_csv("linkedin_jobs.csv", index=False)  # Save for Streamlit UI to read if needed
    return {"message": "Scraping complete", "results": df.to_dict(orient="records")}

# Needed when running locally
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
