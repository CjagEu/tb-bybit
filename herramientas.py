from datetime import datetime
from telegram_bot import send_message

import time
import pandas as pd
import math
import random
import logging
import sys


# Para logging
FILENAME_LOGGING = 'log.txt'
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.addHandler(logging.FileHandler(FILENAME_LOGGING))


# Tomo las nvelas anteriores para comprobar que la ema rapida esté por debajo, probar con otros valores
def signal_long(emarapida, emalenta, nvelas):
    res = True
    for i in range (-nvelas, 0):
        if emarapida.values[i] > emalenta.values[i]:
            res = False
            break
    return res


# Tomo las nvelas anteriores para comprobar que la ema rapida esté por encima, probar con otros valores
def signal_short(emarapida, emalenta, nvelas):
    res = True
    for i in range (-nvelas, 0):
        if emarapida.values[i] < emalenta.values[i]:
            res = False
            break
    return res


def signal_kama(open, close, kama, nvelas2):
    contador = 0
    for i in range(-nvelas2, 0):
        vela_alcista = open.values[i] < close.values[i]
        vela_bajista = open.values[i] > close.values[i]
        if vela_alcista:
            if kama.values[i] >= open.values[i] and kama.values[i] <= close.values[i]:
                contador = contador + 1
        else:
            if kama.values[i] <= open.values[i] and kama.values[i] >= close.values[i]:
                contador = contador + 1
    return contador <= (nvelas2/2)


# Calcula la cantidad que hay que poner en la orden teniendo en cuenta el apalancamiento y el disponible (en USDT) de la cuenta
# si quiero poner la máxima cantidad posible seria: (disponible * apalancamiento)/lastprice
# Le quito 5 usdt para asegurarme de que entre bien las ordenes condicionales
def get_qty(symbol, disponible, apalancamiento, lastprice):
    # Condición especial para BTC, solo se pueden poner órdenes con 3 decimales y para asegurar que el redondeo no supere mi dinero le resto 0.001
    if symbol == 'BTCUSDT':
        return round((((disponible-5) * apalancamiento) / lastprice), 3) - 0.001
    # Condición especial para ETH, solo se pueden poner órdenes con 2 decimales y para asegurar que el redondeo no supere mi dinero le resto 0.01
    elif symbol == 'ETHUSDT':
        return round((((disponible - 5) * apalancamiento) / lastprice), 2) - 0.01
    # Si devuelve por aquí es que el precio de la moneda permite que la cantidad sea mayor que 0.algo
    return math.floor(((disponible-5) * apalancamiento) / lastprice)


# Devuelve true si el cuerpo de la vela anterior fue menor a tamanio_vela (open y close deberían estar al revés pero así funciona mejor...)
def filtro_vela_alcista(open, close, tamanio_vela):
    return ((open / close) * 1000) - 1000 <= tamanio_vela


# Devuelve true si el cuerpo de la vela anterior fue menor a tamanio_vela (open y close deberían estar al revés pero así funciona mejor...)
def filtro_vela_bajista(open, close, tamanio_vela):
    return ((close / open) * 1000) - 1000 <= tamanio_vela


# Si el cuerpo de la vela está dentro de la nube devuelve True (probar con high y low)
def dentro_de_nube(ichimoku_a, ichimoku_b, open, close):
    res = False
    if ichimoku_a > ichimoku_b:
        # a > b: Nube verde
        if ichimoku_b < open and ichimoku_b < close and ichimoku_a > open and ichimoku_a > close:
            res = True 
    else:
        # b > a: Nube Roja
        if ichimoku_a < open and ichimoku_a < close and ichimoku_b > open and ichimoku_b > close:
            res = True
    return res  


# No Long si el precio está por encima de una nube verde
def filtro_nube_verde(ichimoku_a, ichimoku_b, close):
    return ichimoku_a > ichimoku_b and close > ichimoku_a


# No Short si el precio está por debajo de una nube roja
def filtro_nube_roja(ichimoku_a, ichimoku_b, close):
    return ichimoku_b > ichimoku_a and close < ichimoku_a


# Devuelve True si la distancia entre emas es menor a cierto umbral
def umbral_distancia_emas(emacorta, emalenta, umbral):
    if emacorta > emalenta:
        return math.trunc(((emacorta/emalenta) - 1) * 1000) < umbral
    elif emalenta >= emacorta:
        return math.trunc(((emalenta/emacorta) - 1) * 1000) < umbral


