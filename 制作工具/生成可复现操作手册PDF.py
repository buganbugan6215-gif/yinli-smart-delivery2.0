from __future__ import annotations

import html
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "pdf" / "银犁智慧配送_从零制作与完整复现手册.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

font = next((p for p in [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/msyh.ttf"), Path("C:/Windows/Fonts/simhei.ttf")] if p.exists()), None)
if not font:
    raise FileNotFoundError("未找到中文字体")
pdfmetrics.registerFont(TTFont("CN", str(font)))

NAVY, BLUE, ORANGE = colors.HexColor("#173A7A"), colors.HexColor("#3159D9"), colors.HexColor("#F47B32")
INK, MUTED, LIGHT, LINE = colors.HexColor("#202B3D"), colors.HexColor("#64748B"), colors.HexColor("#F3F6FC"), colors.HexColor("#D8E0EF")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="Cover", fontName="CN", fontSize=25, leading=34, textColor=INK, spaceAfter=14))
styles.add(ParagraphStyle(name="Kicker", fontName="CN", fontSize=11, leading=16, textColor=ORANGE, spaceAfter=10))
styles.add(ParagraphStyle(name="Sub", fontName="CN", fontSize=11, leading=18, textColor=MUTED, spaceAfter=7))
styles.add(ParagraphStyle(name="H1", fontName="CN", fontSize=18, leading=25, textColor=NAVY, spaceBefore=8, spaceAfter=9, keepWithNext=True))
styles.add(ParagraphStyle(name="H2", fontName="CN", fontSize=13, leading=19, textColor=INK, spaceBefore=7, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name="H3", fontName="CN", fontSize=10.5, leading=16, textColor=BLUE, spaceBefore=5, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name="Body", fontName="CN", fontSize=9.1, leading=15.2, textColor=INK, spaceAfter=5))
styles.add(ParagraphStyle(name="Small", fontName="CN", fontSize=7.7, leading=12, textColor=MUTED, spaceAfter=4))
styles.add(ParagraphStyle(name="Step", fontName="CN", fontSize=9.1, leading=15.2, textColor=INK, leftIndent=8, firstLineIndent=-8, spaceAfter=4))
styles.add(ParagraphStyle(name="Callout", fontName="CN", fontSize=8.8, leading=14.5, textColor=NAVY, backColor=colors.HexColor("#EAF0FF"), borderColor=LINE, borderWidth=.6, borderPadding=8, spaceBefore=5, spaceAfter=7))
styles.add(ParagraphStyle(name="Warn", fontName="CN", fontSize=8.8, leading=14.5, textColor=colors.HexColor("#8A3D12"), backColor=colors.HexColor("#FFF1E8"), borderColor=colors.HexColor("#F2C3A7"), borderWidth=.6, borderPadding=8, spaceBefore=5, spaceAfter=7))
styles.add(ParagraphStyle(name="TH", fontName="CN", fontSize=7.6, leading=11, textColor=colors.white))
styles.add(ParagraphStyle(name="TD", fontName="CN", fontSize=7.6, leading=11.3, textColor=INK))
styles.add(ParagraphStyle(name="CodeCN", fontName="CN", fontSize=5.7, leading=8.1, textColor=colors.HexColor("#28344C"), leftIndent=3, rightIndent=2, wordWrap="CJK"))
styles.add(ParagraphStyle(name="TOC1", fontName="CN", fontSize=10, leading=15, textColor=NAVY, spaceBefore=4))
styles.add(ParagraphStyle(name="TOC2", fontName="CN", fontSize=8.4, leading=13, textColor=INK, leftIndent=12))


def P(text, style="Body"):
    return Paragraph(text, styles[style])


def H(story, text, level=1):
    story.append(P(text, "H1" if level == 1 else "H2" if level == 2 else "H3"))


def steps(story, items):
    story.extend(P(f"{i}. {item}", "Step") for i, item in enumerate(items, 1))


def bullets(story, items):
    story.extend(P(f"• {item}") for item in items)


def table(rows, widths):
    wrapped = []
    for r, row in enumerate(rows):
        wrapped.append([P(html.escape(str(x)).replace("\n", "<br/>"), "TH" if r == 0 else "TD") for x in row])
    out = Table(wrapped, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), .35, LINE), ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    for r in range(2, len(rows), 2):
        commands.append(("BACKGROUND", (0, r), (-1, r), LIGHT))
    out.setStyle(TableStyle(commands))
    return out


