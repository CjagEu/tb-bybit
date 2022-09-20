from logging import exception
from pybit.usdt_perpetual import HTTP


from herramientas import *
from telegram_bot import send_message
from config import MY_API_KEY, MY_SECRET_KEY
from bot_trader import meter_operacion

import time
import calendar
import pandas as pd
import requests

# Lista de simbolos sobre los que el bot iterará
symbols = ['BTCUSDT']
#symbols = ['BTCUSDT', 'BNBUSDT' ,'AVAXUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT','LTCUSDT', 'ETCUSDT', 'XRPUSDT', 'TRXUSDT','MATICUSDT']

# Listas auxiliares para iterar sobre las monedas y controlar el envío de señales a telegram
posicion_symbols = [0] * len(symbols)
inicio_timers = [0] * len(symbols)

# Intervalo de velas en minutos
tick_interval = '15'

# Parámetros
porcentaje = 1              #5 = 0.5%   2.5 = 0.25%   #1 = 0.10%

session = HTTP(endpoint='https://api.bybit.com', api_key=MY_API_KEY, api_secret=MY_SECRET_KEY)

# Al inicio del bot compruebo que no esté en mercado ya en alguna moneda
contador_symbols = comprobar_si_estoy_en_mercado(session, symbols)

while True:

    final = time.time()
    contador_symbols = 0

    while contador_symbols < len(symbols):
        if posicion_symbols[contador_symbols] == 1:
            # Que pasen 900 segundos (15 mins para volver a enviar una señal si se ha dado recientemente)
            if final - inicio_timers[contador_symbols] >= 900:
                posicion_symbols[contador_symbols] = 0
                inicio_timers[contador_symbols] = 0
            # Si no ha pasado ese tiempo pasa a la siguiente moneda
            else:
                contador_symbols = contador_symbols + 1
                continue
       

        # Devuelve la hora en UTC (2 horas menos)
        now = datetime.now()
        # Convierte now a formato unixtime
        unixtime = calendar.timegm(now.timetuple())
        since = unixtime
        # Empiezo en -200*60 para poder fedear los indicadores
        start = str(since-200*60*int(tick_interval))

        # Url para obtener las velas USDT Perpetual
        url = 'https://api.bybit.com/public/linear/kline?symbol='+symbols[contador_symbols]+'&interval='+tick_interval+'&from='+str(start)

        # Obtener y transformar datos a DataFrame
        data = requests.get(url).json()
        D = pd.DataFrame(data['result'], columns=['id', 'symbol', 'period', 'interval', 'start_at', 'open_time', 'volume', 'open', 'high', 'low', 'close', 'turnover'])

        marketprice = 'https://api.bybit.com/v2/public/tickers?symbol='+symbols[contador_symbols]
        res = requests.get(marketprice)
        data = res.json()
        # Precio actual (debería ser lo mismo que D['close'].values[-1])
        lastprice = float(data['result'][0]['last_price'])

        df_time = D['open_time']
        df_open = D['open']
        df_high = D['high']
        df_low = D['low']
        df_close = D['close']

        # [-1] es la vela actual y [-2] es la vela anterior a la actual
        maximo = obtener_maximo(df_time, df_high)
        minimo = obtener_minimo(df_time, df_low)

        # Se opera entre las 22:00 hasta las 12:00
        if datetime.now().hour == 22 or datetime.now().hour == 23 or datetime.now().hour <= 11:

            # Comprueba si el precio está cerca de un porcentaje dado.
            #precio_cerca_maximo = signal_hasta_maximo(lastprice, maximo, porcentaje)
            #precio_cerca_minimo = signal_hasta_minimo(lastprice, minimo, porcentaje)
            condicion_alerta_maximo = precio_sobre_maximo(lastprice, maximo) 
            condicion_alerta_minimo = precio_bajo_minimo(lastprice, minimo)

            # Devuelve la distancia del precio actual hasta el maximo/minimo (expresado con dos decimales)
            porcentaje_distancia_maximo = obtener_distancia_precio_maximo(maximo, lastprice)
            porcentaje_distancia_minimo = obtener_distancia_precio_minimo(minimo, lastprice)

            # Condición exacta para poner orden condicional
            condicion_exacta_long = numero_velas_bajo_minimo(minimo, df_close)      #condicion_exacta_long = porcentaje_distancia_minimo <= 0.1
            condicion_exacta_short = numero_velas_sobre_maximo(maximo, df_close)    #condicion_exacta_short = porcentaje_distancia_maximo <= 0.1

            # Variables auxiliares para el mensaje de telegram
            log_mensaje_maximo = 'SOBRE' if lastprice > maximo else 'BAJO'
            log_mensaje_minimo = 'BAJO' if lastprice < minimo else 'SOBRE'

        # ----------------------------------------------------------------------------------------------------------------------------------------------------
        # Conexión con bybit
        try:
            #session = HTTP(endpoint='https://api.bybit.com', api_key=MY_API_KEY, api_secret=MY_SECRET_KEY)
            
            print(str(datetime.now().hour) + ":" + str(datetime.now().minute) + ":" + str(datetime.now().second) + "   " + str(symbols[contador_symbols]) + "  " + str(contador_symbols+1) + "     Min: " + str(minimo) + "  Max: " + str(maximo))
            #logger.info(str(datetime.now().hour) + ":" + str(datetime.now().minute) + ":" + str(datetime.utcnow().second) + "   " + str(symbols[contador_symbols]) + "  " + str(contador_symbols+1) + "     Min: " + str(minimo) + "  Max: " + str(maximo))
            #logger.info("Distancia hasta máximo: " + str(porcentaje_distancia_maximo)+"%")
            #logger.info("Distancia hasta mínimo: " + str(porcentaje_distancia_minimo)+"%")

            # Obtener los USDT disponibles que tengo, ['equity'], o si tengo ya una posición lo que me queda estará en ['available_balance']
            disponible_antes = session.get_wallet_balance(coin='USDT')['result']['USDT']['equity']

            # Compruebo condiciones para long (solo opera entre las 22 de la noche y las 12 del mediodia)
            if (datetime.now().hour == 22 or datetime.now().hour == 23 or datetime.now().hour <= 11) and condicion_alerta_minimo:
                #send_message(f"{symbols[contador_symbols]} a {porcentaje_distancia_minimo}%     {log_mensaje_minimo} MÍNIMO")
                if condicion_exacta_long:
                    meter_operacion(session=session, symbol=symbols[contador_symbols], lastprice=lastprice, abrir_long=condicion_exacta_long, abrir_short=False, minimo=minimo, maximo=maximo)
                    while hay_posicion(session, symbols[contador_symbols]):
                        # Opcion de loggear "Esperando a que se complete orden... y el lastprice, tp y sl para comprobar si se cumplió lo esperado"
                        print(f"Posición long abierta en {symbols[contador_symbols]}, esperando a que toque TP o SL...")
                        time.sleep(60)
                    # Comparo el disponible antes del trade y después del trade
                    send_message(f"¡TRADE CERRADO! Resultado: {round(session.get_wallet_balance(coin='USDT')['result']['USDT']['equity']-disponible_antes,2)} USDT\nBOT APAGADO")
                    sys.exit()                                            
                posicion_symbols[contador_symbols] = 1
                inicio_timers[contador_symbols] = time.time()
            # Compruebo condiciones para short (solo entre las 22 de la noche y las 12 del mediodia)
            elif (datetime.now().hour == 22 or datetime.now().hour == 23 or datetime.now().hour <= 11) and condicion_alerta_maximo:
                #send_message(f"{symbols[contador_symbols]} a {porcentaje_distancia_maximo}%     {log_mensaje_maximo} MÁXIMO")
                if condicion_exacta_short:
                    meter_operacion(session=session, symbol=symbols[contador_symbols], lastprice=lastprice, abrir_long=False, abrir_short=condicion_exacta_short, minimo=minimo, maximo=maximo)
                    while hay_posicion(session, symbols[contador_symbols]):
                        # Opcion de loggear "Esperando a que se complete orden... y el lastprice, tp y sl para comprobar si se cumplió lo esperado"
                        print(f"Posición short abierta en {symbols[contador_symbols]}, esperando a que toque TP o SL...")
                        time.sleep(60)
                    # Comparo el disponible antes del trade y después del trade
                    send_message(f"¡TRADE CERRADO! Resultado: {round(session.get_wallet_balance(coin='USDT')['result']['USDT']['equity']-disponible_antes,2)} USDT\nBOT APAGADO") 
                    sys.exit()                 
                posicion_symbols[contador_symbols] = 1
                inicio_timers[contador_symbols] = time.time()

            time.sleep(4)
            contador_symbols = contador_symbols + 1             
        except (Exception,):
            # Posibilidad de mandar mensaje a telegram para avisar
            #send_message(f"El bot se cerró inesperadamente")
            print("el bot fallo en bot_signals")
            contador_symbols = contador_symbols + 1  
            time.sleep(2) 
            pass