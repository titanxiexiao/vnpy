## 策略运行在股指期货1分钟K线行情上，策略低夏普，但稳定性还不错，2016年底公开到Github上

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


class AtrRsiStrategy(CtaTemplate):
    """"""

    author = "用Python的交易员" # 第一个参数最好是作者，万一泄露时还可以证明是你的

    ## 下面6个是定义策略的参数，参数初始化给默认值
    atr_length = 22
    atr_ma_length = 10
    rsi_length = 5
    rsi_entry = 16   # 计算初始化的时候计算rsi买入或者卖出的阈值
    trailing_percent = 0.8
    fixed_size = 1

    
    ## 下面6个是定义策略的默认变量，变量默认给0，代表初始化
    atr_value = 0
    atr_ma = 0
    rsi_value = 0
    rsi_buy = 0
    rsi_sell = 0
    intra_trade_high = 0
    intra_trade_low = 0

    ## 将策略参数的名称字符串放入parameters列表，告诉vnpy这些是参数
    parameters = [
        "atr_length",
        "atr_ma_length",
        "rsi_length",
        "rsi_entry",
        "trailing_percent",
        "fixed_size"
    ]
    ## 将策略变量的名称字符串放入variables列表，告诉vnpy这些是变量
    variables = [
        "atr_value",
        "atr_ma",
        "rsi_value",
        "rsi_buy",
        "rsi_sell",
        "intra_trade_high",
        "intra_trade_low"
    ]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """想显示在策略页面上的，仅仅用来临时存放和调度的临时变量，可以在__init__中进行定义"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.击页面上初始化按钮执行本函数
        """
        self.write_log("策略初始化")

        self.rsi_buy = 50 + self.rsi_entry     # 定义超买区域
        self.rsi_sell = 50 - self.rsi_entry    # 定义超卖区域

        self.load_bar(10)  # cta策略必须在初始化时加载历史k线，把初始化状态算出来。如果是国内品种，如果至少要10天的历史k线计算，考虑到国内黄金周小长假连同周末经常停止交易10天左右，那么这里最好加载20天的历史k线

    def on_start(self):
        """
        Callback when strategy is started. 点“启动”按钮
        """
        self.write_log("策略启动")  # 页面上信息窗口打印“策略启动”这句话

    def on_stop(self):
        """
        Callback when strategy is stopped. 点“停止”按钮
        """
        self.write_log("策略停止") # 页面上信息窗口打印“策略停止”这句话

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update. 实盘中CTP或Bitmex接口每次推送tick变化时都会调用
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update. K线推送的函数。一定是1分钟k线的推送。用于回测，实盘柜台只推送tick
        """
        self.cancel_all()  # 每根k线推送后，撤销之前一根K线上下的所有未成交订单，会导致比较频繁的撤单

        am = self.am        # 实例化ArrayManager对象
        am.update_bar(bar)  # 将k线推送到ArrayManager
        if not am.inited:   # 如判断ArrayManager初始化状态，如果ArrayManager没有完成初始化状态，就不管他
            return

        atr_array = am.atr(self.atr_length, array=True)  # 传入atr的时间窗口，创建atr时间序列
        self.atr_value = atr_array[-1]      # 取最近的atr数值为atr_value
        self.atr_ma = atr_array[-self.atr_ma_length:].mean()  # 给atr时间序列取最老的atr_ma_length个数据的平均值，赋值给atr_ma
        self.rsi_value = am.rsi(self.rsi_length)   # 传入rsi的时间窗口创建rsi指标时间序列
        ## 没有持仓的情况
        if self.pos == 0:
            self.intra_trade_high = bar.high_price   # 将当根bar的最高价赋值，下面似乎没有用到这个值
            self.intra_trade_low = bar.low_price     # 将当根bar的最低价赋值，下面似乎没有用到这个值
            ## 进场逻辑（5行代码）
            if self.atr_value > self.atr_ma:         # 【过滤】当atr超过其10天均值时，意味着短期波动显著上升
                if self.rsi_value > self.rsi_buy:    # 【信号】当最近的rsi进入超买区域
                    self.buy(bar.close_price + 5, self.fixed_size)  # 按照当根bar的收盘价+5个bp下多头限价单，固定仓位1手
                elif self.rsi_value < self.rsi_sell: # 【信号】当rsi进入超卖区域
                    self.short(bar.close_price - 5, self.fixed_size)  # 按照当根bar的收盘价-5个bp下空头限价单，固定仓位1手
        ## 出场策略，移动止损方法
        ## 持有多头仓位的情况
        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)  # 跟踪买入后价格最高到过什么位置
            self.intra_trade_low = bar.low_price   # 记录当根k线最低价水平

            long_stop = self.intra_trade_high * \
                (1 - self.trailing_percent / 100)         # 最高价*价格固定百分比（回撤）作为出场位置
            self.sell(long_stop, abs(self.pos), stop=True)  # 使用停止单卖出，目的在于不等待价格走完，而是当价格下跌超出回撤比例时，立刻执行卖出操作
        ## 持有空头仓位的情况
        elif self.pos < 0:
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)   # 跟踪买入后价格最低到过什么位置
            self.intra_trade_high = bar.high_price

            short_stop = self.intra_trade_low * \
                (1 + self.trailing_percent / 100)
            self.cover(short_stop, abs(self.pos), stop=True)

        self.put_event()   # 刷新vntrader界面上的数据

    def on_order(self, order: OrderData):
        """
        Callback of new order data update. 委托状态推送：发出委托-券商收到-推到交易所-看到委托在交易所中某档挂单-反馈“未成交状态”-成交1手-委托状态变成“部分成交-成交全部-委托状态变成“全部成交”
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update. 停止单的推送
        """
        pass
