import datetime
import json
import uuid
from datetime import date, timedelta
from datetime import datetime
import requests

from pyiikocloudapi.decorators import experimental
from pyiikocloudapi.exception import CheckTimeToken, SetSession, TokenException, PostException, ParamSetException
from pyiikocloudapi.models import *


class BaseAPI:
    DEFAULT_TIMEOUT = "00%3A02%3A00"

    # __BASE_URL = "https://api-ru.iiko.services"

    def __init__(self, api_login: str, session: Optional[requests.Session] = None, debug: bool = False,
                 base_url: str = None, working_token: str = None, base_headers: dict = None):
        """

        :param api_login: login api iiko cloud
        :param session: session object
        :param debug: print dict reponse
        :param base_url: url iiko cloud api
        :param working_token: Initialize an object based on a working token, that is, without requesting a new one
        :param base_headers: base header for request in iiko cloud api
        """

        if session is not None:
            self.__session = session
        else:
            self.__session = requests.Session()

        self.__api_login = api_login
        self.__token: Optional[str] = None
        self.__debug = debug
        self.__time_token: Optional[date] = None
        self.__organizations_ids_model: Optional[BaseOrganizationsModel] = None
        self.__organizations_ids: Optional[List[str]] = None
        self.__strfdt = "%Y-%m-%d %H:%M:%S.000"

        self.__base_url = "https://api-ru.iiko.services" if base_url is None else base_url
        self.__headers = {
            "Content-Type": "application/json",
        } if base_headers is None else base_headers
        self.__set_token(working_token) if working_token is not None else self.__get_access_token()
        # if working_token is not None:
        #     self.__set_token(working_token)
        # else:
        #     self.__get_access_token()

    def check_status_code_token(self, code: Union[str, int]):
        if str(code) == "401":
            self.__get_access_token()
        elif str(code) == "400":
            pass
        elif str(code) == "408":
            pass
        elif str(code) == "500":
            pass

    def check_token_time(self) -> bool:
        """
        Проверка на время жизни маркера доступа
        :return: Если прошло 15 мин будет запрошен токен и метод вернёт True, иначе вернётся False
        """
        fifteen_minutes_ago = datetime.now() - timedelta(minutes=15)
        time_token = self.__time_token
        try:

            if time_token <= fifteen_minutes_ago:
                self.__get_access_token()
                return True
            else:
                return False
        except TypeError:
            raise CheckTimeToken(
                self.__class__.__qualname__,
                self.check_token_time.__name__,
                f"Не запрошен Token и не присвоен объект типа datetime.datetime")

    @property
    def organizations_ids_models(self) -> Optional[List[OrganizationModel]]:
        """Вывести сессию"""
        return self.__organizations_ids_model

    @property
    def organizations_ids(self) -> Optional[List[str]]:
        """Вывести сессию"""
        return self.__organizations_ids

    @property
    def session_s(self) -> requests.Session:
        """Вывести сессию"""
        return self.__session

    @session_s.setter
    def session_s(self, session: requests.Session = None):
        """Изменение сессии"""
        if session is None:
            raise SetSession(
                self.__class__.__qualname__,
                self.session_s.__name__,
                f"Не присвоен объект типа requests.Session")
        else:
            self.__session = session

    @property
    def time_token(self):
        return self.__time_token

    @property
    def api_login(self) -> str:
        return self.__api_login

    @property
    def token(self) -> str:
        return self.__token

    @property
    def base_url(self):
        return self.__base_url

    @base_url.setter
    def base_url(self, value: str):
        self.__base_url = value

    @property
    def strfdt(self):
        return self.__strfdt

    @strfdt.setter
    def strfdt(self, value: str):
        self.__strfdt = value

    @property
    def headers(self):
        return self.__headers

    @headers.setter
    def headers(self, value: str):
        self.__headers = value

    def __set_token(self, token):
        self.__token = token
        self.__headers["Authorization"] = f"Bearer {self.token}"
        self.__time_token = datetime.now()

    def access_token(self):
        """Получить маркер доступа"""
        data = json.dumps({"apiLogin": self.api_login})
        try:
            result = self.session_s.post(f'{self.__base_url}/api/1/access_token', json=data)

            response_data: dict = json.loads(result.content)
            if response_data.get("errorDescription", None) is not None:
                raise TypeError(f'{response_data=}')

            if response_data.get("token", None) is not None:
                self.check_status_code_token(result.status_code)
                self.__set_token(response_data.get("token", ""))

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.access_token.__name__,
                                 f"Не удалось получить маркер доступа: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.access_token.__name__,
                                 f"Не удалось получить маркер доступа: \n{err}")

    def _post_request(self, url: str, data: dict = None, model_response_data=None, model_error=CustomErrorModel):
        if data is None:
            data = {}

        print(json.dumps(data))
        result = self.session_s.post(f'{self.base_url}{url}', json=json.dumps(data),
                                     headers=self.headers)

        response_data: dict = json.loads(result.content)

        print(json.dumps(response_data))

        if self.__debug:
            print(f"{result.status_code=}\n{response_data=}\n")

        if response_data.get("errorDescription", None) is not None:
            error_model = model_error.parse_obj(response_data)
            error_model.status_code = result.status_code
            return error_model
        if model_response_data is not None:
            return model_response_data.parse_obj(response_data)
        return response_data

    def __get_access_token(self):
        out = self.access_token()
        if isinstance(out, CustomErrorModel):
            raise TokenException(self.__class__.__qualname__,
                                 self.access_token.__name__,
                                 f"Не удалось получить маркер доступа: \n{out}")

    def __convert_org_data(self, data: BaseOrganizationsModel):
        self.__organizations_ids = data.__list_id__()

    def organizations(self, organization_ids: List[str] = None, return_additional_info: bool = None,
                      include_disabled: bool = None) -> Union[CustomErrorModel, BaseOrganizationsModel]:
        """
        Возвращает организации, доступные пользователю API-login.
        :param organization_ids: Organizations IDs which have to be returned. By default - all organizations from apiLogin.
        :param return_additional_info: A sign whether additional information about the organization should be returned (RMS version, country, restaurantAddress, etc.), or only minimal information should be returned (id and name).
        :param include_disabled: Attribute that shows that response contains disabled organizations.
        :return:
        """
        #         https://api-ru.iiko.services/api/1/organizations
        data = {}
        if organization_ids is not None:
            data["organizationIds"] = organization_ids
        if return_additional_info is not None:
            data["returnAdditionalInfo"] = return_additional_info
        if include_disabled is not None:
            data["includeDisabled"] = include_disabled
        try:
            response_data = self._post_request(
                url="/api/1/organizations",
                data=data,
                model_response_data=BaseOrganizationsModel
            )
            if isinstance(response_data, BaseOrganizationsModel):
                self.__convert_org_data(data=response_data)

            return response_data

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.organizations.__name__,
                                 f"Не удалось получить организации: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.organizations.__name__,
                            f"Не удалось получить организации: \n{err}")


