#!/usr/bin/python3

import payment
import billmgr.db
import billmgr.exception

import billmgr.logger as logging

import xml.etree.ElementTree as ET

import json
import requests
import hashlib

MODULE = 'payment'
logging.init_logging('pmtinkoffpy')
logger = logging.get_logger('pmtinkoffpy')

class TinkoffPaymentModule(payment.PaymentModule):
    def __init__(self):
        super().__init__()

        self.features[payment.FEATURE_CHECKPAY] = True
        self.features[payment.FEATURE_REDIRECT] = True
        self.features[payment.FEATURE_NOT_PROFILE] = True
        self.features[payment.FEATURE_PMVALIDATE] = True

        self.params[payment.PAYMENT_PARAM_PAYMENT_SCRIPT] = "/mancgi/tinkoffpypayment"


    # в тестовом примере валидация проходит успешно, если
    # Идентификатор терминала = rick, пароль терминала = morty
    def PM_Validate(self, xml : ET.ElementTree):
        logger.info("run pmvalidate")

        # мы всегда можем вывести xml в лог, чтобы изучить, что приходит :)
        logger.info(f"xml input: {ET.tostring(xml.getroot(), encoding='unicode')}")

        #terminalkey_node = xml.find('./terminalkey')
        #terminalpsw_node = xml.find('./terminalpsw')
        #terminalkey = terminalkey_node.text if terminalkey_node is not None else ''
        #terminalpsw = terminalpsw_node.text if terminalpsw_node is not None else ''



    # в тестовом примере получаем необходимые платежи
    # и переводим их все в статус 'оплачен'
    def CheckPay(self):
        logger.info("run checkpay")

        # получаем список платежей в статусе оплачивается
        # и которые используют обработчик pmtestpayment
        payments = billmgr.db.db_query(f'''
            SELECT p.id FROM payment p
            JOIN paymethod pm
            WHERE module = 'pmtinkoffpy' AND p.status = {payment.PaymentStatus.INPAY.value}
        ''')

        for p in payments:
            logger.info(f"change status for payment {p['id']}")
            request_body={}
            request_body["TerminalKey"] = "TinkoffBankTest"
            request_body["PaymentId"] = f"external_{p['id']}"
            request_body["Token"] = hashlib.sha256(payment.get_token(request_body, "TinkoffBankTest").encode("UTF-8")).hexdigest()
            headers = {"Content-Type":"application/json"}
            resp = requests.post(url="https://securepay.tinkoff.ru/v2/GetState",json=request_body,headers=headers)
            if resp.status_code == 503:
                raise billmgr.exception.XmlException('msg_error_repeat_again')
            try: 
                obj = json.loads(resp.content.decode("UTF-8"))
                logger.info(obj)
                status = obj["Status"]
                if status == "CONFIRMED":
                    payment.set_paid(p['id'], '', f"external_{p['id']}")
                elif status ==  "СANCELED":
                    payment.set_canceled(p['id'], '', f"external_{p['id']}")
                elif status ==  "REJECTED":
                    payment.set_canceled(p['id'], '', f"external_{p['id']}")
                else:
                    continue
            except:
                raise billmgr.exception.XmlException('msg_error_json_parsing_error')
            




            


TinkoffPaymentModule().Process()