class Doc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(path, pagesize=A4, leftMargin=17*mm, rightMargin=17*mm, topMargin=17*mm, bottomMargin=18*mm, title="银犁智慧配送从零制作与完整复现手册", author="银犁智慧配送项目")
        self.addPageTemplates(PageTemplate(id="main", frames=Frame(self.leftMargin, self.bottomMargin, self.width, self.height), onPage=self.decorate))

    def decorate(self, canvas, doc):
        canvas.saveState(); canvas.setStrokeColor(LINE); canvas.line(17*mm, 13.5*mm, A4[0]-17*mm, 13.5*mm)
        canvas.setFont("CN", 7.2); canvas.setFillColor(MUTED)
        canvas.drawString(17*mm, 8.5*mm, "银犁智慧配送 - 从零制作与完整复现手册")
        canvas.drawRightString(A4[0]-17*mm, 8.5*mm, f"第 {doc.page} 页"); canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in {"H1", "H2"}:
            level = 0 if flowable.style.name == "H1" else 1
            text = flowable.getPlainText(); key = f"k{self.page}_{abs(hash(text))}"
            self.canv.bookmarkPage(key); self.canv.addOutlineEntry(text, key, level=level, closed=False)
            self.notify("TOCEntry", (level, text, self.page, key))


story = [Spacer(1, 24*mm), P("PYTHON · STREAMLIT · 本地路网 · 订单闭环", "Kicker"), P("银犁智慧配送<br/>从零制作与完整复现手册", "Cover"), P("从一个空文件夹开始，完整搭建当前网站。不是客户下单操作说明，而是开发、数据、测试和部署教程。", "Sub"), Spacer(1, 8*mm)]
story.append(table([["目标", "只凭本 PDF 与规定的原始数据，重新创建目录、安装依赖、编写全部模块和页面、生成数据、启动并验收网站。"], ["对应版本", "银犁智慧配送当前 Streamlit 本地版本，2026-09-17。"], ["关键边界", "客户地图蓝线是订单演示调度线；正式路网最短路径和优化结果来自竞赛成果数据，二者不得混称。"]], [32*mm, 138*mm]))
story += [Spacer(1, 8*mm), P("正文按实际制作顺序编排；遇到“创建某文件”时，从文末代码附录复制该文件。数据文件体积较大，不在 PDF 中逐字展开，而由脚本生成。", "Callout"), PageBreak()]
H(story, "内容导航")
toc = TableOfContents(); toc.levelStyles = [styles["TOC1"], styles["TOC2"]]
story += [toc, PageBreak()]

H(story, "第一章：明确要复现的网站架构")
story.append(P("该项目是 Streamlit 多页面 Python 应用，不是静态 HTML。浏览器负责展示，Python 负责表单、订单状态、报价、地图、文件读取和规划逻辑。"))
H(story, "1.1 六层结构", 2)
story.append(table([["层", "文件或目录", "职责"], ["入口", "app.py、启动网站.bat、打开本地网站.url", "启动与首页"], ["客户业务", "客户下单、订单追踪、配送网络地图、电子签收", "客户订单闭环"], ["工作人员", "企业工作台、运营配送地图", "全量订单与状态推进"], ["决策展示", "驾驶舱、订单与需求、路径、成本、对比", "竞赛结果展示"], ["公共能力", "ui、order_state、maps、data_loader、planner、matlab_bridge", "复用逻辑"], ["数据与测试", "网站数据、整理脚本、契约测试", "派生与验证"]], [27*mm, 68*mm, 75*mm]))
H(story, "1.2 数据流与业务流", 2)
steps(story, ["客户提交表单。", "order_state.py 生成订单号、费用、状态与演示调度线。", "客户追踪、地图和签收只读取当前会话订单。", "工作人员验证环境变量密码后读取本机 Excel 订单。", "工作人员按状态机逐级推进。", "配送途中后客户才能签收。", "模型展示页面独立读取网站数据目录。"])
story.append(P("客户临时订单与竞赛模型成果是两个数据域。前者支撑现场交互，后者支撑正式模型展示；复现时不要互相替代。", "Warn"))
H(story, "1.3 技术栈", 2)
story.append(table([["技术", "用途", "选择原因"], ["Python 3.11-3.13", "服务端逻辑", "Windows 和 Streamlit 兼容稳定"], ["Streamlit", "页面、表单、状态", "快速构建多页面演示系统"], ["Pandas/OpenPyXL", "CSV、Excel、订单", "适配竞赛成果格式"], ["Plotly", "交互图表", "嵌入方便"], ["Folium/streamlit-folium", "地图", "支持本地 GeoJSON"], ["GeoPandas/NetworkX", "预处理 GPKG 与最短路", "仅数据生成阶段需要"]], [37*mm, 55*mm, 78*mm]))
story.append(PageBreak())

