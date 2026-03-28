from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
import glob

router = APIRouter()

# Local path for university logos
LOGO_BASE_DIR = r"c:\Users\임현수\Downloads\대학로고"

@router.get("/univ-logo")
async def get_univ_logo(name: str):
    """
    Finds and returns a university logo file from the local downloads directory.
    Searches recursively for 'name.*'.
    """
    if not name:
        raise HTTPException(status_code=400, detail="University name is required")
        
    # Search for files matching the name in any of the subdirectories
    # Extensions could be .png, .jpg, .gif, etc.
    search_pattern = os.path.join(LOGO_BASE_DIR, "**", f"{name}.*")
    matches = glob.glob(search_pattern, recursive=True)
    
    if not matches:
        # Try a substring match if exact full name fails (e.g. "서울대" -> "서울대학교")
        search_pattern_partial = os.path.join(LOGO_BASE_DIR, "**", f"{name}*.*")
        matches = glob.glob(search_pattern_partial, recursive=True)
        
    if not matches:
        raise HTTPException(status_code=404, detail=f"Logo for {name} not found")
        
    # Pick the first match
    file_path = matches[0]
    
    # Check if it's a file
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Found match is not a file")
        
    return FileResponse(file_path)
