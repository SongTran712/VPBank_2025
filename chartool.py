import os
import json
import boto3
from upload import *
import io
def generate_quickchart_configs(chart_list):
    chart_output = {}
    color_palette = [
        "rgb(54, 162, 235)",
        "rgb(255, 99, 132)",
        "rgb(255, 206, 86)",
        "rgb(75, 192, 192)",
        "rgb(153, 102, 255)",
        "rgb(201, 203, 207)"
    ]

    for chart_name, chart in chart_list.items():
        chart_type = chart["chart_type"]
        quarters = chart["quarters"]
        metrics = chart["labels"]
        data = chart["data"]

        line_datasets = []
        bar_datasets = []

        for i, metric in enumerate(metrics):
            values = data.get(metric, [])
            color = color_palette[i % len(color_palette)]

            # Heuristic: values under 1000 treated as line data (likely ratio/percentage)
            is_line = all(abs(v) < 1000 for v in values if isinstance(v, (int, float)))

            dataset = {
                "label": metric,
                "data": values,
                "backgroundColor": color,
                "borderColor": color,
                "borderWidth": 2
            }

            if is_line:
                dataset["type"] = "line"
                dataset["fill"] = False
                dataset["yAxisID"] = "y2" if chart_type == "mix" else "y"
                line_datasets.append(dataset)
            else:
                dataset["type"] = "bar"
                dataset["yAxisID"] = "y1" if chart_type == "mix" else "y"
                bar_datasets.append(dataset)

        # Order: line first, then bar
        datasets = line_datasets + bar_datasets

        config = {
            "type": "bar" if chart_type in ["bar", "stacked", "mix"] else "line",
            "data": {
                "labels": quarters,
                "datasets": datasets
            },
            "options": {
                "responsive": True,
                "title": {
                    "display": True,
                    "text": chart_name.replace("_", " ").title(),
                    "fontSize": 18
                },
                "legend": {
                    "display": True,
                    "position": "top"
                },
                "tooltips": {
                    "mode": "index",
                    "intersect": True
                },
                "scales": {
                    "xAxes": [{"stacked": chart_type == "stacked"}],
                    "yAxes": []
                }
            }
        }

        # Y-axes configuration
        if chart_type == "mix":
            config["options"]["scales"]["yAxes"] = [
                {
                    "id": "y1",
                    "position": "left",
                    "stacked": True,
                    "ticks": {"beginAtZero": False}
                },
                {
                    "id": "y2",
                    "position": "right",
                    "gridLines": {"drawOnChartArea": False},
                    "ticks": {"beginAtZero": False}
                }
            ]
        else:
            config["options"]["scales"]["yAxes"] = [
                {
                    "id": "y",
                    "position": "left",
                    "stacked": chart_type == "stacked",
                    "ticks": {"beginAtZero": False}
                }
            ]

        chart_output[chart_name] = config

    return chart_output