H(story, "第二章：从空目录建立环境")
H(story, "2.1 安装 Python 与验证", 2)
steps(story, ["安装 64 位 Python 3.11、3.12 或 3.13，并勾选 Add Python to PATH。", "打开 PowerShell，执行 python --version。", "执行 python -m pip --version。", "若电脑有多个 Python，后续始终使用同一个 python 命令。"])
H(story, "2.2 建立项目目录和虚拟环境", 2)
steps(story, ["创建网站根目录。", "在根目录打开 PowerShell。", "执行 python -m venv .venv。", "执行 .\\.venv\\Scripts\\Activate.ps1。", "若执行策略阻止激活，先执行 Set-ExecutionPolicy -Scope Process Bypass。"])
H(story, "2.3 创建目录树", 2)
story.append(table([["目录", "内容", "是否自动产生"], ["pages", "全部子页面", "否"], ["功能组件_页面共用代码", "公共模块", "否"], ["网站数据_页面读取的指标", "轻量 JSON/CSV/GeoJSON", "脚本写入"], ["数据整理脚本_生成网站数据", "数据派生脚本", "否"], ["数据核验测试_检查结果", "数据契约测试", "否"], ["展示图片_地图和答辩图", "成果图片", "否"], ["客户订单数据", "本地订单 Excel", "首次下单自动创建"], [".streamlit", "主题与服务器配置", "否"]], [69*mm, 71*mm, 30*mm]))
H(story, "2.4 依赖安装", 2)
steps(story, ["创建 requirements.txt，内容见附录。", "执行 python -m pip install --upgrade pip。", "执行 python -m pip install -r requirements.txt。", "如需从 GPKG 重建路网，再安装 geopandas networkx pyogrio。", "执行 python -c \"import streamlit,pandas,plotly,folium,openpyxl; print('OK')\"。"])
H(story, "2.5 Streamlit 配置", 2)
story.append(P("创建 .streamlit/config.toml，配置浅色主题、橙色主按钮、200 MB 上传、XSRF 防护和关闭使用统计。工作人员密码不得写入 Python 或 TOML，应通过 YL_STAFF_PASSWORD 或 Streamlit secrets 提供。", "Warn"))
story.append(PageBreak())

