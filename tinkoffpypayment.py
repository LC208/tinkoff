#!/usr/bin/python3

import payment
import sys

import billmgr.logger as logging
import billmgr
import json
import requests
import hashlib


MODULE = 'payment'
logging.init_logging('tinkoffpypayment')
logger = logging.get_logger('tinkoffpypayment')



class TinkoffPaymentCgi(payment.PaymentCgi):

    def Process(self):
        # необходимые данные достаем из self.payment_params, self.paymethod_params, self.user_params
        # здесь для примера выводим параметры метода оплаты (self.paymethod_params) и платежа (self.payment_params) в лог
        logger.info(f"procces pay")
        request_body={}
        request_body["TerminalKey"] = self.paymethod_params["terminalkey"] 
        request_body["Amount"]  =  self.payment_params["paymethodamount"]
        request_body["OrderId"] = f"external_{self.elid}"
        request_body["Description"] =  self.payment_params["description"]
        request_body["Token"] = hashlib.sha256(payment.get_token(request_body, self.paymethod_params['terminalpsw']).encode("UTF-8")).hexdigest()
        request_body["SuccessURL"] = self.success_page
        request_body["FailURL"] = self.fail_page
        headers = {"Content-Type":"application/json"}
        resp = requests.post(url="https://securepay.tinkoff.ru/v2/Init",json=request_body,headers=headers)
        if resp.status_code == 503:
            raise billmgr.exception.XmlException('msg_error_repeat_again')
        
        try: 
            obj = json.loads(resp.content.decode("UTF-8"))
        except:
            raise billmgr.exception.XmlException('msg_error_json_parsing_error')
        
        try:
            redirect_url = obj["PaymentURL"]
        except:
            payment.set_canceled(self.elid,"", f"external_{self.elid}")
            raise billmgr.exception.XmlException('msg_error_no_url_provided')
        
        try:
            payment.set_in_pay(self.elid, '',  obj["PaymentId"])
        except:
             raise billmgr.exception.XmlException('msg_error_no_payment_id_provided')
        
        logger.info(f"set in pay")

        payment_form =  "<html>\n"
        payment_form += "<head><meta http-equiv='Content-Type' content='text/html; charset=UTF-8'>\n"
        payment_form += "<link rel='shortcut icon' href='billmgr.ico' type='image/x-icon' />"
        payment_form += "	<script language='JavaScript'>\n"
        payment_form += "		function DoSubmit() {\n"
        payment_form += "			window.location.assign('" + redirect_url + "');\n"
        payment_form += "		}\n"
        payment_form += "	</script>\n"
        payment_form += "</head>\n"
        payment_form += "<body onload='DoSubmit()'>\n"
        payment_form += "</body>\n"
        payment_form += "</html>\n"

        sys.stdout.write(payment_form)


TinkoffPaymentCgi().Process()