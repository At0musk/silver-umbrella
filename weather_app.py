#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天气获取小程序 - Weather App
使用 Open-Meteo API 获取实时天气信息

安装依赖:
    pip install requests schedule rich

运行命令:
    python weather_app.py
    python weather_app.py --city 上海
    python weather_app.py --city 北京 --interval 60

参数说明:
    --city     指定城市名称，支持中文（默认：北京）
    --interval 指定刷新间隔分钟数（默认：30）

功能特性:
    - 自动将城市名转换为经纬度
    - 定时获取实时天气数据
    - 美观的彩色控制台输出
    - 自动记录日志到 weather.log
    - 完善的错误处理机制
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, Optional

import requests
import schedule
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# 全局控制台对象
console = Console()


def setup_logging() -> None:
    """
    配置日志记录
    设置日志格式、级别和输出文件
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler('weather.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def get_weather_description(code: int) -> str:
    """
    将 WMO Weather interpretation codes 转换为中文描述
    
    参数:
        code: WMO 天气代码
    
    返回:
        对应的中文天气描述
    """
    weather_codes = {
        0: "晴朗 ☀️",
        1: "多云 🌤️",
        2: "多云 ⛅",
        3: "阴天 ☁️",
        45: "雾 🌫️",
        48: "雾凇 🌫️",
        51: "毛毛雨 🌦️",
        53: "小雨 🌦️",
        55: "中雨 🌧️",
        56: "冻雨 🌧️",
        57: "冻雨 🌧️",
        61: "小雨 🌧️",
        63: "中雨 🌧️",
        65: "大雨 🌧️",
        66: "冻雨 🌨️",
        67: "冻雨 🌨️",
        71: "小雪 🌨️",
        73: "中雪 ❄️",
        75: "大雪 ❄️",
        77: "雪粒 🌨️",
        80: "阵雨 🌦️",
        81: "强阵雨 🌧️",
        82: "暴雨 🌧️",
        85: "阵雪 🌨️",
        86: "强阵雪 ❄️",
        95: "雷雨 ⛈️",
        96: "雷雨伴冰雹 ⛈️",
        99: "强雷雨伴冰雹 ⛈️",
    }
    return weather_codes.get(code, f"未知天气 ({code})")


def get_coordinates(city: str) -> Optional[tuple]:
    """
    通过 Open-Meteo 地理编码 API 获取城市经纬度
    
    参数:
        city: 城市名称（支持中文）
    
    返回:
        (纬度, 经度) 元组，失败返回 None
    """
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city,
        "count": 1,
        "language": "zh",
        "format": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "results" not in data or not data["results"]:
            console.print(f"[red]错误：找不到城市 '{city}'，请检查城市名称是否正确[/red]")
            logging.error(f"城市 '{city}' 未找到")
            return None
        
        result = data["results"][0]
        lat = result["latitude"]
        lon = result["longitude"]
        country = result.get("country", "未知国家")
        
        logging.info(f"成功获取 '{city}' 的坐标: 纬度 {lat}, 经度 {lon}, 国家: {country}")
        return (lat, lon)
        
    except requests.exceptions.Timeout:
        console.print("[red]错误：地理编码请求超时，请检查网络连接[/red]")
        logging.error("地理编码请求超时")
    except requests.exceptions.RequestException as e:
        console.print(f"[red]错误：地理编码请求失败 - {e}[/red]")
        logging.error(f"地理编码请求失败: {e}")
    except json.JSONDecodeError:
        console.print("[red]错误：地理编码响应解析失败[/red]")
        logging.error("地理编码响应 JSON 解析失败")
    except KeyError as e:
        console.print(f"[red]错误：地理编码响应格式异常 - 缺少字段 {e}[/red]")
        logging.error(f"地理编码响应格式异常: {e}")
    
    return None


def get_current_weather(lat: float, lon: float) -> Optional[Dict]:
    """
    通过 Open-Meteo API 获取当前天气数据
    
    参数:
        lat: 纬度
        lon: 经度
    
    返回:
        包含天气数据的字典，失败返回 None
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "wind_speed_10m",
            "weather_code"
        ],
        "timezone": "auto"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "current" not in data:
            console.print("[red]错误：天气数据格式异常[/red]")
            logging.error("天气 API 响应缺少 'current' 字段")
            return None
        
        current = data["current"]
        weather_data = {
            "temperature": current.get("temperature_2m"),
            "apparent_temperature": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
            "time": current.get("time")
        }
        
        logging.info(f"成功获取天气数据: {weather_data}")
        return weather_data
        
    except requests.exceptions.Timeout:
        console.print("[red]错误：天气请求超时，请检查网络连接[/red]")
        logging.error("天气 API 请求超时")
    except requests.exceptions.RequestException as e:
        console.print(f"[red]错误：天气请求失败 - {e}[/red]")
        logging.error(f"天气 API 请求失败: {e}")
    except json.JSONDecodeError:
        console.print("[red]错误：天气响应解析失败[/red]")
        logging.error("天气 API 响应 JSON 解析失败")
    except KeyError as e:
        console.print(f"[red]错误：天气响应格式异常 - 缺少字段 {e}[/red]")
        logging.error(f"天气 API 响应格式异常: {e}")
    
    return None