H(story, "第三章：准备网站数据")
H(story, "3.1 三类数据", 2)
story.append(table([["类型", "来源", "用途"], ["原始成果", "完整模型 JSON/CSV/XLSX/GPKG", "生成轻量数据"], ["网站展示数据", "prepare_data.py 派生", "驾驶舱、图表、地图"], ["客户演示订单", "网页表单", "追踪、签收、工作台"]], [38*mm, 70*mm, 62*mm]))
H(story, "3.2 原始成果目录约定", 2)
story.append(table([["变量", "默认目录或文件", "需要内容"], ["NOODLE_DIR", "../___AAAAA面条优化结果_完整模型版", "结果 JSON、路线/到达 CSV、客户表"], ["GINGER_DIR", "../___AAAAA3.2姜蒜专线优化结果_完整模型版", "结果 JSON、路线/到达 CSV、客户表"], ["REUSE_DIR", "../___AAAAA第二问优化结果_增加车辆复用版", "复用 JSON 与时刻表"], ["SENS_DIR", "../___载重对续航的影响（灵敏度分析）", "灵敏度 CSV"], ["GPKG", "../7.0-修复孤立客户拓扑节点.gpkg", "lines、客户点、配送中心图层"]], [30*mm, 72*mm, 68*mm]))
H(story, "3.3 生成步骤", 2)
steps(story, ["复制附录中的 prepare_data.py 和 export_road_network.py。", "按本机成果包位置修改脚本顶部路径常量。", "执行 python 数据整理脚本_生成网站数据\\prepare_data.py。", "需要重建主次道路时执行 export_road_network.py。", "检查网站数据目录是否出现 summaries、history、manifest、customers、routes、arrivals、reuse、sensitivity 和 GeoJSON。"])
H(story, "3.4 数据文件契约", 2)
story.append(table([["文件", "关键结构", "使用处"], ["summaries.json", "noodle/ginger/reuse 指标与成本", "驾驶舱、成本、对比"], ["algorithm_history.json", "搜索历史", "路径优化"], ["customers.csv", "编号、坐标、产品、需求、时间窗", "订单与需求、地图"], ["routes_*.csv", "车辆、访问序列、里程、载重", "路线页面"], ["arrivals_*.csv", "到达、服务、准时", "需求页面"], ["reuse_schedule.csv", "车辆、任务、起止时刻", "驾驶舱"], ["sensitivity.csv", "参数与成本", "成本页"], ["customer_points.geojson", "Point FeatureCollection", "地图"], ["route_features.geojson", "LineString FeatureCollection", "正式路线"], ["road_major/minor.geojson", "主次道路", "离线底图"]], [54*mm, 73*mm, 43*mm]))
story.append(P("完整 GPKG 不直接在网页运行时解析。数据准备阶段把它变成轻量 GeoJSON，避免网页启动慢、云端体积过大。", "Callout"))
story.append(PageBreak())

H(story, "第四章：先实现公共模块")
story.append(table([["模块", "职责", "关键约束"], ["ui.py", "CSS、组件、侧栏、权限", "导航文件名必须真实；图标风格统一"], ["data_loader.py", "集中读取与缓存", "缺文件记录 errors，不让全站崩溃"], ["maps.py", "本地路网和路线图层", "tiles=None，避免在线底图依赖"], ["order_state.py", "订单、报价、状态、存储", "客户会话隔离；编号防碰撞"], ["planner.py", "上传与快速初算", "不得冒充正式算法"], ["matlab_bridge.py", "调用已核验 MATLAB", "路径和超时必须明确"]], [36*mm, 61*mm, 73*mm]))
H(story, "4.1 UI 与导航", 2)
steps(story, ["定义蓝色品牌主色、橙色动作色、灰白背景、圆角、阴影、间距和字号。", "通过 inject_global_css 统一 Streamlit 控件。", "render_sidebar 始终展示客户入口。", "读取环境变量密码后才展示工作人员入口。", "工作人员地图指向运营配送地图，不指向客户单订单地图。", "用统一线性符号，避免混杂彩色 emoji。"])
H(story, "4.2 订单状态与隐私", 2)
steps(story, ["状态机固定为订单已提交、仓库备货中、等待装车、配送途中、配送完成。", "staff_password 先读环境变量，再安全读取 secrets；缺文件时返回 None。", "init_orders() 只返回 session_state 当前订单。", "工作人员页面显式调用 init_orders(include_saved=True)。", "create_order 使用完整时间戳加 UUID 短尾码。", "persist_order 更新同一订单，不重复追加。", "advance_order 一次只推进一级。"])
H(story, "4.3 报价", 2)
story.append(P("预估费用 = 起步价 + 重量×品类基础价 + 参考距离×里程价。默认起步价 12 元、里程价 0.8 元/公里、鲜面条 0.75 元/千克、姜蒜 0.41 元/千克。该报价只用于网页透明展示，不等同于正式模型总成本函数。", "Warn"))
H(story, "4.4 地址与地图", 2)
steps(story, ["地理编码只在用户点击按钮后调用。", "结果用 st.cache_data 缓存 24 小时。", "识别失败时允许手工经纬度。", "Folium 地图禁用在线瓦片并加载本地 road_major/minor。", "订单蓝线只连接配送中心和客户坐标，界面必须称为演示调度线。", "正式路线来自 route_features.geojson。"])
H(story, "4.5 快速初算与正式模型", 2)
story.append(table([["维度", "快速初算", "正式模型"], ["输入", "上传客户坐标和需求", "完整路网、车辆与约束"], ["距离", "坐标近似", "道路最短路"], ["算法", "快速启发式", "团队核验程序"], ["结论", "演示即时方案", "论文和答辩依据"], ["表述", "快速可行初算", "较优可行解，不声称全局最优"]], [35*mm, 66*mm, 69*mm]))
story.append(PageBreak())