# Si el porcentaje es 0.5%, el parámetro será 5
def signal_hasta_maximo(precio_actual, maximo, porcentaje):
    return abs(round((((maximo / precio_actual) - 1) * 1000), 1)) <= porcentaje


# Si el porcentaje es 0.5%, el parámetro será 5
def signal_hasta_minimo(precio_actual, minimo, porcentaje):
    return abs(round((((precio_actual / minimo) - 1) * 1000), 1)) <= porcentaje


# Devuelve la distancia entre el máximo y el precio actual expresado en %
def obtener_distancia_precio_maximo(maximo, precio_actual):
    return abs(round((((maximo / precio_actual) - 1) * 100), 2))


# Devuelve la distancia entre el mínimo y el precio actual expresado en %
def obtener_distancia_precio_minimo(minimo, precio_actual):
    return abs(round((((precio_actual / minimo) - 1) * 100), 2))


# Obtiene el máximo precio alcanzado entre las 12 y las 22
def obtener_maximo(df_time, df_high):
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


# Obtiene el mínimo precio alcanzado entre las 12 y las 22
def obtener_minimo(df_time, df_low):
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
        return n1,n2,kama1,kama2,kama3,nvelas,nvelas2,tamanio_vela,umbral
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
        return n1,n2,kama1,kama2,kama3,nvelas,nvelas2,tamanio_vela,umbral
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
        return n1,n2,kama1,kama2,kama3,nvelas,nvelas2,tamanio_vela,umbral
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
        return n1,n2,kama1,kama2,kama3,nvelas,nvelas2,tamanio_vela,umbral
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
        return n1,n2,kama1,kama2,kama3,nvelas,nvelas2,tamanio_vela,umbral
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
        return n1,n2,kama1,kama2,kama3,nvelas,nvelas2,tamanio_vela,umbral
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
        return n1,n2,kama1,kama2,kama3,nvelas,nvelas2,tamanio_vela,umbral
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
        return n1,n2,kama1,kama2,kama3,nvelas,nvelas2,tamanio_vela,umbral
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
        return n1,n2,kama1,kama2,kama3,nvelas,nvelas2,tamanio_vela,umbral
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
        return n1,n2,kama1,kama2,kama3,nvelas,nvelas2,tamanio_vela,umbral


# Obtiene el numero de decimales de una moneda, si justo el entry_price tiene menos decimales puede haber problemas...
def obtener_decimales_para_bybit(entry_price):
    numero = str(entry_price)
    start = numero.find(".")
    numero = numero[start+1:10]
    # Por problemas a la hora de poner la orden, si el número de decimales es 1, debe devolver 0
    if int(str(len(numero))) == 1:
        return 0
    return int(str(len(numero)))


# Calcula el tamaño de la posicion, y por tanto el apalancamiento necesario
def calcular_apalancamiento(capital, riesgo, sl):
    # capital es los usdt que tengo
    # riesgo es el % de riesgo  ---> 2%     = 0.02
    # sl es el % de sl          ---> 0.25%  = 0.25
    return float(((capital*(riesgo/100)/sl)*100)/capital).__round__(2)


# Devuelve True si hay una posicion abierta o False si no hay posicion
def hay_posicion(session, symbol):
    long  = session.my_position(symbol=symbol)['result'][0]['size']                 # Para longs hay que pillar de [0]
    short = session.my_position(symbol=symbol)['result'][-1]['size']                # Para shorts hay que pillar de [-1]
    return not (long == 0 and short == 0)


# Genera un numero aleatorio para evitar el error de pybit y forzar el cambio de apalancamiento
# TODO Establecer dos variables apalancamiento distintas para long y short para reducir la probabilidad de que se repita el numero
def generar_apalancamiento_aleatorio():
    return round(random.uniform(1,10), 1)


# Comprueba al iniciar el bot si hay alguna posición, si hay entra en bucle hasta que se cierre por sl o tp
def comprobar_si_estoy_en_mercado(session, symbols):
    i = 0
    res = 0
    while i < len(symbols):
        print(f'comprobando si hay posicion en {symbols[i]}')
        while hay_posicion(session, symbols[i]):
            # Opcion de loggear "Esperando a que se complete orden... y el lastprice, tp y sl para comprobar si se cumplió lo esperado"
            print(f"Posición short abierta en {symbols[i]}, esperando a que toque TP o SL...")
            time.sleep(60)
            # Comparo el disponible antes del trade y después del trade
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
