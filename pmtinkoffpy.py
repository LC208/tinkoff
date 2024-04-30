#!/usr/bin/python3

import payment
import billmgr.db
import billmgr.exception

import billmgr.logger as logging

import xml.etree.ElementTree as ET

from payment import Termianl

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
        self.features[payment.FEATURE_REFUND] = True
        self.features[payment.FEATURE_RFSET] = True

        self.params[payment.PAYMENT_PARAM_PAYMENT_SCRIPT] = "/mancgi/tinkoffpypayment"


    def PM_Validate(self, xml : ET.ElementTree):
        logger.info("run pmvalidate")
        #logger.info(f"xml input: {ET.tostring(xml.getroot(), encoding='unicode')}")

        currency_node = xml.find('./paymethod/currency')
        minamount_node = xml.find('./paymethod/minamount')
        commissionamount_node = xml.find('./paymethod/commissionamount')
        commissionpercent_node = xml.find('./paymethod/commissionpercent')
        recurring_node= xml.find('./paymethod/recurring')
        #psw_node= xml.find('./terminalpsw')
        #key_node= xml.find('./terminalkey')

        currency = currency_node.text if currency_node is not None else ''
        minamount= minamount_node.text if minamount_node is not None else ''
        commissionamount= commissionamount_node.text if commissionamount_node is not None else ''
        commissionpercent= commissionpercent_node.text if commissionpercent_node is not None else ''
        recurring= recurring_node.text if recurring_node is not None else ''
        #psw = psw_node.text if psw_node is not None else ''
        #key = key_node.text if key_node is not None else ''
        #TERMINAL = Termianl(key, psw)

        if float(minamount) < 1:
            raise billmgr.exception.XmlException('msg_error_too_small_min_amount')

        if currency != "126":
            raise billmgr.exception.XmlException('msg_error_only_support_rubles')
        
        if float(commissionamount) < 0:
            raise NotImplemented
        
        if float(commissionpercent) < 0:
            raise NotImplemented
        
        if recurring != 'off':
            raise NotImplemented

    
    def RF_Set(self, xml: ET.ElementTree):
        logger.info("start refund process")
        xml = xml.getroot()
        try:
            logger.info(ET.tostring(xml, encoding='unicode'))
            elid_node = xml.find('./source_payment')
            amount_node = xml.find('./payment_paymethodamount')
            elid = elid_node.text if elid_node is not None else ''
            amount = amount_node.text if amount_node is not None else ''
            pm = billmgr.db.db_query(f'''
            SELECT pm.xmlparams FROM paymethod pm
            WHERE pm.module = 'pmtinkoffpy' AND pm.id = {elid}
            ''')
            xml = ET.fromstring(pm['xmlparams'])
            psw_node= xml.find('./terminalpsw')
            key_node= xml.find('./terminalkey')
            psw = psw_node.text if psw_node is not None else ''
            key = key_node.text if key_node is not None else ''
            logger.info(key)
            terminal = Termianl(key, psw)
            #payment_id = terminal.check_order(f"external_{elid}")["Payments"][0]["PaymentId"]
            payment_id = "4338426213"
            terminal.cancel_deal(payment_id,str(int(float(amount)*-100)))
        except:
            logger.info("test")

    def RF_Tune(self, xml):
        return super().RF_Tune(xml)

    def RF_Validate(self, xml):
        return super().RF_Validate(xml)

    # в тестовом примере получаем необходимые платежи
    # и переводим их все в статус 'оплачен'
    def CheckPay(self):
        logger.info("run checkpay")
        
        # получаем список платежей в статусе оплачивается
        # и которые используют обработчик pmtestpayment
        payments = billmgr.db.db_query(f'''
            SELECT p.id, p.externalid, pm.xmlparams FROM payment p, paymethod pm
            WHERE pm.module = 'pmtinkoffpy' AND p.status = {payment.PaymentStatus.INPAY.value} AND p.paymethod = pm.id
        ''')
        for p in payments:
            logger.info(f"change status for payment {p['id']}")
            logger.info(f"pmparams={p['xmlparams']}")
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
