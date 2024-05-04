#!/usr/bin/python3

import billmgr.exception
import payment
import sys

import billmgr.logger as logging
import billmgr

from tinkoffapi import Termianl

from jinja2 import Environment,FileSystemLoader,select_autoescape



MODULE = 'tinkoffpypayment'
logging.init_logging(MODULE)
logger = logging.get_logger(MODULE)

env = Environment(
    loader=FileSystemLoader('.'),
    autoescape=select_autoescape(['html'])
)
template = env.get_template('template.html')

class TinkoffPaymentCgi(payment.PaymentCgi):

    def Process(self):
        # необходимые данные достаем из self.payment_params, self.paymethod_params, self.user_params
        # здесь для примера выводим параметры метода оплаты (self.paymethod_params) и платежа (self.payment_params) в лог
        logger.info(f"procces pay")
        terminal = Termianl(self.paymethod_params["terminalkey"] ,self.paymethod_params["terminalpsw"] )
        fail_form = template.render(url=self.fail_page)
        try:
            obj = terminal.init_deal(str(int(float(self.payment_params["paymethodamount"])*100)), f"external_{self.elid}",self.success_page,self.fail_page)
            redirect_url = obj["PaymentURL"]
            logger.info(f"set in pay")
            payment.set_in_pay(self.elid,'',obj["PaymentId"])
        except billmgr.exception.XmlException as ex:
            logger.error(ex.err_type)
            if(ex.err_type == 'msg_error_payment_fraud'):
                payment.set_fraud(self.elid, f'{obj["Message"]}, {obj["Details"]}',  '')
            sys.stdout.write(fail_form)
        except Exception as err:
            logger.error(err.args)
            sys.stdout.write(fail_form)
        payment_form = template.render(url=redirect_url)
        sys.stdout.write(payment_form)


TinkoffPaymentCgi().Process()