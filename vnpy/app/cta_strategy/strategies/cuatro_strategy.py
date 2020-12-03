## 本策略逻辑：
## 1、运用15分钟k线判断市场趋势
## 2、在5分钟k线级别进行交易，开仓逻辑是趋势配合前提下，达到rsi超买或超卖区，从bolling带上轨或下轨开仓，每次1手，固定仓位

from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager
)


class CuatroStrategy(CtaTemplate):
    """"""
    author = "KeKe"

    rsi_signal = 19    # 定义rsi阈值
    rsi_window = 14
    fast_window = 4
    slow_window = 26
    boll_window = 20
    boll_dev = 1.8
    trailing_short = 0.3
    trailing_long = 0.5
    fixed_size = 1

    boll_up = 0
    boll_down = 0
    rsi_value = 0
    rsi_long = 0
    rsi_short = 0
    fast_ma = 0
    slow_ma = 0
    ma_trend = 0
    long_stop = 0
    short_stop = 0
    intra_trade_high = 0
    intra_trade_low = 0

    parameters = [
        "rsi_signal", "rsi_window",
        "fast_window", "slow_window",
        "boll_window", "boll_dev",
        "trailing_long", "trailing_short",
        "fixed_size"
    ]

    variables = [
        "boll_up", "boll_down",
        "rsi_value", "rsi_long", "rsi_short",
        "fast_ma", "slow_ma", "ma_trend",
        "long_stop", "short_stop"
    ]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(CuatroStrategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.rsi_long = 50 + self.rsi_signal     # 用rsi阈值定义rsi超买区域
        self.rsi_short = 50 - self.rsi_signal    # 用rsi阈值定义rsi超卖区域

        self.bg5 = BarGenerator(self.on_bar, 5, self.on_5min_bar)  # 合成5分钟K线
        self.am5 = ArrayManager()                 # 初始化5分钟k线的时间序列

        self.bg15 = BarGenerator(self.on_bar, 15, self.on_15min_bar)  # 合成15分钟k线
        self.am15 = ArrayManager()                # 初始化15分钟k线的时间序列

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(10)             # 载入最近10根bar

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
        self.bg5.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg5.update_bar(bar)     # 将1分钟k线推送入bg5合成5分钟线
        self.bg15.update_bar(bar)    # 将1分钟k线推送入bg15合成15分钟线

    def on_5min_bar(self, bar: BarData):
        """在5分钟级别进行交易"""
        self.cancel_all()

        self.am5.update_bar(bar)
        if not self.am5.inited:
            return

        if not self.ma_trend:           # 如果ma_trend没有初始化，就跳过这根bar
            return

        self.rsi_value = self.am5.rsi(self.rsi_window)   # 生成5分钟线的rsi指标
        self.boll_up, self.boll_down = self.am5.boll(
            self.boll_window, self.boll_dev)             # 生成5分钟线的bolling指标
        boll_width = self.boll_up - self.boll_down       # 赋值boll宽度变量
        ## 当空仓时
        if self.pos == 0:
            self.intra_trade_low = bar.low_price         # 记录最低价，用于追踪买入后最低价
            self.intra_trade_high = bar.high_price       # 记录最高价，用于追踪买入后最高价

            if self.ma_trend > 0 and self.rsi_value >= self.rsi_long:   # 当上升趋势，且进入超买区
                self.buy(self.boll_up, self.fixed_size, True)           # 在bolling带上轨开1手多头单

            elif self.ma_trend < 0 and self.rsi_value <= self.rsi_short:  # 当下降趋势，且进入超卖区
                self.short(self.boll_down, self.fixed_size, True)       # 在bolling带下轨开1手空头仓位
        ## 当持有多头仓时
        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)  # 逐根k线记录到达过的最高价
            self.long_stop = (self.intra_trade_high -
                              self.trailing_long * boll_width)                  # 追踪止损位是最高价*0.5*boll宽度
            self.sell(self.long_stop, abs(self.pos), True, True)                # 在追踪止损价位平所有多头仓
        ## 当持有空头仓时
        elif self.pos < 0:
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)     # 逐根k线记录到达过的最低价
            self.short_stop = (self.intra_trade_low +
                               self.trailing_short * boll_width)                # 追踪止损位
            self.cover(self.short_stop, abs(self.pos), True, True)              # 轧空

        self.put_event()

    def on_15min_bar(self, bar: BarData):
        """在15分钟级别主要用于判断市场的趋势，起筛选作用"""
        self.am15.update_bar(bar)                                              # 推送bar，生成15分钟的时间序列
        if not self.am15.inited:                                               # 判断15分钟线是否已初始化
            return

        self.fast_ma = self.am15.sma(self.fast_window)                         # 生成15分钟级别的移动平均线快线
        self.slow_ma = self.am15.sma(self.slow_window)                         # 生成15分钟级别的移动平均线慢线

        if self.fast_ma > self.slow_ma:        # 当金叉以后
            self.ma_trend = 1                  # 1代表上升趋势
        else:
            self.ma_trend = -1                 # -1代表下降趋势

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
