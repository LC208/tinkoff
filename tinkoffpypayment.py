#!/usr/bin/python3

import payment
import sys

import billmgr.logger as logging
import billmgr

from payment import Termianl



MODULE = 'payment'
logging.init_logging('tinkoffpypayment')
logger = logging.get_logger('tinkoffpypayment')

class TinkoffPaymentCgi(payment.PaymentCgi):

    def Process(self):
        # необходимые данные достаем из self.payment_params, self.paymethod_params, self.user_params
        # здесь для примера выводим параметры метода оплаты (self.paymethod_params) и платежа (self.payment_params) в лог
        logger.info(f"procces pay")
        terminal = Termianl(self.paymethod_params["terminalkey"] ,self.paymethod_params["terminalpsw"] )

        fail_form =  "<html>\n"
        fail_form += "<head><meta http-equiv='Content-Type' content='text/html; charset=UTF-8'>\n"
        fail_form += "<link rel='shortcut icon' href='billmgr.ico' type='image/x-icon' />"
        fail_form += "	<script language='JavaScript'>\n"
        fail_form += "		function DoSubmit() {\n"
        fail_form += "			window.location.assign('" + self.fail_page + "');\n"
        fail_form += "		}\n"
        fail_form += "	</script>\n"
        fail_form += "</head>\n"
        fail_form += "<body onload='DoSubmit()'>\n"
        fail_form += "</body>\n"
        fail_form += "</html>\n"
        try:
            obj = terminal.init_deal(str(int(float(self.payment_params["paymethodamount"])*100)), f"external_{self.elid}",self.success_page,self.fail_page)
            logger.info(str(int(float(self.payment_params["paymethodamount"])*100)))
            redirect_url = obj["PaymentURL"]
        except Exception as err:
            logger.error(err.args)
            sys.stdout.write(fail_form)
            payment.set_canceled(self.elid, f'{obj["Message"]}, {obj["Details"]}',  '')
        logger.info(f"set in pay")
        payment.set_in_pay(self.elid,'',obj["PaymentId"])

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