from fastapi import FastAPI, HTTPException
from generator.ventyra_v3 import Markov, CORPUS_TEXT, generate, generate_code, code_hash, TEST_KEY

app = FastAPI(title="Ventyra Generator API")
model = Markov(CORPUS_TEXT)

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "ok",
        "generator": "ready",
        "database": "ok"
    }

@app.post("/api/v1/generate")
def generate_result():
    try:
        code = generate_code()
        hash_hex = code_hash(code, TEST_KEY)
        result = generate(hash_hex, model, trace=False)
        return {
            "success": True,
            "code": code,
            "data": {
                "hash": result["hash"],
                "syntax": result["syntax"],
                "selected_words": result["selected_words"],
                "quote": result["quote"],
                "punctuation_checks": result["punctuation_checks"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
