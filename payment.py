import os
os.chdir("/usr/local/mgr5")

from abc import ABC, abstractmethod
from billmgr.misc import MgrctlXml
import billmgr.db
import billmgr.exception
from enum import Enum
import sys
import xml.etree.ElementTree as ET
import requests
import hashlib
import json

MODULE = 'payment'


def parse_cookies(rawdata):
    from http.cookies import SimpleCookie
    cookie = SimpleCookie()
    cookie.load(rawdata)
    return {k: v.value for k, v in cookie.items()}


# cтатусы платежей в том виде, в котором они хранятся в БД
# см. https://docs.ispsystem.ru/bc/razrabotchiku/struktura-bazy-dannyh#id-Структурабазыданных-payment
class PaymentStatus(Enum):
    NEW = 1
    INPAY = 2
    PAID = 4
    FRAUD = 7
    CANCELED = 9


TINKOFF_URL = "https://securepay.tinkoff.ru/v2/"
GET_STATE = "GetState"
INIT = "Init"
CONFIRM = "Confirm"



class Termianl:

    def __init__(self, terminalkey, terminalpsw):
        self.terminalkey = terminalkey
        self.terminalpsw = terminalpsw
        self.BASE_URL = TINKOFF_URL

    def init_deal(self,amount, elid,success_page="", fail_page=""):
        data = {"TerminalKey": self.terminalkey, "OrderId": elid, "Amount": amount}
        obj = self._send_request('POST', 'Init', data,{"SuccessURL":success_page, "FailURL" : fail_page})
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
            raise billmgr.exception.XmlException('msg_error_repeat_again')

        try: 
            obj = json.loads(resp.content.decode("UTF-8"))
        except:
            raise billmgr.exception.XmlException('msg_error_json_parsing_error')
        
        if obj["ErrorCode"] == "202" or obj["ErrorCode"] == "331" or obj["ErrorCode"] == "501":
            raise billmgr.exception.XmlException('msg_error_wrong_terminal_info')
        return obj

    def _generate_token(self, data):
        data = data.copy()
        data["Password"]=self.terminalpsw
        data = dict(sorted(data.items()))
        self.token = hashlib.sha256("".join(data.values()).encode("UTF-8")).hexdigest()
    
    def cancel_deal(self, payment_id, amount):
        data = {"TerminalKey": self.terminalkey, "PaymentId": payment_id,"Amount" : amount}
        return self._send_request('POST', 'Cancel', data)

    def check_order(self, elid):
        data = {"TerminalKey": self.terminalkey, "OrderId": elid}
        return self._send_request('POST', 'CheckOrder', data)

    def confirm_deal(self, payment_id):
        data = {"TerminalKey": self.terminalkey, "PaymentId": payment_id}
        return self._send_request('POST', 'Confirm', data)

    def get_state_deal(self, payment_id):
        data = {"TerminalKey": self.terminalkey, "PaymentId": payment_id}
        return self._send_request('POST', 'GetState', data)


# перевести платеж в статус "оплачивается"
def set_in_pay(payment_id: str, info: str, externalid: str):
    '''
    payment_id - id платежа в BILLmanager
    info       - доп. информация о платеже от платежной системы
    externalid - внешний id на стороне платежной системы
    '''
    MgrctlXml('payment.setinpay', elid=payment_id, info=info, externalid=externalid)


# перевести платеж в статус "мошеннический"
def set_fraud(payment_id: str, info: str, externalid: str):
    MgrctlXml('payment.setfraud', elid=payment_id, info=info, externalid=externalid)


# перевести платеж в статус "оплачен"
def set_paid(payment_id: str, info: str, externalid: str):
    MgrctlXml('payment.setpaid', elid=payment_id, info=info, externalid=externalid)


# перевести платеж в статус "отменен"
def set_canceled(payment_id: str, info: str, externalid: str):
    MgrctlXml('payment.setcanceled', elid=payment_id, info=info, externalid=externalid)