class Dictionaries(BaseAPI):
    def cancel_causes(self, organization_ids: List[str]) -> Union[CustomErrorModel, BaseCancelCausesModel]:
        if not bool(organization_ids):
            raise ParamSetException(self.__class__.__qualname__,
                                    self.cancel_causes.__name__,
                                    f"Пустой список id организаций")
        data = {
            "organizationIds": organization_ids,
        }
        try:

            return self._post_request(
                url="/api/1/cancel_causes",
                data=data,
                model_response_data=BaseCancelCausesModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.cancel_causes.__name__,
                                 f"Не удалось получить причины отмены доставки: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.cancel_causes.__name__,
                            f"Не удалось получить причины отмены доставки: \n{err}")

    def order_types(self, organization_ids: List[str]) -> Union[CustomErrorModel, BaseOrderTypesModel]:
        if not bool(organization_ids):
            raise ParamSetException(self.__class__.__qualname__,
                                    self.order_types.__name__,
                                    f"Пустой список id организаций")
        data = {
            "organizationIds": organization_ids,
        }
        try:

            return self._post_request(
                url="/api/1/deliveries/order_types",
                data=data,
                model_response_data=BaseOrderTypesModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.order_types.__name__,
                                 f"Не удалось получить типы заказа: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.order_types.__name__,
                            f"Не удалось получить типы заказа: \n{err}")

    def discounts(self, organization_ids: List[str]) -> Union[CustomErrorModel, BaseDiscountsModel]:
        if not bool(organization_ids):
            raise ParamSetException(self.__class__.__qualname__,
                                    self.discounts.__name__,
                                    f"Пустой список id организаций")
        data = {
            "organizationIds": organization_ids,
        }
        try:

            return self._post_request(
                url="/api/1/discounts",
                data=data,
                model_response_data=BaseDiscountsModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.discounts.__name__,
                                 f"Не удалось получить скидки/надбавки: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.discounts.__name__,
                            f"Не удалось получить скидки/надбавки: \n{err}")

    def payment_types(self, organization_ids: List[str]) -> Union[CustomErrorModel, BasePaymentTypesModel]:
        if not bool(organization_ids):
            raise ParamSetException(self.__class__.__qualname__,
                                    self.payment_types.__name__,
                                    f"Пустой список id организаций")
        data = {
            "organizationIds": organization_ids,
        }
        try:

            return self._post_request(
                url="/api/1/payment_types",
                data=data,
                model_response_data=BasePaymentTypesModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.payment_types.__name__,
                                 f"Не удалось получить типы оплаты: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.payment_types.__name__,
                            f"Не удалось получить типы оплаты: \n{err}")

    def removal_types(self, organization_ids: List[str]) -> Union[CustomErrorModel, BaseRemovalTypesModel]:
        if not bool(organization_ids):
            raise ParamSetException(self.__class__.__qualname__,
                                    self.removal_types.__name__,
                                    f"Пустой список id организаций")
        data = {
            "organizationIds": organization_ids,
        }
        try:

            return self._post_request(
                url="/api/1/removal_types",
                data=data,
                model_response_data=BaseRemovalTypesModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.removal_types.__name__,
                                 f"Не удалось получить removal_types: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.removal_types.__name__,
                            f"Не удалось получить removal_types: \n{err}")

    def tips_types(self, ) -> Union[CustomErrorModel, BaseTipsTypesModel]:
        try:

            return self._post_request(
                url="/api/1/tips_types",
                model_response_data=BaseTipsTypesModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.removal_types.__name__,
                                 f"Не удалось получить подсказки для группы api-logins rms: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.removal_types.__name__,
                            f"Не удалось получить подсказки для группы api-logins rms: \n{err}")


