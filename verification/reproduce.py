def reproduce(function) -> dict:
    try:
        function(0)
        return {"status": "PASS", "message": "The invalid reproduction did not fail."}
    except ValueError as error:
        return {"status": "FAIL", "message": str(error)}