chart_json = {
    'asset_vs_profitability': {
        'quarters': [],
        'labels': ['tong_tai_san', 'loi_nhuan_sau_thue', 'ROA'],
        'chart_type': 'mix',  # Total Assets, Net Profit, Return on Assets
        'data': {}
    },
    'equity_vs_return': {
        'quarters': [],
        'labels': ['von_chu_so_huu', 'loi_nhuan_sau_thue', 'ROE'],
        'chart_type': 'mix',  # Equity, Net Profit, Return on Equity
        'data': {}
    },
    'revenue_vs_efficiency': {
        'quarters': [],
        'labels': ['tong_doanh_thu', 'loi_nhuan_sau_thue', 'ROS'],
        'chart_type': 'mix',  # Revenue, Net Profit, Return on Sales
        'data': {}
    },
    'gross_margin_vs_profits': {
        'quarters': [],
        'labels': ['GrossProfitMargin', 'loi_nhuan_sau_thue', 'loi_nhuan_gop'],
        'chart_type': 'mix',  # Gross Margin and profits
        'data': {}
    },
    'assets_liabilities_structure': {
        'quarters': [],
        'labels': ['tong_tai_san', 'tong_no', 'DebtRatio'],
        'chart_type': 'stacked',  # Assets, Debt, Debt Ratio
        'data': {}
    },
    'profit_breakdown': {
        'quarters': [],
        'labels': ['loi_nhuan_sau_thue', 'loi_nhuan_truoc_thue', 'loi_nhuan_gop'],
        'chart_type': 'bar',  # Net, Pre-tax, Gross profits
        'data': {}
    },
    'capital_structure': {
        'quarters': [],
        'labels': ['von_chu_so_huu', 'tong_no', 'tong_tai_san'],
        'chart_type': 'stacked',  # Equity, Liabilities, Assets
        'data': {}
    },
    'efficiency_and_liquidity': {
        'quarters': [],
        'labels': ['AssetTurnoverRatio', 'ROA', 'CurrentRatio'],
        'chart_type': 'line',  # Operational ratios
        'data': {}
    }
}
def transform(datas):
    merged = {
        "data": {
            "stat": {},
            "cal": {}
        }
    }
    with open('./charts.json') as f:
        chart_list=json.load(f)
    # Financial metric calculator
    def compute_cal(data):
        return {
            "Bien_loi_nhuan": round(data["loi_nhuan_sau_thue"] / data["tong_doanh_thu"] * 100, 2),
            "ROE": round(data["loi_nhuan_sau_thue"] / data["von_chu_so_huu"] * 100, 2),
            "AssetTurnoverRatio": round(data["tong_doanh_thu"] / data["tong_tai_san"], 4),
            "EquityRatio": round(data["von_chu_so_huu"] / data["tong_tai_san"] * 100, 2),
            "DebtRatio": round(data["tong_no"] / data["tong_tai_san"] * 100, 2),
            "CurrentRatio": round(data["tong_tai_san_luu_dong_ngan_han"] / data["no_ngan_han"], 2),
            "GrossProfitMargin": round(data["loi_nhuan_gop"] / data["tong_doanh_thu"] * 100, 2),
            "ROA": round(data["loi_nhuan_sau_thue"] / data["tong_tai_san"] * 100, 2),
            "ROCE": round(data["loi_nhuan_truoc_thue"] / (data["tong_tai_san"] - data["no_ngan_han"]) * 100, 2),
            'ROS': round(data['loi_nhuan_sau_thue']/(data['tong_doanh_thu'])*100)
        }

    for d in datas:
        quarter = d["quy"]
        stat = {k: v for k, v in d.items() if k != "quy"}
        cal = compute_cal(stat)

        # Save to merged dictionary
        merged["data"]["stat"][quarter] = stat
        merged["data"]["cal"][quarter] = cal

        # Fill each chart's data
        for chart in chart_list.values():
            chart["quarters"].append(quarter)
            for label in chart["labels"]:
                # Initialize list if not already
                if label not in chart["data"]:
                    chart["data"][label] = []
                # Get value from stat or cal
                value = stat.get(label) if label in stat else cal.get(label)
                chart["data"][label].append(value)
    return merged, chart_list
from quickchart import QuickChart
import os
from upload import *
from dotenv import load_dotenv
load_dotenv()
access = os.getenv('accesskey')
secret = os.getenv('serectkey')
def save_charts_with_quickchart(chart_configs, output_dir):
    """
    Given chart configs in QuickChart format, render and save them as PNG images.
    :param chart_configs: dict of {chart_name: quickchart_config}
    :param output_dir: folder to save PNG files
    """
    os.makedirs(output_dir, exist_ok=True)

    for name, config in chart_configs.items():
        qc = QuickChart()
        qc.width = 800
        qc.height = 500
        qc.device_pixel_ratio = 2.0
        qc.config = config

        # Save PNG file
        output_path = os.path.join(output_dir, f"{name}.png")
        try:
            # Get image bytes
            img_bytes = qc.get_bytes()
            img_buffer = io.BytesIO(img_bytes)
            img_buffer.seek(0)

            # filename = f"charts/{name}.png"
            upload_to_s3_safe(img_buffer,'vpbank-team91',output_path,access,secret,'ap-southeast-1')
        except Exception as e:
            print("ERROR: ",e)


import os
import base64
import os
import base64
import boto3
import json

import boto3
import json
import base64
# from pdf2image import convert_from_path
from PIL import Image
def get_chart_context(images):
    # Add instruction to describe each chart and return structured JSON
    images.append({
        "type": "text",
        "text": (
            "Hãy mô tả nội dung của từng ảnh một cách chi tiết dưới dạng JSON, "
            "với cấu trúc: { \"chart_name\": \"phân tích\" }. "
            "Sau đó, đưa ra một kết luận tổng thể dựa trên tất cả các ảnh dưới key `tong_quan`."
        )
    })

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0,
        "system": (
            "Bạn là một chuyên gia phân tích tài chính. Với mỗi biểu đồ tài chính "
            "được cung cấp (ảnh), hãy đánh giá tình hình tài chính của công ty và "
            "xuất kết quả phân tích theo dạng JSON. Mỗi ảnh có key tên biểu đồ. "
            "Thêm phần `tong_quan` cuối cùng để tổng kết toàn bộ ảnh."
        ),
        "messages": [
            {
                "role": "user",
                "content": images
            }
        ]
    }

    session = boto3.Session(
        aws_access_key_id="access",
        aws_secret_access_key="secret",
        region_name="us-west-2"
    )
    client = session.client("bedrock-runtime")

    response = client.invoke_model(
        modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
        contentType='application/json',
        accept='application/json',
        body=json.dumps(payload)
    )

    response_body = json.loads(response['body'].read())
    # print("\nClaude Response:\n")
    raw_text = response_body["content"][0]["text"]

    try:
        structured_output = json.loads(raw_text)
    except json.JSONDecodeError:
        print("⚠️ Output is not valid JSON. Raw output:")
        print(raw_text)
        return None

    return structured_output


