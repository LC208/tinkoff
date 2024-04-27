import hashlib
import requests
import json

def get_token(request, pswd):
    token_body = request.copy()
    token_body["Password"]=pswd
    token_body = dict(sorted(token_body.items()))
    token = ""
    for v in [*token_body.values()]:
        token+=v
    return token

request_body={}
request_body["TerminalKey"] = "TinkoffBankTest"
request_body["Amount"]  =  "112321"
request_body["OrderId"] = "elid=1"
request_body["Description"] =  "dassda"
request_body["Token"] = hashlib.sha256(get_token(request_body, "TinkoffBankTest").encode("UTF-8")).hexdigest()
headers = {"Content-Type":"application/json"}
resp = requests.post(url="https://securepay.tinkoff.ru/v2/Init",json=request_body,headers=headers)
obj = json.loads(resp.content.decode("UTF-8"))
print(obj)
try:
    print(obj["PaymentURL"])
except:
    print("err")
    #raise billmgr.exception.XmlException('msg_error_no_url_provided')