class Menu(BaseAPI):
    def nomenclature(self, organization_id: str, start_revision: int = None) -> Union[CustomErrorModel,
                                                                                      BaseNomenclatureModel]:
        data = {
            "organizationId": organization_id,
        }
        if start_revision is not None:
            data["startRevision"] = start_revision

        try:

            return self._post_request(
                url="/api/1/nomenclature",
                data=data,
                model_response_data=BaseNomenclatureModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.nomenclature.__name__,
                                 f"Не удалось получить номенклатуру: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.nomenclature.__name__,
                            f"Не удалось получить номенклатуру: \n{err}")

    def menu(self, ) -> Union[CustomErrorModel, BaseMenuModel]:
        try:

            return self._post_request(
                url="/api/2/menu",
                model_response_data=BaseMenuModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.nomenclature.__name__,
                                 f"Не удалось получить внешние меню с ценовыми категориями: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.nomenclature.__name__,
                            f"Не удалось получить внешние меню с ценовыми категориями: \n{err}")

    def menu_by_id(self, external_menu_id: str, organization_ids: List[str], price_category_id: str = None) -> Union[
        CustomErrorModel, BaseMenuByIdModel]:

        data = {
            "externalMenuId": external_menu_id,
            "organizationIds": organization_ids,
        }

        if price_category_id is not None:
            data["priceCategoryId"] = price_category_id

        try:

            return self._post_request(
                url="/api/2/menu/by_id",
                data=data,
                model_response_data=BaseMenuByIdModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.nomenclature.__name__,
                                 f"Не удалось получить внешнее меню по ID.: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.nomenclature.__name__,
                            f"Не удалось получить внешнее меню по ID.: \n{err}")