H(story, "第五章：逐页构建网站")
page_guides = [
    ("5.1 app.py 首页", ["st.set_page_config 必须最先执行，侧栏默认 expanded。", "调用统一 CSS 与侧栏。", "只放品牌、价值、三步流程和入口。", "page_link 必须与真实文件名一致。", "首页不要加载大表格和地图。"]),
    ("5.2 客户下单", ["采集客户、联系人、电话和地址。", "地址识别放在按钮事件；保留手填坐标。", "品类、重量和时间窗必填。", "默认时间窗 08:00-18:00，并校验先后。", "提交前展示费用拆分。", "坐标齐全后调用 create_order。"]),
    ("5.3 订单追踪", ["只调用 init_orders()。", "无订单显示空状态。", "展示状态、时间窗、费用和配送安排。", "状态顺序来自 STATUS_FLOW。"]),
    ("5.4 客户配送地图", ["只读取当前会话订单。", "绘制配送中心、客户点、本地道路。", "叠加订单蓝色演示线。", "明确说明不等同正式最短路。"]),
    ("5.5 电子签收", ["状态必须严格等于配送途中才显示按钮。", "确认后持久化配送完成。", "异常反馈独立保存。", "完成后不重复确认。"]),
    ("5.6 企业工作台", ["开头 require_staff_access。", "读取 include_saved=True。", "显示订单指标。", "一次点击只推进一级。", "演示边界集中成一条提示。"]),
    ("5.7 运营配送地图", ["仅工作人员可见。", "显示正式路网与全部本机订单。", "用颜色区分正式路线和演示线。"]),
    ("5.8 模型成果页", ["驾驶舱展示关键指标与总览。", "订单与需求展示客户和到达。", "路径页展示车辆路线和搜索历史。", "成本页展示拆分与敏感性。", "对比页横向比较三类方案。", "数据导入页提供上传、校验、快速初算和下载。"]),
]
for title, items in page_guides:
    H(story, title, 2); steps(story, items)
story.append(PageBreak())

H(story, "第六章：把订单闭环接通")
H(story, "6.1 状态动作矩阵", 2)
story.append(table([["状态", "追踪", "地图", "工作人员", "签收"], ["订单已提交", "可见", "可能无路线", "推进", "禁止"], ["仓库备货中", "可见", "有演示线", "推进", "禁止"], ["等待装车", "可见", "保留", "推进", "禁止"], ["配送途中", "可见", "保留", "可推进", "允许"], ["配送完成", "完成", "历史展示", "停止", "不重复"]], [31*mm, 29*mm, 39*mm, 39*mm, 32*mm]))
H(story, "6.2 演示调度线", 2)
story.append(P("下单有经纬度时，create_order 同步写入 FeatureCollection/LineString，坐标顺序为配送中心到客户。该线解决“下单后地图永远无路线”的流程断点，但它只用于串联演示流程。正式 Dijkstra 路线继续使用竞赛成果数据。"))
H(story, "6.3 本地持久化", 2)
story.append(P("订单保存到 客户订单数据/日期/品类订单.xlsx。路线和报价字典写入前转成 JSON 字符串，读取时恢复。客户页面不扫描该目录；工作人员页面经授权后读取。"))
H(story, "6.4 地址识别的容错", 2)
steps(story, ["用户输入地址。", "点击识别按钮才发起 Nominatim 请求。", "成功后回填坐标。", "失败时显示提示但不丢失表单。", "手填坐标后仍可完成报价、下单、地图、追踪和签收。"])
story.append(PageBreak())

