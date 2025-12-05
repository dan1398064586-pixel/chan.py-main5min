import os
import ccxt
import time
import pandas as pd
from datetime import datetime
from Common.CEnum import AUTYPE, DATA_FIELD, KL_TYPE
from Common.CTime import CTime
from Common.func_util import kltype_lt_day, str2float
from KLine.KLine_Unit import CKLine_Unit
from .CommonStockAPI import CCommonStockApi

def GetColumnNameFromFieldList(fileds: str):
    _dict = {
        "time": DATA_FIELD.FIELD_TIME,
        "open": DATA_FIELD.FIELD_OPEN,
        "high": DATA_FIELD.FIELD_HIGH,
        "low": DATA_FIELD.FIELD_LOW,
        "close": DATA_FIELD.FIELD_CLOSE,
        "volume": DATA_FIELD.FIELD_VOLUME,
    }
    return [_dict[x] for x in fileds.split(",")]

class CCXT(CCommonStockApi):
    def __init__(self, code, k_type=KL_TYPE.K_DAY, begin_date=None, end_date=None, autype=AUTYPE.QFQ):
        super(CCXT, self).__init__(code, k_type, begin_date, end_date, autype)

    def get_kl_data(self):
        fields = "time,open,high,low,close,volume"
        
        # === 代理配置 ===
        my_proxies = {
            'http': 'http://127.0.0.1:10809', 
            'https': 'http://127.0.0.1:10809',
        }
        
        exchange = ccxt.binance({
            'proxies': my_proxies,
            'timeout': 30000,
            'enableRateLimit': True,
        })

        timeframe = self.__convert_type()
        
        # --- 缓存文件路径 ---
        # 例如: BTC_USDT_5m.csv
        safe_code = self.code.replace('/', '_')
        cache_file = f"{safe_code}_{timeframe}.csv"
        
        # 1. 读取本地缓存
        cached_data = []
        last_timestamp = None
        
        if os.path.exists(cache_file):
            try:
                # 读取 CSV，不包含表头，列顺序：timestamp, open, high, low, close, volume
                df_cache = pd.read_csv(cache_file)
                if not df_cache.empty:
                    # 转换为列表 [ [ts, o, h, l, c, v], ... ]
                    cached_data = df_cache.values.tolist()
                    last_timestamp = int(cached_data[-1][0]) # 获取最后一根K线的时间戳
                    print(f"✅ 读取本地缓存成功：{len(cached_data)} 条 (最新时间: {datetime.fromtimestamp(last_timestamp/1000)})")
            except Exception as e:
                print(f"⚠️ 缓存读取失败，将重新下载: {e}")
                cached_data = []

        # 2. 准备下载
        target_limit = 100000 # 如果没有缓存，首次下载的数量
        new_data = []
        
        # --- 自动重试与增量下载逻辑 ---
        def fetch_page(since=None, params={}):
            for i in range(3):
                try:
                    if since:
                        return exchange.fetch_ohlcv(self.code, timeframe, since=since, limit=1000, params=params)
                    else:
                        return exchange.fetch_ohlcv(self.code, timeframe, limit=1000, params=params)
                except Exception as e:
                    print(f"网络波动，第 {i+1} 次重试... ({e})")
                    time.sleep(2)
            raise Exception("连接交易所失败")

        try:
            if last_timestamp:
                # === 增量模式：只下载比缓存更新的数据 ===
                print(">> 正在检查新数据...")
                # since = 最后一根时间 + 1ms，避免重复
                current_batch = fetch_page(since=last_timestamp + 1)
                while current_batch:
                    new_data.extend(current_batch)
                    print(f"   已获取新数据: {len(new_data)} 条")
                    
                    # 如果取满了1000条，可能还有更多，继续取
                    if len(current_batch) < 1000:
                        break
                        
                    last_ts = current_batch[-1][0]
                    current_batch = fetch_page(since=last_ts + 1)
                    time.sleep(0.1)
            else:
                # === 首次模式：下载最近的 target_limit 根 ===
                print(f">> 本地无缓存，开始下载最近 {target_limit} 条数据...")
                current_batch = fetch_page()
                new_data = current_batch
                
                while len(new_data) < target_limit:
                    if not current_batch: break
                    first_ts = current_batch[0][0]
                    params = {'endTime': first_ts - 1}
                    
                    print(f"   加载历史中... (当前 {len(new_data)}/{target_limit})")
                    current_batch = fetch_page(params=params)
                    if not current_batch: break
                    
                    new_data = current_batch + new_data
                    time.sleep(0.1)
                
                # 如果超出了，只保留最后 target_limit 条
                if len(new_data) > target_limit:
                    new_data = new_data[-target_limit:]

        except Exception as e:
            print(f"❌ 数据同步中断: {e}")
            # 如果是增量更新失败，至少可以用旧缓存跑，不抛出异常
            if not cached_data:
                raise e

        # 3. 合并与去重
        if new_data:
            print(f"💾 合并并保存 {len(new_data)} 条新数据到本地...")
            total_data = cached_data + new_data
            
            # 使用字典去重 (以时间戳为key)，防止重叠
            data_dict = {x[0]: x for x in total_data}
            # 按时间排序
            sorted_data = sorted(data_dict.values(), key=lambda x: x[0])
            
            # 保存回 CSV
            df_save = pd.DataFrame(sorted_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_save.to_csv(cache_file, index=False)
            
            final_data = sorted_data
        else:
            print(">> 没有新数据，直接使用缓存。")
            final_data = cached_data

        # 4. 生成 K 线对象返回给主程序
        for item in final_data:
            time_obj = datetime.fromtimestamp(item[0] / 1000)
            item_data = [time_obj, item[1], item[2], item[3], item[4], item[5]]
            yield CKLine_Unit(self.create_item_dict(item_data, GetColumnNameFromFieldList(fields)), autofix=True)

    def SetBasciInfo(self): pass
    @classmethod
    def do_init(cls): pass
    @classmethod
    def do_close(cls): pass

    def __convert_type(self):
        _dict = {
            KL_TYPE.K_DAY: '1d', KL_TYPE.K_WEEK: '1w', KL_TYPE.K_MON: '1M',
            KL_TYPE.K_1M: '1m', KL_TYPE.K_5M: '5m', KL_TYPE.K_15M: '15m',
            KL_TYPE.K_30M: '30m', KL_TYPE.K_60M: '1h', 
        }
        return _dict[self.k_type]

    def parse_time_column(self, inp):
        if isinstance(inp, datetime):
            is_day_level = not kltype_lt_day(self.k_type)
            return CTime(inp.year, inp.month, inp.day, inp.hour, inp.minute, auto=is_day_level)
        return inp

    def create_item_dict(self, data, column_name):
        for i in range(len(data)):
            if i == 0: data[i] = self.parse_time_column(data[i])
            else: data[i] = str2float(data[i])
        return dict(zip(column_name, data))