class TerminalGroup(BaseAPI):
    def terminal_groups(self, organization_ids: List[str], include_disabled: bool = False) -> Union[CustomErrorModel,
                                                                                                    BaseTerminalGroupsModel]:
        """

        :param organization_ids: 	Array of strings <uuid>, Organizations IDs for which information is requested.
        :param include_disabled:
        :return:
        """
        if not bool(organization_ids):
            raise ParamSetException(self.__class__.__qualname__,
                                    self.terminal_groups.__name__,
                                    f"Пустой список id организаций")
        data = {
            "organizationIds": organization_ids,
        }
        if include_disabled:
            data["includeDisabled"] = include_disabled
        try:

            return self._post_request(
                url="/api/1/terminal_groups",
                data=data,
                model_response_data=BaseTerminalGroupsModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.terminal_groups.__name__,
                                 f"Не удалось получить регионы: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.terminal_groups.__name__,
                            f"Не удалось получить регионы: \n{err}")

    def is_alive(self, organization_ids: List[str], terminal_group_ids: List[str], ) -> Union[CustomErrorModel,
                                                                                              BaseTGIsAliveyModel]:
        """

        :param terminal_group_ids:
        :param organization_ids: 	Array of strings <uuid>, Organizations IDs for which information is requested.
        :return:
        """
        if not bool(organization_ids):
            raise ParamSetException(self.__class__.__qualname__,
                                    self.is_alive.__name__,
                                    f"Пустой список id организаций")
        data = {
            "organizationIds": organization_ids,
            "terminalGroupIds": terminal_group_ids
        }

        try:

            return self._post_request(
                url="/api/1/terminal_groups/is_alive",
                data=data,
                model_response_data=BaseTGIsAliveyModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.is_alive.__name__,
                                 f"Не удалось получить регионы: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.is_alive.__name__,
                            f"Не удалось получить регионы: \n{err}")


class Address(BaseAPI):
    def regions(self, organization_ids: List[str], ) -> Union[CustomErrorModel, BaseRegionsModel]:
        """
        Возвращает регионы, доступные пользователю API-login.
        :return:
        """
        #         https://api-ru.iiko.services/api/1/organizations
        if not bool(organization_ids):
            raise ParamSetException(self.__class__.__qualname__,
                                    self.regions.__name__,
                                    f"Пустой список id организаций")

        data = {
            "organizationIds": organization_ids,
        }
        try:

            return self._post_request(
                url="/api/1/regions",
                data=data,
                model_response_data=BaseRegionsModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.regions.__name__,
                                 f"Не удалось получить регионы: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.regions.__name__,
                            f"Не удалось получить регионы: \n{err}")

    def cities(self, organization_ids: List[str], ) -> Union[CustomErrorModel, BaseCitiesModel]:
        """
        Возвращает регионы, доступные пользователю API-login.
        :return:
        """
        #         https://api-ru.iiko.services/api/1/organizations
        if not bool(organization_ids):
            raise ParamSetException(self.__class__.__qualname__,
                                    self.cities.__name__,
                                    f"Пустой список id организаций")

        data = {
            "organizationIds": organization_ids,
        }
        try:

            return self._post_request(
                url="/api/1/cities",
                data=data,
                model_response_data=BaseCitiesModel
            )


        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.cities.__name__,
                                 f"Не удалось получить города: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.cities.__name__,
                            f"Не удалось получить города: \n{err}")

    def by_city(self, organization_id: str, city_id: str) -> Union[CustomErrorModel, BaseStreetByCityModel]:
        """
        Возвращает регионы, доступные пользователю API-login.
        :return:
        """
        #         https://api-ru.iiko.services/api/1/organizations

        data = {
            "organizationId": organization_id,
            "cityId": city_id
        }
        try:

            return self._post_request(
                url="/api/1/streets/by_city",
                data=data,
                model_response_data=BaseStreetByCityModel
            )


        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.cities.__name__,
                                 f"Не удалось получить улицы: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.cities.__name__,
                            f"Не удалось получить улицы: \n{err}")


