from herramientas import *
from telegram_bot import send_message
import time


def meter_operacion(session, symbol, lastprice, abrir_long, abrir_short, minimo, maximo):    
    
    # Inicialización de las variables, necesario según si la orden es un long o un short
    long = session.my_position(symbol=symbol)['result'][0]['size']                 # Para longs hay que pillar de [0]
    short = session.my_position(symbol=symbol)['result'][-1]['size']                # Para shorts hay que pillar de [-1]

    # Obtener los USDT disponibles que tengo, ['equity'], o si tengo ya una posición lo que me queda estará en ['available_balance']
    disponible = session.get_wallet_balance(coin='USDT')['result']['USDT']['equity']
    pct_riesgo = 2
    pct_sl = 0.6

    if long > 0 and short == 0:
        # Side será 'Buy'
        position_side = session.my_position(symbol=symbol)['result'][0]['side']
        # Precio de entrada de una orden abierta
        entry_price = session.my_position(symbol=symbol)['result'][0]['entry_price']
        # Precio de stop_loss de una orden abierta
        stop_loss = session.my_position(symbol=symbol)['result'][0]['stop_loss']
        # Tamaño de la posición
        position_size = session.my_position(symbol=symbol)['result'][0]['size']
        # Apalancamiento en Longs
        apalancamiento = session.my_position(symbol=symbol)['result'][0]['leverage']

    elif long == 0 and short > 0:
        # Side será 'Sell'
        position_side = session.my_position(symbol=symbol)['result'][-1]['side']
        # Precio de entrada de una orden abierta
        entry_price = session.my_position(symbol=symbol)['result'][-1]['entry_price']
        # Precio de stop_loss de una orden abierta
        stop_loss = session.my_position(symbol=symbol)['result'][-1]['stop_loss']
        # Tamaño de la posición
        position_size = session.my_position(symbol=symbol)['result'][-1]['size']
        # Apalancamiento en Shorts
        apalancamiento = session.my_position(symbol=symbol)['result'][-1]['leverage']
        # Si la posición es para un short, el número debe ser negativo
        if position_side == 'Sell':
            position_size = position_size * -1
    else:
        # No debería entrar nunca por aquí
        position_side = ''
        position_size = 0
        entry_price = 0
        stop_loss = 0
        
    try:
        # Si no estoy en posición
        if position_size == 0:

            # Generar apalancamiento aleatorio
            apalancamiento = generar_apalancamiento_aleatorio()
            session.set_leverage(symbol=symbol, buy_leverage=apalancamiento, sell_leverage=apalancamiento)
            time.sleep(1)
            # Establecer apalancamiento real
            apalancamiento = calcular_apalancamiento(capital=disponible, riesgo=pct_riesgo, sl=pct_sl)
            session.set_leverage(symbol=symbol, buy_leverage=apalancamiento, sell_leverage=apalancamiento)

            if abrir_long:
                # LONG (qty es cantidad de monedas, por eso uso la función get_qty())
                # Busco ratio 1:2   [SL: 0.5% <--> TP: 1%]
                sl = float(lastprice*0.994).__round__(obtener_decimales_para_bybit(entry_price=lastprice))
                tp = float(lastprice*1.01).__round__(obtener_decimales_para_bybit(entry_price=lastprice))
                session.place_active_order(
                                    side='Buy',
                                    symbol=symbol,
                                    order_type='Market',
                                    qty=get_qty(symbol=symbol, disponible=disponible, apalancamiento=apalancamiento, lastprice=lastprice),
                                    price=lastprice,
                                    stop_loss=sl,
                                    take_profit=tp,
                                    time_in_force='GoodTillCancel',
                                    reduce_only=False,
                                    close_on_trigger=False)
                #session.place_conditional_order(side                = 'Buy',symbol              = symbol,order_type          = 'Limit',qty                 = get_qty(symbol=symbol, disponible=disponible, apalancamiento=apalancamiento, lastprice=minimo),price               = minimo,base_price          = lastprice,stop_px             = minimo,                                        stop_loss           = sl,take_profit         = tp,time_in_force       = 'GoodTillCancel',trigger_by          = 'LastPrice',reduce_only         = False,close_on_trigger    = False)
                #send_message(f"ORDEN CONDICIONAL LONG PENDIENTE en {symbol}.\nEN: {minimo}\nSL: {sl}\nTP: {tp}")
                send_message(f"ORDEN A MERCADO LONG en {symbol}.\nAP: {apalancamiento}x\nPR:{pct_riesgo}%\nPS:{pct_sl}%\nEN: {lastprice}\nSL: {sl}\nTP: {tp}")
                time.sleep(2)
            elif abrir_short:
                # SHORT (qty es cantidad de monedas, por eso uso la función get_qty())
                # Busco ratio 1:2   [SL: 0.5% <--> TP: 1%]
                sl = float(lastprice*1.006).__round__(obtener_decimales_para_bybit(entry_price=lastprice))
                tp = float(lastprice*0.99).__round__(obtener_decimales_para_bybit(entry_price=lastprice))
                session.place_active_order(
                    side='Sell',
                    symbol=symbol,
                    order_type='Market',
                    qty=get_qty(symbol=symbol, disponible=disponible, apalancamiento=apalancamiento, lastprice=lastprice),
                    price=lastprice,
                    stop_loss=sl,
                    take_profit=tp,
                    time_in_force='GoodTillCancel',
                    reduce_only=False,
                    close_on_trigger=False)
                #session.place_conditional_order(side                = 'Sell',symbol              = symbol,order_type          = 'Limit',qty                 = get_qty(symbol=symbol, disponible=disponible, apalancamiento=apalancamiento, lastprice=maximo),price               = maximo,base_price          = lastprice,stop_px             = maximo, stop_loss           = sl,take_profit         = tp,time_in_force       = 'GoodTillCancel',trigger_by          = 'LastPrice',                                    reduce_only         = False,close_on_trigger    = False)
                #send_message(f"ORDEN CONDICIONAL SHORT PENDIENTE en {symbol}.\nEN: {maximo}\nSL: {sl}\nTP: {tp}") 
                send_message(f"ORDEN A MERCADO SHORT en {symbol}.\nAP: {apalancamiento}x\nPR:{pct_riesgo}%\nPS:{pct_sl}%\nEN: {lastprice}\nSL: {sl}\nTP: {tp}")
                time.sleep(2)        


