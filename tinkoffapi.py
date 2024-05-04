import requests
import hashlib
import json
import billmgr.exception
import billmgr.logger as logging

MODULE = 'tinkoffapi'
logging.init_logging(MODULE)
logger = logging.get_logger(MODULE)
TERMINAL_ACCES_ERORS = ('60','66','202','205','331','501')

TINKOFF_URL = "https://securepay.tinkoff.ru/v2/"
GET_STATE = "GetState"
INIT = "Init"
CONFIRM = "Confirm"
CHECKORDER = "CheckOrder"
CANCEL = "Cancel"
ADDCUSTOMER = "AddCustomer"

class Termianl:

    def __init__(self, terminalkey, terminalpsw):
        self.terminalkey = terminalkey
        self.terminalpsw = terminalpsw
        self.BASE_URL = TINKOFF_URL

    def init_deal(self,amount, elid,success_page="", fail_page=""):
        data = {"TerminalKey": self.terminalkey, "OrderId": elid, "Amount": amount}
        obj = self._send_request('POST', INIT, data,{"SuccessURL":success_page, "FailURL" : fail_page})
        try:
            obj["PaymentURL"]
        except:
            raise billmgr.exception.XmlException('msg_error_no_url_provided')
        try:
            obj["PaymentId"]
        except:
            raise billmgr.exception.XmlException('msg_error_no_payment_id_provided')
        return obj

    def _send_request(self,method,command, main_param ={}, additional_param={}):
        self._generate_token(main_param)
        main_param["Token"] = self.token
        resp = requests.request(method=method,url=f"{self.BASE_URL}{command}",json=dict(list(main_param.items()) + list(additional_param.items())),headers={"Content-Type":"application/json"})
        if resp.status_code == 503:
            logger.info(1)
            logger.info(obj)
            raise billmgr.exception.XmlException('msg_error_repeat_again')
        try:
            obj = json.loads(resp.content.decode("UTF-8"))
        except:
            logger.info(2)
            logger.info(obj)
            raise billmgr.exception.XmlException('msg_error_json_parsing_error')
        if obj["ErrorCode"] in TERMINAL_ACCES_ERORS:
            logger.info(3)
            logger.info(obj)
            raise billmgr.exception.XmlException('msg_error_wrong_terminal_info')
        if obj["ErrorCode"] == "3003":
            logger.info(4)
            logger.info(obj)
            raise billmgr.exception.XmlException('msg_error_payment_fraud')
        if obj["ErrorCode"] != "0":
            logger.info(obj)
            raise billmgr.exception.XmlException('msg_error_unknown_error')
        return obj

    def _generate_token(self, data):
        data = data.copy()
        data["Password"]=self.terminalpsw
        data = dict(sorted(data.items()))
        self.token = hashlib.sha256("".join(data.values()).encode("UTF-8")).hexdigest()
    
    def cancel_deal(self, payment_id, amount):
        data = {"TerminalKey": self.terminalkey, "PaymentId": payment_id,"Amount" : amount}
        return self._send_request('POST', CANCEL, data)

    def check_order(self, elid):
        data = {"TerminalKey": self.terminalkey, "OrderId": elid}
        return self._send_request('POST', CHECKORDER, data)

    def confirm_deal(self, payment_id):
        data = {"TerminalKey": self.terminalkey, "PaymentId": payment_id}
        return self._send_request('POST', CONFIRM, data)

    def add_customer(self, customer_id):
        data = {"TerminalKey": self.terminalkey, "CustomerKey": customer_id}
        return self._send_request('POST', ADDCUSTOMER, data)

    def get_state_deal(self, payment_id):
        data = {"TerminalKey": self.terminalkey, "PaymentId": payment_id}
        return self._send_request('POST', GET_STATE, data)