class Orders(BaseAPI):
    def order_create(self, order: OrderCreateRequestModel) -> \
            Union[CustomErrorModel, BaseCreatedOrderInfoModel]:
        try:

            return self._post_request(
                url="/api/1/order/create",
                data=order.dict(),
                model_response_data=BaseCreatedOrderInfoModel

            )
        except requests.exceptions.RequestException as err:
            raise PostException(self.__class__.__qualname__,
                                self.order_create.__name__,
                                f"Не удалось создать заказ из за: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.order_create.__name__,
                            f"Не удалось создать заказ из за: \n{err}")

    def get_orders_by_ids(self, data: OrderRetrieveByIdsRequestModel):
        # https://api-ru.iiko.services/api/1/order/by_id

        try:

            return self._post_request(
                url="/api/1/order/by_id",
                data=data.dict(),
                model_response_data=OrderResponseModel
            )

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.get_orders_by_ids.__name__,
                                 f"Не удалось получить заказы: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.get_orders_by_ids.__name__,
                                 f"Не удалось: \n{err}")

    def get_orders_by_tables(self, data: OrderRetrieveByTablesRequestModel):
        # https://api-ru.iiko.services/api/1/order/by_table

        try:

            return self._post_request(
                url="/api/1/order/by_table",
                data=data.dict(),
                model_response_data=OrderResponseModel
            )

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.get_orders_by_tables.__name__,
                                 f"Не удалось получить заказы: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.get_orders_by_tables.__name__,
                                 f"Не удалось: \n{err}")

    def close_order(self, data: OrderCloseRequestModel):
        # https://api-ru.iiko.services/api/1/order/close

        try:

            return self._post_request(
                url="/api/1/order/close",
                data=data.dict(),
                model_response_data=BaseResponseModel
            )

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.close_order.__name__,
                                 f"Не удалось получить заказы: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.close_order.__name__,
                                 f"Не удалось: \n{err}")

    def add_items_to_order(self, data: OrderAddItemsRequestModel):
        # https://api-ru.iiko.services/api/1/order/add_items

        try:

            return self._post_request(
                url="/api/1/order/add_items",
                data=data.dict(),
                model_response_data=BaseResponseModel
            )

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.add_items_to_order.__name__,
                                 f"Не удалось получить заказы: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.add_items_to_order.__name__,
                                 f"Не удалось: \n{err}")

    def change_order_payments(self, data: OrderPaymentsChangeRequestModel):
        # https://api-ru.iiko.services/api/1/order/change_payments

        try:

            return self._post_request(
                url="/api/1/order/change_payments",
                data=data.dict(),
                model_response_data=BaseResponseModel
            )

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.change_order_payments.__name__,
                                 f"Не удалось получить заказы: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.change_order_payments.__name__,
                                 f"Не удалось: \n{err}")

    def init_orders_by_tables(self, data: OrderInitByTablesRequestModel):
        # https://api-ru.iiko.services/api/1/order/init_by_table

        try:

            return self._post_request(
                url="/api/1/order/by_table",
                data=data.dict(),
                model_response_data=BaseResponseModel
            )

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.init_orders_by_tables.__name__,
                                 f"Не удалось получить заказы: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.init_orders_by_tables.__name__,
                                 f"Не удалось: \n{err}")


