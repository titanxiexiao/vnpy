from datetime import time

from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    Direction,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)
from vnpy.trader.constant import Interval


class SuperComboStrategy(CtaTemplate):
    """"""
    author = "用Python的交易员"

    # Parameters
    thrust_long = 0.32
    trailing_long = 0.35

    thrust_short = 0.4
    trailing_short = 0.8

    trading_size = 1

    # Variables
    day_open = 0
    day_high = 0
    day_low = 0
    sum_range = 0

    long_entry = 0
    short_entry = 0
    intra_trade_high = 0
    intra_trade_low = 0
    long_stop = 0
    short_stop = 0
    last_bar = None

    parameters = [
        "thrust_long", "trailing_long",
        "thrust_short", "trailing_short",
        "trading_size"
    ]

    variables = [
        "day_high", "day_low", "sum_range", "long_entry", "short_entry",
        "intra_trade_high", "intra_trade_low", "long_stop", "short_stop"
    ]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar)

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        self.load_bar(10)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.cancel_all()

        if not self.last_bar:
            self.last_bar = bar
            return

        # For a new day, update all entry_range
        if bar.datetime.day != self.last_bar.datetime.day:  # 当根k线的日期不同于上一根k线的日期，即换日了
            self.sum_range = self.day_high - self.day_low   # 计算日内震幅
            self.day_open = bar.open_price                  # 赋值当前k线开盘价
            self.day_high = bar.high_price                  # 计算当根k线最高价
            self.day_low = bar.low_price                    # 计算当根k线最低价

            long_entry_range = self.thrust_long * self.sum_range  # 用波幅计算做多开仓点位
            self.long_entry = self.day_open + long_entry_range    # 开盘价上浮long_entry_range则开仓

            short_entry_range = self.thrust_short * self.sum_range  # 用波幅计算做空开仓点位
            self.short_entry = self.day_open - short_entry_range    # 开盘价下浮short_entry_range则开仓
        # Otherwise update daily high/low price
        else:                                                      # 否则，没有换日的情况下
            self.day_high = max(self.day_high, bar.high_price)     # 记录到过的k线最高价
            self.day_low = min(self.day_low, bar.low_price)        # 记录到过的k线最低价

            self.long_entry = max(self.long_entry, self.day_high)  # 以最高价作为多头开仓点
            self.short_entry = min(self.short_entry, self.day_low) # 以最低价作为空头开仓点

        # Only open positions before 14:55   只在14:55之前开仓
        if bar.datetime.time() < time(14, 55):
            # No pos                        没有持仓的情况
            if not self.pos:
                self.intra_trade_low = bar.low_price    # intra_trade_low用来记录持仓后的最低点
                self.intra_trade_high = bar.high_price  # intra_trade_high用来记录持仓后的最高点

                if bar.close_price > self.day_open:     # 当收盘价突破开盘价
                    self.buy(self.long_entry, self.trading_size, True, True)  # 下多头限价单
                else:
                    self.short(self.short_entry, self.trading_size, True, True)  # 当收盘价未突破开盘价，下空头限价单
            # Long pos                       持有多头仓位的情况
            elif self.pos > 0:
                self.intra_trade_high = max(
                    self.intra_trade_high, bar.high_price)     # 记录买入后的最高价
                self.long_stop = self.intra_trade_high * \
                    (1 - self.trailing_long / 100)             # 计算追击止损位，最高价回撤比例
                self.sell(self.long_stop, abs(self.pos), True, True)  # 在追击止损卖出多头仓位
            # Short pos                     持有空头仓位的情况
            else:
                self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
                self.short_stop = self.intra_trade_low * \
                    (1 + self.trailing_short / 100)
                self.cover(self.short_stop, abs(self.pos), True, True)
        # Close all positions after 14:55   # 当14:55之后，无论持有多仓还是空头仓，均只卖出，不买入
        else:
            if self.pos > 0:
                self.sell(bar.close_price - 10, abs(self.pos), True, True)   # 按当根bar收盘价下浮10个bp的基数，卖出全部持仓
            elif self.pos < 0:
                self.cover(bar.close_price + 10, abs(self.pos), True, True)

        self.last_bar = bar
        self.put_event()

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        pass

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
