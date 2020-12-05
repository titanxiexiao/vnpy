## 使用螺纹钢交易的15分钟级别的策略

from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)


class CincoStrategy(CtaTemplate):
    """"""

    author = "用Python的交易员"

    boll_window = 42
    boll_dev = 2.2
    atr_window = 4
    risk_level = 200
    trailing_short = 0.7
    trailing_long = 0.65

    boll_up = 0
    boll_down = 0
    rsi_buy = 0
    rsi_sell = 0
    atr_value = 0
    trading_size = 0

    intra_trade_high = 0
    intra_trade_low = 0
    long_stop = 0
    short_stop = 0

    parameters = [
        "boll_window", "boll_dev", "risk_level",
        "atr_window", 
        "trailing_short", "trailing_long"
    ]

    variables = [
        "boll_up", "boll_down", "atr_value",
        "intra_trade_high", "intra_trade_low",
        "long_stop", "short_stop"
    ]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(CincoStrategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)
        # self.bg = MyGenerator(self.on_bar, self.interval, self.on_15min_bar)   # 合成15分钟k线
        self.am = ArrayManager()

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
        self.bg.update_bar(bar)     # 推送下一根k线

    def on_15min_bar(self, bar: BarData):
        """"""
        self.cancel_all()           # 先取消全部未成交的订单

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        self.boll_up, self.boll_down = am.boll(self.boll_window, self.boll_dev)   # 生成bolling带上下轨
        boll_width = self.boll_up - self.boll_down                                # 计算bolling带宽度
        ## 空仓时
        if self.pos == 0:
            atr_fix = am.atr(self.atr_window)                     # 计算atr指标
            self.trading_size = int(self.risk_level / atr_fix)    # 根据用风险控制水平除以atr得到开仓量，吗每单固定风险，根据atr调整仓位大小

            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price
            self.long_stop = 0
            self.short_stop = 0

            self.buy(self.boll_up, self.trading_size, stop=True)        # 在bolling带上轨开多仓
            self.short(self.boll_down, self.trading_size, stop=True)    # 在bolling带下轨开空仓
        ## 持有多仓时
        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)  # 计算持仓以后到达过的最高价
            self.intra_trade_low = bar.low_price                                # 计算当根k线最低价

            self.long_stop = (self.intra_trade_high -
                              self.trailing_long * boll_width)                  # 用最高价回撤bolling带宽度与参数的方式计算追踪止损位置
            self.sell(self.long_stop, abs(self.pos), stop=True)                      # 在追踪止损位卖出全部持仓
        ## 当持有空头仓位时
        elif self.pos < 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)     # 计算持仓后的最低价

            self.short_stop = (self.intra_trade_low +
                               self.trailing_short * boll_width)                # 计算追踪止损位置
            self.cover(self.short_stop, abs(self.pos), stop=True)                    # 平掉全部空仓

        self.put_event()                                        # 更新vntrader界面数据
        self.sync_data()                                        # 将策略运行数据同步保存到本地

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