class Deliveries(BaseAPI):
    def delivery_create(self, organization_id: str, order: dict, terminal_group_id: str = None,
                        create_order_settings: Optional[int] = None, ) -> Union[
        CustomErrorModel, BaseCreatedDeliveryOrderInfoModel]:
        """"""
        data = {
            "organizationIds": organization_id,
            "order": order,
        }
        if terminal_group_id is not None:
            data["terminalGroupId"] = terminal_group_id

        if create_order_settings is not None:
            data["createOrderSettings"] = create_order_settings

        try:

            return self._post_request(
                url="/api/1/delivery/create",
                data=data,
                model_response_data=BaseCreatedDeliveryOrderInfoModel
            )
        except requests.exceptions.RequestException as err:
            raise PostException(self.__class__.__qualname__,
                                self.delivery_create.__name__,
                                f"Не удалось создать заказ из за: \n{err}")
        except TypeError as err:
            raise TypeError(self.__class__.__qualname__,
                            self.delivery_create.__name__,
                            f"Не удалось создать заказ из за: \n{err}")

    def update_order_delivery_status(self,
                                     organization_id: List[str],
                                     order_id: str,
                                     delivery_status: str = "Delivered",
                                     delivery_date: datetime = datetime.now()
                                     ):
        """
        :param organization_id: Organization ID
        :param order_id: Order ID.
        :param delivery_status: Enum: "Waiting" "OnWay" "Delivered", Delivery status. Can be only switched between these three statuses.
        :param delivery_date: The date and time when the order was received by the guest (Local for delivery terminal). This field must be filled in only if the order is transferred to the "Delivered" status.

        :return:
        """
        #         https://api-ru.iiko.services/api/1/deliveries/update_order_delivery_status
        if not isinstance(delivery_date, datetime):
            raise TypeError("delivery_date != datetime")
        data = {
            "organizationIds": organization_id,
            "orderId": order_id,
            "deliveryStatus": delivery_status,
        }
        if delivery_status == "Delivered":
            data["deliveryDate"] = delivery_date.strftime(self.strfdt)
        try:

            return self._post_request(
                url="/api/1/deliveries/update_order_delivery_status",
                data=data,
                model_response_data=BaseResponseModel
            )
        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.update_order_delivery_status.__name__,
                                 f"Не удалось изменить статус: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.update_order_delivery_status.__name__,
                                 f"Не удалось: \n{err}")

    def confirm(self,
                organization_id: List[str],
                order_id: str,
                ):
        """
        Подвердить статус доставки заказа

        :param organization_id: Organization ID
        :param order_id: Order ID.
        :return: dict response
        """
        #         https://api-ru.iiko.services/api/1/deliveries/confirm
        data = {
            "organizationIds": organization_id,
            "orderId": order_id,
        }

        try:
            return self._post_request(
                url="/api/1/deliveries/confirm",
                data=data,
                model_response_data=BaseResponseModel,
            )

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.confirm.__name__,
                                 f"Не удалось изменить статус: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.confirm.__name__,
                                 f"Не удалось: \n{err}")

    def cancel_confirmation(self,
                            organization_id: List[str],
                            order_id: str,
                            ):
        """
        Отменить подтверждение доставки

        :param organization_id: Organization ID
        :param order_id: Order ID.
        :return: dict response
        """
        # https://api-ru.iiko.services/api/1/deliveries/cancel_confirmation
        data = {
            "organizationIds": organization_id,
            "orderId": order_id,
        }

        try:

            return self._post_request(
                url="/api/1/deliveries/cancel_confirmation",
                data=data,
                model_response_data=BaseResponseModel
            )

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.cancel_confirmation.__name__,
                                 f"Не удалось изменить статус: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.cancel_confirmation.__name__,
                                 f"Не удалось: \n{err}")

    def by_delivery_date_and_status(self,
                                    organization_id: List[str],
                                    delivery_date_from: Union[datetime, str],
                                    delivery_date_to: Union[datetime, str] = None,
                                    statuses: list = None,
                                    source_keys: list = None
                                    ) -> Union[ByDeliveryDateAndStatusModel, CustomErrorModel]:
        """


        :param organization_id:
        :param delivery_date_from: datetime or "%Y-%m-%d %H:%M:%S.%f". Order delivery date (Local for delivery terminal). Lower limit.
        :param delivery_date_to: datetime or "%Y-%m-%d %H:%M:%S.%f". Order delivery date (Local for delivery terminal). Upper limit.
        :param statuses: Items Enum: "Unconfirmed", "WaitCooking", "ReadyForCooking", "CookingStarted", "CookingCompleted", "Waiting", "OnWay", "Delivered", "Closed", "Cancelled",  Allowed order statuses.
        :param source_keys:Source keys.
        :return:
        """
        # https://api-ru.iiko.services/api/1/deliveries/by_delivery_date_and_status
        data = {
            "organizationIds": organization_id,
        }
        if isinstance(delivery_date_from, datetime):
            data["deliveryDateFrom"] = delivery_date_from.strftime(self.strfdt)
        elif isinstance(delivery_date_from, str):
            data["deliveryDateFrom"] = delivery_date_from

        if isinstance(delivery_date_to, datetime):
            data["deliveryDateTo"] = delivery_date_to.strftime(self.strfdt)
        elif isinstance(delivery_date_to, str):
            data["deliveryDateTo"] = delivery_date_to
        if delivery_date_to is not None:
            if isinstance(delivery_date_to, datetime):
                data["deliveryDateTo"] = delivery_date_to.strftime(self.strfdt)
            elif isinstance(delivery_date_to, str):
                data["deliveryDateTo"] = delivery_date_to
            else:
                raise TypeError("type delivery_date_to != datetime or str")

        if statuses is not None:
            if not isinstance(statuses, list):
                raise TypeError("type statuses != list")
            data["statuses"] = statuses

        if source_keys is not None:
            if not isinstance(source_keys, list):
                raise TypeError("type source_keys != list")
            data["sourceKeys"] = source_keys

        try:
            # result = self.session_s.post(f'{self.base_url}/api/1/deliveries/by_delivery_date_and_status',
            #                              json=json.dumps(data),
            #                              headers=self.headers)
            # out: dict = json.loads(result.content)
            # print(out)
            # if out.get("errorDescription", None) is not None:
            #     # raise PostException(self.__class__.__qualname__,
            #     #                     self.by_delivery_date_and_status.__name__,
            #     #                     f"Не удалось получить заказы: \n{out}")
            #     return ErrorModel.parse_obj(out)
            # return ByDeliveryDateAndStatusModel.parse_obj(out)
            return self._post_request(
                url="/api/1/deliveries/by_delivery_date_and_status",
                data=data,
                model_response_data=ByDeliveryDateAndStatusModel
            )

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.by_delivery_date_and_status.__name__,
                                 f"Не удалось получить заказы: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.by_delivery_date_and_status.__name__,
                                 f"Не удалось: \n{err}")

    @experimental("будет дописан в будущем!")
    def by_revision(self):
        # Retrieve list of orders changed from the time revision was passed.
        # https://api-ru.iiko.services/api/1/deliveries/by_revision
        pass

    @experimental("будет дописан в будущем!")
    def by_delivery_date_and_phone(self):
        # Retrieve list of orders changed from the time revision was passed.
        # https://api-ru.iiko.services/api/1/deliveries/by_delivery_date_and_phone
        pass

    def by_delivery_date_and_source_key_and_filter(self,
                                                   organization_id: List[str],
                                                   terminal_group_ids: Optional[List[Union[str, uuid.UUID]]] = None,
                                                   delivery_date_from: Optional[str] = None,
                                                   delivery_date_to: Optional[str] = None,
                                                   statuses: Optional[List[str]] = None,
                                                   has_problem: Optional[bool] = None,
                                                   order_service_type: Optional[str] = None,
                                                   search_text: Optional[str] = None,
                                                   time_to_cooking_error_timeout: Optional[int] = None,
                                                   cooking_timeout: Optional[int] = None,
                                                   sort_property: Optional[str] = None,
                                                   sort_direction: Optional[str] = None,
                                                   rows_count: Optional[int] = None,
                                                   source_keys: Optional[List[str]] = None,
                                                   order_ids: Optional[List[Union[str, uuid.UUID]]] = None,
                                                   ):
        """

        :param organization_id: List
        :param terminal_group_ids: List of terminal groups IDs.
        :param delivery_date_from: Order delivery date (Local for delivery terminal). Lower limit.
        :param delivery_date_to: Order delivery date (Local for delivery terminal). Upper limit.
        :param statuses: Enum: "Unconfirmed" "WaitCooking" "ReadyForCooking" "CookingStarted" "CookingCompleted" "Waiting" "OnWay" "Delivered" "Closed" "Cancelled", Array of strings (iikoTransport.PublicApi.Contracts.Deliveries.Common.DeliveryStatus) Nullable
        :param has_problem: If true, delivery has a problem
        :param order_service_type: Order service type. Enum: "DeliveryByCourier" "DeliveryByClient"
        :param search_text: Value for search. Used for prefix search.
        :param time_to_cooking_error_timeout: Error timeout for status time to cooking, in seconds.
        :param cooking_timeout: Expected cooking time, in seconds.
        :param sort_property:  Enum: ("Number", "CompleteBefore", "Sum", "Customer", "Courier", "Status"),  Sorting property.
        :param sort_direction: Enum: ("Ascending", "Descending"),  Sorting direction.
        :param rows_count: Maximum number of items returned.
        :param source_keys: Source keys.
        :param order_ids: Order IDs
        :return:
        """

        #         https://api-ru.iiko.services/api/1/deliveries/by_delivery_date_and_source_key_and_filter
        data = {
            "organizationIds": organization_id,
        }

        if terminal_group_ids is not None:
            if not isinstance(terminal_group_ids, list):
                raise TypeError("type terminal_group_ids != list")
            data["terminalGroupIds"] = terminal_group_ids

        if delivery_date_from is not None:
            if not isinstance(delivery_date_from, str):
                raise TypeError("type delivery_date_from != str")
            data["deliveryDateFrom"] = delivery_date_from

        if delivery_date_to is not None:
            if not isinstance(delivery_date_to, str):
                raise TypeError("type delivery_date_to != str")
            data["deliveryDateTo"] = delivery_date_to

        if statuses is not None:
            if not isinstance(statuses, list):
                raise TypeError("type statuses != list")
            data["statuses"] = statuses

        if has_problem is not None:
            if not isinstance(has_problem, bool):
                raise TypeError("type has_problem != list")
            data["hasProblem"] = has_problem

        if order_service_type is not None:
            if not isinstance(order_service_type, str):
                raise TypeError("type order_service_type != str")
            data["orderServiceType"] = order_service_type

        if search_text is not None:
            if not isinstance(search_text, str):
                raise TypeError("type search_text != str")
            data["searchText"] = search_text

        if time_to_cooking_error_timeout is not None:
            if not isinstance(time_to_cooking_error_timeout, int):
                raise TypeError("type time_to_cooking_error_timeout != int")
            data["timeToCookingErrorTimeout"] = time_to_cooking_error_timeout

        if cooking_timeout is not None:
            if not isinstance(cooking_timeout, int):
                raise TypeError("type cooking_timeout != int")
            data["cookingTimeout"] = cooking_timeout

        if sort_property is not None:
            if not isinstance(sort_property, str):
                raise TypeError("type sort_property != str")
            data["sortProperty"] = sort_property

        if sort_direction is not None:
            if not isinstance(sort_direction, str):
                raise TypeError("type sort_direction != str")
            data["sortDirection"] = sort_direction

        if rows_count is not None:
            if not isinstance(rows_count, int):
                raise TypeError("type rows_count != int")
            data["rowsCount"] = rows_count

        if source_keys is not None:
            if not isinstance(source_keys, list):
                raise TypeError("type source_keys != list")
            data["sourceKeys"] = source_keys

        if order_ids is not None:
            if not isinstance(order_ids, list):
                raise TypeError("type order_ids != list")
            data["orderIds"] = order_ids

        try:
            return self._post_request(
                url="/api/1/deliveries/by_delivery_date_and_source_key_and_filter",
                data=data,
                model_response_data=ByDeliveryDateAndSourceKeyAndFilter,
            )

        except requests.exceptions.RequestException as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.by_delivery_date_and_status.__name__,
                                 f"Не удалось получить заказы: \n{err}")
        except TypeError as err:
            raise TokenException(self.__class__.__qualname__,
                                 self.by_delivery_date_and_status.__name__,
                                 f"Не удалось: \n{err}")


