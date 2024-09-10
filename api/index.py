from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio
from app import main  # Import your existing main function

app = FastAPI()

@app.get("/")
async def root():
    result = await asyncio.to_thread(main)  # Run your main function
    return JSONResponse(content={"message": "Daily update processed", "result": result})