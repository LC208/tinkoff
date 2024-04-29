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


    def PM_Validate(self, xml : ET.ElementTree):
        logger.info("run pmvalidate")
        logger.info(f"xml input: {ET.tostring(xml.getroot(), encoding='unicode')}")

        currency_node = xml.find('./paymethod/currency')
        minamount_node = xml.find('./paymethod/minamount')
        commissionamount_node = xml.find('./paymethod/commissionamount')
        commissionpercent_node = xml.find('./paymethod/commissionpercent')
        recurring_node= xml.find('./paymethod/recurring')

        currency = currency_node.text if currency_node is not None else ''
        minamount= minamount_node.text if minamount_node is not None else ''
        commissionamount= commissionamount_node.text if commissionamount_node is not None else ''
        commissionpercent= commissionpercent_node.text if commissionpercent_node is not None else ''
        recurring= recurring_node.text if recurring_node is not None else ''
        
        if float(minamount) < 1:
            raise billmgr.exception.XmlException('msg_error_too_small_min_amount')

        if currency != "126":
            raise billmgr.exception.XmlException('msg_error_only_support_rubles')
        
        if float(commissionamount) > 0:
            raise NotImplemented
        
        if float(commissionpercent) > 0:
            raise NotImplemented
        
        if recurring != 'off':
            raise NotImplemented



    # в тестовом примере получаем необходимые платежи
    # и переводим их все в статус 'оплачен'
    def CheckPay(self):
        logger.info("run checkpay")

        # получаем список платежей в статусе оплачивается
        # и которые используют обработчик pmtestpayment
        payments = billmgr.db.db_query(f'''
            SELECT p.id, p.externalid FROM payment p
            JOIN paymethod pm
            WHERE module = 'pmtinkoffpy' AND p.status = {payment.PaymentStatus.INPAY.value}
        ''')

        for p in payments:
            logger.info(f"change status for payment {p['id']}")
            request_body={}
            request_body["TerminalKey"] = "TinkoffBankTest"
            request_body["PaymentId"] = p["externalid"]
            request_body["Token"] = hashlib.sha256(payment.get_token(request_body, "TinkoffBankTest").encode("UTF-8")).hexdigest()
            headers = {"Content-Type":"application/json"}
            resp = requests.post(url="https://securepay.tinkoff.ru/v2/GetState",json=request_body,headers=headers)
            if resp.status_code == 503:
                raise billmgr.exception.XmlException('msg_error_repeat_again')
            try: 
                obj = json.loads(resp.content.decode("UTF-8"))
                status = obj["Status"]
                if status == "CONFIRMED":
                    payment.set_paid(p['id'], '', p['externalid'])
                elif status ==  "REJECTED":
                    payment.set_canceled(p['id'], '', p['externalid'])
                    raise billmgr.exception.XmlException('msg_error_status_rejected')
                elif status == "AUTHORIZED":
                    resp = requests.post(url="https://securepay.tinkoff.ru/v2/Confirm",json=request_body,headers=headers)
                    obj = json.loads(resp.content.decode("UTF-8"))
                    if obj["Status"] == "true":
                        logger.info(f"confirm authorized payment id: {p['id']}")
                else:
                    continue
            except:
                raise billmgr.exception.XmlException('msg_error_json_parsing_error')
            




            


TinkoffPaymentModule().Process()