def chart_tool(datas:list,ses:str):
    transformed,chart_list =transform(datas)

    upload_to_s3_safe(transformed,'vpbank-team91',f"{ses}_raw/{ses}_transformed.json",access,secret,'ap-southeast-1')

    upload_to_s3_safe(chart_list,'vpbank-team91',f"{ses}_raw/{ses}_chart_list.json",access,secret,'ap-southeast-1')
  
    chart_configs = generate_quickchart_configs(chart_list)

    save_charts_with_quickchart(chart_configs,output_dir=f"{ses}_charts")

    images = images_as_base64_blocks('vpbank-team91',f"{ses}_charts",access,secret,)

    if images:
        imagescontext = get_chart_context(images)
    else:
        print("error")


    upload_to_s3_safe(imagescontext,'vpbank-team91',f"{ses}_raw/imagescontext.json",access,secret,'ap-southeast-1')
    return imagescontext

if __name__=="__main__":
    data = {
    "quy": "Q1/2025",
    "tong_tai_san_cuoi_quy": 3242801930898, 
    "loi_nhuan_sau_thue": -116915411380,
    "loi_nhuan_gop": -61372849620,
    "von_chu_so_huu": 119953583407,
    "tong_doanh_thu": 74478217583,
    "tong_tai_san": 3242801930898,
    "tong_no": 3122848347491,
    "gia_von_hang_ban": 135851067203,
    "loi_nhuan_gop_ve_BH_va_CCDV": -61372849620,
    "loi_nhuan_tai_chinh": -53217597991,
    "loi_nhuan_truoc_thue": -116888181727,
    "tong_tai_san_luu_dong_ngan_han": 2285669507340,
    "no_ngan_han": 2524167001622
    }
    data2={
    "quy": "Q2/2024",
    "tong_tai_san_cuoi_quy": 3888127929013,
    "loi_nhuan_sau_thue": -39411140488,
    "loi_nhuan_gop": -14535635495,
    "von_chu_so_huu": 639804256084,
    "tong_doanh_thu": 25303024143,
    "tong_tai_san": 3888127929013,
    "tong_no": 3248323672929,
    "gia_von_hang_ban": 39838659638,
    "loi_nhuan_gop_ve_BH_va_CCDV": -14535635495,
    "loi_nhuan_tai_chinh": -21624894106,
    "loi_nhuan_truoc_thue": -39411140488,
    "tong_tai_san_luu_dong_ngan_han": 2645837926158,
    "no_ngan_han": 1794456519079
    }

    data3={
    "quy": "Q3/2024",
    "tong_tai_san_cuoi_quy": 3813551935399,
    "loi_nhuan_sau_thue": -52971181445,
    "loi_nhuan_gop": 2077811611,
    "von_chu_so_huu": 512359235517,
    "tong_doanh_thu": 25826311936,
    "tong_tai_san": 3813551935399,
    "tong_no": 3301192699882,
    "gia_von_hang_ban": 23748500325,
    "loi_nhuan_gop_ve_bh_va_ccdv": 2077811611,
    "loi_nhuan_tai_chinh": -51327780954,
    "loi_nhuan_truoc_thue": -52971181392,
    "tong_tai_san_luu_dong_ngan_han": 2607354571405,
    "no_ngan_han": 2453654772417
    }

    data4={
    "quy": "Q4/2024",
    "tong_tai_san_cuoi_quy": 3337972266791,
    "loi_nhuan_sau_thue": -214198247455,
    "loi_nhuan_gop": 123088516,
    "von_chu_so_huu": 298160982194,
    "tong_doanh_thu": 184348685030,
    "tong_tai_san": 3337972266791,
    "tong_no": 3039811284597,
    "gia_von_hang_ban": 184225596514,
    "loi_nhuan_gop_ve_BH_va_CCDV": 123088516,
    "loi_nhuan_tai_chinh": -52153621130,
    "loi_nhuan_truoc_thue": -214198247455,
    "tong_tai_san_luu_dong_ngan_han": 2357624604751,
    "no_ngan_han": 2441157168380
    }
    chart_tool([data,data2,data3,data4],'stkltd')