#        long  = session.my_position(symbol=symbols[contador_symbols])['result'][0]['size']                 # Para longs hay que pillar de [0]
#        short = session.my_position(symbol=symbols[contador_symbols])['result'][-1]['size']                # Para shorts hay que pillar de [-1]

        """GESTIÓN DE LA OPERATIVA LONG"""   
#        while long:
#            print("Estoy en long, esperando a que toque TP o SL...")
#            time.sleep(2)
        # Si estoy en LONG
#       if position_size > 0:
#           session.set_trading_stop(symbol=symbol,side=position_side,stop_loss=float(entry_price*0.995).__round__(obtener_decimales_para_bybit(symbol=symbol, entry_price=entry_price)))  
        
        """GESTIÓN DE LA OPERATIVA SHORT"""  
#        while short:
#            print("Estoy en short, esperando a que toque TP o SL...")
#            time.sleep(2)
        # Si estoy en SHORT
#       if position_size < 0:
#           session.set_trading_stop(symbol=symbol,side=position_side,stop_loss=float(entry_price*1.005).__round__(obtener_decimales_para_bybit(symbol=symbol, entry_price=entry_price)))

        """A LA ESPERA DE QUE SE ACTIVE LA ORDEN""" 
#        while str(session.query_conditional_order(symbol=symbol)['result'][-1]['order_status']) == 'Untriggered':
#            print(f"{datetime.now().hour}:{datetime.now().minute}:{datetime.now().second}  Orden puesta en {symbol}, esperando a que entre, estado: {session.query_conditional_order(symbol=symbol)['result'][-1]['order_status']}")
#            time.sleep(60)
    
#        send_message(f"¡ORDEN ENTRÓ!")

    except (Exception,):
        # Posibilidad de mandar mensaje a telegram para avisar
        send_message(f"Exception en bot_trader.py")
        #print("el bot fallo en bot_trader, porque ya se triggereó la orden")
        pass


"""
    # MIRAR QUE ES REDUCE_ONLY Y CLOSE_ON_TRIGGER
    #
    # Para ver cual es mi SL                                => print(session.my_position(symbol=symbol)['result'][0]['stop_loss'])
    # Para ver si estoy en posicion                         => session.my_position(symbol=symbol)['result'][0]['size']                      (0 no, > 0 LONG, < 0 SHORT)
    # Para modificar el apalancamiento                      => session.set_leverage(symbol=symbol, buy_leverage=5, sell_leverage=10)
    # Para comprobar el estado de una orden                 => session.get_active_order(symbol=symbol)
    # Para ver el ultimo precio en mercado                  => float(session.latest_information_for_symbol(symbol=symbol)['result'][0]['last_price'])
    # Para ver los USDT que tengo en la billetera           => session.get_wallet_balance(coin='USDT')['result']['USDT']['equity']
    # Igual que arriba pero si tengo posicion abierta       => session.get_wallet_balance(coin='USDT')['result']['USDT']['available_balance']
    # Para modificar el SL de una orden ABIERTA             => session.set_trading_stop(symbol=symbol,side='Buy',stop_loss=24.30)
    # Para saber el entry_price de la orden ABIERTA         => session.my_position(symbol=symbol)['result'][0]['entry_price']
    # Dataframe de 2 filas con información de la posicion   => df_posiciones_buy_or_sell = pd.DataFrame(session.my_position(symbol=symbol)['result'])
    # Obtener comisión por órdenes a mercado                => session.query_trading_fee_rate(symbol=symbol)['result']['taker_fee_rate']
    # Obtener comisión por órdenes límite                   => session.query_trading_fee_rate(symbol=symbol)['result']['maker_fee_rate']

    # Importante para los Stop Loss, el parámetro de __round__(n) debe ser el numero de decimales que tenga la moneda en Bybit, sino da error al poner el Stop Loss
    # Establecer SL para SHORTS                             => session.set_trading_stop(symbol=symbol,side=position_side,stop_loss=float(entry_price*1.01).__round__(3))
    # Establecer SL para LONGS                              => session.set_trading_stop(symbol=symbol,side=position_side,stop_loss=float(entry_price*0.99).__round__(3))
"""