H(story, "第七章：启动入口")
H(story, "7.1 首次手工启动", 2)
steps(story, ["进入根目录并激活 .venv。", "执行 $env:YL_STAFF_PASSWORD='设置自己的演示密码'。", "执行 python -m streamlit run app.py --server.headless true --server.port 8501。", "访问 http://localhost:8501/。", "保持终端打开，Ctrl+C 停止。"])
H(story, "7.2 双击脚本与快捷方式", 2)
story.append(P("启动网站.bat 负责进入正确目录、配置本地环境、启动服务并等待端口；打开本地网站.url 只负责访问 http://localhost:8501/，不能代替启动服务。公开仓库不得包含真实密码。", "Warn"))
H(story, "7.3 首次打开检查", 2)
bullets(story, ["首页标题正确。", "侧栏默认展开。", "客户入口可点击。", "工作人员入口未验证前隐藏。", "页面无 Python 异常红框。", "控制台无 ModuleNotFoundError。"])
story.append(PageBreak())

H(story, "第八章：测试与验收")
H(story, "8.1 静态与数据测试", 2)
steps(story, ["对 app.py、pages 和公共模块执行 py_compile。", "搜索硬编码密码。", "搜索旧数字前缀与无效 page_link。", "运行 test_data_contract.py。", "缺文件先重新生成数据，缺字段再修正映射。"])
H(story, "8.2 完整业务回归", 2)
story.append(table([["编号", "动作", "通过条件"], ["C01", "打开首页", "HTTP 200，侧栏展开"], ["C02", "完整下单并填坐标", "生成唯一编号和报价"], ["C03", "追踪", "仓库备货中，已有配送安排"], ["C04", "客户地图", "出现中心、客户点、蓝线"], ["C05", "备货阶段打开签收", "无确认按钮"], ["C06", "工作人员逐级推进", "每次只前进一步"], ["C07", "配送途中签收", "完成并持久化"], ["C08", "新会话查看客户订单", "不显示他人历史订单"], ["C09", "断网手填坐标", "闭环仍能完成"]], [18*mm, 67*mm, 85*mm]))
H(story, "8.3 HTTP 路由", 2)
story.append(P("使用 Invoke-WebRequest 逐一请求首页、客户下单、订单追踪、配送网络地图、电子签收和运营配送地图，StatusCode 应为 200。HTTP 200 不能替代交互测试。"))
H(story, "8.4 视觉验收", 2)
bullets(story, ["1920×1080 无横向滚动。", "蓝橙品牌色、圆角和阴影一致。", "服务图标统一为成熟线性符号。", "表单标签与错误信息对齐。", "地图和图表不截断。", "主按钮与次按钮层级清楚。"])
story.append(PageBreak())

H(story, "第九章：迁移和公网部署")
H(story, "9.1 迁移到新电脑", 2)
steps(story, ["复制源码、轻量网站数据和必要图片，不复制 .venv。", "重新安装 Python、创建虚拟环境并安装依赖。", "设置密码环境变量。", "运行数据契约测试。", "启动并执行完整业务回归。", "如需 MATLAB，修改本机可执行文件与模型目录。"])
H(story, "9.2 Streamlit Community Cloud", 2)
steps(story, ["以网站目录为 GitHub 仓库根目录。", "提交源码、requirements、runtime、轻量数据和必要图片。", "排除订单、密码、个人信息、大型路网、旧备份和 .venv。", "在 Streamlit Cloud 选择 app.py。", "在 Secrets 配置 YL_STAFF_PASSWORD。", "部署后检查路径大小写、中文编码和地图体积。"])
story.append(P("云端本地磁盘会重置。当前 Excel 持久化适合本地竞赛演示，不是生产数据库。正式上线必须接入有权限控制的外部数据库或订单服务。", "Warn"))
story.append(PageBreak())

