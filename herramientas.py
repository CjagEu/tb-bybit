from datetime import datetime
from telegram_bot import send_message
from pybit.usdt_perpetual import HTTP

import time
import pandas as pd
import math
import logging
import sys


# Para logging
FILENAME_LOGGING = 'log.txt'
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.addHandler(logging.FileHandler(FILENAME_LOGGING))


def filtro_long(emarapida: pd.DataFrame, emalenta: pd.DataFrame, nvelas: int):
    """
    Toma las nvelas anteriores para comprobar que la ema rapida se mantenga por debajo de la emalenta
    :return bool:
    """
    res = True
    for i in range(-nvelas, 0):
        if emarapida.values[i] > emalenta.values[i]:
            res = False
            break
    return res


def filtro_short(emarapida: pd.DataFrame, emalenta: pd.DataFrame, nvelas: int):
    """
    Toma las nvelas anteriores para comprobar que la ema rapida se mantenga por encima de la emalenta
    :return bool:
    """
    res = True
    for i in range(-nvelas, 0):
        if emarapida.values[i] < emalenta.values[i]:
            res = False
            break
    return res


def filtro_kama(df_open: pd.DataFrame, df_close: pd.DataFrame, kama_avg: pd.DataFrame, nvelas2: int):
    """
    Comprueba cuantas veces la media kama_avg está dentro del cuerpo de las nvelas2.
    Devuelve True si esto ocurre <= (nvelas2/2), es una forma de filtrar la volatilidad que ha habido en las últimas nvelas2
    :return bool:
    """
    contador = 0
    for i in range(-nvelas2, 0):
        vela_alcista = df_open.values[i] < df_close.values[i]
        if vela_alcista:
            if kama_avg.values[i] >= df_open.values[i] and kama_avg.values[i] <= df_close.values[i]:
                contador = contador + 1
        # vela_bajista
        else:
            if kama_avg.values[i] <= df_open.values[i] and kama_avg.values[i] >= df_close.values[i]:
                contador = contador + 1
    return contador <= (nvelas2/2)


def get_qty(symbol: str, disponible: float, apalancamiento: float, lastprice: float):
    """
    Calcula la cantidad que hay que poner en la orden teniendo en cuenta el apalancamiento y el disponible (en USDT) de la cuenta.
    El cálculo se realiza con 5 usdt menos para asegurar que la posición entra bien para órdenes condicionales
    :return float:
    """
    # Condición especial para BTC, solo se pueden poner órdenes con 3 decimales y para asegurar que el redondeo no supere mi dinero le resto 0.001
    if symbol == 'BTCUSDT':
        return round((((disponible-5) * apalancamiento) / lastprice), 3) - 0.001
    # Condición especial para ETH, solo se pueden poner órdenes con 2 decimales y para asegurar que el redondeo no supere mi dinero le resto 0.01
    elif symbol == 'ETHUSDT':
        return round((((disponible - 5) * apalancamiento) / lastprice), 2) - 0.01
    # En este caso el precio de la moneda permite que la cantidad sea mayor que 0.algo
    return math.floor(((disponible-5) * apalancamiento) / lastprice)


def filtro_dentro_de_nube(ichimoku_a: float, ichimoku_b: float, df_open: float, df_close: float):
    """
     Comprueba si el cuerpo de la vela está dentro de la nube.
     (Modificar función para tomar el High y Low)
    :return bool:
    """
    res = False
    if ichimoku_a > ichimoku_b:
        # a > b: Nube verde
        if ichimoku_b < df_open and ichimoku_b < df_close and ichimoku_a > df_open and ichimoku_a > df_close:
            res = True 
    else:
        # b > a: Nube Roja
        if ichimoku_a < df_open and ichimoku_a < df_close and ichimoku_b > df_open and ichimoku_b > df_close:
            res = True
    return res  


def filtro_nube_verde(ichimoku_a: float, ichimoku_b: float, close: float):
    """
    False si la vela cierra por encima de una nube verde, (no Longs)
    :return bool:
    """
    return ichimoku_a > ichimoku_b and close > ichimoku_a


def filtro_nube_roja(ichimoku_a: float, ichimoku_b: float, close: float):
    """
    False si la vela cierra por debajo de una nube roja, (no Shorts)
    :return bool:
    """
    return ichimoku_b > ichimoku_a and close < ichimoku_a


def umbral_distancia_emas(emacorta: float, emalenta: float, umbral: int):
    """
    Devuelve True si la distancia entre emas es menor al umbral.
    Si las emas están 'pegadas' hay poca volatilidad
    :return bool:
    """
    if emacorta > emalenta:
        return math.trunc(((emacorta/emalenta) - 1) * 1000) < umbral
    elif emalenta >= emacorta:
        return math.trunc(((emalenta/emacorta) - 1) * 1000) < umbral


