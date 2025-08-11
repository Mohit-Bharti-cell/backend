from fastapi import APIRouter, HTTPException
from schemas.test_schemas import TestRequest, TestFinalizeRequest
from services.test_generator import generate_questions
from db.supabase import supabase
from uuid import uuid4
from typing import List
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/generate-test")
async def create_test(request: TestRequest):
    # Generate questions using LLM
    questions = await generate_questions(request)
    return {"questions": questions}

@router.post("/finalize-test")
async def finalize_test(request: TestFinalizeRequest):
    question_set_id = str(uuid4())
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(hours=2)

    # Insert into question_sets with duration
    supabase.table("question_sets").insert({
        "id": question_set_id,
        "jd_id": request.jd_id,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "duration": request.duration  # Add duration field
    }).execute()

    # Insert questions linked to this set
    for q in request.questions:
        supabase.table("questions").insert({
            "question_set_id": question_set_id,
            "jd_id": request.jd_id,
            "question": q.question,        # ✅ Access attributes
            "options": q.options,          # ✅ Might be None
            "answer": q.answer,            # ✅ Optional
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat()
        }).execute()

    test_link = f"http://localhost:5173/test/{question_set_id}"
    return {
        "test_link": test_link,
        "test_id": question_set_id,
        "jd_id": request.jd_id,
        "duration": request.duration,
        "message": "Test finalized successfully"
    }

@router.get("/tests")
async def get_all_tests():
    """Get all tests created by HR with their basic info"""
    try:
        # Fetch all question sets with basic info
        result = supabase.table("question_sets").select("id, created_at, expires_at, duration").order("created_at", desc=True).execute()
        
        tests = []
        for test in result.data:
            # Get question count for each test
            questions_result = supabase.table("questions").select("id", count="exact").eq("question_set_id", test["id"]).execute()
            question_count = questions_result.count or 0
            
            # Get submission count for each test
            submissions_result = supabase.table("test_results").select("id", count="exact").eq("question_set_id", test["id"]).execute()
            submission_count = submissions_result.count or 0
            
            # Check if test is still active
            expires_at = datetime.fromisoformat(test["expires_at"])
            is_active = datetime.utcnow() < expires_at
            
            tests.append({
                "test_id": test["id"],
                "duration": test.get("duration", 20),
                "question_count": question_count,
                "submission_count": submission_count,
                "created_at": test["created_at"],
                "expires_at": test["expires_at"],
                "is_active": is_active,
                "test_link": f"http://localhost:5173/test/{test['id']}"
            })
        
        return {
            "tests": tests,
            "total_tests": len(tests)
        }
        
    except Exception as e:
        print(f"❌ Error fetching tests: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch tests: {str(e)}")

@router.get("/tests/{test_id}/results")
async def get_test_results(test_id: str):
    """Get all submissions/results for a specific test"""
    try:
        # Fetch test results for the specific test
        result = supabase.table("test_results").select("*").eq("question_set_id", test_id).order("created_at", desc=True).execute()
        
        # Also get test info
        test_info = supabase.table("question_sets").select("duration").eq("id", test_id).execute()
        test_duration = test_info.data[0]["duration"] if test_info.data else 20
        
        results = []
        for res in result.data:
            results.append({
                "result_id": res["id"],
                "score": res["score"],
                "max_score": res["max_score"],
                "percentage": res["percentage"],
                "status": res["status"],
                "duration_used_minutes": res.get("duration_used_minutes"),
                "duration_used_seconds": res.get("duration_used_seconds"),
                "submitted_at": res["created_at"],
                "raw_feedback": res.get("raw_feedback", "")
            })
        
        return {
            "test_id": test_id,
            "test_duration": test_duration,
            "results": results,
            "total_submissions": len(results),
            "average_score": sum(r["score"] for r in results) / len(results) if results else 0,
            "average_time_used": sum(r["duration_used_minutes"] for r in results if r["duration_used_minutes"]) / len([r for r in results if r["duration_used_minutes"]]) if any(r["duration_used_minutes"] for r in results) else None
        }
        
    except Exception as e:
        print(f"❌ Error fetching test results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch test results: {str(e)}")

@router.delete("/tests/{test_id}")
async def delete_test(test_id: str):
    """Delete a test and all its associated data"""
    try:
        # Delete in order: test_results -> questions -> question_sets
        
        # Delete test results
        supabase.table("test_results").delete().eq("question_set_id", test_id).execute()
        
        # Delete questions
        supabase.table("questions").delete().eq("question_set_id", test_id).execute()
        
        # Delete question set
        result = supabase.table("question_sets").delete().eq("id", test_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Test not found")
        
        return {
            "message": "Test deleted successfully",
            "test_id": test_id
        }
        
    except Exception as e:
        print(f"❌ Error deleting test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete test: {str(e)}")

@router.put("/tests/{test_id}/extend")
async def extend_test_expiry(test_id: str, hours: int = 24):
    """Extend the expiry time of a test"""
    try:
        new_expires_at = datetime.utcnow() + timedelta(hours=hours)
        
        result = supabase.table("question_sets").update({
            "expires_at": new_expires_at.isoformat()
        }).eq("id", test_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Test not found")
        
        return {
            "message": f"Test expiry extended by {hours} hours",
            "test_id": test_id,
            "new_expires_at": new_expires_at.isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error extending test expiry: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to extend test expiry: {str(e)}")


@router.get("/questions/{jd_id}")
async def get_questions_by_jd(jd_id: str):
    try:
        # ✅ Fetch questions from Supabase by jd_id
        response = supabase.table("questions").select("*").eq("jd_id", jd_id).execute()
 
        if not response.data:
            raise HTTPException(status_code=404, detail="No questions found for this jd_id")
 
        return {
            "jd_id": jd_id,
            "total_questions": len(response.data),
            "questions": response.data
        }
 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))