class PaymentCgi(ABC):
    # основной метод работы cgi
    # абстрактный метод, который необходимо переопределить в конкретной реализации
    @abstractmethod
    def Process(self):
        pass

    def __init__(self):
        self.elid = ""           # ID платежа
        self.auth = ""           # токен авторизации
        self.mgrurl = ""         # url биллинга
        self.pending_page = ""   # url страницы биллинга с информацией об ожидании зачисления платежа
        self.fail_page = ""      # url страницы биллинга с информацией о неуспешной оплате
        self.success_page = ""   # url страницы биллинга с информацией о успешной оплате

        self.payment_params = {}   # параметры платежа
        self.paymethod_params = {} # параметры метода оплаты
        self.user_params = {}      # параметры пользователя

        self.lang = None           # язык используемый у клиента

        # по-умолчанию используется https
        if os.environ['HTTPS'] != 'on':
            raise NotImplemented
        
        # пока поддерживаем только http метод GET
        # POST включён в условие для работы возможности перехода на оплату уже созданного платежа
        if os.environ['REQUEST_METHOD'] not in ['POST', 'GET']:
            raise NotImplemented
        
        # получаем id платежа, он же elid
        input_str = os.environ['QUERY_STRING']
        for key, val in [param.split('=') for param in input_str.split('&')]:
            if key == "elid":
                self.elid = val
    
        # получаем url к панели
        self.mgrurl =  "https://" + os.environ['HTTP_HOST'] + "/billmgr"
        self.pending_page = f'{self.mgrurl}?func=payment.pending'
        self.fail_page = f'{self.mgrurl}?func=payment.fail'
        self.success_page = f'{self.mgrurl}?func=payment.success'

        # получить cookie
        cookies = parse_cookies(os.environ['HTTP_COOKIE'])
        _, self.lang = cookies["billmgrlang5"].split(':')

        # получить токен авторизации
        self.auth = cookies["billmgrses5"]

        # получить параметры платежа и метода оплаты
        # см. https://docs.ispsystem.ru/bc/razrabotchiku/sozdanie-modulej/sozdanie-modulej-plateyonyh-sistem#id-Созданиемодулейплатежныхсистем-CGIскриптымодуля
        payment_info_xml = MgrctlXml("payment.info", elid = self.elid, lang = self.lang)
        for elem in payment_info_xml.findall("./payment/"):
            self.payment_params[elem.tag] = elem.text
        for elem in payment_info_xml.findall("./payment/paymethod/"):
            self.paymethod_params[elem.tag] = elem.text
        
        # получаем параметры пользователя
        # получаем с помощью функции whoami информацию о авторизованном пользователе
        # в качестве параметра передаем auth - токен сессии
        user_node = MgrctlXml("whoami", auth = self.auth).find('./user')
        if user_node is None:
            raise billmgr.exception.XmlException("invalid_whoami_result")

        # получаем из бд данные о пользователях
        user_query = billmgr.db.get_first_record(
            " SELECT u.*, IFNULL(c.iso2, 'EN') AS country, a.registration_date"
            " FROM user u"
			" LEFT JOIN account a ON a.id=u.account"
			" LEFT JOIN country c ON c.id=a.country"
			" WHERE u.id = '" +  user_node.attrib['id'] + "'"
        )
        if user_query:
            self.user_params["user_id"] = user_query["id"]
            self.user_params["phone"] = user_query["phone"]
            self.user_params["email"] = user_query["email"]
            self.user_params["realname"] = user_query["realname"]
            self.user_params["language"] = user_query["language"]
            self.user_params["country"] = user_query["country"]
            self.user_params["account_id"] = user_query["account"]
            self.user_params["account_registration_date"] = user_query["registration_date"]


# фичи платежного модуля
# полный список можно посмотреть в документации
# https://docs.ispsystem.ru/bc/razrabotchiku/sozdanie-modulej/sozdanie-modulej-plateyonyh-sistem#id-Созданиемодулейплатежныхсистем-Основнойскриптмодуля
FEATURE_REDIRECT = "redirect"               # нужен ли переход в платёжку для оплаты
FEATURE_CHECKPAY = "checkpay"               # проверка статуса платежа по крону
FEATURE_NOT_PROFILE = "notneedprofile"      # оплата без плательщика (позволит зачислить платеж без создания плательщика)
FEATURE_PMVALIDATE = "pmvalidate"           # проверка введённых данных на форме создания платежной системы
FEATURE_PMUSERCREATE = "pmusercreate"       # для ссылки на регистрацию в платежке
FEATURE_REFUND = "refund"
FEATURE_RFTUNE = "rftune"
FEATURE_RFVALIDATE = "rfvalidate"
FEATURE_RFSET = "rfset"
# параметры платежного модуля
PAYMENT_PARAM_PAYMENT_SCRIPT = "payment_script" # mancgi/<наименование cgi скрипта>


class PaymentModule(ABC):
    # Абстрактные методы CheckPay и PM_Validate необходимо переопределить в своей реализации
    # см пример реализации в pmtestpayment.py

    # проверить оплаченные платежи
    # реализация --command checkpay
    # здесь делаем запрос в БД, получаем список платежей в статусе "оплачивается"
    # идем в платежку и проверяем прошли ли платежи
    # если платеж оплачен, выставляем соответствующий статус c помощью функции set_paid
    @abstractmethod
    def CheckPay(self):
        pass

    # вызывается для проверки введенных в настройках метода оплаты значений
    # реализация --command pmvalidate
    # принимается xml с веденными на форме значениями
    # если есть некорректные значения, то бросаем исключение billmgr.exception.XmlException
    # если все значение валидны, то ничего не возвращаем, исключений не бросаем
    @abstractmethod
    def PM_Validate(self, xml):
        pass

    @abstractmethod
    def RF_Tune(self, xml):
        pass

    @abstractmethod
    def RF_Validate(self, xml):
        pass

    @abstractmethod
    def RF_Set(self, xml):
        pass

    def __init__(self):
        self.features = {}
        self.params = {}

    # возращает xml с кофигурацией метода оплаты
    # реализация --command config
    def Config(self):
        config_xml = ET.Element('doc')
        feature_node = ET.SubElement(config_xml, 'feature')
        for key, val in self.features.items():
            ET.SubElement(feature_node, key).text = "on" if val else "off"

        param_node = ET.SubElement(config_xml, 'param')
        for key, val in self.params.items():
            ET.SubElement(param_node, key).text = val

        return config_xml

    def Process(self):
        try:
            # лайтовый парсинг аргументов командной строки
            # ожидаем --command <наименование команды>
            if len(sys.argv) < 3:
                raise billmgr.exception.XmlException("invalid_arguments")

            if sys.argv[1] != "--command":
                raise Exception("invalid_arguments")

            command = sys.argv[2]

            if command == "config":
                xml = self.Config()
                if xml is not None:
                    ET.dump(xml)

            elif command == FEATURE_PMVALIDATE:
                self.PM_Validate(ET.parse(sys.stdin))

            elif command == FEATURE_CHECKPAY:
                self.CheckPay()
            elif command == FEATURE_RFTUNE:
                self.RF_Tune(ET.parse(sys.stdin))
            elif command == FEATURE_RFSET:
                self.RF_Set(ET.parse(sys.stdin))
            elif command == FEATURE_RFVALIDATE:
                self.RF_Validate(ET.parse(sys.stdin))

        except billmgr.exception.XmlException as exception:
            sys.stdout.write(exception.as_xml())

