"""本机 Dijkstra 精算任务的导出、导入与结果校验。"""
from __future__ import annotations

from io import BytesIO
import json
from typing import Any
import zipfile

import pandas as pd


def is_dijkstra_route(order: dict[str, Any]) -> bool:
    route = order.get("路线GeoJSON") or {}
    features = route.get("features") if isinstance(route, dict) else None
    if not features:
        return False
    return all(str(feature.get("properties", {}).get("route_mode", "")).startswith("Dijkstra") for feature in features)


def build_formal_job(order: dict[str, Any]) -> bytes:
    """生成供企业电脑本机求解器读取的任务压缩包，不包含任何地图密钥。"""
    order_id = str(order.get("订单编号", "未编号订单"))
    task_dir = rf"C:\Users\DELL\Downloads\{order_id}_Dijkstra任务"
    solver = r"D:\A-university\竞赛\第六届四川省物流设计大赛\___网址 - 副本\本机正式求解器\路网Dijkstra订单求解.py"
    road_gpkg = r"D:\A-university\竞赛\第六届四川省物流设计大赛\7.0-修复孤立客户拓扑节点.gpkg"
    command = f'python "{solver}" --orders "{task_dir}\\orders.xlsx" --road-gpkg "{road_gpkg}" --output "{task_dir}\\result"'
    powershell_script = f'''$ErrorActionPreference = "Stop"
$solver = "{solver}"
$orders = Join-Path $PSScriptRoot "orders.xlsx"
$roadGpkg = "{road_gpkg}"
$resultDir = Join-Path $PSScriptRoot "result"

Write-Host "正在计算订单 {order_id} 的 Dijkstra 路网最短路径……" -ForegroundColor Cyan
python $solver --orders $orders --road-gpkg $roadGpkg --output $resultDir
if ($LASTEXITCODE -ne 0) {{
    throw "求解失败，请保留本窗口中的红色错误信息。"
}}
Write-Host "求解完成。请回到企业工作台上传：" -ForegroundColor Green
Write-Host (Join-Path $resultDir "formal_result.json") -ForegroundColor Yellow
Read-Host "按回车键关闭窗口"
'''
    instructions = f'''银犁智慧配送｜订单 {order_id}｜Dijkstra 本机求解

一、准备
1. 请先把下载的“{order_id}_Dijkstra任务.zip”全部解压。
2. 默认解压目录必须是：
   {task_dir}
3. 确认该目录内存在 orders.xlsx。

二、直接复制到 PowerShell 运行
请完整复制下一行，不要添加反引号，不要分行：

{command}

三、更简单的一键运行
也可以右键本文件夹中的“一键求解.ps1”，选择“使用 PowerShell 运行”。
如果系统阻止脚本，请使用上面的单行命令。

四、求解结果
成功后结果保存在：
{task_dir}\result

需要上传到企业工作台的文件是：
{task_dir}\result\formal_result.json

distance_matrix.xlsx 用于查看配送中心与订单点之间的 Dijkstra 距离矩阵；
route_map.geojson 用于在 QGIS 等地图软件中核验道路路径。
'''
    columns = ["订单编号", "客户名称", "收货地址", "经度", "纬度", "品类", "配送重量_kg", "期望送达日期", "最早到达", "最晚到达", "服务时间_分钟"]
    row = {column: order.get(column, "") for column in columns}
    manifest = {
        "任务类型": "Dijkstra 路网最短路",
        "订单编号": order_id,
        "说明": "使用 7.0-修复孤立客户拓扑节点.gpkg；结果必须写为 formal_result.json。",
        "禁止事项": "不得使用坐标直线距离替代路网最短路径。",
    }
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        xlsx = BytesIO()
        pd.DataFrame([row]).to_excel(xlsx, index=False)
        archive.writestr("orders.xlsx", xlsx.getvalue())
        archive.writestr("job.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("运行说明.txt", instructions.encode("utf-8-sig"))
        archive.writestr("PowerShell直接复制命令.txt", (command + "\n").encode("utf-8-sig"))
        archive.writestr("一键求解.ps1", powershell_script.encode("utf-8-sig"))
    return output.getvalue()


def parse_formal_result(raw: bytes, filename: str) -> dict[str, Any]:
    """读取本机求解器 formal_result.json，拒绝演示直线结果。"""
    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            names = archive.namelist()
            name = next((item for item in names if item.endswith("formal_result.json")), None)
            if not name:
                raise ValueError("压缩包中缺少 formal_result.json。")
            payload = json.loads(archive.read(name).decode("utf-8"))
    else:
        payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("正式结果必须是 JSON 对象。")
    route = payload.get("路线GeoJSON")
    if not isinstance(route, dict) or not route.get("features"):
        raise ValueError("正式结果缺少路线GeoJSON。")
    candidate = {"路线GeoJSON": route}
    if not is_dijkstra_route(candidate):
        raise ValueError("路线不是 Dijkstra 路网结果，不能用于发车。")
    return payload
