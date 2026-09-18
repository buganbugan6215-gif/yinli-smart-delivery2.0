from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle

ROOT = Path(__file__).parent
OUT = ROOT / '网址制作说明_详细版.pdf'
pdfmetrics.registerFont(TTFont('NotoSC', r'C:\Windows\Fonts\NotoSansSC-VF.ttf'))
ss = getSampleStyleSheet()
ss.add(ParagraphStyle(name='titlecn', fontName='NotoSC', fontSize=25, leading=34, textColor=colors.HexColor('#143F36'), alignment=1, spaceAfter=16))
ss.add(ParagraphStyle(name='subcn', fontName='NotoSC', fontSize=12, leading=20, textColor=colors.HexColor('#60736B'), alignment=1))
ss.add(ParagraphStyle(name='h1cn', fontName='NotoSC', fontSize=18, leading=26, textColor=colors.HexColor('#143F36'), spaceBefore=8, spaceAfter=10))
ss.add(ParagraphStyle(name='h2cn', fontName='NotoSC', fontSize=13, leading=20, textColor=colors.HexColor('#C66335'), spaceBefore=8, spaceAfter=5))
ss.add(ParagraphStyle(name='bodycn', fontName='NotoSC', fontSize=9.5, leading=17, textColor=colors.HexColor('#253B35'), spaceAfter=6))
ss.add(ParagraphStyle(name='smallcn', fontName='NotoSC', fontSize=8, leading=13, textColor=colors.HexColor('#53675F')))
ss.add(ParagraphStyle(name='codecn', fontName='NotoSC', fontSize=8.5, leading=14, textColor=colors.HexColor('#EAF4EF'), backColor=colors.HexColor('#1B2925'), borderPadding=8))

def p(s, style='bodycn'): return Paragraph(s, ss[style])
def bullets(items): return [p('• ' + x) for x in items]
def make_table(rows, widths):
    t = Table([[p(str(x), 'smallcn') for x in row] for row in rows], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DDEBE4')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#C9D8D1')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    return t
def footer(c, d):
    c.saveState(); c.setStrokeColor(colors.HexColor('#D5E1DB')); c.line(18*mm,15*mm,192*mm,15*mm); c.setFont('NotoSC',7.5); c.setFillColor(colors.HexColor('#718079')); c.drawString(18*mm,9.5*mm,'银犁智慧配送平台 · 网站制作说明'); c.drawRightString(192*mm,9.5*mm,f'第 {d.page} 页'); c.restoreState()