def obtener_distancia_precio_maximo(maximo: float, precio_actual: float):
    """
    Devuelve la distancia entre el máximo y el precio actual expresado en %
    Ej: 1.87%
    :return float:
    """
    return abs(round((((maximo / precio_actual) - 1) * 100), 2))


def obtener_distancia_precio_minimo(minimo: float, precio_actual: float):
    """
    Devuelve la distancia entre el mínimo y el precio actual expresado en %
    Ej: 1.34%
    :return float:
    """
    return abs(round((((precio_actual / minimo) - 1) * 100), 2))


def obtener_maximo(df_time: pd.DataFrame, df_high: pd.DataFrame):
    """
    Devuelve el precio máximo alcanzado entre las 22:00 (del día anterior) y las 12:00 (del día actual)
    :return float:
    """
    # Establezco la variable 'hoy' al día anterior si cuando se está calculando la hora está entre las 22:00 y las 00:00
    hoy = datetime.now().day
    if datetime.now().hour != 22 and datetime.now().hour != 23:
        hoy = hoy - 1
    maximo_a_devolver = 0
    i = -185
    j = 0
    enc = False
    enc2 = False
    # Primer bucle para posicionarnos a las 12:00 del dia anterior
    while i < 0 and not enc:
        dia_vela = datetime.fromtimestamp(df_time.values[i]).day
        if dia_vela == hoy and datetime.fromtimestamp(df_time.values[i]).hour == 12:
            j = i
            enc = True
        i = i+1
    
    # Recorro todas velas hasta las 22:00
    while j < 0 and not enc2:
        if datetime.fromtimestamp(df_time.values[j]).hour == 22:
            enc2 = True
        else:
            if df_high.values[j] > maximo_a_devolver:
                maximo_a_devolver = df_high.values[j]
        j = j+1

    return maximo_a_devolver


def obtener_minimo(df_time: pd.DataFrame, df_low: pd.DataFrame):
    """
    Devuelve el precio mínimo alcanzado entre las 22:00 (del día anterior) y las 12:00 (del día actual)
    :return float:
    """
    # Establezco la variable 'hoy' al día anterior si cuando se está calculando la hora está entre las 22:00 y las 00:00
    hoy = datetime.now().day
    if datetime.now().hour != 22 and datetime.now().hour != 23:
        hoy = hoy - 1
    minimo_a_devolver = 1000000
    i = -185
    j = 0
    enc = False
    enc2 = False
    # Primer bucle para posicionarnos a las 12:00
    while i < 0 and not enc:
        dia_vela = datetime.fromtimestamp(df_time.values[i]).day
        if dia_vela == hoy and datetime.fromtimestamp(df_time.values[i]).hour == 12:
            j = i
            enc = True
        i = i+1

    # Recorro todas velas hasta las 22:00
    while j < 0 and not enc2:
        if datetime.fromtimestamp(df_time.values[j]).hour == 22:
            enc2 = True
        else:
            if df_low.values[j] < minimo_a_devolver:
                minimo_a_devolver = df_low.values[j]
        j = j+1

    return minimo_a_devolver    


# Modifica los parámetros para cada symbol en base a un backtest realizado previamente.
def configurar_bot(symbol, n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral):
    if symbol == 'BTCUSDT':
        n1 = 0
        n2 = 0
        kama1 = 0
        kama2 = 0
        kama3 = 0
        nvelas = 0
        nvelas2 = 0
        tamanio_vela = 0
        umbral = 0
        return n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral
    elif symbol == 'AVAXUSDT':
        n1 = 5
        n2 = 48
        kama1 = 10
        kama2 = 2
        kama3 = 21
        nvelas = 4
        nvelas2 = 3
        tamanio_vela = 5
        umbral = 7
        return n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral
    elif symbol == 'ETHUSDT':
        n1 = 0
        n2 = 0
        kama1 = 0
        kama2 = 0
        kama3 = 0
        nvelas = 0
        nvelas2 = 0
        tamanio_vela = 0
        umbral = 0
        return n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral
    elif symbol == 'SOLUSDT':
        n1 = 5
        n2 = 56
        kama1 = 10
        kama2 = 4
        kama3 = 31
        nvelas = 8
        nvelas2 = 9
        tamanio_vela = 2
        umbral = 18
        return n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral
    elif symbol == 'DOTUSDT':
        n1 = 0
        n2 = 0
        kama1 = 0
        kama2 = 0
        kama3 = 0
        nvelas = 0
        nvelas2 = 0
        tamanio_vela = 0
        umbral = 0
        return n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral
    elif symbol == 'ETCUSDT':
        n1 = 0
        n2 = 0
        kama1 = 0
        kama2 = 0
        kama3 = 0
        nvelas = 0
        nvelas2 = 0
        tamanio_vela = 0
        umbral = 0
        return n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral
    elif symbol == 'XRPUSDT':
        n1 = 0
        n2 = 0
        kama1 = 0
        kama2 = 0
        kama3 = 0
        nvelas = 0
        nvelas2 = 0
        tamanio_vela = 0
        umbral = 0
        return n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral
    elif symbol == 'TRXUSDT':
        n1 = 5
        n2 = 44
        kama1 = 5
        kama2 = 4
        kama3 = 23
        nvelas = 7
        nvelas2 = 1
        tamanio_vela = 1
        umbral = 5
        return n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral
    elif symbol == 'ADAUSDT':
        n1 = 0
        n2 = 0
        kama1 = 0
        kama2 = 0
        kama3 = 0
        nvelas = 0
        nvelas2 = 0
        tamanio_vela = 0
        umbral = 0
        return n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral
    elif symbol == 'MATICUSDT':
        n1 = 6
        n2 = 55
        kama1 = 6
        kama2 = 3
        kama3 = 24
        nvelas = 9
        nvelas2 = 3
        tamanio_vela = 5
        umbral = 8
        return n1, n2, kama1, kama2, kama3, nvelas, nvelas2, tamanio_vela, umbral