H(story, "第十章：故障排查与最终清单")
story.append(table([["现象", "原因", "检查", "修复"], ["无法打开", "服务未启动", "请求 localhost:8501", "先运行启动脚本"], ["8501 占用", "旧进程", "netstat -ano | findstr :8501", "确认 PID 后关闭"], ["导航报错", "文件名不一致", "核对 pages 与 ui.py", "统一路径"], ["客户见历史单", "错误读取 saved", "搜索 init_orders", "客户页不传 True"], ["地图无蓝线", "无坐标/路线", "查经纬度和路线GeoJSON", "提交前强制坐标"], ["提前签收", "状态条件太宽", "查电子签收判断", "只允许配送途中"], ["地址输入卡", "每次 rerun 请求", "查调用位置", "按钮触发并缓存"], ["离线地图空", "在线瓦片/缺文件", "断网检查数据", "tiles=None 加本地路网"], ["云端订单丢", "临时磁盘", "查重启日志", "接外部数据库"]], [34*mm, 39*mm, 49*mm, 48*mm]))
H(story, "10.1 最终复现验收清单", 2)
checks = ["虚拟环境和依赖可重建", "目录结构完整", "公共模块可导入", "数据契约测试通过", "全部页面 HTTP 200", "下单生成唯一编号与演示线", "客户会话隔离", "工作人员逐级推进", "配送途中前禁止签收", "断网地图可显示", "快速初算与正式模型边界清楚", "发布包不含密码和客户数据"]
story.append(table([["序号", "验收项", "完成"]] + [[i, x, "□"] for i, x in enumerate(checks, 1)], [16*mm, 130*mm, 24*mm]))
H(story, "10.2 最小交付包", 2)
bullets(story, ["app.py、pages、公共模块。", "requirements、runtime、Streamlit 配置。", "轻量网站数据与必要图片。", "数据整理脚本和契约测试。", "README、启动脚本、网址快捷方式。", "本 PDF。"])
story += [PageBreak(), P("完整源码附录", "Cover"), P("下面自动读取当前版本源文件。按标题路径保存，全部 Python 文件使用 UTF-8。大型数据不展开，按第三章生成。", "Callout"), PageBreak()]

files = [
    ("requirements.txt", "运行依赖"), ("runtime.txt", "云端 Python 版本"), (".streamlit/config.toml", "主题与服务器配置"), ("app.py", "首页"),
    ("功能组件_页面共用代码/__init__.py", "包标记"), ("功能组件_页面共用代码/data_loader.py", "数据加载"), ("功能组件_页面共用代码/order_state.py", "订单状态"), ("功能组件_页面共用代码/maps.py", "地图"), ("功能组件_页面共用代码/planner.py", "快速规划"), ("功能组件_页面共用代码/matlab_bridge.py", "MATLAB 桥"), ("功能组件_页面共用代码/ui.py", "统一 UI"),
    ("pages/客户下单.py", "客户下单"), ("pages/订单追踪.py", "订单追踪"), ("pages/配送网络地图.py", "客户地图"), ("pages/电子签收.py", "电子签收"), ("pages/企业工作台.py", "企业工作台"), ("pages/运营配送地图.py", "运营地图"), ("pages/方案驾驶舱.py", "方案驾驶舱"), ("pages/订单与需求.py", "订单与需求"), ("pages/车辆路径优化.py", "路径优化"), ("pages/成本与绩效.py", "成本绩效"), ("pages/方案对比.py", "方案对比"), ("pages/数据导入与方案生成.py", "上传与生成"),
    ("数据整理脚本_生成网站数据/prepare_data.py", "数据生成"), ("数据整理脚本_生成网站数据/export_road_network.py", "路网导出"), ("数据核验测试_检查结果/test_data_contract.py", "契约测试"), ("README.md", "项目说明"), ("启动网站.bat", "双击启动"), ("打开本地网站.url", "网址快捷方式")
]
for i, (relative, note) in enumerate(files):
    H(story, f"代码附录：{relative}")
    path = ROOT / relative
    if path.exists():
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if relative == "启动网站.bat":
            text = text.replace(
                'set "YL_STAFF_PASSWORD=123456"',
                'set /p "YL_STAFF_PASSWORD=请输入工作人员演示密码: "',
            )
        story.append(P(f"用途：{note}。当前版本共 {len(text.splitlines())} 行。", "Small"))
        for number, line in enumerate(text.splitlines(), 1):
            safe = html.escape(line.expandtabs(4)).replace(" ", "&#160;") or "&#160;"
            story.append(P(f'<font color="#8792A8">{number:04d}</font>&#160;&#160;{safe}', "CodeCN"))
    else:
        story.append(P("当前项目中未找到该文件。", "Warn"))
    if i != len(files)-1:
        story.append(PageBreak())

story += [PageBreak(), P("手册结束", "Cover"), P("完成正文步骤、代码复制、数据生成和验收清单后，即可从空目录复现当前银犁智慧配送网站。", "Sub")]
Doc(str(OUT)).multiBuild(story)
print(OUT)