s = [Spacer(1,35*mm),p('银犁智慧配送平台','titlecn'),p('网站是怎么做的｜技术、页面、数据与部署说明','subcn'),Spacer(1,12*mm),p('面向客户与企业的生鲜配送数字化平台','subcn'),Spacer(1,55*mm),p('版本：Streamlit 公网版<br/>公开地址：https://yinli-smart-delivery-ela2rjizikvorzecncckvb.streamlit.app/','smallcn'),PageBreak()]
s += [p('一、网站是什么','h1cn'),p('这是一个把客户下单、订单跟踪、配送方案生成、路线查看和企业运营放在同一个入口中的生鲜配送平台。客户填写配送需求后，可以查看订单状态；企业可以导入订单数据，查看车辆、路线、成本和服务表现。'),p('面向不同使用者的作用','h2cn')]
s += bullets(['客户：提交收货地址、品类、数量和时间要求，获得订单编号和配送进度。','调度人员：查看订单、车辆、路线顺序、到达时刻和异常情况。','企业管理者：查看里程、成本、准时情况、车辆效率和方案差异。','项目团队：把已有 Excel、JSON、地图和路线结果转成可访问的业务页面。'])
s += [p('界面采用暖白背景、深绿色主体和陶土橙强调色。首页先讲清楚平台能做什么，专业分析放在企业端，避免客户打开页面就面对复杂算法术语。'),p('二、页面结构','h1cn'),make_table([['页面','主要功能','主要使用者'],['首页 / 方案驾驶舱','平台介绍、服务入口、核心结果','客户、管理者'],['客户下单','填写地址、品类、数量和时间','客户'],['订单追踪','查询订单处理进度','客户'],['数据导入与方案生成','上传订单并形成配送方案','调度人员'],['配送网络地图','查看配送中心、客户和车辆线路','调度人员'],['车辆路径优化','按车辆看访问顺序、时刻和载重','调度人员'],['成本与绩效 / 方案对比','看成本、准时率和不同方案','管理者'],['企业工作台 / 电子签收','订单运营和签收处理','企业、配送人员']],[38*mm,86*mm,43*mm]),p('页面入口由首页卡片按钮进入；分支页面保留自定义返回首页按钮。Streamlit 默认导航被隐藏，使用网站自己的中文导航。')]
s += [p('三、技术架构','h1cn'),p('网站采用 Python 数据层、Streamlit 页面层、Plotly/Folium 可视化层以及 GitHub/Streamlit Cloud 部署。它不需要单独购买服务器，也不需要先学习 React 或 Vue。'),make_table([['层次','技术','作用'],['页面层','Streamlit / Python','按钮、表单、筛选、多页面逻辑'],['数据层','Pandas / JSON / CSV / GeoJSON','读取订单、路线、成本和地图数据'],['图表层','Plotly','成本、需求、准时率和装载率图表'],['地图层','Folium + streamlit-folium','中心、客户点和实际道路路线'],['状态层','Streamlit session state','保存当前会话中的订单状态'],['代码仓库','GitHub','保存代码、数据、图片和依赖'],['公网运行','Streamlit Community Cloud','把 app.py 运行成公开网址']],[28*mm, fifty:=47*mm,90*mm]),p('浏览器打开网址后，云端拉取 GitHub 的代码，启动 app.py，再从网站数据目录读取相对路径文件。')]
s += [p('四、文件夹和代码作用','h1cn'),make_table([['文件 / 文件夹','作用'],['app.py','首页：品牌介绍、入口卡片、指标摘要和导航。'],['pages/','多页面目录，每个 Python 文件对应一个板块。'],['功能组件_页面共用代码/','公共样式、数据读取、订单状态和方案逻辑。'],['网站数据_页面读取的指标/','网页运行时读取的紧凑 JSON、CSV 和 GeoJSON。'],['展示图片_地图和答辩图/','路线、地图和项目展示图片。'],['requirements.txt','云端安装的 Python 依赖清单。'],['.streamlit/config.toml','主题和 Streamlit 配置。'],['README.md','本地启动、数据刷新和部署说明。']],[68*mm,97*mm]),p('网页使用相对路径，例如“网站数据_页面读取的指标/summary.json”；不能写死 D:\\A-university... 这样的本机路径，否则换电脑和云端都无法读取。')]
s += [p('五、数据怎样进入网站','h1cn'),p('网站分为“已有结果展示”和“客户新订单”两条路径。已有结果用于企业分析，新订单用于客户下单和状态查看。'),p('已有结果展示','h2cn'),p('原始 Excel、JSON、GPKG 或路线图片先由数据整理脚本提取需要的字段，生成紧凑的 JSON、CSV 和 GeoJSON。页面通过 data_loader.py 统一读取，避免云端加载百兆级路网文件。'),make_table([['数据接口','网页用途'],['scenario_summary','客户数、车辆数、里程、成本、准时率和方案类型'],['routes','车辆、产品、访问顺序、里程、载重、时刻和成本'],['arrivals','需求、时间窗、到达时间、离开时间和准时状态'],['cost_breakdown','固定、运输、制冷、时间惩罚、货损和总成本'],['reuse_schedule','物理车辆、产品任务、发车和回场时间'],['sensitivity','载重、续航、能耗增幅和成本上界']],[45*mm,120*mm]),p('客户新订单','h2cn'),p('客户下单页把填写内容保存到当前会话，订单追踪页和企业工作台可以读取。当前是轻量演示流程；刷新或重启后临时订单可能清空，正式运营需要数据库或订单 API。')]
s += [p('六、客户怎么使用','h1cn'),make_table([['步骤','客户看到的内容','系统动作'],['1','首页了解平台能做什么','点击立即下单或查询订单'],['2','填写门店、地址、品类、数量和时间','校验必填项'],['3','提交配送需求','生成订单编号并保存状态'],['4','进入订单追踪','显示待确认、备货中、配送中、已送达'],['5','查看配送','进入地图或路线页看车辆和预计到达'],['6','完成签收','企业侧更新签收状态']],[15*mm,75*mm,75*mm]),p('客户侧使用“预计送达、配送进度、路线位置、订单状态”等语言；车辆利用率、时间窗约束、启发式算法等专业内容保留在企业端。')]
s += [p('七、企业怎么导入数据并获得方案','h1cn'),p('企业从数据导入与方案生成进入，上传订单文件后进行字段检查。完整规模方案以预先计算的结果为主，不在公网端直接运行耗时的 ALNS 或完整优化程序，保证页面能快速打开。'),p('建议字段','h2cn')]
s += bullets(['客户编号、客户名称、经度、纬度或地址。','配送品类，如鲜面条、姜蒜等。','需求量和单位。','最早 / 最晚送达时间。','服务时间、车辆容量或车型要求（如成果包已有）。'])
s += [p('生成方案包括车辆分配、客户访问顺序、预计到达和离开时间、本车里程、载重、装载率、分项成本和地图路线。页面上的车辆数量、速度、准时率等控件当前主要用于切换已有情景，不代表每次点击都会实时重新求解。')]
s += [p('八、地图和图表怎样做','h1cn'),p('Folium 地图展示配送中心、客户点和车辆线路。点击客户点可以查看需求、时间窗、实际到达、准时状态和所属车辆；每辆车可以单独开关。路线优先使用预生成的真实道路 GeoJSON，而不是用坐标画直线。Plotly 图表支持悬停原值、图例开关和缩放。数据缺失时显示“暂无可验证数据”，不自动补零。')]
s += [p('九、本地运行','h1cn'),p('在 Windows PowerShell 中执行：'),p('cd "D:\\A-university\\竞赛\\第六届四川省物流设计大赛\\___网址"<br/>streamlit run app.py','codecn'),p('然后访问 http://localhost:8501/。localhost 只对当前电脑有效，不能发给外部客户；对外分享应使用 Cloud 生成的 https 网址。网站目录也有启动网站.bat，可双击启动。')]
s += [p('十、公网部署','h1cn'),p('GitHub 保存代码，Streamlit Community Cloud 负责运行。部署时选择仓库、main 分支和根目录 app.py，Cloud 自动安装 requirements.txt。'),p('部署步骤','h2cn')]
s += bullets(['登录 Streamlit Community Cloud 并授权 GitHub。','选择仓库 buganbugan6215-gif/yinli-smart-delivery。','Branch 选择 main，Main file path 选择 app.py。','点击 Deploy，等待依赖安装和应用启动。','代码提交到 main 后，Cloud 会拉取新版本；依赖变化时点击 Reboot app。'])
s += [p('当前公开地址：<br/>https://yinli-smart-delivery-ela2rjizikvorzecncckvb.streamlit.app/','codecn'),p('免费服务可能在无人访问一段时间后休眠，别人第一次打开时可能等待几十秒唤醒。')]
s += [p('十一、部署中遇到的问题','h1cn'),make_table([['问题','原因','处理'],['localhost 发给别人打不开','localhost 指向对方电脑','使用 Cloud https 公网网址'],['上传后目录摊平','网页上传不一定保留文件夹','使用 API 脚本保留相对目录'],['依赖安装失败','旧 Streamlit 依赖旧 Pillow，云端 Python 3.14 无适配包','改用不锁死旧版本的依赖'],['PowerShell 请求中断','本机到 GitHub 偶发断开','加入 TLS 1.2 和自动重试'],['新文件读取 404','API 把新建文件当成旧文件','脚本区分创建和更新']],[39*mm,62*mm,64*mm]),p('云端部署不仅要检查本地能否运行，还要检查 Python 版本、二进制依赖和仓库路径。')]
s += [p('十二、正式企业化还需补充','h1cn')]
s += bullets(['数据库：保存客户、订单、车辆、路线、签收和异常记录。','账号权限：区分客户、调度员、司机和管理者。','地址服务：把地址转坐标并检查有效性。','实时位置：接入车辆定位或司机端上报。','在线求解服务：后台运行完整优化算法，网页提交任务并读取结果。','消息通知：通知备货、发车、到达和签收。','数据安全：正式使用前采用私有仓库、认证和脱敏。'])
s += [p('建议顺序：先稳定订单和企业工作台，再接数据库；随后接入地址 / 定位服务；最后把完整优化算法做成后台服务。'),p('十三、当前版本边界','h1cn')]
s += bullets(['公开版本读取 GitHub 中的代码和数据。','订单状态主要保存在当前网页会话，不等同于正式订单数据库。','方案情景切换不等同于公网实时运行完整优化算法。','缺少统一排放因子时不显示虚构碳排放。','公开仓库中的代码、图片和网站数据可能被访问，正式商业使用前应脱敏并改为私有仓库。'])
s += [Spacer(1,8),p('本说明对应当前网址目录中的文件组织和部署流程；更换数据、页面或云端服务后，应同步更新本文件。')]

SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=17*mm, bottomMargin=21*mm, title='银犁智慧配送平台网站制作说明').build(s, onFirstPage=footer, onLaterPages=footer)
print(OUT)