def obtener_decimales_para_bybit(entry_price: float):
    """
    Devuelve el número de decimales de una moneda con los que trabaja Bybit
    Se toma como referencia el entry_price, y en base a ese valor se realizan los cálculos
    TODO: Modificar el parámetro porque si el entry_price resulta ser sin decimales, no será fiable.
    :return int:
    """
    numero = str(entry_price)
    start = numero.find(".")
    numero = numero[start+1:10]
    # Por problemas a la hora de poner la orden, si el número de decimales es 1, debe devolver 0
    if int(str(len(numero))) == 1:
        return 0
    return int(str(len(numero)))


def calcular_apalancamiento(capital: float, pct_riesgo: float, pct_sl: float):
    """
    Calcula el apalancamiento necesario teniendo en cuenta el capital, pct_riesgo y pct_sl establecidos, el apalancamiento en Bybit puede tener hasta 2 decimales

    'Capital' es los usdt que tengo

    'pct_riesgo' es el % de riesgo  ---> 2%     = 0.02

    'pct_sl' es el % de sl          ---> 0.25%  = 0.25
    :return float:
    """
    return float(((capital*(pct_riesgo/100)/pct_sl)*100)/capital).__round__(2)


def hay_posicion(session: HTTP, symbol: str):
    """
    Devuelve True si hay una posición abierta en la moneda pasada por parámetro
    :return bool:
    """
    long = session.my_position(symbol=symbol)['result'][0]['size']                  # Para longs hay que pillar de [0]
    short = session.my_position(symbol=symbol)['result'][-1]['size']                # Para shorts hay que pillar de [-1]
    return not (long == 0 and short == 0)


def comprobar_si_estoy_en_mercado(session: HTTP, symbols: list[str]):
    """
    Esta función tiene dos propósitos:

    1) Función ejecutada al inicio del bot, comprueba si existe alguna posición abierta en alguna moneda.
    Si hay alguna posición abierta, el bot entrará en bucle esperando a que se cierre por SL o TP

    2) Si no hay posición en ninguna, inicializa la variable contador_symbols a 0
    :return int:
    """
    i = 0
    res = 0
    while i < len(symbols):
        print(f'comprobando si hay posicion en {symbols[i]}')
        while hay_posicion(session, symbols[i]):
            # Opcion de loggear "Esperando a que se complete orden... y el lastprice, tp y sl para comprobar si se cumplió lo esperado"
            print(f"{datetime.now().hour}:{datetime.now().minute}:{datetime.now().second}   Posición abierta (previa al inicio del bot) en {symbols[i]}, esperando a que toque TP o SL...")
            time.sleep(60)
            send_message(f"¡TRADE CERRADO! (El bot se inició con un trade activo)\nBOT APAGADO") 
            sys.exit()
        i = i + 1
        time.sleep(1)     
    return res


# Devuelve True si el número de velas que han cerrado por encima del máximo es 4 (se puede poner como parámetro)
def numero_velas_sobre_maximo(maximo, df_close):
    n_velas = 0
    for i in range(-4, 0):
        if df_close.values[i] > maximo:
            n_velas = n_velas + 1
    return n_velas == 4


# Devuelve True si el número de velas que han cerrado por debajo del minimo es 4 (se puede poner como parámetro)
def numero_velas_bajo_minimo(minimo, df_close):
    n_velas = 0
    for i in range(-4, 0):
        if df_close.values[i] < minimo:
            n_velas = n_velas + 1
    return n_velas == 4


# True si el precio está por encima del maximo
def precio_sobre_maximo(lastprice, maximo):
    return lastprice > maximo


# True si el precio está por debajo del minimo
def precio_bajo_minimo(lastprice, minimo):
    return lastprice < minimo
