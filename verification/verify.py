def verify_fix(function) -> dict:
    try:
        result = function(0)
        return {"status": "PASS", "message": result}
    except Exception as error:
        return {"status": "FAIL", "message": str(error)}