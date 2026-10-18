import tkinter as tk
import random
#настройки
LOT = 100            #акций за одну покупку
TAKE = 1.02          #продаем при росте на 2%
STOP = 0.985         #продаем при падении на 1.5%

#состояния: q0 стоп, q1 анализ, q2 ждем покупку, q3 держим акции, q4 ждем продажу, q5 ошибка
#входы: S - включен, B - покупать, H - продавать, F - ордер исполнен, E - ошибка, R - сброс
names = {"q0": "Стоп", "q1": "Анализ", "q2": "Покупка", "q3": "Позиция", "q4": "Продажа", "q5": "Ошибка"}
outputs = {"q0": "-", "q1": "y1 запрос цен", "q2": "y2 ордер BUY", "q3": "y1 запрос цен",
           "q4": "y3 ордер SELL", "q5": "y4 авария"}


def next_state(q, x):
    #x - словарь входных сигналов ошибка E главнее всего
    if q == "q0":
        return "q1" if x["S"] else "q0"
    if q == "q5":
        return "q0" if x["R"] else "q5"
    if x["E"]:
        return "q5"
    if q == "q1":
        if not x["S"]:
            return "q0"
        return "q2" if x["B"] else "q1"
    if q == "q2":
        return "q3" if x["F"] else "q2"
    if q == "q3":
        return "q4" if x["H"] else "q3"
    if q == "q4":
        return "q1" if x["F"] else "q4"


#скользящая средняя
def sma(data, n):
    return sum(data[-n:]) / n


#данные модели
prices = [100.0]
for i in range(60):
    prices.append(prices[-1] + random.gauss(0, 1))
state = "q0"
cash = 100000.0
shares = 0
buy_price = 0
order_wait = 0       #сколько тактов осталось до исполнения ордера
pause = 0            #пауза после продажи
want_on = False      #сигнал S
want_err = False     #сигнал E (кнопка)
want_reset = False   #сигнал R (кнопка)
running = False
marks = []           #сделки: (номер точки, "BUY"/"SELL")


root = tk.Tk()
root.title("Биржевой робот")
chart = tk.Canvas(root, width=520, height=260, bg="white")
chart.grid(row=0, column=0, padx=5, pady=5)
info = tk.Label(root, text="", justify="left", font=("Courier", 10))
info.grid(row=1, column=0, sticky="w", padx=5)
log = tk.Text(root, height=7, width=100)
log.grid(row=2, column=0, padx=5, pady=5)
buttons = tk.Frame(root)
buttons.grid(row=3, column=0, pady=5)


def write(text):
    log.insert("end", text + "\n")
    log.see("end")


def draw():
    #график цены
    chart.delete("all")
    data = prices[-100:]
    lo = min(data)
    hi = max(data)
    start = len(prices) - len(data)

    def X(i):
        return 10 + (i - start) * 480 / 105

    def Y(v):
        return 250 - (v - lo) / (hi - lo + 0.001) * 230

    for i in range(start + 1, len(prices)):
        chart.create_line(X(i - 1), Y(prices[i - 1]), X(i), Y(prices[i]), fill="blue", width=2)
        if i >= 15:
            chart.create_line(X(i - 1), Y(sma(prices[:i], 5)), X(i), Y(sma(prices[:i + 1], 5)), fill="orange")
            chart.create_line(X(i - 1), Y(sma(prices[:i], 15)), X(i), Y(sma(prices[:i + 1], 15)), fill="green")
    for m in marks:
        if m[0] >= start:
            color = "green" if m[1] == "BUY" else "red"
            chart.create_oval(X(m[0]) - 5, Y(prices[m[0]]) - 5, X(m[0]) + 5, Y(prices[m[0]]) + 5, fill=color)
    chart.create_text(10, 8, anchor="w", font=("Arial", 8),
                      text="синий - цена, оранжевый - SMA5, зеленый - SMA15")

    price = prices[-1]
    info.config(text="Состояние: %s (%s)   выход: %s\n"
                     "Цена %.2f  SMA5 %.2f  SMA15 %.2f\n"
                     "Акций %d  деньги %.0f  итог %.0f" % (
                         state, names[state], outputs[state], price, sma(prices, 5), sma(prices, 15),
                         shares, cash, cash + shares * price - 100000))


def step():
    global state, cash, shares, buy_price, order_wait, pause, want_err, want_reset
    prices.append(max(1, prices[-1] + random.gauss(0, 1)))
    price = prices[-1]
    if order_wait > 0:
        order_wait -= 1
    if pause > 0:
        pause -= 1

    #собираем входы автомата
    x = {"S": want_on, "B": False, "H": False, "F": False, "E": False, "R": want_reset}
    if state != "q0" and state != "q5":
        x["E"] = want_err or random.random() < 0.002
    s5 = sma(prices, 5)
    s15 = sma(prices, 15)
    if s5 > s15 and pause == 0 and cash > price * LOT:
        x["B"] = True
    if shares > 0 and (price > buy_price * TAKE or price < buy_price * STOP or s5 < s15):
        x["H"] = True
    if state in ("q2", "q4") and order_wait == 0:
        x["F"] = True

    old = state
    state = next_state(old, x)
    if state != old:
        write("%s -> %s" % (old, state))
        if state in ("q2", "q4"):
            order_wait = random.randint(1, 3)
        if old == "q2" and state == "q3":
            cash -= price * LOT
            shares = LOT
            buy_price = price
            marks.append((len(prices) - 1, "BUY"))
            write("Купили по %.2f" % price)
        if old == "q4" and state == "q1":
            cash += price * shares
            write("Продали по %.2f (%.2f%%)" % (price, (price / buy_price - 1) * 100))
            shares = 0
            pause = 6
            marks.append((len(prices) - 1, "SELL"))
        if state == "q5":
            write("АВАРИЯ!")
            if shares > 0:       #при аварии закрываем позицию
                cash += price * shares
                shares = 0
                marks.append((len(prices) - 1, "SELL"))
    want_err = False
    want_reset = False
    draw()


def loop():
    if running:
        step()
        root.after(300, loop)


def on_play():
    global running
    running = not running
    if running:
        loop()


def on_on():
    global want_on
    want_on = not want_on
    write("Робот включен" if want_on else "Робот выключен")


def on_err():
    global want_err
    want_err = True


def on_reset():
    global want_reset
    want_reset = True


tk.Button(buttons, text="Пуск / пауза", command=on_play).pack(side="left", padx=3)
tk.Button(buttons, text="Шаг", command=step).pack(side="left", padx=3)
tk.Button(buttons, text="Вкл / выкл робота (S)", command=on_on).pack(side="left", padx=3)
tk.Button(buttons, text="Ошибка (E)", command=on_err).pack(side="left", padx=3)
tk.Button(buttons, text="Сброс (R)", command=on_reset).pack(side="left", padx=3)

write("Нажмите 'Вкл робота', потом 'Пуск'")
draw()
root.mainloop()