class Employees(BaseAPI):

    def couriers(self, organization_id: List[str], ):

        #     https://api-ru.iiko.services/api/1/employees/couriers
        data = {
            "organizationIds": organization_id,
        }

        try:
            return self._post_request(
                url="/api/1/employees/couriers",
                data=data,
                model_response_data=CouriersModel
            )
        except requests.exceptions.RequestException as err:
            raise PostException(self.__class__.__qualname__,
                                self.couriers.__name__,
                                f"Не удалось получить курьеров: \n{err}")
        except TypeError as err:
            raise PostException(self.__class__.__qualname__,
                                self.couriers.__name__,
                                f"Не удалось: \n{err}")


class Reserve(BaseAPI):
    def available_restaurant_sections(
            self,
            terminalGroupIds: List[str],
            returnSchema: bool = False,
            revision: int = 0
    ):

        #     https://api-ru.iiko.services/api/1/reserve/available_restaurant_sections
        data = {
            'terminalGroupIds': terminalGroupIds,
            'returnSchema': returnSchema,
            'revision': revision
        }

        try:
            return self._post_request(
                url="/api/1/reserve/available_restaurant_sections",
                data=data,
                model_response_data=AvailableRestaurantSections
            )
        except requests.exceptions.RequestException as err:
            raise PostException(self.__class__.__qualname__,
                                self.available_restaurant_sections.__name__,
                                f"{err}")
        except TypeError as err:
            raise PostException(self.__class__.__qualname__,
                                self.available_restaurant_sections.__name__,
                                f"{err}")


class IikoTransport(Orders, Deliveries, Employees, Address, TerminalGroup, Menu, Dictionaries, Reserve):
    pass