def print_weather(data: Dict, city: str) -> None:
    """
    使用 Rich 库美化打印天气信息
    
    参数:
        data: 天气数据字典
        city: 城市名称
    """
    if not data:
        return
    
    # 获取当前时间
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 获取天气描述
    weather_code = data.get("weather_code", -1)
    weather_desc = get_weather_description(weather_code)
    
    # 提取数据
    temp = data.get("temperature", "N/A")
    apparent_temp = data.get("apparent_temperature", "N/A")
    humidity = data.get("humidity", "N/A")
    wind_speed = data.get("wind_speed", "N/A")
    
    # 创建表格
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("项目", style="cyan", justify="right")
    table.add_column("数值", style="white")
    
    table.add_row("温度:", f"{temp} °C" if temp != "N/A" else "N/A")
    table.add_row("体感温度:", f"{apparent_temp} °C" if apparent_temp != "N/A" else "N/A")
    table.add_row("湿度:", f"{humidity}%" if humidity != "N/A" else "N/A")
    table.add_row("风速:", f"{wind_speed} km/h" if wind_speed != "N/A" else "N/A")
    table.add_row("天气状况:", weather_desc)
    
    # 创建面板
    title = Text(f"🌤️ [{current_time}] {city} 天气更新", style="bold yellow")
    panel = Panel(
        table,
        title=title,
        border_style="bright_blue",
        padding=(1, 2)
    )
    
    console.print()
    console.print(panel)
    console.print()


def log_weather_data(data: Dict, city: str) -> None:
    """
    将天气数据记录到日志文件
    
    参数:
        data: 天气数据字典
        city: 城市名称
    """
    if not data:
        return
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    weather_code = data.get("weather_code", -1)
    weather_desc = get_weather_description(weather_code).split()[0]  # 移除 emoji
    
    log_entry = (
        f"[{current_time}] 城市: {city} | "
        f"温度: {data.get('temperature', 'N/A')}°C | "
        f"体感: {data.get('apparent_temperature', 'N/A')}°C | "
        f"湿度: {data.get('humidity', 'N/A')}% | "
        f"风速: {data.get('wind_speed', 'N/A')}km/h | "
        f"天气: {weather_desc}"
    )
    
    logging.info(log_entry)


def fetch_and_display_weather(city: str, coordinates: tuple) -> None:
    """
    获取并显示天气信息（定时任务调用）
    
    参数:
        city: 城市名称
        coordinates: (纬度, 经度) 元组
    """
    lat, lon = coordinates
    weather_data = get_current_weather(lat, lon)
    
    if weather_data:
        print_weather(weather_data, city)
        log_weather_data(weather_data, city)
    else:
        console.print(f"[yellow]警告：本次获取 '{city}' 天气数据失败，将在下次重试[/yellow]")
        logging.warning(f"获取 '{city}' 天气数据失败")


def parse_arguments() -> argparse.Namespace:
    """
    解析命令行参数
    
    返回:
        解析后的参数命名空间
    """
    parser = argparse.ArgumentParser(
        description="天气获取小程序 - 使用 Open-Meteo API 获取实时天气",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python weather_app.py                    # 默认获取北京天气，30分钟刷新
  python weather_app.py --city 上海        # 获取上海天气
  python weather_app.py --city 纽约 --interval 60  # 获取纽约天气，60分钟刷新
        """
    )
    
    parser.add_argument(
        "--city",
        type=str,
        default="北京",
        help="指定城市名称，支持中文（默认：北京）"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="指定刷新间隔分钟数（默认：30）"
    )
    
    return parser.parse_args()


def main() -> None:
    """
    主函数：程序入口
    解析参数、获取坐标、设置定时任务、进入主循环
    """
    # 设置日志
    setup_logging()
    logging.info("天气应用启动")
    
    # 解析命令行参数
    args = parse_arguments()
    city = args.city
    interval = args.interval
    
    # 验证参数
    if interval < 1:
        console.print("[red]错误：间隔时间必须大于等于 1 分钟[/red]")
        sys.exit(1)
    
    console.print(f"[green]启动天气获取程序...[/green]")
    console.print(f"[blue]目标城市: {city}[/blue]")
    console.print(f"[blue]刷新间隔: {interval} 分钟[/blue]")
    console.print()
    
    # 获取城市坐标
    coordinates = get_coordinates(city)
    if not coordinates:
        console.print("[red]程序退出：无法获取城市坐标[/red]")
        sys.exit(1)
    
    # 立即获取一次天气
    fetch_and_display_weather(city, coordinates)
    
    # 设置定时任务
    schedule.every(interval).minutes.do(fetch_and_display_weather, city, coordinates)
    console.print(f"[green]已设置定时任务，每 {interval} 分钟自动刷新...[/green]")
    console.print("[dim]按 Ctrl+C 停止程序[/dim]")
    console.print()
    
    # 主循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]程序已停止[/yellow]")
        logging.info("天气应用停止")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]发生未预期的错误: {e}[/red]")
        logging.error(f"未预期的错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


"""
========================================
扩展建议（未来可添加的功能）
========================================

1. 邮件通知功能：
   - 使用 smtplib 库在特定天气条件（如温度超过阈值、下雨）时发送邮件
   - 需要配置 SMTP 服务器信息

2. 桌面通知功能：
   - Windows: 使用 win10toast 库
   - macOS: 使用 osascript 或 pync 库
   - Linux: 使用 notify2 库
   - 在天气异常或定时提醒时弹出桌面通知

3. GUI 界面：
   - 使用 tkinter 创建图形界面
   - 添加城市选择下拉框
   - 使用 matplotlib 绘制温度趋势图
   - 添加系统托盘图标

4. 历史数据保存：
   - 使用 sqlite3 将数据保存到本地数据库
   - 提供查询历史天气功能
   - 生成周报/月报统计

5. 多城市支持：
   - 同时监控多个城市天气
   - 配置文件保存关注城市列表

6. 语音播报：
   - 使用 pyttsx3 实现天气语音播报
   - 适合不方便看屏幕的场景

7. Web 服务：
   - 使用 Flask/FastAPI 提供 Web API
   - 前端使用 Vue/React 展示天气图表

8. Docker 部署：
   - 创建 Dockerfile 便于部署
   - 使用 docker-compose 管理配置
"""
