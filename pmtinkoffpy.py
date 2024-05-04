#!/usr/bin/python3

import payment
import billmgr.db
import billmgr.exception

import billmgr.logger as logging

import xml.etree.ElementTree as ET

from tinkoffapi import Termianl
from tinkoffapi import TERMINAL_ACCES_ERORS

MODULE = 'pmtinkoffpy'
logging.init_logging(MODULE)
logger = logging.get_logger(MODULE)

class TinkoffPaymentModule(payment.PaymentModule):
    def __init__(self):
        super().__init__()

        self.features[payment.FEATURE_CHECKPAY] = True
        self.features[payment.FEATURE_REDIRECT] = True
        self.features[payment.FEATURE_NOT_PROFILE] = True
        self.features[payment.FEATURE_PMVALIDATE] = True
        self.features[payment.FEATURE_REFUND] = True
        self.features[payment.FEATURE_RFSET] = True

        self.params[payment.PAYMENT_PARAM_PAYMENT_SCRIPT] = "/mancgi/tinkoffpypayment"


    def PM_Validate(self, xml : ET.ElementTree):
        logger.info("run pmvalidate")
        #logger.info(f"xml input: {ET.tostring(xml.getroot(), encoding='unicode')}")

        currency_node = xml.find('./paymethod/currency')
        minamount_node = xml.find('./paymethod/minamount')
        psw_node= xml.find('./terminalpsw')
        key_node= xml.find('./terminalkey')

        currency = currency_node.text if currency_node is not None else ''
        minamount= minamount_node.text if minamount_node is not None else ''
        psw = psw_node.text if psw_node is not None else ''
        key = key_node.text if key_node is not None else ''
        terminal = Termianl(key, psw)

        if float(minamount) < 1:
            raise billmgr.exception.XmlException('msg_error_too_small_min_amount')

        #126 - рубли
        if currency != "126":
            raise billmgr.exception.XmlException('msg_error_only_support_rubles')
        

        terminal.init_deal("1000","TinkoffBankTest")

        

    
    def RF_Set(self, xml: ET.ElementTree):
        try:
            xml = xml.getroot()

            elid_node = xml.find('./source_payment')
            amount_node = xml.find('./payment_paymethodamount')

            amount = amount_node.text if amount_node is not None else ''
            elid = elid_node.text if elid_node is not None else ''
            logger.info(f"start refund for payment {elid}")
            pm = billmgr.db.db_query(f'''
            SELECT pm.xmlparams, p.externalid FROM paymethod pm, payment p
            WHERE pm.module = 'pmtinkoffpy' AND p.id = %s AND p.paymethod = pm.id
            ''', elid)

            xml1 = ET.fromstring(pm[0]['xmlparams'])
            psw_node= xml1.find('./terminalpsw')
            key_node= xml1.find('./terminalkey')

            psw = psw_node.text if psw_node is not None else ''
            key = key_node.text if key_node is not None else ''

            terminal = Termianl(key, psw)
            obj = terminal.get_state_deal(pm[0]['externalid'])
            if(not (obj["Status"] == 'CONFIRMED' or obj["Status"] == 'AUTHORIZED' or obj["Status"] == "PARTIAL_REFUNDED")):
                raise NotImplemented
            terminal.cancel_deal(pm[0]['externalid'],str(int(float(amount)*-100)))
            logger.info("refunded")
        except Exception as ex:
            logger.info(ex)
            raise NotImplemented

        
        
    # в тестовом примере получаем необходимые платежи
    # и переводим их все в статус 'оплачен'
    def CheckPay(self):
        logger.info("run checkpay")
        
        # получаем список платежей в статусе оплачивается
        # и которые используют обработчик pmtestpayment
        payments = billmgr.db.db_query(f'''
            SELECT p.id, p.externalid, p.createdate ,pm.xmlparams FROM payment p, paymethod pm
            WHERE pm.module = 'pmtinkoffpy' AND p.status = {payment.PaymentStatus.INPAY.value} AND p.paymethod = pm.id AND DATE(p.createdate) BETWEEN DATE(CURRENT_DATE() - INTERVAL 1 MINUTE) AND CURRENT_DATE()
        ''')
        logger.info(payments)
        for p in payments:
            logger.info(f"change status for payment {p['id']}")
            xml = ET.fromstring(p['xmlparams'])
            psw_node= xml.find('./terminalpsw')
            key_node= xml.find('./terminalkey')
            psw = psw_node.text if psw_node is not None else ''
            key = key_node.text if key_node is not None else ''
            terminal = Termianl(key, psw)
            obj = terminal.get_state_deal(p["externalid"])
            logger.info(p["externalid"])
            status = obj["Status"]
            if status == "CONFIRMED":
                payment.set_paid(p['id'], '', p['externalid'])
            elif status ==  "REJECTED" or status == "DEADLINE_EXPIRED":
                payment.set_canceled(p['id'], '', p['externalid'])
                raise billmgr.exception.XmlException('msg_error_status_rejected')
            elif status == "AUTHORIZED":
                obj = terminal.confirm_deal(p['externalid'])
                if obj["Status"] == "true":
                    logger.info(f"confirm authorized payment id: {p['id']}")
            else:
                continue
            




            


TinkoffPaymentModule().Process()
