def load_served(url, signature_json):
    import json
    import urllib.request

    signature = json.loads(signature_json)

    def predict(inputs):
        request = {
            "inputs": [
                {"name": entry["name"], "shape": [len(inputs[entry["name"]])], "datatype": entry["datatype"], "data": inputs[entry["name"]]} for entry in signature["inputs"] if entry["name"] in inputs
            ]
        }
        http_request = urllib.request.Request(url, data=json.dumps(request).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(http_request, timeout=30) as response:
            return {output["name"]: output["data"] for output in json.load(response)["outputs"]}

    return predict
