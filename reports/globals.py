#coding:utf-8

class Constant:

    DATETIME_STRING_KEY_FORMAT = "%Y/%m/%d-%H:%M:%S"

    POINTS_IN_GRAPHICS_IDEAL = 9000
    POINTS_IN_GRAPHICS_MAX = 15000
    POINTS_IN_GRAPHICS_MIN = 5000


class SystemError:

    GET_CONSUMER_UNIT_ELECTRICAL_PARAMETER_DATA_CLUSTERED_ERROR =\
        "GET_CONSUMER_UNIT_ELECTRICAL_PARAMETER_DATA_CLUSTERED_ERROR"

    GET_DATA_CLUSTER_CONSUMED_JSON_ERROR =\
        "GET_DATA_CLUSTER_CONSUMED_JSON_ERROR"

    GET_DATA_CLUSTERS_LIST_ERROR = "GET_DATA_CLUSTERS_LIST_ERROR"
    GET_INSTANT_DELTA_FROM_TIMEDELTA_ERROR =\
        "GET_INSTANT_DELTA_FROM_TIMEDELTA_ERROR"

    GET_NORMALIZED_REQUEST_DATA_LIST_ERROR =\
        "GET_NORMALIZED_REQUEST_DATA_LIST_ERROR"

    GET_TIMEDELTA_FROM_NORMALIZED_REQUEST_DATA_LIST_ERROR =\
        "GET_TIMEDELTA_FROM_NORMALIZED_REQUEST_DATA_LIST_ERROR"

    RENDER_INSTANT_MEASUREMENTS_ERROR = "RENDER_INSTANT_MEASUREMENTS_ERROR"


class Word:

    CONSUMER_UNIT = u"Unidad de Consumo"
    DATETIME_FROM = u"Desde"
    DATETIME_TO = u"Hasta"
    ELECTRICAL_PARAMETER = u"Parámetro Eléctrico"

