import os
import httpx
import re
from schemas.test_schemas import TestSubmission
from dotenv import load_dotenv

load_dotenv()

async def evaluate_test(submission: TestSubmission):
    # Enhanced prompt with clearer instructions
    prompt = (
        "You are an expert HR evaluator tasked with scoring a candidate's test submission.\n\n"
        "Each question is either:\n"
        "  • An MCQ (Multiple Choice Question) with predefined options and one correct answer.\n"
        "  • A Coding Problem requiring code-based solutions.\n\n"
        "Scoring Instructions:\n"
        "1. **MCQ Questions**:\n"
        "   - If the candidate's answer exactly matches the correct option, award **10/10**.\n"
        "   - If it does not match, award **0/10**. No partial marks.\n"
        "2. **Coding Questions**:\n"
        "   - Evaluate based on: **Correctness, Logic, Efficiency, and Code Quality**.\n"
        "   - Use the following rough rubric:\n"
        "       - 10/10: Fully correct, optimal logic, clean code.\n"
        "       - 8/10: Correct output, minor inefficiencies or style issues.\n"
        "       - 6/10: Mostly correct, but logic can be improved.\n"
        "       - 4/10: Partially working code, poor logic or structure.\n"
        "       - 2/10 or 0/10: Wrong, incomplete, or irrelevant code.\n\n"
        "**You MUST follow this exact output format**:\n"
        "Q1 - Type: MCQ - Score: X/10\n"
        "Q2 - Type: Coding - Score: X/10\n"
        "...\n\n"
        "At the end, provide ONLY:\n"
        "TOTAL SCORE: X/Y\n"
        "STATUS: Pass (if X >= 50% of Y) or Fail\n\n"
        f"Number of Questions: {len(submission.questions)}\n"
        f"Maximum Possible Score: {len(submission.questions) * 10}\n\n"
        "Evaluate the following Questions and Answers:\n"
    )

    
    # Add each question and answer pair with clear formatting
    for i, (question, answer) in enumerate(zip(submission.questions, submission.answers), 1):
        # Handle Question object (Pydantic model)
        question_text = question.question
        options = question.options or []
        
        prompt += f"\nQ{i}: {question_text}\n"
        if options and len(options) > 0:
            prompt += f"Options: {', '.join(options)}\n"
            prompt += f"Type: MCQ\n"
        else:
            prompt += f"Type: Coding\n"
        
        prompt += f"Candidate's Answer: {answer}\n"
        prompt += "---\n"

    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "HTTP-Referer": "https://your-actual-domain.com",
        "X-Title": "Test Evaluation",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,  # Lower temperature for more consistent scoring
        "max_tokens": 2000
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=60
            )

            if response.status_code != 200:
                error_data = response.json().get("error", {})
                print(f"⚠️ Evaluation API error: {response.status_code} - {error_data.get('message', 'Unknown error')}")
                return {
                    "score": 0, 
                    "max_score": len(submission.questions) * 10, 
                    "status": "Evaluation failed", 
                    "raw_feedback": f"API Error: {error_data.get('message', 'Unknown error')}"
                }

            content = response.json()["choices"][0]["message"]["content"]
            print("📬 Raw model output:\n", content)

            # Enhanced score extraction with multiple patterns
            score, max_score = extract_score_from_response(content, len(submission.questions))
            
            # Calculate percentage and determine status
            percentage = (score / max_score * 100) if max_score > 0 else 0
            status = "Pass" if percentage >= 50 else "Fail"
            
            print(f"📊 Extracted Score: {score}/{max_score} ({percentage:.1f}%) - Status: {status}")

            return {
                "score": score,
                "max_score": max_score,
                "percentage": percentage,
                "status": status,
                "raw_feedback": content
            }

    except httpx.RequestError as e:
        print(f"❌ HTTP error during evaluation: {e}")
        return {
            "score": 0, 
            "max_score": len(submission.questions) * 10, 
            "status": "Network error", 
            "raw_feedback": f"HTTP Error: {str(e)}"
        }

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {
            "score": 0, 
            "max_score": len(submission.questions) * 10, 
            "status": "Internal error", 
            "raw_feedback": f"Internal Error: {str(e)}"
        }


def extract_score_from_response(content: str, num_questions: int) -> tuple[int, int]:
    """
    Extract score from LLM response using multiple parsing strategies
    Returns: (score, max_score)
    """
    max_score = num_questions * 10
    
    print(f"🔍 Attempting to extract score from response (expected max: {max_score})")
    
    # Strategy 1: Look for "TOTAL SCORE: X/Y" pattern
    total_patterns = [
        r"TOTAL SCORE:\s*(\d+)/(\d+)",
        r"TOTAL SCORE:\s*(\d+)\s*/\s*(\d+)",
        r"Total Score:\s*(\d+)/(\d+)",
        r"Total:\s*(\d+)/(\d+)"
    ]
    
    for pattern in total_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            extracted_max = int(match.group(2))
            print(f"✅ Found total score pattern '{pattern}': {score}/{extracted_max}")
            return score, extracted_max

    # Strategy 2: Sum individual question scores
    question_patterns = [
        r"Q(\d+).*?Score:\s*(\d+)/10",
        r"Question\s*(\d+).*?Score:\s*(\d+)/10",
        r"Q(\d+).*?(\d+)/10"
    ]
    
    for pattern in question_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
        if matches and len(matches) == num_questions:
            total_score = sum(int(match[1]) for match in matches)
            print(f"✅ Calculated from individual scores using pattern '{pattern}': {[match[1] for match in matches]} = {total_score}/{max_score}")
            return total_score, max_score

    # Strategy 3: Look for individual scores without question numbers
    score_matches = re.findall(r"Score:\s*(\d+)/10", content, re.IGNORECASE)
    if score_matches and len(score_matches) == num_questions:
        total_score = sum(int(score) for score in score_matches)
        print(f"✅ Calculated from individual scores: {score_matches} = {total_score}/{max_score}")
        return total_score, max_score

    # Strategy 4: Look for any reasonable X/Y pattern
    all_score_patterns = re.findall(r"(\d+)\s*/\s*(\d+)", content)
    for score_str, max_str in all_score_patterns:
        potential_score = int(score_str)
        potential_max = int(max_str)
        
        # Check if this looks like a reasonable total score
        if potential_max == max_score and 0 <= potential_score <= potential_max:
            print(f"✅ Found reasonable score pattern: {potential_score}/{potential_max}")
            return potential_score, potential_max

    # Strategy 5: Look for status and try to infer
    if "pass" in content.lower():
        # If it says pass, assume at least 50%
        min_pass_score = max_score // 2
        print(f"⚠️ Found 'Pass' status, inferring minimum passing score: {min_pass_score}/{max_score}")
        return min_pass_score, max_score
    
    # Fallback: return 0 if nothing found
    print("❌ Could not extract score from response, defaulting to 0")
    print("📄 Response content for debugging:")
    print(content[:500] + "..." if len(content) > 500 else content)
    return 0, max_score